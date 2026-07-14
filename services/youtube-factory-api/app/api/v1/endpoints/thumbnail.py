"""Thumbnail API endpoints — list, create, get, delete, file download."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.thumbnail_result import ThumbnailResult
from app.repositories.thumbnail_repository import ThumbnailRepository
from app.schemas.thumbnail import ThumbnailRequest, ThumbnailResultSchema, ThumbnailStatus
from app.services.thumbnail_service import ThumbnailService

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])


def _to_api(thumbnail: ThumbnailResult) -> ThumbnailResultSchema:
    return ThumbnailResultSchema(
        id=thumbnail.id,
        render_id=thumbnail.render_id,
        status=ThumbnailStatus(thumbnail.status),
        candidates=thumbnail.candidates or [],
        selected_candidate_ids=thumbnail.selected_candidate_ids or [],
        templates=thumbnail.templates or [],
        title_overlay=thumbnail.title_overlay or {},
        brand_colors=thumbnail.brand_colors or [],
        logs=thumbnail.logs or [],
        error_message=thumbnail.error_message,
        created_at=thumbnail.created_at,
        updated_at=thumbnail.updated_at,
        completed_at=thumbnail.completed_at,
    )


@router.get("", response_model=dict)
async def list_thumbnails(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    render_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ThumbnailService(ThumbnailRepository(db))
    thumbnails, total = await service.list_thumbnails(limit=limit, offset=offset, status=status, render_id=render_id)
    return {"items": [_to_api(t) for t in thumbnails], "total": total}


@router.post("", response_model=ThumbnailResultSchema, status_code=202)
async def start_thumbnail(request: ThumbnailRequest, db: AsyncSession = Depends(get_db)) -> ThumbnailResultSchema:
    service = ThumbnailService(ThumbnailRepository(db))
    try:
        thumbnail = await service.start_thumbnail(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_api(thumbnail)


@router.get("/{thumbnail_id}", response_model=ThumbnailResultSchema)
async def get_thumbnail(thumbnail_id: str, db: AsyncSession = Depends(get_db)) -> ThumbnailResultSchema:
    service = ThumbnailService(ThumbnailRepository(db))
    thumbnail = await service.get_thumbnail(thumbnail_id)
    if not thumbnail:
        raise HTTPException(status_code=404, detail=f"Thumbnail {thumbnail_id!r} not found")
    return _to_api(thumbnail)


@router.delete("/{thumbnail_id}", status_code=204, response_model=None)
async def delete_thumbnail(thumbnail_id: str, db: AsyncSession = Depends(get_db)) -> None:
    service = ThumbnailService(ThumbnailRepository(db))
    deleted = await service.delete_thumbnail(thumbnail_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thumbnail {thumbnail_id!r} not found")


@router.get("/{thumbnail_id}/file/{candidate_id}")
async def get_thumbnail_file(thumbnail_id: str, candidate_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    service = ThumbnailService(ThumbnailRepository(db))
    thumbnail = await service.get_thumbnail(thumbnail_id)
    if not thumbnail:
        raise HTTPException(status_code=404, detail=f"Thumbnail {thumbnail_id!r} not found")
    candidate = next((c for c in (thumbnail.candidates or []) if c.get("candidate_id") == candidate_id), None)
    if not candidate or not os.path.isfile(candidate.get("path", "")):
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found")
    return FileResponse(candidate["path"])
