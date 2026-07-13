"""Celery tasks for asynchronous voice (narration/TTS) generation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


@celery_app.task(
    name="voice.generate",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def run_voice_task(self, voice_id: str) -> dict:
    """Execute the narration-generation pipeline for a given voice record.

    This is a Celery task that wraps the async VoiceService.execute_voice()
    using asyncio.run(), matching the pattern from script_tasks.py.
    """
    logger.info("Starting voice task for id=%s (attempt=%d)", voice_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.voice_repository import VoiceRepository
        from app.services.voice_service import VoiceService

        async with async_session_factory() as session:
            async with session.begin():
                repo = VoiceRepository(session)
                service = VoiceService(repo)
                result = await service.execute_voice(voice_id)
                if result is None:
                    return {"status": "not_found", "id": voice_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Voice task failed for id=%s: %s", voice_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Voice %s exhausted retries — marking as failed", voice_id)
            _mark_failed(voice_id, str(exc))
            return {"status": "failed", "id": voice_id, "error": str(exc)}


def _mark_failed(voice_id: str, error: str) -> None:
    """Best-effort failure mark when retries are exhausted."""
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.voice_repository import VoiceRepository
        from datetime import datetime, timezone

        async with async_session_factory() as session:
            async with session.begin():
                repo = VoiceRepository(session)
                await repo.update(
                    voice_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark voice %s as failed: %s", voice_id, e)


@celery_app.task(name="voice.cleanup_stale", bind=True)
def cleanup_stale_voices(self) -> dict:
    """Periodic task — mark stale pending/running voice jobs as failed."""

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.voice_repository import VoiceRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = VoiceRepository(session)
                stale_pending = await repo.get_by_status("pending")
                stale_running = await repo.get_by_status("running")
                stale = stale_pending + stale_running

                now = datetime.now(timezone.utc)
                count = 0
                for voice in stale:
                    age_minutes = (now - voice.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    if age_minutes > _STALE_PENDING_MINUTES:
                        await repo.update(
                            voice.id,
                            status="failed",
                            error_message=f"Stale job timed out after {_STALE_PENDING_MINUTES} minutes",
                            updated_at=now,
                        )
                        count += 1

                logger.info("Cleaned up %d stale voice jobs", count)
                return {"cleaned": count}

    return asyncio.run(_run())
