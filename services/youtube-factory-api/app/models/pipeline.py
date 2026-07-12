"""Pipeline ORM models."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PipelineStage:
    """Value object representing a single pipeline stage."""
    name: str
    status: str  # pending | running | completed | failed | skipped
    order: int
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "order": self.order,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "durationMs": self.duration_ms,
            "error": self.error,
        }


PIPELINE_STAGE_NAMES = [
    "research",
    "script",
    "scene_planning",
    "image_generation",
    "voice_generation",
    "video_editing",
    "subtitle_generation",
    "thumbnail_generation",
    "seo_generation",
    "upload",
]


def default_stages() -> list[dict]:
    return [
        PipelineStage(name=name, status="pending", order=i).to_dict()
        for i, name in enumerate(PIPELINE_STAGE_NAMES)
    ]


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        # enum: queued | running | completed | failed | cancelled
    )
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stages: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=default_stages)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id!r} project_id={self.project_id!r} status={self.status!r}>"
