"""Subtitle API endpoints — list, create, get, delete, file download."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.subtitle_result import SubtitleResult
from app.repositories.subtitle_repository import SubtitleRepository
from app.schemas.subtitle import SubtitleRequest, SubtitleResultSchema, SubtitleStatus
from app.services.subtitle_service import SubtitleService

router = APIRouter(prefix="/subtitles", tags=["subtitles"])


def _to_api(subtitle: SubtitleResult) -> SubtitleResultSchema:
    return SubtitleResultSchema(
        id=subtitle.id,
        render_id=subtitle.render_id,
        status=SubtitleStatus(subtitle.status),
        language=subtitle.language,
        used_provider=subtitle.used_provider,
        providers=subtitle.providers or [],
        words=subtitle.words or [],
        sentences=subtitle.sentences or [],
        paragraphs=subtitle.paragraphs or [],
        srt_content=subtitle.srt_content,
        vtt_content=subtitle.vtt_content,
        ass_content=subtitle.ass_content,
        srt_path=subtitle.srt_path,
        vtt_path=subtitle.vtt_path,
        ass_path=subtitle.ass_path,
        burned_metadata=subtitle.burned_metadata or {},
        animated_caption_metadata=subtitle.animated_caption_metadata or {},
        karaoke_metadata=subtitle.karaoke_metadata or {},
        style=subtitle.style or {},
        caption_presets=subtitle.caption_presets or [],
        speaker_metadata=subtitle.speaker_metadata or [],
        avg_confidence=subtitle.avg_confidence,
        word_count=subtitle.word_count,
        duration_ms=subtitle.duration_ms,
        logs=subtitle.logs or [],
        error_message=subtitle.error_message,
        created_at=subtitle.created_at,
        updated_at=subtitle.updated_at,
        completed_at=subtitle.completed_at,
    )


@router.get("", response_model=dict)
async def list_subtitles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    render_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SubtitleService(SubtitleRepository(db))
    subtitles, total = await service.list_subtitles(limit=limit, offset=offset, status=status, render_id=render_id)
    return {"items": [_to_api(s) for s in subtitles], "total": total}


@router.post("", response_model=SubtitleResultSchema, status_code=202)
async def start_subtitle(request: SubtitleRequest, db: AsyncSession = Depends(get_db)) -> SubtitleResultSchema:
    service = SubtitleService(SubtitleRepository(db))
    try:
        subtitle = await service.start_subtitle(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_api(subtitle)


@router.get("/{subtitle_id}", response_model=SubtitleResultSchema)
async def get_subtitle(subtitle_id: str, db: AsyncSession = Depends(get_db)) -> SubtitleResultSchema:
    service = SubtitleService(SubtitleRepository(db))
    subtitle = await service.get_subtitle(subtitle_id)
    if not subtitle:
        raise HTTPException(status_code=404, detail=f"Subtitle {subtitle_id!r} not found")
    return _to_api(subtitle)


@router.delete("/{subtitle_id}", status_code=204, response_model=None)
async def delete_subtitle(subtitle_id: str, db: AsyncSession = Depends(get_db)) -> None:
    service = SubtitleService(SubtitleRepository(db))
    deleted = await service.delete_subtitle(subtitle_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Subtitle {subtitle_id!r} not found")


@router.get("/{subtitle_id}/file/{format}")
async def get_subtitle_file(subtitle_id: str, format: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    service = SubtitleService(SubtitleRepository(db))
    subtitle = await service.get_subtitle(subtitle_id)
    if not subtitle:
        raise HTTPException(status_code=404, detail=f"Subtitle {subtitle_id!r} not found")
    path_by_format = {"srt": subtitle.srt_path, "vtt": subtitle.vtt_path, "ass": subtitle.ass_path}
    path = path_by_format.get(format)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"No {format!r} file available for subtitle {subtitle_id!r}")
    return FileResponse(path)
