"""Celery tasks for asynchronous script generation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


@celery_app.task(
    name="script.generate",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def run_script_task(self, script_id: str) -> dict:
    """Execute the script-generation pipeline for a given script record.

    This is a Celery task that wraps the async ScriptService.execute_script()
    using asyncio.run(), matching the pattern from research_tasks.py.
    """
    logger.info("Starting script task for id=%s (attempt=%d)", script_id, self.request.retries + 1)

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.script_repository import ScriptRepository
        from app.services.script_service import ScriptService

        async with async_session_factory() as session:
            async with session.begin():
                repo = ScriptRepository(session)
                service = ScriptService(repo)
                result = await service.execute_script(script_id)
                if result is None:
                    return {"status": "not_found", "id": script_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Script task failed for id=%s: %s", script_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Script %s exhausted retries — marking as failed", script_id)
            _mark_failed(script_id, str(exc))
            return {"status": "failed", "id": script_id, "error": str(exc)}


def _mark_failed(script_id: str, error: str) -> None:
    """Best-effort failure mark when retries are exhausted."""
    async def _run() -> None:
        from app.core.database import async_session_factory
        from app.repositories.script_repository import ScriptRepository
        from datetime import datetime, timezone

        async with async_session_factory() as session:
            async with session.begin():
                repo = ScriptRepository(session)
                await repo.update(
                    script_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark script %s as failed: %s", script_id, e)


@celery_app.task(name="script.cleanup_stale", bind=True)
def cleanup_stale_scripts(self) -> dict:
    """Periodic task — mark stale pending/running scripts as failed."""

    async def _run() -> dict:
        from app.core.database import async_session_factory
        from app.repositories.script_repository import ScriptRepository

        async with async_session_factory() as session:
            async with session.begin():
                repo = ScriptRepository(session)
                stale_pending = await repo.get_by_status("pending")
                stale_running = await repo.get_by_status("running")
                stale = stale_pending + stale_running

                now = datetime.now(timezone.utc)
                count = 0
                for script in stale:
                    age_minutes = (now - script.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
                    if age_minutes > _STALE_PENDING_MINUTES:
                        await repo.update(
                            script.id,
                            status="failed",
                            error_message=f"Stale job timed out after {_STALE_PENDING_MINUTES} minutes",
                            updated_at=now,
                        )
                        count += 1

                logger.info("Cleaned up %d stale script jobs", count)
                return {"cleaned": count}

    return asyncio.run(_run())
