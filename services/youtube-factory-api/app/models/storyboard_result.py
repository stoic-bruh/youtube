"""SQLAlchemy ORM model for storyboard results."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoryboardResult(Base):
    __tablename__ = "storyboard_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    research_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # Input parameters
    script_style: Mapped[str] = mapped_column(String(50), nullable=False, default="educational")
    script_tone: Mapped[str] = mapped_column(String(50), nullable=False, default="engaging")
    target_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Core content — JSON arrays
    scenes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scene_timeline: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    narration_timing: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visual_cues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Production metrics
    total_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    editing_complexity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_render_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_pacing: Mapped[str | None] = mapped_column(String(20), nullable=True)
    narration_pacing: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Pipeline
    providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    used_providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<StoryboardResult id={self.id!r} topic={self.topic!r} status={self.status!r}>"
