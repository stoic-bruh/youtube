"""Pipeline management endpoints."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.pipeline import Pipeline
from app.models.project import Project
from app.repositories.pipeline_repository import PipelineRepository
from app.repositories.project_repository import ProjectRepository

router = APIRouter()


def pipeline_to_dict(p: Pipeline) -> dict:
    return {
        "id": p.id,
        "projectId": p.project_id,
        "status": p.status,
        "currentStage": p.current_stage,
        "progress": p.progress,
        "stages": p.stages or [],
        "startedAt": p.started_at.isoformat(),
        "completedAt": p.completed_at.isoformat() if p.completed_at else None,
        "errorMessage": p.error_message,
    }


@router.get("")
async def list_pipelines(
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    repo = PipelineRepository(db)
    filters = {}
    if project_id:
        filters["project_id"] = project_id
    if status:
        filters["status"] = status
    rows, total = await repo.list(limit=limit, **filters)
    return {"items": [pipeline_to_dict(p) for p in rows], "total": total}


@router.get("/{id}")
async def get_pipeline(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = PipelineRepository(db)
    pipeline = await repo.get(id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Not found")
    return pipeline_to_dict(pipeline)


@router.post("/{id}/cancel")
async def cancel_pipeline(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = PipelineRepository(db)
    pipeline = await repo.update(
        id, status="cancelled", completed_at=datetime.now(timezone.utc)
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail="Not found")

    project_repo = ProjectRepository(db)
    await project_repo.update(
        pipeline.project_id,
        status="cancelled",
        updated_at=datetime.now(timezone.utc),
    )
    return pipeline_to_dict(pipeline)


@router.post("/{id}/retry", status_code=202)
async def retry_pipeline(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = PipelineRepository(db)
    pipeline = await repo.get(id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Not found")

    reset_stages = [
        {**s, "status": "completed" if s["status"] == "completed" else "pending", "error": None}
        for s in (pipeline.stages or [])
    ]
    updated = await repo.update(id, status="queued", error_message=None, stages=reset_stages)

    project_repo = ProjectRepository(db)
    await project_repo.update(pipeline.project_id, status="queued", updated_at=datetime.now(timezone.utc))

    # TODO: Re-enqueue pipeline.run_full_pipeline.delay(id, pipeline.project_id)
    return pipeline_to_dict(updated)
