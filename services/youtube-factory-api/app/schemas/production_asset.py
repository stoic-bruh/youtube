"""Pydantic schemas for the Production Asset bundle (Post-Processing)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProductionAssetStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"


class ProductionAssetResultSchema(BaseModel):
    id: str
    render_id: str
    status: ProductionAssetStatus = ProductionAssetStatus.PENDING
    subtitle_id: str | None = None
    thumbnail_id: str | None = None
    chapter_id: str | None = None
    subtitle: dict[str, Any] | None = None
    thumbnail: dict[str, Any] | None = None
    chapter: dict[str, Any] | None = None
    export_manifest: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
