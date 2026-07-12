"""Job management endpoints."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.job_repository import JobRepository

router = APIRouter()


def job_to_dict(j) -> dict:
    return {
        "id": j.id,
        "type": j.type,
        "status": j.status,
        "projectId": j.project_id,
        "pipelineId": j.pipeline_id,
        "payload": j.payload or {},
        "result": j.result,
        "error": j.error,
        "retryCount": j.retry_count,
        "maxRetries": j.max_retries,
        "createdAt": j.created_at.isoformat(),
        "startedAt": j.started_at.isoformat() if j.started_at else None,
        "completedAt": j.completed_at.isoformat() if j.completed_at else None,
    }


@router.get("")
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    repo = JobRepository(db)
    filters = {}
    if status:
        filters["status"] = status
    if type:
        filters["type"] = type
    rows, total = await repo.list(limit=limit, **filters)
    return {"items": [job_to_dict(j) for j in rows], "total": total}


@router.get("/{id}")
async def get_job(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = JobRepository(db)
    job = await repo.get(id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job_to_dict(job)


@router.post("/{id}/retry", status_code=202)
async def retry_job(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = JobRepository(db)
    job = await repo.update(
        id, status="retrying", error=None, started_at=None, completed_at=None
    )
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job_to_dict(job)


@router.post("/{id}/cancel")
async def cancel_job(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = JobRepository(db)
    job = await repo.update(
        id, status="cancelled", completed_at=datetime.now(timezone.utc)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job_to_dict(job)
