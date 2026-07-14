"""Celery tasks for asynchronous subtitle transcription."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


@celery_app.task(name="subtitle.generate", bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def run_subtitle_task(self, subtitle_id: str) -> dict:
    logger.info("Starting subtitle task for id=%s (attempt=%d)", subtitle_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.subtitle_repository import SubtitleRepository
        from app.services.subtitle_service import SubtitleService

        async with async_session_factory() as session:
            async with session.begin():
                repo = SubtitleRepository(session)
                service = SubtitleService(repo)
                result = await service.execute_subtitle(subtitle_id)
                if result is None:
                    return {"status": "not_found", "id": subtitle_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Subtitle task failed for id=%s: %s", subtitle_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(subtitle_id, str(exc))
            return {"status": "failed", "id": subtitle_id, "error": str(exc)}


def _mark_failed(subtitle_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.subtitle_repository import SubtitleRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = SubtitleRepository(session)
                await repo.update(
                    subtitle_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark subtitle %s as failed: %s", subtitle_id, e)


@celery_app.task(name="subtitle.cleanup_stale", bind=True)
def cleanup_stale_subtitles(self) -> dict:
    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.subtitle_repository import SubtitleRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = SubtitleRepository(session)
                pending, _ = await repo.list(limit=10_000, offset=0, status="pending")
                running, _ = await repo.list(limit=10_000, offset=0, status="running")
                stale = list(pending) + list(running)
                now = datetime.now(timezone.utc)
                count = 0
                for item in stale:
                    age_minutes = (now - item.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    if age_minutes > _STALE_PENDING_MINUTES:
                        await repo.update(item.id, status="failed", error_message="Stale job timed out", updated_at=now)
                        count += 1
                return {"cleaned": count}

    return asyncio.run(_run())
