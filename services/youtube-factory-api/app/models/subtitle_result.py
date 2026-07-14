"""SQLAlchemy ORM model for the Subtitle Engine (Post-Processing)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubtitleResult(Base):
    """
    Subtitle — transcribes a completed RenderResult's audio track (Whisper),
    falling back to known-correct narration script text mapped onto real Voice
    section timestamps when the audio contains no detectable speech. Produces
    word/sentence/paragraph timestamps plus SRT/VTT/ASS export files.
    """
    __tablename__ = "subtitle_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    render_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    used_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    providers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    words: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sentences: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    paragraphs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    srt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    vtt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    ass_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    srt_path: Mapped[str | None] = mapped_column(String, nullable=True)
    vtt_path: Mapped[str | None] = mapped_column(String, nullable=True)
    ass_path: Mapped[str | None] = mapped_column(String, nullable=True)

    burned_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    animated_caption_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    karaoke_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    style: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    caption_presets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    speaker_metadata: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SubtitleResult id={self.id!r} render_id={self.render_id!r} status={self.status!r}>"
