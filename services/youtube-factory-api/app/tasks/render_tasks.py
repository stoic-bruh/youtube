"""Celery tasks for asynchronous MoviePy/FFmpeg rendering."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 60  # renders take longer than most other stages


@celery_app.task(
    name="render.execute",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
    acks_late=True,
)
def run_render_task(self, render_id: str, request_json: dict) -> dict:
    """Execute the render pipeline for a given render record.

    Wraps the async RenderService.execute_render() using asyncio.run(),
    matching the pattern from voice_tasks.py/timeline_tasks.py. Retries are
    capped at 1 — a failed MoviePy render is expensive to retry blindly and
    the failure is almost always deterministic (bad plan/media), not
    transient like a network call.
    """
    logger.info("Starting render task for id=%s (attempt=%d)", render_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.render_repository import RenderRepository
        from app.schemas.render import RenderRequest
        from app.services.render_service import RenderService

        async with async_session_factory() as session:
            async with session.begin():
                repo = RenderRepository(session)
                service = RenderService(repo)
                request = RenderRequest.model_validate(request_json)
                result = await service.execute_render(render_id, request)
                if result is None:
                    return {"status": "not_found_or_failed", "id": render_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Render task failed for id=%s: %s", render_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Render %s exhausted retries — marking as failed", render_id)
            _mark_failed(render_id, str(exc))
            return {"status": "failed", "id": render_id, "error": str(exc)}


def _mark_failed(render_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.render_repository import RenderRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = RenderRepository(session)
                await repo.update(
                    render_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark render %s as failed: %s", render_id, e)


@celery_app.task(name="render.cleanup_stale", bind=True)
def cleanup_stale_renders(self) -> dict:
    """Periodic task — mark stale pending/running render jobs as failed."""

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.render_repository import RenderRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = RenderRepository(session)
                stale = await repo.get_by_status("pending") + await repo.get_by_status("running")

                now = datetime.now(timezone.utc)
                count = 0
                for render in stale:
                    age_minutes = (now - render.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    if age_minutes > _STALE_PENDING_MINUTES:
                        await repo.update(
                            render.id,
                            status="failed",
                            error_message=f"Stale job timed out after {_STALE_PENDING_MINUTES} minutes",
                            updated_at=now,
                        )
                        count += 1

                logger.info("Cleaned up %d stale render jobs", count)
                return {"cleaned": count}

    return asyncio.run(_run())
