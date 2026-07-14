"""Chapter API endpoints — list, create, get, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.chapter_result import ChapterResult
from app.repositories.chapter_repository import ChapterRepository
from app.schemas.chapter import ChapterRequest, ChapterResultSchema, ChapterStatus
from app.services.chapter_service import ChapterService

router = APIRouter(prefix="/chapters", tags=["chapters"])


def _to_api(chapter: ChapterResult) -> ChapterResultSchema:
    return ChapterResultSchema(
        id=chapter.id,
        render_id=chapter.render_id,
        status=ChapterStatus(chapter.status),
        chapters=chapter.chapters or [],
        youtube_export=chapter.youtube_export,
        sources=chapter.sources or {},
        logs=chapter.logs or [],
        error_message=chapter.error_message,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        completed_at=chapter.completed_at,
    )


@router.get("", response_model=dict)
async def list_chapters(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    render_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChapterService(ChapterRepository(db))
    chapters, total = await service.list_chapters(limit=limit, offset=offset, status=status, render_id=render_id)
    return {"items": [_to_api(c) for c in chapters], "total": total}


@router.post("", response_model=ChapterResultSchema, status_code=202)
async def start_chapter(request: ChapterRequest, db: AsyncSession = Depends(get_db)) -> ChapterResultSchema:
    service = ChapterService(ChapterRepository(db))
    try:
        chapter = await service.start_chapter(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_api(chapter)


@router.get("/{chapter_id}", response_model=ChapterResultSchema)
async def get_chapter(chapter_id: str, db: AsyncSession = Depends(get_db)) -> ChapterResultSchema:
    service = ChapterService(ChapterRepository(db))
    chapter = await service.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_id!r} not found")
    return _to_api(chapter)


@router.delete("/{chapter_id}", status_code=204, response_model=None)
async def delete_chapter(chapter_id: str, db: AsyncSession = Depends(get_db)) -> None:
    service = ChapterService(ChapterRepository(db))
    deleted = await service.delete_chapter(chapter_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_id!r} not found")
