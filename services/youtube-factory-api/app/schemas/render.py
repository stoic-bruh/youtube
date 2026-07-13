"""Pydantic schemas for the Render Engine (MoviePy/FFmpeg) — request, response,
and the RenderPlan document shared by the Python service and the Node builder."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class RenderStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RenderResolution(str, Enum):
    HD720 = "720p"
    HD1080 = "1080p"
    UHD4K = "4k"  # placeholder — encodes at 1080p internally, tagged as 4k target


class RenderAspectRatio(str, Enum):
    WIDESCREEN = "16:9"
    VERTICAL = "9:16"
    SQUARE = "1:1"


class RenderCropMode(str, Enum):
    SAFE_CROP = "safe_crop"
    LETTERBOX = "letterbox"
    BLUR_PAD = "blur_pad"


class RenderTransitionType(str, Enum):
    CUT = "cut"
    CROSSFADE = "crossfade"
    FADE = "fade"


RESOLUTION_DIMENSIONS: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


# ── RenderPlan document (scenes / clips / tracks / transitions) ───────────────

class RenderTransition(BaseModel):
    type: RenderTransitionType = RenderTransitionType.CROSSFADE
    duration_ms: int = 500


class RenderClip(BaseModel):
    """A single visual clip within a scene — an image or video asset with a
    Ken Burns pan/zoom animation applied over its on-screen duration."""

    clip_id: str
    scene_index: int
    asset_id: str | None = None
    kind: str = "image"  # image | video | placeholder
    source_path: str | None = None
    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 0
    ken_burns: bool = True
    pan_direction: str = "right"  # left | right | up | down | none
    zoom_start: float = 1.0
    zoom_end: float = 1.08


class RenderScene(BaseModel):
    """A scene — narration text + timing + the clip(s) that cover it, plus the
    transition into the next scene."""

    scene_index: int
    title: str = ""
    narration: str = ""
    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 0
    clips: list[RenderClip] = Field(default_factory=list)
    transition_out: RenderTransition = Field(default_factory=RenderTransition)


class RenderAudioTrack(BaseModel):
    kind: str = "narration"  # narration | music | sfx
    source_path: str | None = None
    start_ms: int = 0
    end_ms: int = 0
    volume: float = 1.0


class RenderVideoTrack(BaseModel):
    kind: str = "main"  # main | overlay
    scene_indices: list[int] = Field(default_factory=list)


class RenderPlan(BaseModel):
    """Fully-resolved render document — everything the renderer backend needs
    to composite the final video, independent of any DB/ORM types."""

    timeline_id: str
    voice_id: str | None = None
    title: str = ""
    resolution: RenderResolution = RenderResolution.HD1080
    width: int = 1920
    height: int = 1080
    fps: int = 30
    aspect_ratio: RenderAspectRatio = RenderAspectRatio.WIDESCREEN
    crop_mode: RenderCropMode = RenderCropMode.SAFE_CROP
    hardware_acceleration: bool = False
    add_background_music: bool = False
    background_music_path: str | None = None
    music_volume: float = 0.12
    scenes: list[RenderScene] = Field(default_factory=list)
    video_tracks: list[RenderVideoTrack] = Field(default_factory=list)
    audio_tracks: list[RenderAudioTrack] = Field(default_factory=list)
    total_duration_ms: int = 0


# ── Output / metadata / stats ─────────────────────────────────────────────────

class RenderOutput(BaseModel):
    local_path: str | None = None
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: int = 0
    codec: str = "libx264"
    audio_codec: str = "aac"
    format: str = "mp4"


class RenderMetadata(BaseModel):
    scene_count: int = 0
    clip_count: int = 0
    placeholder_clip_count: int = 0
    has_narration: bool = False
    has_background_music: bool = False
    source_timeline_id: str = ""
    source_voice_id: str | None = None


class RenderStats(BaseModel):
    render_time_seconds: float = 0.0
    frames_encoded: int = 0
    encode_fps: float = 0.0
    realtime_factor: float = 0.0  # output_duration / render_time
    retries: int = 0


# ── Request ───────────────────────────────────────────────────────────────────

class RenderRequest(BaseModel):
    """Input schema for starting a render job."""

    timeline_id: str = Field(..., description="Timeline to render")
    voice_id: str | None = Field(default=None, description="Voice narration to synchronize; auto-detected if omitted")
    resolution: RenderResolution = RenderResolution.HD1080
    fps: int = Field(default=30, description="Frames per second: 24, 30, or 60")
    aspect_ratio: RenderAspectRatio = RenderAspectRatio.WIDESCREEN
    crop_mode: RenderCropMode = RenderCropMode.SAFE_CROP
    hardware_acceleration: bool = Field(default=False, description="Placeholder — hardware encode not yet wired")
    add_background_music: bool = False
    music_volume: float = Field(default=0.12, ge=0.0, le=1.0)
    generate_preview: bool = Field(default=True, description="Also render a short preview clip")


# ── Full result (API response) ────────────────────────────────────────────────

class RenderResultSchema(BaseModel):
    """Full render result returned by the API."""

    id: str
    timeline_id: str
    voice_id: str | None = None
    status: RenderStatus = RenderStatus.PENDING
    progress: int = 0
    resolution: str = "1080p"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    aspect_ratio: str = "16:9"
    crop_mode: str = "safe_crop"
    hardware_acceleration: bool = False
    render_plan: dict[str, Any] = Field(default_factory=dict)
    render_output: dict[str, Any] = Field(default_factory=dict)
    render_stats: dict[str, Any] = Field(default_factory=dict)
    render_metadata: dict[str, Any] = Field(default_factory=dict)
    preview_output: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RenderProviderStats(BaseModel):
    """Aggregate render-engine statistics (there is one backend — MoviePy —
    but the shape mirrors the other stages' provider-stats endpoints so the
    frontend statistics widgets are consistent)."""

    backend: str = "moviepy"
    total_renders: int = 0
    completed: int = 0
    failed: int = 0
    avg_render_time_seconds: float = 0.0
    avg_realtime_factor: float = 0.0
    total_output_seconds: float = 0.0
