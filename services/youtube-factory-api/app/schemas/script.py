"""Pydantic schemas for the Script Service — request, response, and internal types."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class ScriptStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class ScriptStyle(str, Enum):
    EDUCATIONAL = "educational"
    DOCUMENTARY = "documentary"
    STORYTELLING = "storytelling"
    TUTORIAL = "tutorial"
    NEWS = "news"
    LONG_FORM = "long_form"
    SHORTS = "shorts"


class ScriptTone(str, Enum):
    ENGAGING = "engaging"
    AUTHORITATIVE = "authoritative"
    CASUAL = "casual"
    INSPIRATIONAL = "inspirational"
    CONVERSATIONAL = "conversational"


class ScriptSectionType(str, Enum):
    HOOK = "hook"
    INTRODUCTION = "introduction"
    MAIN_POINT = "main_point"
    TRANSITION = "transition"
    EXAMPLE = "example"
    ANALOGY = "analogy"
    CALL_TO_ACTION = "call_to_action"
    OUTRO = "outro"


class ScriptProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENROUTER = "openrouter"


class EmphasisType(str, Enum):
    STRONG = "strong"
    ITALIC = "italic"
    PAUSE_BEFORE = "pause_before"
    RAISE_PITCH = "raise_pitch"


class PauseType(str, Enum):
    SHORT = "short"        # 0.3s
    MEDIUM = "medium"      # 0.7s
    LONG = "long"          # 1.5s
    DRAMATIC = "dramatic"  # 2.5s


class VisualCueType(str, Enum):
    B_ROLL = "b_roll"
    GRAPHIC = "graphic"
    TITLE_CARD = "title_card"
    ZOOM = "zoom"
    CUT = "cut"
    LOWER_THIRD = "lower_third"


# ── Sub-models ────────────────────────────────────────────────────────────────

class ScriptSection(BaseModel):
    """A single structured section of the script."""

    section_type: ScriptSectionType
    title: str
    content: str                            # full narration text for this section
    word_count: int = 0
    duration_seconds: float = 0.0
    order: int = 0
    transition_in: str | None = None        # bridging sentence from previous section
    transition_out: str | None = None       # bridging sentence to next section
    storytelling_notes: str | None = None   # director / talent notes
    visual_suggestion: str | None = None    # suggested visual treatment


class NarrationTiming(BaseModel):
    """Precise start/end timing for a script section."""

    section_title: str
    start_ms: int
    end_ms: int
    wpm: float
    word_count: int = 0


class EmphasisMarker(BaseModel):
    """A word or phrase that should be emphasised during narration."""

    text: str
    position: int                           # character offset in full script text
    section_index: int = 0                  # which section this belongs to
    emphasis_type: EmphasisType


class PauseMarker(BaseModel):
    """A strategic pause inserted at a specific position in the script."""

    position: int                           # character offset in full script text
    duration_ms: int
    pause_type: PauseType
    context: str                            # surrounding phrase for reference


class PronunciationHint(BaseModel):
    """Phonetic guidance for technical or unusual words."""

    word: str
    phonetic: str
    note: str | None = None


class VisualCue(BaseModel):
    """A production instruction tied to a point in narration time."""

    time_ms: int
    description: str
    cue_type: VisualCueType
    duration_ms: int = 3000


class ScriptVersionEntry(BaseModel):
    """Snapshot of a previous script version kept for history."""

    version: int
    created_at: str
    word_count: int
    style: str
    hook: str | None = None
    summary: str | None = None              # one-line summary of the version


# ── Provider-level result ─────────────────────────────────────────────────────

class ScriptProviderResult(BaseModel):
    """Full structured output from a single script-generation provider."""

    provider_name: str
    topic: str
    title: str = ""
    hook: str = ""
    introduction: str = ""
    outro: str = ""
    call_to_action: str = ""
    sections: list[ScriptSection] = Field(default_factory=list)
    narration_timing: list[NarrationTiming] = Field(default_factory=list)
    emphasis_markers: list[EmphasisMarker] = Field(default_factory=list)
    pauses: list[PauseMarker] = Field(default_factory=list)
    pronunciation_hints: list[PronunciationHint] = Field(default_factory=list)
    visual_cues: list[VisualCue] = Field(default_factory=list)
    word_count: int = 0
    estimated_duration_seconds: int = 0
    reading_time_seconds: int = 0
    scene_count: int = 0
    pacing_wpm: float = 130.0
    confidence: float = 0.8
    error: str | None = None
    duration_ms: int = 0


# ── Request ───────────────────────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    """Input schema for starting a script-generation job."""

    research_id: str | None = None
    topic: str = Field(..., min_length=3, max_length=500, description="Video topic")
    style: ScriptStyle = ScriptStyle.EDUCATIONAL
    tone: ScriptTone = ScriptTone.ENGAGING
    language: str = Field(default="en", min_length=2, max_length=10)
    target_audience: str = Field(default="general audience")
    target_duration_minutes: int = Field(default=10, ge=1, le=120)
    providers: list[ScriptProviderName] = Field(
        default=[ScriptProviderName.OPENAI, ScriptProviderName.CLAUDE],
        min_length=1,
        max_length=4,
        description="Script providers to use",
    )

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, v: str) -> str:
        return v.strip()


# ── Full result (API response) ────────────────────────────────────────────────

class ScriptResultSchema(BaseModel):
    """Full script result returned by the API."""

    id: str
    research_id: str | None = None
    topic: str
    title: str | None = None
    status: ScriptStatus = ScriptStatus.PENDING
    style: str = "educational"
    tone: str = "engaging"
    language: str = "en"
    target_audience: str = "general audience"
    target_duration_minutes: int = 10
    version: int = 1
    # Core content
    hook: str | None = None
    introduction: str | None = None
    outro: str | None = None
    call_to_action: str | None = None
    sections: list[ScriptSection] = Field(default_factory=list)
    # Metrics
    word_count: int | None = None
    estimated_duration_seconds: int | None = None
    reading_time_seconds: int | None = None
    scene_count: int | None = None
    pacing_wpm: float | None = None
    # Production metadata
    narration_timing: list[dict[str, Any]] = Field(default_factory=list)
    emphasis_markers: list[dict[str, Any]] = Field(default_factory=list)
    pauses: list[dict[str, Any]] = Field(default_factory=list)
    pronunciation_hints: list[dict[str, Any]] = Field(default_factory=list)
    visual_cues: list[dict[str, Any]] = Field(default_factory=list)
    versions: list[dict[str, Any]] = Field(default_factory=list)
    # Pipeline
    providers: list[str] = Field(default_factory=list)
    used_providers: list[str] = Field(default_factory=list)
    job_id: str | None = None
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
