"""Celery tasks for asynchronous storyboard generation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


@celery_app.task(
    name="storyboard.generate",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def run_storyboard_task(self, storyboard_id: str) -> dict:
    """Execute the storyboard-generation pipeline for a given storyboard record."""
    logger.info(
        "Starting storyboard task id=%s (attempt=%d)",
        storyboard_id,
        self.request.retries + 1,
    )

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.repositories.storyboard_repository import StoryboardRepository  # noqa: PLC0415
        from app.services.storyboard_service import StoryboardService  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                repo = StoryboardRepository(session)
                service = StoryboardService(repo)
                result = await service.execute_storyboard(storyboard_id)
                if result is None:
                    return {"status": "not_found", "id": storyboard_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Storyboard task failed id=%s: %s", storyboard_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Storyboard %s exhausted retries — marking as failed", storyboard_id)
            _mark_failed(storyboard_id, str(exc))
            return {"status": "failed", "id": storyboard_id, "error": str(exc)}


def _mark_failed(storyboard_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.repositories.storyboard_repository import StoryboardRepository  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                repo = StoryboardRepository(session)
                await repo.update(
                    storyboard_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark storyboard %s as failed: %s", storyboard_id, e)


@celery_app.task(name="storyboard.cleanup_stale", bind=True)
def cleanup_stale_storyboards(self) -> dict:
    """Periodic task — mark stale pending/running storyboards as failed."""

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.repositories.storyboard_repository import StoryboardRepository  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                repo = StoryboardRepository(session)
                stale = await repo.get_by_status("pending") + await repo.get_by_status("running")
                now = datetime.now(timezone.utc)
                count = 0
                for sb in stale:
                    age = (now - sb.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    if age > _STALE_PENDING_MINUTES:
                        await repo.update(
                            sb.id,
                            status="failed",
                            error_message=f"Stale job timed out after {_STALE_PENDING_MINUTES} minutes",
                            updated_at=now,
                        )
                        count += 1
                logger.info("Cleaned up %d stale storyboard jobs", count)
                return {"cleaned": count}

    return asyncio.run(_run())
