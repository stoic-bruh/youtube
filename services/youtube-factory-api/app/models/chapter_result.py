"""SQLAlchemy ORM model for the Chapter Engine (Post-Processing)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChapterResult(Base):
    """
    Chapter — derives YouTube chapters purely from structured pipeline data
    (Timeline scenes, Script section titles, Voice section timestamps); no
    media analysis is required since the render plan already carries exact,
    real timing for every scene.
    """
    __tablename__ = "chapter_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    render_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    chapters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    youtube_export: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ChapterResult id={self.id!r} render_id={self.render_id!r} status={self.status!r}>"
