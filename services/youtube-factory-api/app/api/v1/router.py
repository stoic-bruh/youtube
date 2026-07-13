"""API v1 router — aggregates all endpoint routers."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    projects,
    pipelines,
    jobs,
    analytics,
    logs,
    settings,
    research,
    script,
    storyboard,
    voice,
)

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(script.router, tags=["scripts"])
router.include_router(storyboard.router, tags=["storyboards"])
router.include_router(voice.router, tags=["voices"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(logs.router, prefix="/logs", tags=["logs"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])

from app.api.v1.endpoints import assets  # noqa: E402
router.include_router(assets.router, tags=["assets"])

from app.api.v1.endpoints import timelines  # noqa: E402
router.include_router(timelines.router, tags=["timelines"])
