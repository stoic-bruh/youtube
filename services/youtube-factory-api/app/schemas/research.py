"""Pydantic schemas for the Research Service — request, response, and internal types."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class ResearchStyle(str, Enum):
    EDUCATIONAL = "educational"
    ENTERTAINING = "entertaining"
    DOCUMENTARY = "documentary"
    HOW_TO = "how-to"


class ResearchTone(str, Enum):
    ENGAGING = "engaging"
    AUTHORITATIVE = "authoritative"
    CASUAL = "casual"
    INSPIRATIONAL = "inspirational"


class SectionType(str, Enum):
    SUMMARY = "summary"
    CONCEPT = "concept"
    FACT = "fact"
    TIMELINE = "timeline"
    ENTITY = "entity"
    STATISTIC = "statistic"
    EXAMPLE = "example"
    ANALOGY = "analogy"
    MISCONCEPTION = "misconception"
    FAQ = "faq"


class SourceType(str, Enum):
    WEB = "web"
    WIKIPEDIA = "wikipedia"
    ACADEMIC = "academic"
    VIDEO = "video"
    BOOK = "book"
    NEWS = "news"
    SOCIAL = "social"


class ProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    PERPLEXITY = "perplexity"
    WIKIPEDIA = "wikipedia"
    DUCKDUCKGO = "duckduckgo"
    GOOGLE_SEARCH = "google_search"


# ── Request ───────────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    """Input schema for starting a research job."""

    topic: str = Field(..., min_length=3, max_length=500, description="YouTube video topic to research")
    target_audience: str = Field(default="general audience", description="Intended audience")
    video_length_minutes: int = Field(default=10, ge=1, le=120, description="Target video length")
    language: str = Field(default="en", min_length=2, max_length=10)
    style: ResearchStyle = Field(default=ResearchStyle.EDUCATIONAL)
    tone: ResearchTone = Field(default=ResearchTone.ENGAGING)
    providers: list[ProviderName] = Field(
        default=[ProviderName.OPENAI, ProviderName.WIKIPEDIA, ProviderName.DUCKDUCKGO],
        min_length=1,
        max_length=8,
        description="Providers to use for research",
    )

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, v: str) -> str:
        return v.strip()


# ── Sub-models ────────────────────────────────────────────────────────────────

class ResearchKeyword(BaseModel):
    """A keyword extracted from research with relevance metadata."""

    term: str
    relevance: float = Field(ge=0.0, le=1.0)
    search_volume: int | None = None
    difficulty: str | None = None  # low | medium | high
    semantic_tags: list[str] = Field(default_factory=list)


class ResearchReference(BaseModel):
    """A source reference with credibility scoring and citation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    url: str
    source_type: SourceType
    author: str | None = None
    published_at: str | None = None
    snippet: str | None = None
    credibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    citation_format: str = ""  # APA-formatted citation
    provider: str = ""


class ResearchSection(BaseModel):
    """A structured section of the research output."""

    section_type: SectionType
    title: str
    content: str = ""  # prose summary of this section
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    items: list[str] = Field(default_factory=list)  # bullet-point items
    source_ids: list[str] = Field(default_factory=list)  # reference IDs


# ── Provider-level types ──────────────────────────────────────────────────────

class ProviderResult(BaseModel):
    """Raw output from a single research provider."""

    provider_name: str
    topic: str
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    timeline_events: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    statistics: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    analogies: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    faqs: list[dict[str, str]] = Field(default_factory=list)  # [{q, a}]
    references: list[ResearchReference] = Field(default_factory=list)
    keywords: list[ResearchKeyword] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    error: str | None = None
    duration_ms: int = 0


# ── Full Research Result ──────────────────────────────────────────────────────

class ResearchResultSchema(BaseModel):
    """Full research result returned by the API."""

    id: str
    topic: str
    target_audience: str | None = None
    video_length_minutes: int = 10
    language: str = "en"
    style: str = "educational"
    tone: str = "engaging"
    status: ResearchStatus = ResearchStatus.PENDING
    job_id: str | None = None
    summary: str | None = None
    confidence_score: float | None = None
    estimated_difficulty: str | None = None  # beginner | intermediate | advanced
    sections: list[ResearchSection] = Field(default_factory=list)
    references: list[ResearchReference] = Field(default_factory=list)
    keywords: list[ResearchKeyword] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    used_providers: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
