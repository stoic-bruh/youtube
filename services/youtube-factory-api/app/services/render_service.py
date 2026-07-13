"""RenderService — production-ready MoviePy/FFmpeg render orchestration.

Architecture (mirrors Voice/Timeline):
  1. start_render(request) → validate timeline (and voice, if given) exist and
                              are completed → create DB record → enqueue
                              Celery task → return record
  2. execute_render(id)    → build RenderPlan from Timeline+Voice+Assets →
                              run the RendererBackend (MoviePy) → persist
                              RenderOutput/RenderMetadata/RenderStats
  3. get / list / delete   → thin repo wrappers
  4. provider_stats        → aggregate render_results (single backend: MoviePy)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from app.models.render import RenderResult
from app.repositories.asset_repository import AssetRepository
from app.repositories.render_repository import RenderRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.voice_repository import VoiceRepository
from app.schemas.render import RenderProviderStats, RenderRequest, RenderStatus
from app.services.render.base import RenderProgress
from app.services.render.moviepy_backend import MoviePyRenderer
from app.services.render.plan_builder import build_render_plan

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.environ.get("RENDER_OUTPUT_DIR", "/tmp/render_engine/output")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


class RenderService:
    """Orchestrates the full Timeline+Voice+Assets -> MP4 render pipeline."""

    def __init__(
        self,
        repo: RenderRepository,
        timeline_repo: TimelineRepository | None = None,
        voice_repo: VoiceRepository | None = None,
        asset_repo: AssetRepository | None = None,
    ) -> None:
        self._repo = repo
        self._timeline_repo = timeline_repo or TimelineRepository(repo._db)
        self._voice_repo = voice_repo or VoiceRepository(repo._db)
        self._asset_repo = asset_repo or AssetRepository(repo._db)
        self._renderer = MoviePyRenderer()

    # ── Public API ────────────────────────────────────────────────────────

    async def start_render(self, request: RenderRequest) -> RenderResult:
        timeline = await self._timeline_repo.get(request.timeline_id)
        if not timeline:
            raise ValueError(f"Timeline {request.timeline_id!r} not found")
        if timeline.status not in ("completed",):
            raise ValueError(f"Timeline {request.timeline_id!r} is not ready to render (status={timeline.status!r})")

        voice = None
        if request.voice_id:
            voice = await self._voice_repo.get(request.voice_id)
            if not voice:
                raise ValueError(f"Voice {request.voice_id!r} not found")
        else:
            candidates = await self._voice_repo.get_by_script_id(timeline.script_id) if timeline.script_id else []
            completed = [v for v in candidates if v.status == "completed"]
            voice = completed[0] if completed else None

        import uuid
        job_id = str(uuid.uuid4())
        render = await self._repo.create(
            timeline_id=request.timeline_id,
            voice_id=voice.id if voice else None,
            status=RenderStatus.PENDING.value,
            resolution=request.resolution.value,
            width=0,
            height=0,
            fps=request.fps,
            aspect_ratio=request.aspect_ratio.value,
            crop_mode=request.crop_mode.value,
            hardware_acceleration=request.hardware_acceleration,
            render_plan={},
            render_output={},
            render_stats={},
            render_metadata={},
            preview_output={},
            logs=[f"{_ts()} INFO  Render job created. Job ID: {job_id}"],
        )
        logger.info("Render job created id=%s timeline_id=%s", render.id, request.timeline_id)

        try:
            from app.tasks.render_tasks import run_render_task
            run_render_task.delay(render.id, request.model_dump(mode="json"))
        except Exception as exc:
            logger.warning("Celery not available — render will not auto-process: %s", exc)

        return render

    async def execute_render(self, render_id: str, request: RenderRequest) -> RenderResult | None:
        """Main execution entry point called by the Celery worker."""
        render = await self._repo.get(render_id)
        if not render:
            logger.error("Render %s not found", render_id)
            return None

        logs: list[str] = list(render.logs or [])

        def log(level: str, msg: str) -> None:
            logs.append(f"{_ts()} {level.upper():<5} {msg}")
            logger.info(msg)

        try:
            await self._repo.update(render_id, status=RenderStatus.RUNNING.value, logs=logs, progress=5)
            log("INFO", f"Starting render for timeline={render.timeline_id!r} voice={render.voice_id!r}")

            timeline = await self._timeline_repo.get(render.timeline_id)
            if not timeline:
                raise RuntimeError(f"Source timeline {render.timeline_id!r} no longer exists")
            voice = await self._voice_repo.get(render.voice_id) if render.voice_id else None
            assets = await self._asset_repo.get_by_storyboard(timeline.storyboard_id) if timeline.storyboard_id else []

            log("INFO", "Phase 1/3 — Building RenderPlan from Timeline + Voice + Assets")
            plan = build_render_plan(request, timeline=timeline, voice=voice, assets=assets)
            log("INFO", f"RenderPlan assembled — {len(plan.scenes)} scene(s), {plan.width}x{plan.height}@{plan.fps}fps")
            await self._repo.update(render_id, render_plan=plan.model_dump(mode="json"), width=plan.width, height=plan.height, progress=15)

            log("INFO", "Phase 2/3 — Compositing with MoviePy/FFmpeg")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, f"{render_id}.mp4")
            preview_path = os.path.join(OUTPUT_DIR, f"{render_id}_preview.mp4") if request.generate_preview else None

            def on_progress(p: RenderProgress) -> None:
                logs.append(f"{_ts()} INFO  [{p.phase}] {p.percent}% {p.message}")

            output, stats = await self._renderer.render(plan, output_path, on_progress=on_progress)
            preview_output = None
            if preview_path:
                preview_output = await self._renderer.render_preview(plan, preview_path, on_progress=on_progress)

            log("INFO", f"Phase 3/3 — Render complete: {output.file_size_bytes} bytes, {output.duration_seconds}s")

            metadata = {
                "scene_count": len(plan.scenes),
                "clip_count": sum(len(s.clips) for s in plan.scenes),
                "placeholder_clip_count": sum(1 for s in plan.scenes for c in s.clips if c.kind == "placeholder"),
                "has_narration": bool(voice),
                "has_background_music": plan.add_background_music,
                "source_timeline_id": render.timeline_id,
                "source_voice_id": render.voice_id,
            }

            updated = await self._repo.update(
                render_id,
                status=RenderStatus.COMPLETED.value,
                progress=100,
                render_output=output.model_dump(mode="json"),
                render_stats=stats.model_dump(mode="json"),
                render_metadata=metadata,
                preview_output=preview_output.model_dump(mode="json") if preview_output else {},
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Render %s completed successfully", render_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Render failed: {error_msg}")
            await self._repo.update(
                render_id,
                status=RenderStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Render %s failed: %s", render_id, error_msg, exc_info=True)
            return None

    async def get_render(self, render_id: str) -> RenderResult | None:
        return await self._repo.get(render_id)

    async def list_renders(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        timeline_id: str | None = None,
    ) -> tuple[list[RenderResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        if timeline_id:
            kwargs["timeline_id"] = timeline_id
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_render(self, render_id: str) -> bool:
        render = await self._repo.get(render_id)
        if render:
            output = render.render_output or {}
            local_path = output.get("local_path")
            if local_path and os.path.isfile(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass
        return await self._repo.delete(render_id)

    async def provider_stats(self) -> RenderProviderStats:
        renders, total = await self._repo.list(limit=10_000, offset=0)
        completed = [r for r in renders if r.status == "completed"]
        failed = [r for r in renders if r.status == "failed"]
        render_times = [r.render_stats.get("render_time_seconds", 0.0) for r in completed if r.render_stats]
        realtime_factors = [r.render_stats.get("realtime_factor", 0.0) for r in completed if r.render_stats]
        output_seconds = [r.render_output.get("duration_seconds", 0.0) for r in completed if r.render_output]
        return RenderProviderStats(
            backend="moviepy",
            total_renders=total,
            completed=len(completed),
            failed=len(failed),
            avg_render_time_seconds=round(sum(render_times) / len(render_times), 2) if render_times else 0.0,
            avg_realtime_factor=round(sum(realtime_factors) / len(realtime_factors), 3) if realtime_factors else 0.0,
            total_output_seconds=round(sum(output_seconds), 2),
        )
