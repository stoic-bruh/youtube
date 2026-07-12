"""Project CRUD endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.pipeline import Pipeline, default_stages
from app.repositories.project_repository import ProjectRepository
from app.repositories.pipeline_repository import PipelineRepository

router = APIRouter()


class ProjectInputSchema(BaseModel):
    title: str
    topic: str
    description: str | None = None
    tags: list[str] = []


class ProjectUpdateSchema(BaseModel):
    title: str | None = None
    topic: str | None = None
    description: str | None = None
    status: str | None = None
    tags: list[str] | None = None


def project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "topic": p.topic,
        "description": p.description,
        "status": p.status,
        "thumbnailUrl": p.thumbnail_url,
        "videoUrl": p.video_url,
        "youtubeId": p.youtube_id,
        "youtubeUrl": p.youtube_url,
        "pipelineId": p.pipeline_id,
        "tags": p.tags or [],
        "createdAt": p.created_at.isoformat(),
        "updatedAt": p.updated_at.isoformat(),
    }


@router.get("")
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    repo = ProjectRepository(db)
    filters = {"status": status} if status else {}
    rows, total = await repo.list(limit=limit, offset=offset, **filters)
    return {"items": [project_to_dict(p) for p in rows], "total": total}


@router.post("", status_code=201)
async def create_project(
    body: ProjectInputSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = ProjectRepository(db)
    project = await repo.create(**body.model_dump())
    return project_to_dict(project)


@router.get("/{id}")
async def get_project(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = ProjectRepository(db)
    project = await repo.get(id)
    if not project:
        raise HTTPException(status_code=404, detail="Not found")
    return project_to_dict(project)


@router.patch("/{id}")
async def update_project(
    id: str,
    body: ProjectUpdateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = ProjectRepository(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc)
    project = await repo.update(id, **updates)
    if not project:
        raise HTTPException(status_code=404, detail="Not found")
    return project_to_dict(project)


@router.delete("/{id}", status_code=204)
async def delete_project(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = ProjectRepository(db)
    deleted = await repo.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/{id}/run", status_code=202)
async def run_project(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Start the full autonomous pipeline for a project."""
    project_repo = ProjectRepository(db)
    pipeline_repo = PipelineRepository(db)

    project = await project_repo.get(id)
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    pipeline = await pipeline_repo.create(
        project_id=project.id,
        status="queued",
        stages=default_stages(),
    )
    await project_repo.update(
        id,
        status="queued",
        pipeline_id=pipeline.id,
        updated_at=datetime.now(timezone.utc),
    )

    # TODO: Enqueue pipeline.run_full_pipeline.delay(pipeline.id, project.id)

    return {
        "id": pipeline.id,
        "projectId": pipeline.project_id,
        "status": pipeline.status,
        "currentStage": pipeline.current_stage,
        "progress": pipeline.progress,
        "stages": pipeline.stages,
        "startedAt": pipeline.started_at.isoformat(),
        "completedAt": None,
        "errorMessage": None,
    }
