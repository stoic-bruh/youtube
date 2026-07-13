"""Celery tasks for asynchronous timeline building."""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="timeline.build",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def build_timeline_task(self, timeline_id: str) -> dict:
    """Run the Media Timeline Engine for a single timeline record."""
    logger.info(
        "Starting timeline build id=%s (attempt=%d)",
        timeline_id,
        self.request.retries + 1,
    )

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.services.timeline_service import TimelineService  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                service = TimelineService(session)
                result = await service.execute_timeline(timeline_id)
                if result is None:
                    return {"status": "not_found", "id": timeline_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Timeline task failed id=%s: %s", timeline_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Timeline %s exhausted retries", timeline_id)
            return {"status": "failed", "id": timeline_id, "error": str(exc)}
