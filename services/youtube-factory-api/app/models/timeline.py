"""SQLAlchemy ORM model for the Media Timeline Engine."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimelineResult(Base):
    """
    Media Timeline — merges Storyboard + Assets + Voice (placeholder)
    into one production timeline document.
    """
    __tablename__ = "timeline_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    storyboard_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    script_id: Mapped[str | None] = mapped_column(String, nullable=True)

    topic: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_scenes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSONB columns — timeline data
    tracks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scenes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    render_plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation_errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TimelineResult id={self.id!r} storyboard={self.storyboard_id!r} "
            f"status={self.status!r} scenes={self.total_scenes}>"
        )
