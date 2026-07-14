"""ThumbnailService — Post-Processing thumbnail orchestration.

Architecture (mirrors Voice/Render/Subtitle):
  1. start_thumbnail(request) → validate the source render exists & is
                                 completed → create DB record → enqueue
                                 Celery task → return record
  2. execute_thumbnail(id)    → probe real duration → extract real candidate
                                 frames via FFmpeg → score each with real
                                 Pillow-based analysis → select the best →
                                 persist
  3. get / list / delete      → thin repo wrappers
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from app.models.thumbnail_result import ThumbnailResult
from app.repositories.render_repository import RenderRepository
from app.repositories.thumbnail_repository import ThumbnailRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.thumbnail import ThumbnailRequest, ThumbnailStatus
from app.services.postprocess.ffmpeg_utils import extract_frame, probe_duration_ms
from app.services.postprocess.scoring import (
    PlaceholderDetector,
    brightness,
    dominant_color,
    quality_score,
    safe_text_regions,
    sharpness_score,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.environ.get("POSTPROCESS_OUTPUT_DIR", "/tmp/postprocess_engine")
THUMBNAIL_DIR = os.path.join(OUTPUT_DIR, "thumbnails")

_TEMPLATES = [
    {"id": "bold-title-bottom", "label": "Bold Title (bottom band)", "textRegion": "lower-third"},
    {"id": "minimal-corner-badge", "label": "Minimal Corner Badge", "textRegion": "upper-third"},
    {"id": "high-contrast-split", "label": "High-Contrast Split", "textRegion": "lower-third"},
]

_CANDIDATE_MULTIPLIER = 2  # generate more candidates than we ultimately select


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


class ThumbnailService:
    def __init__(
        self,
        repo: ThumbnailRepository,
        render_repo: RenderRepository | None = None,
        timeline_repo: TimelineRepository | None = None,
    ) -> None:
        self._repo = repo
        self._render_repo = render_repo or RenderRepository(repo._db)
        self._timeline_repo = timeline_repo or TimelineRepository(repo._db)

    async def start_thumbnail(self, request: ThumbnailRequest) -> ThumbnailResult:
        render = await self._render_repo.get(request.render_id)
        if not render:
            raise ValueError(f"Render {request.render_id!r} not found")
        if render.status != "completed":
            raise ValueError(f"Render {request.render_id!r} is not completed (status={render.status!r})")
        if not (render.render_output or {}).get("local_path"):
            raise ValueError(f"Render {request.render_id!r} has no output file to extract frames from")

        job_id = str(uuid.uuid4())
        thumbnail = await self._repo.create(
            render_id=request.render_id,
            status=ThumbnailStatus.PENDING.value,
            logs=[f"{_ts()} INFO  Thumbnail job created. Job ID: {job_id}"],
        )
        thumbnail._requested_count = request.count  # type: ignore[attr-defined]

        try:
            from app.tasks.thumbnail_tasks import run_thumbnail_task
            run_thumbnail_task.delay(thumbnail.id, request.count)
        except Exception as exc:
            logger.warning("Celery not available — thumbnail will not auto-process: %s", exc)

        return thumbnail

    async def execute_thumbnail(self, thumbnail_id: str, count: int = 3) -> ThumbnailResult | None:
        thumbnail = await self._repo.get(thumbnail_id)
        if not thumbnail:
            logger.error("Thumbnail %s not found", thumbnail_id)
            return None

        logs: list[str] = list(thumbnail.logs or [])

        def log(level: str, msg: str) -> None:
            logs.append(f"{_ts()} {level.upper():<5} {msg}")
            logger.info(msg)

        try:
            await self._repo.update(thumbnail_id, status=ThumbnailStatus.RUNNING.value, logs=logs)
            log("INFO", f"Starting thumbnail extraction for render={thumbnail.render_id!r}")

            render = await self._render_repo.get(thumbnail.render_id)
            if not render:
                raise RuntimeError(f"Source render {thumbnail.render_id!r} no longer exists")
            video_path = (render.render_output or {}).get("local_path")
            if not video_path or not os.path.isfile(video_path):
                raise RuntimeError(f"Render output file not found: {video_path!r}")

            log("INFO", "Phase 1/3 — Probing real video duration")
            duration_ms = (render.render_output or {}).get("duration_seconds")
            duration_ms = int(duration_ms * 1000) if duration_ms else await probe_duration_ms(video_path)
            log("INFO", f"Duration: {duration_ms}ms")

            n_candidates = max(count * _CANDIDATE_MULTIPLIER, count)
            # Skip the first/last 5% (title cards / fade-outs tend to be there).
            lo, hi = int(duration_ms * 0.05), int(duration_ms * 0.95)
            span = max(hi - lo, 1)
            timestamps = [lo + int(span * (i + 1) / (n_candidates + 1)) for i in range(n_candidates)]

            os.makedirs(THUMBNAIL_DIR, exist_ok=True)
            log("INFO", f"Phase 2/3 — Extracting {len(timestamps)} real candidate frame(s) via FFmpeg")

            candidates = []
            for i, ts_ms in enumerate(timestamps):
                candidate_id = f"{thumbnail_id}-c{i}"
                jpg_path = os.path.join(THUMBNAIL_DIR, f"{candidate_id}.jpg")
                try:
                    await extract_frame(video_path, ts_ms, jpg_path)
                except Exception as exc:
                    log("WARN", f"Frame extraction failed at {ts_ms}ms: {exc}")
                    continue

                from PIL import Image
                with Image.open(jpg_path) as img:
                    width, height = img.size

                sharp = sharpness_score(jpg_path)
                bright = brightness(jpg_path)
                color = dominant_color(jpg_path)
                quality = quality_score(sharp, bright)

                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "timestamp_ms": ts_ms,
                        "path": jpg_path,
                        "width": width,
                        "height": height,
                        "sharpness_score": sharp,
                        "quality_score": quality,
                        "brightness": bright,
                        "dominant_color": color,
                        "face_detected": PlaceholderDetector.detect_faces(jpg_path),
                        "objects_detected": PlaceholderDetector.detect_objects(jpg_path),
                        "safe_text_regions": safe_text_regions(width, height),
                    }
                )

            if not candidates:
                raise RuntimeError("No thumbnail candidates could be extracted from the render output")

            log("INFO", "Phase 3/3 — Scoring and selecting best candidates")
            candidates.sort(key=lambda c: c["quality_score"], reverse=True)
            selected_ids = [c["candidate_id"] for c in candidates[:count]]

            brand_colors: list[str] = []
            for c in candidates[:count]:
                if c["dominant_color"] not in brand_colors:
                    brand_colors.append(c["dominant_color"])

            timeline = await self._timeline_repo.get(render.timeline_id) if render.timeline_id else None
            title_overlay = {
                "text": (getattr(timeline, "title", None) or getattr(timeline, "topic", None)) if timeline else None,
                "fontFamily": "Anton",
                "color": "#FFFFFF",
                "strokeColor": "#000000",
                "strokeWidth": 6,
            }

            log("INFO", f"Selected {len(selected_ids)} of {len(candidates)} candidate(s)")

            updated = await self._repo.update(
                thumbnail_id,
                status=ThumbnailStatus.COMPLETED.value,
                candidates=candidates,
                selected_candidate_ids=selected_ids,
                templates=_TEMPLATES,
                title_overlay=title_overlay,
                brand_colors=brand_colors,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Thumbnail %s completed successfully", thumbnail_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Thumbnail generation failed: {error_msg}")
            await self._repo.update(
                thumbnail_id,
                status=ThumbnailStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Thumbnail %s failed: %s", thumbnail_id, error_msg, exc_info=True)
            return None

    async def get_thumbnail(self, thumbnail_id: str) -> ThumbnailResult | None:
        return await self._repo.get(thumbnail_id)

    async def list_thumbnails(
        self, limit: int = 50, offset: int = 0, status: str | None = None, render_id: str | None = None,
    ) -> tuple[list[ThumbnailResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        if render_id:
            kwargs["render_id"] = render_id
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_thumbnail(self, thumbnail_id: str) -> bool:
        thumbnail = await self._repo.get(thumbnail_id)
        if thumbnail:
            for c in thumbnail.candidates or []:
                path = c.get("path")
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        return await self._repo.delete(thumbnail_id)
