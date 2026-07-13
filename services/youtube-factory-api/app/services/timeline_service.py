"""TimelineService — Media Timeline Engine.

Merges Storyboard + Assets + Voice (placeholder) into a production timeline.
Does NOT do MoviePy rendering — only timeline planning and data assembly.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timeline import TimelineResult
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.timeline import (
    MarkerType,
    RenderFormat,
    TimelineClip,
    TimelineMarker,
    TimelineMetadata,
    TimelineRenderPlan,
    TimelineRequest,
    TimelineResultSchema,
    TimelineScene,
    TimelineStatus,
    TimelineTrack,
    TrackKind,
    TransitionType,
)

logger = logging.getLogger(__name__)


def _ts() -> str:
    return f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]"


def _make_id() -> str:
    return str(uuid.uuid4())


class TimelineService:
    """
    Media Timeline Engine.

    Build flow:
      1. Load storyboard (scenes with timing data)
      2. Load acquired assets for each scene
      3. Build video track  — one clip per scene (asset or placeholder)
      4. Build audio track  — placeholder narration timings from storyboard
      5. Build subtitle track — placeholder from storyboard subtitle_timing
      6. Compute transitions between scenes
      7. Generate render plan
      8. Detect gaps and validate
      9. Persist and return
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = TimelineRepository(db)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def list_timelines(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        storyboard_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[TimelineResult], int]:
        filters: dict = {}
        if storyboard_id:
            filters["storyboard_id"] = storyboard_id
        if status:
            filters["status"] = status
        rows, total = await self._repo.list(limit=limit, offset=offset, **filters)
        return list(rows), total

    async def get_timeline(self, timeline_id: str) -> TimelineResult | None:
        return await self._repo.get(timeline_id)

    async def delete_timeline(self, timeline_id: str) -> bool:
        return await self._repo.delete(timeline_id)

    async def build_timeline(self, request: TimelineRequest) -> TimelineResult:
        """
        Create a pending timeline record and immediately build it inline.
        In production this would be dispatched to a Celery task.
        """
        timeline = await self._repo.create(
            id=_make_id(),
            storyboard_id=request.storyboard_id,
            script_id=request.script_id,
            topic="",  # filled during build
            status=TimelineStatus.PENDING.value,
            logs=[f"{_ts()} INFO  Timeline build started"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await self._run_build(timeline, request)
        return timeline

    async def execute_timeline(self, timeline_id: str) -> TimelineResult | None:
        """Called from Celery task to build a pending timeline."""
        timeline = await self._repo.get(timeline_id)
        if not timeline:
            logger.warning("Timeline %s not found", timeline_id)
            return None
        request = TimelineRequest(
            storyboard_id=timeline.storyboard_id,
            script_id=timeline.script_id,
        )
        await self._run_build(timeline, request)
        return timeline

    # ── Build Engine ───────────────────────────────────────────────────────────

    async def _run_build(self, timeline: TimelineResult, request: TimelineRequest) -> None:
        """Core build logic — loads storyboard+assets, assembles tracks."""
        try:
            await self._set_status(timeline, TimelineStatus.RUNNING)

            # ── Step 1: Load storyboard ───────────────────────────────────────
            storyboard = await self._load_storyboard(request.storyboard_id)
            if not storyboard:
                await self._fail(timeline, f"Storyboard {request.storyboard_id!r} not found")
                return

            timeline.topic = storyboard.get("topic", "")
            timeline.title = storyboard.get("title") or storyboard.get("topic", "")
            await self._log(timeline, f"{_ts()} INFO  Loaded storyboard: {timeline.title!r}")

            raw_scenes: list[dict] = storyboard.get("scenes", []) or []
            await self._log(timeline, f"{_ts()} INFO  Found {len(raw_scenes)} scene(s)")

            # ── Step 2: Load assets ───────────────────────────────────────────
            asset_map = await self._load_assets(request.storyboard_id)
            await self._log(timeline, f"{_ts()} INFO  Found {len(asset_map)} acquired asset(s)")

            # ── Step 3: Build scene list with timing ──────────────────────────
            tl_scenes, cursor_ms = [], 0
            for i, raw in enumerate(raw_scenes):
                scene_id = (
                    raw.get("scene_id")
                    or raw.get("id")
                    or f"scene_{i + 1:03d}"
                )
                duration_ms = int(
                    raw.get("duration_ms")
                    or (raw.get("estimated_video_length_seconds", 5) * 1000)
                    or 5000
                )
                scene = TimelineScene(
                    scene_id=scene_id,
                    scene_number=i + 1,
                    title=raw.get("scene_title") or raw.get("title") or f"Scene {i + 1}",
                    start_ms=cursor_ms,
                    end_ms=cursor_ms + duration_ms,
                    duration_ms=duration_ms,
                    has_video_asset=scene_id in asset_map,
                    has_audio_placeholder=bool(raw.get("narration")),
                    asset_ids=asset_map.get(scene_id, []),
                    transition_in=TransitionType(raw.get("transition_type", "cut"))
                    if raw.get("transition_type") in {t.value for t in TransitionType}
                    else TransitionType.CUT,
                    transition_out=TransitionType.CUT,
                    narration=raw.get("narration"),
                    visual_description=raw.get("visual_description"),
                )
                tl_scenes.append(scene)
                cursor_ms += duration_ms

            total_duration_ms = cursor_ms
            await self._log(timeline, f"{_ts()} INFO  Total duration: {total_duration_ms / 1000:.1f}s")

            # ── Step 4: Build video track ─────────────────────────────────────
            video_track_id = _make_id()
            video_clips: list[TimelineClip] = []
            for scene in tl_scenes:
                asset_ids = scene.asset_ids
                asset_id = asset_ids[0] if asset_ids else None
                clip = TimelineClip(
                    clip_id=_make_id(),
                    track_id=video_track_id,
                    scene_id=scene.scene_id,
                    asset_id=asset_id,
                    asset_kind="image",
                    start_ms=scene.start_ms,
                    end_ms=scene.end_ms,
                    duration_ms=scene.duration_ms,
                    out_point_ms=scene.duration_ms,
                )
                video_clips.append(clip)

            video_track = TimelineTrack(
                track_id=video_track_id,
                kind=TrackKind.VIDEO,
                order=0,
                label="Video",
                clips=video_clips,
            )

            # ── Step 5: Build audio track (placeholder) ───────────────────────
            audio_track_id = _make_id()
            audio_clips: list[TimelineClip] = []
            for scene in tl_scenes:
                if scene.has_audio_placeholder:
                    clip = TimelineClip(
                        clip_id=_make_id(),
                        track_id=audio_track_id,
                        scene_id=scene.scene_id,
                        asset_id=None,
                        asset_kind="audio",
                        start_ms=scene.start_ms,
                        end_ms=scene.end_ms,
                        duration_ms=scene.duration_ms,
                        volume=1.0,
                    )
                    audio_clips.append(clip)

            audio_track = TimelineTrack(
                track_id=audio_track_id,
                kind=TrackKind.AUDIO,
                order=1,
                label="Narration (placeholder)",
                clips=audio_clips,
                is_muted=True,  # placeholder — no real audio yet
            )

            # ── Step 6: Build subtitle track (placeholder) ────────────────────
            subtitle_track_id = _make_id()
            subtitle_clips: list[TimelineClip] = []
            for scene in tl_scenes:
                if scene.narration:
                    clip = TimelineClip(
                        clip_id=_make_id(),
                        track_id=subtitle_track_id,
                        scene_id=scene.scene_id,
                        asset_id=None,
                        asset_kind="subtitle",
                        start_ms=scene.start_ms,
                        end_ms=scene.end_ms,
                        duration_ms=scene.duration_ms,
                    )
                    subtitle_clips.append(clip)

            subtitle_track = TimelineTrack(
                track_id=subtitle_track_id,
                kind=TrackKind.SUBTITLE,
                order=2,
                label="Subtitles (placeholder)",
                clips=subtitle_clips,
            )

            tracks = [video_track, audio_track, subtitle_track]

            # ── Step 7: Build chapter markers ─────────────────────────────────
            markers: list[TimelineMarker] = []
            for scene in tl_scenes:
                if scene.scene_number % 3 == 1 or scene.scene_number == 1:
                    markers.append(TimelineMarker(
                        marker_id=_make_id(),
                        label=scene.title,
                        timestamp_ms=scene.start_ms,
                        marker_type=MarkerType.CHAPTER,
                    ))

            # ── Step 8: Render plan ───────────────────────────────────────────
            render_plan = TimelineRenderPlan(
                width=request.width,
                height=request.height,
                fps=request.fps,
                format=request.render_format,
                estimated_render_time_ms=total_duration_ms * 2,  # rough estimate
            )

            # ── Step 9: Metadata + validation ─────────────────────────────────
            has_gaps = False
            gap_count = 0
            prev_end = 0
            for clip in video_clips:
                if clip.start_ms > prev_end + 100:  # >100ms gap
                    has_gaps = True
                    gap_count += 1
                prev_end = clip.end_ms

            scenes_with_assets = sum(1 for s in tl_scenes if s.has_video_asset)
            coverage_pct = (scenes_with_assets / len(tl_scenes) * 100) if tl_scenes else 0.0

            metadata = TimelineMetadata(
                total_duration_ms=total_duration_ms,
                total_scenes=len(tl_scenes),
                video_clip_count=len(video_clips),
                audio_clip_count=len(audio_clips),
                has_gaps=has_gaps,
                gap_count=gap_count,
                transition_count=max(0, len(tl_scenes) - 1),
                estimated_file_size_bytes=int(total_duration_ms * render_plan.bitrate_kbps / 8),
                asset_coverage_pct=round(coverage_pct, 1),
            )

            validation_errors: list[str] = []
            if not tl_scenes:
                validation_errors.append("No scenes found in storyboard")
            if has_gaps:
                validation_errors.append(f"{gap_count} gap(s) detected in video track")
            if coverage_pct < 50:
                validation_errors.append(
                    f"Only {coverage_pct:.0f}% of scenes have assets — acquire assets first"
                )

            # ── Step 10: Persist ──────────────────────────────────────────────
            timeline.topic = storyboard.get("topic", "")
            timeline.title = storyboard.get("title") or storyboard.get("topic", "")
            timeline.total_duration_ms = total_duration_ms
            timeline.total_scenes = len(tl_scenes)
            timeline.tracks = [t.model_dump() for t in tracks]
            timeline.scenes = [s.model_dump() for s in tl_scenes]
            timeline.markers = [m.model_dump() for m in markers]
            timeline.render_plan = render_plan.model_dump()
            timeline.metadata = metadata.model_dump()
            timeline.validation_errors = validation_errors
            timeline.status = TimelineStatus.COMPLETED.value
            timeline.completed_at = datetime.now(timezone.utc)
            timeline.updated_at = datetime.now(timezone.utc)

            status_line = "✓ complete" if not validation_errors else f"⚠ {len(validation_errors)} warning(s)"
            await self._log(
                timeline,
                f"{_ts()} INFO  Timeline built — {len(tl_scenes)} scenes, "
                f"{total_duration_ms / 1000:.1f}s, {status_line}",
            )
            await self._db.flush()

        except Exception as exc:
            logger.error("Timeline build failed id=%s: %s", timeline.id, exc, exc_info=True)
            await self._fail(timeline, str(exc))

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _load_storyboard(self, storyboard_id: str) -> dict | None:
        from sqlalchemy import select
        from app.models.storyboard_result import StoryboardResult
        stmt = select(StoryboardResult).where(StoryboardResult.id == storyboard_id)
        result = await self._db.execute(stmt)
        sb = result.scalar_one_or_none()
        if not sb:
            return None
        return {
            "id": sb.id,
            "topic": sb.topic,
            "title": getattr(sb, "title", None),
            "scenes": sb.scenes if isinstance(sb.scenes, list) else [],
        }

    async def _load_assets(self, storyboard_id: str) -> dict[str, list[str]]:
        """Returns {scene_id: [asset_id, ...]} for all ready/cached assets."""
        from sqlalchemy import select
        from app.models.asset import AssetResult
        stmt = select(AssetResult).where(
            AssetResult.storyboard_id == storyboard_id,
            AssetResult.status.in_(["ready", "cached"]),
        )
        result = await self._db.execute(stmt)
        assets = result.scalars().all()
        mapping: dict[str, list[str]] = {}
        for asset in assets:
            mapping.setdefault(asset.scene_id, []).append(asset.id)
        return mapping

    async def _set_status(self, timeline: TimelineResult, status: TimelineStatus) -> None:
        timeline.status = status.value
        timeline.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _log(self, timeline: TimelineResult, message: str) -> None:
        logs = list(timeline.logs or [])
        logs.append(message)
        timeline.logs = logs
        timeline.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _fail(self, timeline: TimelineResult, reason: str) -> None:
        await self._log(timeline, f"{_ts()} ERROR {reason}")
        timeline.status = TimelineStatus.FAILED.value
        timeline.error_message = reason
        timeline.updated_at = datetime.now(timezone.utc)
        await self._db.flush()
