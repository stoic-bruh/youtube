"""Research Celery tasks — async job execution for the ResearchService.

The Celery task handles DB session creation (sync wrapper around async service).
"""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="research.run",
    max_retries=2,
    default_retry_delay=30,
    queue="research",
    time_limit=300,   # 5 min hard kill
    soft_time_limit=270,
)
def run_research_task(self, research_id: str) -> dict:
    """Execute research pipeline for the given research_id.

    Celery tasks must be synchronous; we run the async service via asyncio.run().
    """
    logger.info("Celery worker starting research task for id=%s", research_id)
    try:
        result = asyncio.run(_execute(research_id))
        if result is None:
            return {"research_id": research_id, "status": "failed"}
        return {"research_id": research_id, "status": result.status}
    except Exception as exc:
        logger.error("Research task failed for id=%s: %s", research_id, exc, exc_info=True)
        raise self.retry(exc=exc)


async def _execute(research_id: str) -> object | None:
    """Async inner execution — creates DB session and calls ResearchService."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import async_session_factory
    from app.repositories.research_repository import ResearchRepository
    from app.services.research_service import ResearchService

    async with async_session_factory() as session:
        async with session.begin():
            repo = ResearchRepository(session)
            service = ResearchService(repo)
            return await service.execute_research(research_id)


# ── Utility tasks ──────────────────────────────────────────────────────────────

@celery_app.task(name="research.cleanup_stale", queue="research")
def cleanup_stale_research() -> dict:
    """Periodic task: mark stuck 'running' research as failed after timeout."""
    result = asyncio.run(_cleanup_stale())
    return result


async def _cleanup_stale() -> dict:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, update
    from app.core.database import async_session_factory
    from app.models.research_result import ResearchResult

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    async with async_session_factory() as session:
        async with session.begin():
            stmt = (
                update(ResearchResult)
                .where(ResearchResult.status == "running")
                .where(ResearchResult.updated_at < cutoff)
                .values(
                    status="failed",
                    error_message="Timed out — worker may have crashed",
                    updated_at=datetime.now(timezone.utc),
                )
                .returning(ResearchResult.id)
            )
            result = await session.execute(stmt)
            stale_ids = [row[0] for row in result.fetchall()]
    logger.info("Cleaned up %d stale research jobs: %s", len(stale_ids), stale_ids)
    return {"cleaned": len(stale_ids), "ids": stale_ids}
