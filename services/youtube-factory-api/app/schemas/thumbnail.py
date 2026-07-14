"""Pydantic schemas for the Thumbnail Engine (Post-Processing)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ThumbnailStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ThumbnailCandidate(BaseModel):
    candidate_id: str
    timestamp_ms: int
    path: str
    width: int
    height: int
    sharpness_score: float
    quality_score: float
    brightness: float
    dominant_color: str | None = None
    # Placeholders — no face/object detection model is wired up yet; these
    # interfaces exist so a real detector can be dropped in later without
    # changing the ThumbnailResult contract.
    face_detected: bool | None = None
    objects_detected: list[str] = Field(default_factory=list)
    safe_text_regions: list[dict[str, Any]] = Field(default_factory=list)


class ThumbnailRequest(BaseModel):
    render_id: str = Field(..., description="Completed render to extract frames from")
    count: int = Field(default=3, ge=1, le=10)


class ThumbnailResultSchema(BaseModel):
    id: str
    render_id: str
    status: ThumbnailStatus = ThumbnailStatus.PENDING
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    title_overlay: dict[str, Any] = Field(default_factory=dict)
    brand_colors: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
