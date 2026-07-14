"""SQLAlchemy ORM model for the Thumbnail Engine (Post-Processing)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ThumbnailResult(Base):
    """
    Thumbnail — extracts real candidate frames from a completed RenderResult's
    output video via FFmpeg, scores them (sharpness/quality/brightness) with
    Pillow, and selects the best candidates.
    """
    __tablename__ = "thumbnail_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    render_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    candidates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    selected_candidate_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    templates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    title_overlay: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    brand_colors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ThumbnailResult id={self.id!r} render_id={self.render_id!r} status={self.status!r}>"
