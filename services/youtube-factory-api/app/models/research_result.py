"""SQLAlchemy ORM model for research results."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchResult(Base):
    __tablename__ = "research_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    topic_normalized: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # for cache lookup
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_length_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="educational")
    tone: Mapped[str] = mapped_column(String(50), nullable=False, default="engaging")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
        # enum: pending | running | completed | failed | cached
    )
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    references: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    used_providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ResearchResult id={self.id!r} topic={self.topic!r} status={self.status!r}>"
