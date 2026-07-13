"""SQLAlchemy ORM model for the MoviePy Render Engine."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RenderResult(Base):
    """
    Render — merges Timeline + Voice + Assets into a final rendered video via
    the MoviePy/FFmpeg rendering pipeline (RenderPlan -> RenderOutput).
    """
    __tablename__ = "render_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timeline_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    voice_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Render configuration
    resolution: Mapped[str] = mapped_column(String(20), nullable=False, default="1080p")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1920)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    fps: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False, default="16:9")
    crop_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="safe_crop")  # safe_crop | letterbox | blur_pad
    hardware_acceleration: Mapped[bool] = mapped_column(JSON, nullable=False, default=False)

    # JSONB columns — the render document
    render_plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    render_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    render_stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    render_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    preview_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<RenderResult id={self.id!r} timeline={self.timeline_id!r} "
            f"status={self.status!r} resolution={self.resolution!r}>"
        )
