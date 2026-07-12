"""Analytics and dashboard endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.pipeline import Pipeline
from app.models.job import Job

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    project_status_rows = (
        await db.execute(
            select(Project.status, func.count(Project.id).label("count")).group_by(Project.status)
        )
    ).all()

    job_status_rows = (
        await db.execute(
            select(Job.status, func.count(Job.id).label("count")).group_by(Job.status)
        )
    ).all()

    projects_by_status = [{"status": r[0], "count": r[1]} for r in project_status_rows]
    jobs_by_status = {r[0]: r[1] for r in job_status_rows}

    total_projects = sum(r["count"] for r in projects_by_status)
    total_videos = next((r["count"] for r in projects_by_status if r["status"] == "completed"), 0)
    active_jobs = jobs_by_status.get("running", 0)
    queued_jobs = jobs_by_status.get("pending", 0)
    failed_jobs = jobs_by_status.get("failed", 0)
    completed_jobs = jobs_by_status.get("completed", 0)
    total_processed = completed_jobs + failed_jobs
    success_rate = round((completed_jobs / total_processed * 100), 1) if total_processed > 0 else 0

    recent_projects = (
        await db.execute(
            select(Project).order_by(Project.updated_at.desc()).limit(10)
        )
    ).scalars().all()

    recent_activity = [
        {
            "id": p.id,
            "type": "project",
            "message": f'Project "{p.title}" — {p.status}',
            "projectId": p.id,
            "status": p.status,
            "timestamp": p.updated_at.isoformat(),
        }
        for p in recent_projects
    ]

    return {
        "totalProjects": total_projects,
        "totalVideos": total_videos,
        "activeJobs": active_jobs,
        "queuedJobs": queued_jobs,
        "failedJobs": failed_jobs,
        "successRate": success_rate,
        "totalRuntime": 0,
        "projectsByStatus": projects_by_status,
        "recentActivity": recent_activity,
    }


@router.get("/pipeline-activity")
async def get_pipeline_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, le=100),
) -> dict:
    pipelines = (
        await db.execute(select(Pipeline).order_by(Pipeline.started_at.desc()).limit(limit))
    ).scalars().all()

    items = [
        {
            "id": p.id,
            "type": "pipeline",
            "message": f"Pipeline {p.status}" + (f" — stage: {p.current_stage}" if p.current_stage else ""),
            "projectId": p.project_id,
            "status": p.status,
            "timestamp": p.started_at.isoformat(),
        }
        for p in pipelines
    ]
    return {"items": items}


@router.get("/stage-breakdown")
async def get_stage_breakdown(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    stage_names = [
        "research", "script", "scene_planning", "image_generation",
        "voice_generation", "video_editing", "subtitle_generation",
        "thumbnail_generation", "seo_generation", "upload",
    ]
    return {
        "stages": [
            {"name": name, "completed": 0, "failed": 0, "avgDurationMs": 0}
            for name in stage_names
        ]
    }
