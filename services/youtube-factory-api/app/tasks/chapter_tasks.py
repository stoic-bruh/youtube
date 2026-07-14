"""Celery tasks for asynchronous chapter derivation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="chapter.generate", bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def run_chapter_task(self, chapter_id: str) -> dict:
    logger.info("Starting chapter task for id=%s (attempt=%d)", chapter_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.chapter_repository import ChapterRepository
        from app.services.chapter_service import ChapterService

        async with async_session_factory() as session:
            async with session.begin():
                repo = ChapterRepository(session)
                service = ChapterService(repo)
                result = await service.execute_chapter(chapter_id)
                if result is None:
                    return {"status": "not_found", "id": chapter_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Chapter task failed for id=%s: %s", chapter_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(chapter_id, str(exc))
            return {"status": "failed", "id": chapter_id, "error": str(exc)}


def _mark_failed(chapter_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.chapter_repository import ChapterRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = ChapterRepository(session)
                await repo.update(
                    chapter_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark chapter %s as failed: %s", chapter_id, e)
