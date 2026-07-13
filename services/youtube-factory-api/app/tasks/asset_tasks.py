"""Celery tasks for asynchronous asset acquisition."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


@celery_app.task(
    name="asset.acquire",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def acquire_asset_task(self, asset_id: str) -> dict:
    """Run the Asset Intelligence Engine decision flow for a single asset record."""
    logger.info(
        "Starting asset acquisition id=%s (attempt=%d)",
        asset_id,
        self.request.retries + 1,
    )

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.services.asset_service import AssetService  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                service = AssetService(session)
                result = await service.execute_asset(asset_id)
                if result is None:
                    return {"status": "not_found", "id": asset_id}
                return {"status": result.status, "id": result.id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Asset task failed id=%s: %s", asset_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("Asset %s exhausted retries — marking as failed", asset_id)
            _mark_failed(asset_id, str(exc))
            return {"status": "failed", "id": asset_id, "error": str(exc)}


@celery_app.task(
    name="asset.acquire_batch",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def acquire_assets_batch_task(self, storyboard_id: str, asset_ids: list[str]) -> dict:
    """Acquire a batch of asset records (one per scene) for a storyboard."""
    logger.info(
        "Starting batch asset acquisition storyboard=%s count=%d",
        storyboard_id,
        len(asset_ids),
    )

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.services.asset_service import AssetService  # noqa: PLC0415

        results: dict = {"completed": 0, "failed": 0, "ids": []}
        async with async_session_factory() as session:
            async with session.begin():
                service = AssetService(session)
                for asset_id in asset_ids:
                    try:
                        result = await service.execute_asset(asset_id)
                        if result:
                            results["ids"].append(result.id)
                            if result.status in ("ready", "cached"):
                                results["completed"] += 1
                            else:
                                results["failed"] += 1
                    except Exception as e:
                        logger.error("Failed to acquire asset %s: %s", asset_id, e)
                        results["failed"] += 1
        return results

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Batch asset task failed storyboard=%s: %s", storyboard_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "storyboard_id": storyboard_id, "error": str(exc)}


@celery_app.task(name="asset.cleanup_stale", bind=True)
def cleanup_stale_assets(self) -> dict:
    """Periodic task — mark stale pending/searching assets as failed."""

    async def _run() -> dict:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.repositories.asset_repository import AssetRepository  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                repo = AssetRepository(session)
                stale = (
                    await repo.get_by_status("pending")
                    + await repo.get_by_status("searching")
                    + await repo.get_by_status("generating")
                    + await repo.get_by_status("downloading")
                )
                now = datetime.now(timezone.utc)
                count = 0
                for asset in stale:
                    created = asset.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    age_minutes = (now - created).total_seconds() / 60
                    if age_minutes > _STALE_PENDING_MINUTES:
                        await repo.update(
                            asset.id,
                            status="failed",
                            error_message=f"Stale job timed out after {_STALE_PENDING_MINUTES} minutes",
                            updated_at=now,
                        )
                        count += 1
                logger.info("Cleaned up %d stale asset jobs", count)
                return {"cleaned": count}

    return asyncio.run(_run())


def _mark_failed(asset_id: str, error: str) -> None:
    async def _run() -> None:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.repositories.asset_repository import AssetRepository  # noqa: PLC0415

        async with async_session_factory() as session:
            async with session.begin():
                repo = AssetRepository(session)
                await repo.update(
                    asset_id,
                    status="failed",
                    error_message=f"Max retries exceeded: {error}",
                    updated_at=datetime.now(timezone.utc),
                )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("Could not mark asset %s as failed: %s", asset_id, e)
