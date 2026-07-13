"""Render API endpoints — list, create, get, delete, provider stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.render import RenderResult
from app.repositories.render_repository import RenderRepository
from app.schemas.render import RenderProviderStats, RenderRequest, RenderResultSchema, RenderStatus
from app.services.render_service import RenderService

router = APIRouter(prefix="/renders", tags=["renders"])


def _to_api(render: RenderResult) -> RenderResultSchema:
    """Coerce ORM model to API schema."""
    return RenderResultSchema(
        id=render.id,
        timeline_id=render.timeline_id,
        voice_id=render.voice_id,
        status=RenderStatus(render.status),
        progress=render.progress,
        resolution=render.resolution,
        width=render.width,
        height=render.height,
        fps=render.fps,
        aspect_ratio=render.aspect_ratio,
        crop_mode=render.crop_mode,
        hardware_acceleration=bool(render.hardware_acceleration),
        render_plan=render.render_plan or {},
        render_output=render.render_output or {},
        render_stats=render.render_stats or {},
        render_metadata=render.render_metadata or {},
        preview_output=render.preview_output or {},
        logs=render.logs or [],
        error_message=render.error_message,
        created_at=render.created_at,
        updated_at=render.updated_at,
        completed_at=render.completed_at,
    )


@router.get("", response_model=dict)
async def list_renders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    timeline_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of render results (the Render Queue)."""
    service = RenderService(RenderRepository(db))
    renders, total = await service.list_renders(limit=limit, offset=offset, status=status, timeline_id=timeline_id)
    return {"items": [_to_api(r) for r in renders], "total": total}


@router.post("", response_model=RenderResultSchema, status_code=202)
async def start_render(
    request: RenderRequest,
    db: AsyncSession = Depends(get_db),
) -> RenderResultSchema:
    """Enqueue a new render job for a completed timeline."""
    service = RenderService(RenderRepository(db))
    try:
        render = await service.start_render(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_api(render)


@router.get("/providers/stats", response_model=RenderProviderStats)
async def get_render_provider_stats(db: AsyncSession = Depends(get_db)) -> RenderProviderStats:
    """Aggregate render-engine statistics (single backend: MoviePy)."""
    service = RenderService(RenderRepository(db))
    return await service.provider_stats()


@router.get("/{render_id}", response_model=RenderResultSchema)
async def get_render(
    render_id: str,
    db: AsyncSession = Depends(get_db),
) -> RenderResultSchema:
    """Fetch a single render result by ID."""
    service = RenderService(RenderRepository(db))
    render = await service.get_render(render_id)
    if not render:
        raise HTTPException(status_code=404, detail=f"Render {render_id!r} not found")
    return _to_api(render)


@router.delete("/{render_id}", status_code=204)
async def delete_render(
    render_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a render result (and its output file, if present)."""
    service = RenderService(RenderRepository(db))
    deleted = await service.delete_render(render_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Render {render_id!r} not found")
