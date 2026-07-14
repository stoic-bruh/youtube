"""Celery tasks for asynchronous thumbnail extraction/scoring."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="thumbnail.generate", bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def run_thumbnail_task(self, thumbnail_id: str, count: int = 3) -> dict:
    logger.info("Starting thumbnail task for id=%s (attempt=%d)", thumbnail_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.thumbnail_repository import ThumbnailRepository
        from app.services.thumbnail_service import ThumbnailService

        async with async_session_factory() as session:
            async with session.begin():
                repo = ThumbnailRepository(session)
                service = ThumbnailService(repo)
                result = await service.execute_thumbnail(thumbnail_id, count)
                if result is None:
                    return {"status": "not_found", "id": thumbnail_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Thumbnail task failed for id=%s: %s", thumbnail_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(thumbnail_id, str(exc))
            return {"status": "failed", "id": thumbnail_id, "error": str(exc)}


def _mark_failed(thumbnail_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.thumbnail_repository import ThumbnailRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = ThumbnailRepository(session)
                await repo.update(
                    thumbnail_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark thumbnail %s as failed: %s", thumbnail_id, e)
