"""Pydantic schemas for the Media Timeline Engine."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enumerations ───────────────────────────────────────────────────────────────

class TimelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrackKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    OVERLAY = "overlay"


class TransitionType(str, Enum):
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE = "wipe"
    ZOOM = "zoom"


class MarkerType(str, Enum):
    CHAPTER = "chapter"
    BEAT = "beat"
    NOTE = "note"


class RenderFormat(str, Enum):
    MP4 = "mp4"
    WEBM = "webm"


# ── Sub-schemas ────────────────────────────────────────────────────────────────

class TimelineClip(BaseModel):
    """A single clip placed on a timeline track."""
    clip_id: str
    track_id: str
    scene_id: str
    asset_id: str | None = None
    asset_kind: str = "image"
    start_ms: int
    end_ms: int
    duration_ms: int
    source_url: str | None = None
    local_path: str | None = None
    in_point_ms: int = 0
    out_point_ms: int | None = None
    volume: float = 1.0
    opacity: float = 1.0
    effects: list[dict[str, Any]] = Field(default_factory=list)


class TimelineTrack(BaseModel):
    """A named track (video, audio, subtitle, overlay) containing clips."""
    track_id: str
    kind: TrackKind
    order: int
    label: str
    clips: list[TimelineClip] = Field(default_factory=list)
    is_muted: bool = False
    is_locked: bool = False


class TimelineTransition(BaseModel):
    """Transition between two consecutive scenes."""
    from_scene_id: str
    to_scene_id: str
    transition_type: TransitionType = TransitionType.CUT
    duration_ms: int = 0


class TimelineScene(BaseModel):
    """Scene-level timeline entry (maps to storyboard scene)."""
    scene_id: str
    scene_number: int
    title: str
    start_ms: int
    end_ms: int
    duration_ms: int
    has_video_asset: bool = False
    has_audio_placeholder: bool = False
    asset_ids: list[str] = Field(default_factory=list)
    transition_in: TransitionType = TransitionType.CUT
    transition_out: TransitionType = TransitionType.CUT
    narration: str | None = None
    visual_description: str | None = None


class TimelineMarker(BaseModel):
    """Named marker (chapter, beat, note) at a specific timestamp."""
    marker_id: str
    label: str
    timestamp_ms: int
    marker_type: MarkerType = MarkerType.CHAPTER
    color: str | None = None


class TimelineRenderPlan(BaseModel):
    """Render configuration for the final video."""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    format: RenderFormat = RenderFormat.MP4
    codec: str = "h264"
    audio_codec: str = "aac"
    bitrate_kbps: int = 8000
    estimated_render_time_ms: int | None = None


class TimelineMetadata(BaseModel):
    """Computed statistics about the timeline."""
    total_duration_ms: int = 0
    total_scenes: int = 0
    video_clip_count: int = 0
    audio_clip_count: int = 0
    has_gaps: bool = False
    gap_count: int = 0
    transition_count: int = 0
    estimated_file_size_bytes: int | None = None
    asset_coverage_pct: float = 0.0


# ── Request schemas ────────────────────────────────────────────────────────────

class TimelineRequest(BaseModel):
    """Request to build a timeline from a storyboard."""
    storyboard_id: str
    script_id: str | None = None
    render_format: RenderFormat = RenderFormat.MP4
    fps: int = Field(default=30, ge=24, le=60)
    width: int = Field(default=1920)
    height: int = Field(default=1080)


# ── Result schemas ─────────────────────────────────────────────────────────────

class TimelineResultSchema(BaseModel):
    """Full timeline record returned by the API."""
    id: str
    storyboard_id: str
    script_id: str | None = None
    topic: str
    title: str | None = None
    status: TimelineStatus = TimelineStatus.PENDING
    total_duration_ms: int | None = None
    total_scenes: int | None = None
    tracks: list[TimelineTrack] = Field(default_factory=list)
    scenes: list[TimelineScene] = Field(default_factory=list)
    markers: list[TimelineMarker] = Field(default_factory=list)
    render_plan: TimelineRenderPlan | None = None
    metadata: TimelineMetadata | None = None
    validation_errors: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TimelineList(BaseModel):
    """Paginated list of timelines."""
    items: list[TimelineResultSchema]
    total: int
