"""Pydantic schemas for the Asset Intelligence Engine."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enumerations ───────────────────────────────────────────────────────────────

class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    SVG = "svg"
    CHART = "chart"
    MAP = "map"
    ICON = "icon"


class AssetStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    CACHED = "cached"


class AssetLicense(str, Enum):
    PUBLIC_DOMAIN = "public_domain"
    CC0 = "cc0"
    CC_BY = "cc_by"
    CC_BY_SA = "cc_by_sa"
    COMMERCIAL = "commercial"
    GENERATED = "generated"
    MIT = "mit"
    UNKNOWN = "unknown"


class AssetProviderName(str, Enum):
    # AI image generation
    FLUX = "flux"
    SDXL = "sdxl"
    GPT_IMAGE = "gpt_image"
    GEMINI_IMAGE = "gemini_image"
    IDEOGRAM = "ideogram"
    # Stock image
    WIKIMEDIA = "wikimedia"
    UNSPLASH = "unsplash"
    PIXABAY = "pixabay"
    PEXELS = "pexels"
    # Stock video
    PEXELS_VIDEO = "pexels_video"
    PIXABAY_VIDEO = "pixabay_video"
    MIXKIT = "mixkit"
    # Icons / graphics
    LUCIDE = "lucide"
    HEROICONS = "heroicons"
    MATERIAL_ICONS = "material_icons"


# ── Request schemas ────────────────────────────────────────────────────────────

class AssetRequest(BaseModel):
    """Request to acquire assets for a storyboard."""
    storyboard_id: str
    scene_ids: list[str] = Field(default_factory=list, description="Empty = all scenes")
    asset_kinds: list[AssetKind] = Field(
        default_factory=lambda: [AssetKind.IMAGE],
        description="Which asset types to acquire",
    )
    providers: list[AssetProviderName] = Field(
        default_factory=lambda: [
            AssetProviderName.WIKIMEDIA,
            AssetProviderName.PEXELS,
            AssetProviderName.PIXABAY,
            AssetProviderName.FLUX,
        ],
        description="Ordered preference list: stock providers searched first, then generation",
    )
    force_generate: bool = Field(
        False,
        description="Skip stock search and go straight to AI generation",
    )


class SingleAssetRequest(BaseModel):
    """Request to acquire a single asset for one scene."""
    storyboard_id: str
    scene_id: str
    asset_kind: AssetKind = AssetKind.IMAGE
    prompt: str
    negative_prompt: str = ""
    search_query: str | None = None
    width: int = 1920
    height: int = 1080
    provider_preference: list[AssetProviderName] = Field(
        default_factory=lambda: [
            AssetProviderName.WIKIMEDIA,
            AssetProviderName.PEXELS,
            AssetProviderName.PIXABAY,
            AssetProviderName.FLUX,
        ],
    )
    force_generate: bool = False


# ── Result schemas ─────────────────────────────────────────────────────────────

class AssetResultSchema(BaseModel):
    """Full asset record returned by the API."""
    id: str
    storyboard_id: str
    scene_id: str

    asset_kind: AssetKind
    provider: AssetProviderName | None = None
    provider_asset_id: str | None = None

    source_url: str | None = None
    license: AssetLicense = AssetLicense.UNKNOWN

    prompt: str | None = None
    negative_prompt: str | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)

    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None

    status: AssetStatus = AssetStatus.PENDING
    cost_estimate_usd: float | None = None
    generation_time_ms: int | None = None

    file_size_bytes: int | None = None
    local_cache_path: str | None = None
    thumbnail_path: str | None = None

    tags: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    relevance_score: float | None = None

    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssetList(BaseModel):
    """Paginated list of assets."""
    items: list[AssetResultSchema]
    total: int


# ── Provider-level result (internal) ──────────────────────────────────────────

class AssetProviderResult(BaseModel):
    """Internal result returned by a single provider attempt."""
    provider_name: str
    found: bool = False
    asset_kind: AssetKind = AssetKind.IMAGE
    provider_asset_id: str | None = None
    source_url: str | None = None
    license: AssetLicense = AssetLicense.UNKNOWN
    prompt: str | None = None
    negative_prompt: str | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    cost_estimate_usd: float = 0.0
    generation_time_ms: int = 0
    file_size_bytes: int | None = None
    tags: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    relevance_score: float = 0.0
    error: str | None = None
