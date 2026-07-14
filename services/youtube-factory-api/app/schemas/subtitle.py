"""Pydantic schemas for the Subtitle Engine (Post-Processing)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SubtitleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubtitleProviderName(str, Enum):
    WHISPER = "whisper"
    SCRIPT_NARRATION = "script-narration"


class SubtitleWord(BaseModel):
    word: str
    start_ms: int
    end_ms: int
    confidence: float = 0.0
    speaker: str | None = None


class SubtitleSentence(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    confidence: float = 0.0
    speaker: str | None = None


class SubtitleParagraph(BaseModel):
    text: str
    start_ms: int
    end_ms: int


class SubtitleProviderResult(BaseModel):
    """Full structured output from a single transcription provider."""

    provider_name: str
    words: list[SubtitleWord] = Field(default_factory=list)
    sentences: list[SubtitleSentence] = Field(default_factory=list)
    paragraphs: list[SubtitleParagraph] = Field(default_factory=list)
    avg_confidence: float = 0.0
    duration_ms: int = 0
    error: str | None = None


class SubtitleRequest(BaseModel):
    render_id: str = Field(..., description="Completed render to transcribe")
    language: str = Field(default="en", min_length=2, max_length=10)
    providers: list[SubtitleProviderName] = Field(
        default=[SubtitleProviderName.WHISPER, SubtitleProviderName.SCRIPT_NARRATION],
        min_length=1,
        description="Subtitle providers to try, in fallback order",
    )


class SubtitleResultSchema(BaseModel):
    id: str
    render_id: str
    status: SubtitleStatus = SubtitleStatus.PENDING
    language: str = "en"
    used_provider: str | None = None
    providers: list[str] = Field(default_factory=list)
    words: list[dict[str, Any]] = Field(default_factory=list)
    sentences: list[dict[str, Any]] = Field(default_factory=list)
    paragraphs: list[dict[str, Any]] = Field(default_factory=list)
    srt_content: str | None = None
    vtt_content: str | None = None
    ass_content: str | None = None
    srt_path: str | None = None
    vtt_path: str | None = None
    ass_path: str | None = None
    burned_metadata: dict[str, Any] = Field(default_factory=dict)
    animated_caption_metadata: dict[str, Any] = Field(default_factory=dict)
    karaoke_metadata: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    caption_presets: list[dict[str, Any]] = Field(default_factory=list)
    speaker_metadata: list[dict[str, Any]] = Field(default_factory=list)
    avg_confidence: float | None = None
    word_count: int | None = None
    duration_ms: int | None = None
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
