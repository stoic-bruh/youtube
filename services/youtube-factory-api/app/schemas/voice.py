"""Pydantic schemas for the Voice Engine — request, response, and internal types."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class VoiceStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class VoiceProviderName(str, Enum):
    OPENAI_TTS = "openai-tts"
    ELEVENLABS = "elevenlabs"


# ── Sub-models ────────────────────────────────────────────────────────────────

class SectionAudio(BaseModel):
    """Generated narration audio for a single script section."""

    section_index: int
    section_title: str
    text: str
    start_ms: int
    end_ms: int
    duration_ms: int
    word_count: int = 0
    local_path: str
    sample_rate: int = 44100


# ── Provider-level result ─────────────────────────────────────────────────────

class VoiceProviderResult(BaseModel):
    """Full structured output from a single voice-generation provider."""

    provider_name: str
    sections: list[SectionAudio] = Field(default_factory=list)
    total_duration_ms: int = 0
    sample_rate: int = 44100
    audio_format: str = "mp3"
    cost_usd: float = 0.0
    confidence: float = 0.8
    error: str | None = None
    duration_ms: int = 0  # provider fetch latency


# ── Request ───────────────────────────────────────────────────────────────────

class VoiceRequest(BaseModel):
    """Input schema for starting a voice-generation job."""

    script_id: str = Field(..., description="Script to synthesise narration for")
    voice_id: str = Field(default="alloy", min_length=1, max_length=100)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str = Field(default="en", min_length=2, max_length=10)
    target_loudness_lufs: float = Field(default=-14.0, ge=-30.0, le=-6.0)
    providers: list[VoiceProviderName] = Field(
        default=[VoiceProviderName.OPENAI_TTS, VoiceProviderName.ELEVENLABS],
        min_length=1,
        max_length=2,
        description="Voice providers to try, in fallback order",
    )

    @field_validator("script_id")
    @classmethod
    def clean_script_id(cls, v: str) -> str:
        return v.strip()


# ── Full result (API response) ────────────────────────────────────────────────

class VoiceResultSchema(BaseModel):
    """Full voice result returned by the API."""

    id: str
    script_id: str
    status: VoiceStatus = VoiceStatus.PENDING
    voice_id: str = "alloy"
    speed: float = 1.0
    language: str = "en"
    sections: list[dict[str, Any]] = Field(default_factory=list)
    total_duration_ms: int | None = None
    word_count: int | None = None
    sample_rate: int | None = None
    audio_format: str | None = None
    normalized: bool = False
    target_loudness_lufs: float = -14.0
    cost_usd: float | None = None
    used_provider: str | None = None
    providers: list[str] = Field(default_factory=list)
    job_id: str | None = None
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
