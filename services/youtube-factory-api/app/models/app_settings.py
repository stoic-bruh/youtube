"""Application settings ORM model (singleton row)."""
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    youtube_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    openai_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4o")
    image_provider: Mapped[str] = mapped_column(String(100), nullable=False, default="dall-e-3")
    voice_provider: Mapped[str] = mapped_column(String(100), nullable=False, default="openai-tts")
    default_video_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="1080p")
    notifications_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
