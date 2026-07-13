"""Voice API endpoints — list, create, get, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.voice_result import VoiceResult
from app.repositories.voice_repository import VoiceRepository
from app.schemas.voice import VoiceRequest, VoiceResultSchema, VoiceStatus
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voices", tags=["voices"])


def _to_api(voice: VoiceResult) -> VoiceResultSchema:
    """Coerce ORM model to API schema."""
    return VoiceResultSchema(
        id=voice.id,
        script_id=voice.script_id,
        status=VoiceStatus(voice.status),
        voice_id=voice.voice_id,
        speed=voice.speed,
        language=voice.language,
        sections=voice.sections or [],
        total_duration_ms=voice.total_duration_ms,
        word_count=voice.word_count,
        sample_rate=voice.sample_rate,
        audio_format=voice.audio_format,
        normalized=voice.normalized,
        target_loudness_lufs=voice.target_loudness_lufs,
        cost_usd=voice.cost_usd,
        used_provider=voice.used_provider,
        providers=voice.providers or [],
        job_id=voice.job_id,
        logs=voice.logs or [],
        error_message=voice.error_message,
        created_at=voice.created_at,
        updated_at=voice.updated_at,
        completed_at=voice.completed_at,
    )


@router.get("", response_model=dict)
async def list_voices(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    script_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of voice results."""
    service = VoiceService(VoiceRepository(db))
    voices, total = await service.list_voices(limit=limit, offset=offset, status=status, script_id=script_id)
    return {"items": [_to_api(v) for v in voices], "total": total}


@router.post("", response_model=VoiceResultSchema, status_code=202)
async def start_voice(
    request: VoiceRequest,
    db: AsyncSession = Depends(get_db),
) -> VoiceResultSchema:
    """Enqueue a new narration (TTS) generation job for a script."""
    service = VoiceService(VoiceRepository(db))
    try:
        voice = await service.start_voice(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_api(voice)


@router.get("/{voice_id}", response_model=VoiceResultSchema)
async def get_voice(
    voice_id: str,
    db: AsyncSession = Depends(get_db),
) -> VoiceResultSchema:
    """Fetch a single voice result by ID."""
    service = VoiceService(VoiceRepository(db))
    voice = await service.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice {voice_id!r} not found")
    return _to_api(voice)


@router.delete("/{voice_id}", status_code=204, response_model=None)
async def delete_voice(
    voice_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a voice result."""
    service = VoiceService(VoiceRepository(db))
    deleted = await service.delete_voice(voice_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Voice {voice_id!r} not found")
