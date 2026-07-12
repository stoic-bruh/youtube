"""SQLAlchemy ORM model for script results."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScriptResult(Base):
    __tablename__ = "script_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="educational")
    tone: Mapped[str] = mapped_column(String(50), nullable=False, default="engaging")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Core content
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    outro: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured JSON fields
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    narration_timing: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    emphasis_markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    pauses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    pronunciation_hints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visual_cues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    versions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Metrics
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reading_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pacing_wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
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
        return f"<ScriptResult id={self.id!r} topic={self.topic!r} status={self.status!r}>"
