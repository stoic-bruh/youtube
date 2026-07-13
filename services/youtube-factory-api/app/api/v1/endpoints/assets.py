"""Asset Intelligence Engine API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.asset import AssetProviderMetadata, AssetResult
from app.repositories.asset_repository import AssetProviderMetadataRepository
from app.schemas.asset import (
    AssetKind,
    AssetLicense,
    AssetProviderName,
    AssetRequest,
    AssetResultSchema,
    AssetList,
    AssetStatus,
)
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])

# Provider type, by name — used to build zeroed defaults before any run has happened.
_PROVIDER_TYPES: dict[str, str] = {
    AssetProviderName.FLUX.value: "generate",
    AssetProviderName.SDXL.value: "generate",
    AssetProviderName.GPT_IMAGE.value: "generate",
    AssetProviderName.GEMINI_IMAGE.value: "generate",
    AssetProviderName.IDEOGRAM.value: "generate",
    AssetProviderName.WIKIMEDIA.value: "stock",
    AssetProviderName.UNSPLASH.value: "stock",
    AssetProviderName.PIXABAY.value: "stock",
    AssetProviderName.PEXELS.value: "stock",
    AssetProviderName.PEXELS_VIDEO.value: "stock",
    AssetProviderName.PIXABAY_VIDEO.value: "stock",
    AssetProviderName.MIXKIT.value: "stock",
    AssetProviderName.LUCIDE.value: "icon",
    AssetProviderName.HEROICONS.value: "icon",
    AssetProviderName.MATERIAL_ICONS.value: "icon",
}


def _provider_stats_to_api(m: AssetProviderMetadata) -> dict:
    return {
        "providerName": m.provider_name,
        "providerType": m.provider_type,
        "isEnabled": m.is_enabled,
        "totalRequests": m.total_requests,
        "successfulRequests": m.successful_requests,
        "failedRequests": m.failed_requests,
        "avgLatencyMs": m.avg_latency_ms,
        "avgCostUsd": m.avg_cost_usd,
        "totalCostUsd": m.total_cost_usd,
        "cacheHits": m.cache_hits,
        "supportedKinds": m.supported_kinds or [],
    }


def _default_provider_stats(name: str) -> dict:
    return {
        "providerName": name,
        "providerType": _PROVIDER_TYPES.get(name, "stock"),
        "isEnabled": True,
        "totalRequests": 0,
        "successfulRequests": 0,
        "failedRequests": 0,
        "avgLatencyMs": None,
        "avgCostUsd": None,
        "totalCostUsd": 0.0,
        "cacheHits": 0,
        "supportedKinds": [],
    }


def _to_api(a: AssetResult) -> AssetResultSchema:
    """Coerce ORM model → API schema."""
    return AssetResultSchema(
        id=a.id,
        storyboard_id=a.storyboard_id,
        scene_id=a.scene_id,
        asset_kind=AssetKind(a.asset_kind),
        provider=AssetProviderName(a.provider) if a.provider else None,
        provider_asset_id=a.provider_asset_id,
        source_url=a.source_url,
        license=AssetLicense(a.license) if a.license else AssetLicense.UNKNOWN,
        prompt=a.prompt,
        negative_prompt=a.negative_prompt,
        generation_parameters=a.generation_parameters or {},
        width=a.width,
        height=a.height,
        aspect_ratio=a.aspect_ratio,
        status=AssetStatus(a.status),
        cost_estimate_usd=a.cost_estimate_usd,
        generation_time_ms=a.generation_time_ms,
        file_size_bytes=a.file_size_bytes,
        local_cache_path=a.local_cache_path,
        thumbnail_path=a.thumbnail_path,
        tags=a.tags or [],
        quality_score=a.quality_score,
        relevance_score=a.relevance_score,
        logs=a.logs or [],
        error_message=a.error_message,
        created_at=a.created_at,
        updated_at=a.updated_at,
        completed_at=a.completed_at,
    )


@router.get("", response_model=AssetList)
async def list_assets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    storyboard_id: str | None = Query(None),
    scene_id: str | None = Query(None),
    status: str | None = Query(None),
    asset_kind: str | None = Query(None),
    provider: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> AssetList:
    """Return a paginated list of asset results."""
    service = AssetService(db)
    assets, total = await service.list_assets(
        limit=limit,
        offset=offset,
        storyboard_id=storyboard_id,
        scene_id=scene_id,
        status=status,
        asset_kind=asset_kind,
        provider=provider,
    )
    return AssetList(items=[_to_api(a) for a in assets], total=total)


@router.post("", response_model=dict, status_code=202)
async def acquire_assets(
    request: AssetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Enqueue asset acquisition for all scenes in a storyboard.
    Returns the list of created asset records immediately (202 Accepted).
    Actual acquisition runs asynchronously via Celery.
    """
    service = AssetService(db)
    assets = await service.start_acquisition(request)

    # Fire Celery tasks for each asset
    try:
        from app.tasks.asset_tasks import acquire_asset_task  # noqa: PLC0415
        for asset in assets:
            acquire_asset_task.delay(asset.id)
    except Exception:  # noqa: BLE001
        # Celery unavailable in dev — run inline (setImmediate equivalent)
        import asyncio  # noqa: PLC0415
        for asset in assets:
            asyncio.create_task(_run_inline(asset.id))

    return {
        "items": [_to_api(a) for a in assets],
        "total": len(assets),
        "message": f"Asset acquisition queued for {len(assets)} scenes",
    }


@router.get("/{asset_id}", response_model=AssetResultSchema)
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
) -> AssetResultSchema:
    """Fetch a single asset record by ID."""
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id!r} not found")
    return _to_api(asset)


@router.get("/providers", response_model=dict)
async def list_asset_providers(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return runtime statistics for every known asset provider."""
    repo = AssetProviderMetadataRepository(db)
    rows, _ = await repo.list(limit=100)
    by_name = {r.provider_name: r for r in rows}
    items = [
        _provider_stats_to_api(by_name[name]) if name in by_name else _default_provider_stats(name)
        for name in _PROVIDER_TYPES
    ]
    return {"items": items}


@router.delete("/{asset_id}", status_code=204, response_model=None)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an asset record."""
    service = AssetService(db)
    deleted = await service.delete_asset(asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id!r} not found")


async def _run_inline(asset_id: str) -> None:
    """Inline async fallback when Celery is not running."""
    try:
        from app.core.database import async_session_factory  # noqa: PLC0415
        from app.services.asset_service import AssetService as _S  # noqa: PLC0415
        async with async_session_factory() as session:
            async with session.begin():
                await _S(session).execute_asset(asset_id)
    except Exception as e:
        import logging  # noqa: PLC0415
        logging.getLogger(__name__).error("Inline asset execution failed %s: %s", asset_id, e)
