"""Pydantic schemas for the Chapter Engine (Post-Processing)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChapterStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ChapterEntry(BaseModel):
    title: str
    start_ms: int
    end_ms: int
    description: str | None = None


class ChapterRequest(BaseModel):
    render_id: str = Field(..., description="Completed render to derive chapters from")


class ChapterResultSchema(BaseModel):
    id: str
    render_id: str
    status: ChapterStatus = ChapterStatus.PENDING
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    youtube_export: str | None = None
    sources: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
