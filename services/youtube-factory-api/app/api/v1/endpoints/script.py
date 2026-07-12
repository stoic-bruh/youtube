"""Script API endpoints — list, create, get, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.script_result import ScriptResult
from app.repositories.script_repository import ScriptRepository
from app.schemas.script import ScriptRequest, ScriptResultSchema, ScriptStatus
from app.services.script_service import ScriptService

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _to_api(script: ScriptResult) -> ScriptResultSchema:
    """Coerce ORM model to API schema."""
    return ScriptResultSchema(
        id=script.id,
        research_id=script.research_id,
        topic=script.topic,
        title=script.title,
        status=ScriptStatus(script.status),
        style=script.style,
        tone=script.tone,
        language=script.language,
        target_audience=script.target_audience or "general audience",
        target_duration_minutes=script.target_duration_minutes,
        version=script.version,
        hook=script.hook,
        introduction=script.introduction,
        outro=script.outro,
        call_to_action=script.call_to_action,
        sections=script.sections or [],
        word_count=script.word_count,
        estimated_duration_seconds=script.estimated_duration_seconds,
        reading_time_seconds=script.reading_time_seconds,
        scene_count=script.scene_count,
        pacing_wpm=script.pacing_wpm,
        narration_timing=script.narration_timing or [],
        emphasis_markers=script.emphasis_markers or [],
        pauses=script.pauses or [],
        pronunciation_hints=script.pronunciation_hints or [],
        visual_cues=script.visual_cues or [],
        versions=script.versions or [],
        providers=script.providers or [],
        used_providers=script.used_providers or [],
        job_id=script.job_id,
        logs=script.logs or [],
        error_message=script.error_message,
        created_at=script.created_at,
        updated_at=script.updated_at,
        completed_at=script.completed_at,
    )


@router.get("", response_model=dict)
async def list_scripts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of script results."""
    service = ScriptService(ScriptRepository(db))
    scripts, total = await service.list_scripts(limit=limit, offset=offset, status=status)
    return {"items": [_to_api(s) for s in scripts], "total": total}


@router.post("", response_model=ScriptResultSchema, status_code=202)
async def start_script(
    request: ScriptRequest,
    db: AsyncSession = Depends(get_db),
) -> ScriptResultSchema:
    """Enqueue a new script-generation job."""
    service = ScriptService(ScriptRepository(db))
    script = await service.start_script(request)
    return _to_api(script)


@router.get("/{script_id}", response_model=ScriptResultSchema)
async def get_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScriptResultSchema:
    """Fetch a single script result by ID."""
    service = ScriptService(ScriptRepository(db))
    script = await service.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id!r} not found")
    return _to_api(script)


@router.delete("/{script_id}", status_code=204)
async def delete_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a script result."""
    service = ScriptService(ScriptRepository(db))
    deleted = await service.delete_script(script_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Script {script_id!r} not found")
