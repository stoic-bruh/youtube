"""Storyboard API endpoints — list, create, get, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.research import get_db
from app.models.storyboard_result import StoryboardResult
from app.repositories.storyboard_repository import StoryboardRepository
from app.schemas.storyboard import StoryboardRequest, StoryboardResultSchema, StoryboardStatus
from app.services.storyboard_service import StoryboardService

router = APIRouter(prefix="/storyboards", tags=["storyboards"])


def _to_api(sb: StoryboardResult) -> StoryboardResultSchema:
    """Coerce ORM model to API schema."""
    return StoryboardResultSchema(
        id=sb.id,
        script_id=sb.script_id,
        research_id=sb.research_id,
        topic=sb.topic,
        title=sb.title,
        status=StoryboardStatus(sb.status),
        script_style=sb.script_style,
        script_tone=sb.script_tone,
        target_duration_minutes=sb.target_duration_minutes,
        target_audience=sb.target_audience or "general audience",
        language=sb.language,
        version=sb.version,
        scenes=sb.scenes or [],
        scene_timeline=sb.scene_timeline or [],
        narration_timing=sb.narration_timing or [],
        visual_cues=sb.visual_cues or [],
        total_duration_seconds=sb.total_duration_seconds,
        scene_count=sb.scene_count,
        image_count=sb.image_count,
        editing_complexity_score=sb.editing_complexity_score,
        estimated_render_time_minutes=sb.estimated_render_time_minutes,
        estimated_cost_usd=sb.estimated_cost_usd,
        visual_pacing=sb.visual_pacing,
        narration_pacing=sb.narration_pacing,
        providers=sb.providers or [],
        used_providers=sb.used_providers or [],
        job_id=sb.job_id,
        logs=sb.logs or [],
        error_message=sb.error_message,
        created_at=sb.created_at,
        updated_at=sb.updated_at,
        completed_at=sb.completed_at,
    )


@router.get("", response_model=dict)
async def list_storyboards(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a paginated list of storyboard results."""
    service = StoryboardService(StoryboardRepository(db))
    storyboards, total = await service.list_storyboards(limit=limit, offset=offset, status=status)
    return {"items": [_to_api(sb) for sb in storyboards], "total": total}


@router.post("", response_model=StoryboardResultSchema, status_code=202)
async def start_storyboard(
    request: StoryboardRequest,
    db: AsyncSession = Depends(get_db),
) -> StoryboardResultSchema:
    """Enqueue a new storyboard-generation job."""
    service = StoryboardService(StoryboardRepository(db))
    sb = await service.start_storyboard(request)
    return _to_api(sb)


@router.get("/{storyboard_id}", response_model=StoryboardResultSchema)
async def get_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
) -> StoryboardResultSchema:
    """Fetch a single storyboard result by ID."""
    service = StoryboardService(StoryboardRepository(db))
    sb = await service.get_storyboard(storyboard_id)
    if not sb:
        raise HTTPException(status_code=404, detail=f"Storyboard {storyboard_id!r} not found")
    return _to_api(sb)


@router.delete("/{storyboard_id}", status_code=204)
async def delete_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a storyboard result."""
    service = StoryboardService(StoryboardRepository(db))
    deleted = await service.delete_storyboard(storyboard_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Storyboard {storyboard_id!r} not found")
