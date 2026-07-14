"""SQLAlchemy ORM model for the Production Asset bundle (Post-Processing)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductionAsset(Base):
    """Aggregates Subtitle + Thumbnail + Chapter outputs for one RenderResult."""
    __tablename__ = "production_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    render_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # enum: pending | partial | completed

    subtitle_id: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_id: Mapped[str | None] = mapped_column(String, nullable=True)
    chapter_id: Mapped[str | None] = mapped_column(String, nullable=True)

    export_manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ProductionAsset id={self.id!r} render_id={self.render_id!r} status={self.status!r}>"
