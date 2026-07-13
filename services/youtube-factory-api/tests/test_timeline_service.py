"""Tests for the Media Timeline Engine (schemas + service build logic)."""
from __future__ import annotations

import uuid

import pytest

from app.schemas.timeline import (
    MarkerType,
    RenderFormat,
    TimelineClip,
    TimelineMarker,
    TimelineMetadata,
    TimelineRenderPlan,
    TimelineRequest,
    TimelineScene,
    TimelineStatus,
    TimelineTrack,
    TrackKind,
    TransitionType,
)
from app.services.timeline_service import TimelineService


# ── Schema tests (no DB required) ────────────────────────────────────────────────

class TestSchemas:
    def test_timeline_clip_defaults(self):
        clip = TimelineClip(
            clip_id="c1", track_id="t1", scene_id="s1",
            start_ms=0, end_ms=5000, duration_ms=5000,
        )
        assert clip.asset_kind == "image"
        assert clip.in_point_ms == 0
        assert clip.volume == 1.0
        assert clip.opacity == 1.0
        assert clip.effects == []

    def test_timeline_track_defaults(self):
        track = TimelineTrack(track_id="t1", kind=TrackKind.VIDEO, order=0, label="Video")
        assert track.clips == []
        assert track.is_muted is False
        assert track.is_locked is False

    def test_timeline_scene_defaults(self):
        scene = TimelineScene(
            scene_id="s1", scene_number=1, title="Scene 1",
            start_ms=0, end_ms=5000, duration_ms=5000,
        )
        assert scene.transition_in == TransitionType.CUT
        assert scene.has_video_asset is False
        assert scene.asset_ids == []

    def test_render_plan_defaults(self):
        plan = TimelineRenderPlan()
        assert plan.width == 1920
        assert plan.height == 1080
        assert plan.fps == 30
        assert plan.format == RenderFormat.MP4
        assert plan.codec == "h264"

    def test_metadata_defaults(self):
        meta = TimelineMetadata()
        assert meta.total_duration_ms == 0
        assert meta.has_gaps is False
        assert meta.asset_coverage_pct == 0.0

    def test_marker_default_type(self):
        marker = TimelineMarker(marker_id="m1", label="Intro", timestamp_ms=0)
        assert marker.marker_type == MarkerType.CHAPTER

    def test_request_fps_bounds(self):
        with pytest.raises(Exception):
            TimelineRequest(storyboard_id="sb1", fps=10)
        with pytest.raises(Exception):
            TimelineRequest(storyboard_id="sb1", fps=120)
        req = TimelineRequest(storyboard_id="sb1", fps=60)
        assert req.fps == 60

    def test_request_defaults(self):
        req = TimelineRequest(storyboard_id="sb1")
        assert req.render_format == RenderFormat.MP4
        assert req.width == 1920
        assert req.height == 1080

    def test_enum_values(self):
        assert TimelineStatus.PENDING.value == "pending"
        assert TrackKind.SUBTITLE.value == "subtitle"
        assert TransitionType.DISSOLVE.value == "dissolve"
        assert MarkerType.BEAT.value == "beat"
        assert RenderFormat.WEBM.value == "webm"


# ── Build engine tests (require a real DB session) ──────────────────────────────

def _make_scene(i: int, *, duration_ms: int = 5000, narration: str | None = "Some narration") -> dict:
    return {
        "scene_id": f"scene_{i:03d}",
        "scene_title": f"Scene {i}",
        "duration_ms": duration_ms,
        "narration": narration,
        "visual_description": "A description",
        "transition_type": "fade" if i == 1 else "cut",
    }


async def _create_storyboard(db_session, *, scenes: list[dict], topic: str = "test topic") -> str:
    from app.models.storyboard_result import StoryboardResult

    sb_id = str(uuid.uuid4())
    sb = StoryboardResult(
        id=sb_id,
        topic=topic,
        title=f"Video about {topic}",
        status="completed",
        scenes=scenes,
    )
    db_session.add(sb)
    await db_session.flush()
    return sb_id


async def _create_asset(db_session, *, storyboard_id: str, scene_id: str, status: str = "ready") -> str:
    from app.models.asset import AssetResult

    asset_id = str(uuid.uuid4())
    asset = AssetResult(
        id=asset_id,
        storyboard_id=storyboard_id,
        scene_id=scene_id,
        asset_kind="image",
        status=status,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset_id


class TestTimelineBuildEngine:
    @pytest.mark.asyncio
    async def test_build_full_coverage_no_gaps(self, db_session):
        scenes = [_make_scene(i) for i in range(1, 4)]
        sb_id = await _create_storyboard(db_session, scenes=scenes)
        for s in scenes:
            await _create_asset(db_session, storyboard_id=sb_id, scene_id=s["scene_id"])

        service = TimelineService(db_session)
        timeline = await service.build_timeline(TimelineRequest(storyboard_id=sb_id))

        assert timeline.status == TimelineStatus.COMPLETED.value
        assert timeline.total_scenes == 3
        assert timeline.total_duration_ms == 15000
        assert len(timeline.tracks) == 3  # video, audio, subtitle
        assert timeline.timeline_metadata["asset_coverage_pct"] == 100.0
        assert timeline.timeline_metadata["has_gaps"] is False
        assert timeline.validation_errors == []

        video_track = next(t for t in timeline.tracks if t["kind"] == "video")
        assert len(video_track["clips"]) == 3
        assert all(c["asset_id"] for c in video_track["clips"])

        audio_track = next(t for t in timeline.tracks if t["kind"] == "audio")
        assert audio_track["is_muted"] is True  # voice is still a placeholder

    @pytest.mark.asyncio
    async def test_build_low_coverage_produces_warning(self, db_session):
        scenes = [_make_scene(i) for i in range(1, 5)]
        sb_id = await _create_storyboard(db_session, scenes=scenes)
        # Only one of four scenes gets an asset — below the 50% coverage threshold.
        await _create_asset(db_session, storyboard_id=sb_id, scene_id=scenes[0]["scene_id"])

        service = TimelineService(db_session)
        timeline = await service.build_timeline(TimelineRequest(storyboard_id=sb_id))

        assert timeline.status == TimelineStatus.COMPLETED.value
        assert timeline.timeline_metadata["asset_coverage_pct"] == 25.0
        assert any("acquire assets" in e for e in timeline.validation_errors)

    @pytest.mark.asyncio
    async def test_build_missing_storyboard_fails(self, db_session):
        service = TimelineService(db_session)
        timeline = await service.build_timeline(
            TimelineRequest(storyboard_id="does-not-exist"),
        )
        assert timeline.status == TimelineStatus.FAILED.value
        assert "not found" in (timeline.error_message or "")

    @pytest.mark.asyncio
    async def test_build_generates_chapter_markers(self, db_session):
        scenes = [_make_scene(i) for i in range(1, 7)]
        sb_id = await _create_storyboard(db_session, scenes=scenes)
        timeline = await TimelineService(db_session).build_timeline(
            TimelineRequest(storyboard_id=sb_id),
        )
        # Markers land on scene 1 and every 3rd scene thereafter (1, 4).
        marker_scene_numbers = sorted(
            i + 1 for i, s in enumerate(scenes)
            if (i + 1) % 3 == 1 or i == 0
        )
        assert len(timeline.markers) == len(marker_scene_numbers)

    @pytest.mark.asyncio
    async def test_list_get_delete_round_trip(self, db_session):
        sb_id = await _create_storyboard(db_session, scenes=[_make_scene(1)])
        service = TimelineService(db_session)
        built = await service.build_timeline(TimelineRequest(storyboard_id=sb_id))

        fetched = await service.get_timeline(built.id)
        assert fetched is not None
        assert fetched.id == built.id

        rows, total = await service.list_timelines(storyboard_id=sb_id)
        assert total == 1
        assert rows[0].id == built.id

        deleted = await service.delete_timeline(built.id)
        assert deleted is True
        assert await service.get_timeline(built.id) is None
