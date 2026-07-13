"""SQLAlchemy ORM model for voice (narration) results."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VoiceResult(Base):
    __tablename__ = "voice_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False, default="alloy")
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # Structured JSON fields
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Metrics
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    normalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_loudness_lufs: Mapped[float] = mapped_column(Float, nullable=False, default=-14.0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Pipeline
    used_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<VoiceResult id={self.id!r} script_id={self.script_id!r} status={self.status!r}>"
