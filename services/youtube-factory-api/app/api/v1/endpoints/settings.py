"""Application settings endpoints."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.app_settings import AppSettings

router = APIRouter()

SETTINGS_ID = "default"


class SettingsUpdateSchema(BaseModel):
    youtube_enabled: bool | None = None
    auto_upload: bool | None = None
    default_language: str | None = None
    max_concurrent_jobs: int | None = None
    openai_model: str | None = None
    image_provider: str | None = None
    voice_provider: str | None = None
    default_video_quality: str | None = None
    notifications_email: str | None = None
    webhook_url: str | None = None


def settings_to_dict(s: AppSettings) -> dict:
    return {
        "id": s.id,
        "youtubeEnabled": s.youtube_enabled,
        "autoUpload": s.auto_upload,
        "defaultLanguage": s.default_language,
        "maxConcurrentJobs": s.max_concurrent_jobs,
        "openaiModel": s.openai_model,
        "imageProvider": s.image_provider,
        "voiceProvider": s.voice_provider,
        "defaultVideoQuality": s.default_video_quality,
        "notificationsEmail": s.notifications_email,
        "webhookUrl": s.webhook_url,
        "updatedAt": s.updated_at.isoformat(),
    }


async def _get_or_create_settings(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == SETTINGS_ID))
    existing = result.scalar_one_or_none()
    if not existing:
        existing = AppSettings(id=SETTINGS_ID)
        db.add(existing)
        await db.flush()
        await db.refresh(existing)
    return existing


@router.get("")
async def get_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    settings = await _get_or_create_settings(db)
    return settings_to_dict(settings)


@router.patch("")
async def update_settings(
    body: SettingsUpdateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    settings = await _get_or_create_settings(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for k, v in updates.items():
        setattr(settings, k, v)
    settings.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(settings)
    return settings_to_dict(settings)
