"""Production Asset bundle API endpoints — list, get-or-assemble."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.production_asset import ProductionAsset
from app.repositories.production_asset_repository import ProductionAssetRepository
from app.schemas.production_asset import ProductionAssetResultSchema, ProductionAssetStatus
from app.services.production_asset_service import ProductionAssetService

router = APIRouter(prefix="/production-assets", tags=["production-assets"])


def _to_api(bundle: ProductionAsset, joined: dict) -> ProductionAssetResultSchema:
    return ProductionAssetResultSchema(
        id=bundle.id,
        render_id=bundle.render_id,
        status=ProductionAssetStatus(bundle.status),
        subtitle_id=bundle.subtitle_id,
        thumbnail_id=bundle.thumbnail_id,
        chapter_id=bundle.chapter_id,
        subtitle=joined.get("subtitle"),
        thumbnail=joined.get("thumbnail"),
        chapter=joined.get("chapter"),
        export_manifest=bundle.export_manifest or {},
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
        completed_at=bundle.completed_at,
    )


@router.get("", response_model=dict)
async def list_production_assets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ProductionAssetService(ProductionAssetRepository(db))
    bundles, total = await service.list_bundles(limit=limit, offset=offset)
    items = []
    for bundle in bundles:
        result = await service.get_or_assemble(bundle.render_id)
        if result:
            updated, joined = result
            items.append(_to_api(updated, joined))
    return {"items": items, "total": total}


@router.get("/{render_id}", response_model=ProductionAssetResultSchema)
async def get_production_assets(render_id: str, db: AsyncSession = Depends(get_db)) -> ProductionAssetResultSchema:
    service = ProductionAssetService(ProductionAssetRepository(db))
    result = await service.get_or_assemble(render_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Render {render_id!r} not found")
    bundle, joined = result
    return _to_api(bundle, joined)
