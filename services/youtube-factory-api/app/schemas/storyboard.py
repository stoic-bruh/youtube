"""Pydantic schemas for the Storyboard / Scene Planner Service."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class StoryboardStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class ShotType(str, Enum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    OVER_THE_SHOULDER = "over_the_shoulder"
    POINT_OF_VIEW = "point_of_view"
    AERIAL = "aerial"
    ESTABLISHING = "establishing"
    INSERT = "insert"
    CUTAWAY = "cutaway"


class CameraMovement(str, Enum):
    STATIC = "static"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    DOLLY_IN = "dolly_in"
    DOLLY_OUT = "dolly_out"
    TRACKING = "tracking"
    HANDHELD = "handheld"
    CRANE_UP = "crane_up"
    CRANE_DOWN = "crane_down"


class TransitionType(str, Enum):
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    ZOOM_TRANSITION = "zoom_transition"
    MORPH = "morph"
    FLASH = "flash"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"


class LightingStyle(str, Enum):
    NATURAL = "natural"
    STUDIO = "studio"
    CINEMATIC = "cinematic"
    DRAMATIC = "dramatic"
    SOFT = "soft"
    HARSH = "harsh"
    GOLDEN_HOUR = "golden_hour"
    BLUE_HOUR = "blue_hour"
    NEON = "neon"
    LOW_KEY = "low_key"
    HIGH_KEY = "high_key"


class VisualPacing(str, Enum):
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    VERY_FAST = "very_fast"


class NarrationPacing(str, Enum):
    DELIBERATE = "deliberate"    # < 110 wpm
    CONVERSATIONAL = "conversational"  # 120–140 wpm
    ENERGETIC = "energetic"      # 140–160 wpm
    RAPID = "rapid"              # > 160 wpm


class VisualType(str, Enum):
    B_ROLL = "b_roll"
    TALKING_HEAD = "talking_head"
    ANIMATION = "animation"
    TEXT_OVERLAY = "text_overlay"
    SCREEN_RECORDING = "screen_recording"
    STOCK_FOOTAGE = "stock_footage"
    ILLUSTRATION = "illustration"
    INFOGRAPHIC = "infographic"


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO_CLIP = "video_clip"
    SOUND_EFFECT = "sound_effect"
    MUSIC_TRACK = "music_track"
    ICON = "icon"
    FONT = "font"
    LOGO = "logo"
    LOWER_THIRD = "lower_third"


class StoryboardProviderName(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENROUTER = "openrouter"


# ── Sub-models ────────────────────────────────────────────────────────────────

class SubtitleTiming(BaseModel):
    """Subtitle/caption timing for a scene segment."""
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None


class SceneAsset(BaseModel):
    """A production asset required for a scene."""
    asset_type: AssetType
    description: str
    is_required: bool = True
    source_type: str = "generate"   # generate | stock | record | existing
    search_query: str | None = None


class ScenePrompt(BaseModel):
    """AI generation prompts for a scene."""
    image_prompt: str
    negative_prompt: str = ""
    video_prompt: str = ""          # Veo / Runway / Sora forward-compatible
    style_preset: str = "cinematic"


class AnimationInstruction(BaseModel):
    """Animation or motion graphic instruction for a scene."""
    element: str                    # what to animate
    animation_type: str             # fade_in | slide_in | scale | typewriter | etc.
    duration_ms: int = 500
    delay_ms: int = 0
    easing: str = "ease_in_out"


class Scene(BaseModel):
    """Complete production-ready scene specification."""

    # Identity & timing
    scene_number: int
    scene_title: str
    start_time_ms: int
    end_time_ms: int
    duration_ms: int

    # Content
    narration: str
    visual_description: str
    visual_type: VisualType = VisualType.B_ROLL

    # Prompts
    prompts: ScenePrompt

    # Camera
    shot_type: ShotType = ShotType.MEDIUM
    camera_angle: str = "eye_level"     # eye_level | high_angle | low_angle | dutch | overhead
    camera_movement: CameraMovement = CameraMovement.STATIC
    zoom_instructions: str | None = None
    pan_instructions: str | None = None

    # Animation
    animation_suggestions: list[AnimationInstruction] = Field(default_factory=list)

    # Transition (to next scene)
    transition_type: TransitionType = TransitionType.CUT
    transition_duration_ms: int = 500

    # Mood & aesthetics
    scene_emotion: str = "neutral"      # e.g. excited, pensive, dramatic, hopeful
    color_palette: list[str] = Field(default_factory=list)   # hex codes
    lighting_style: LightingStyle = LightingStyle.CINEMATIC
    background_description: str = ""
    foreground_description: str = ""

    # Elements
    characters: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)

    # Text & subtitles
    text_overlay_suggestions: list[str] = Field(default_factory=list)
    subtitle_timing: SubtitleTiming | None = None

    # Audio
    sound_effect_suggestions: list[str] = Field(default_factory=list)
    background_music_mood: str = ""

    # Supplementary footage
    b_roll_suggestions: list[str] = Field(default_factory=list)
    stock_footage_suggestions: list[str] = Field(default_factory=list)

    # Production
    asset_requirements: list[SceneAsset] = Field(default_factory=list)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    estimated_image_count: int = 1
    estimated_video_length_seconds: float = 5.0


class SceneTimeline(BaseModel):
    """Compact timeline entry for the production overview."""
    scene_number: int
    scene_title: str
    start_time_ms: int
    end_time_ms: int
    duration_ms: int
    shot_type: ShotType
    transition_type: TransitionType
    visual_type: VisualType
    importance_score: float


class NarrationTiming(BaseModel):
    """Narration timing entry mapped to a scene."""
    scene_number: int
    scene_title: str
    start_ms: int
    end_ms: int
    wpm: float
    word_count: int
    speaker_note: str | None = None


class VisualCue(BaseModel):
    """Production cue tied to a point in the timeline."""
    time_ms: int
    cue_type: str   # cut | effect | graphic | subtitle | music_change | sfx
    description: str
    scene_number: int
    duration_ms: int = 0


class StoryboardProviderResult(BaseModel):
    """Full structured output from a single storyboard-generation provider."""
    provider_name: str
    topic: str
    title: str = ""
    scenes: list[Scene] = Field(default_factory=list)
    scene_timeline: list[SceneTimeline] = Field(default_factory=list)
    narration_timing: list[NarrationTiming] = Field(default_factory=list)
    visual_cues: list[VisualCue] = Field(default_factory=list)
    total_duration_seconds: int = 0
    scene_count: int = 0
    image_count: int = 0
    editing_complexity_score: float = 0.5
    estimated_render_time_minutes: int = 5
    estimated_cost_usd: float = 0.0
    visual_pacing: VisualPacing = VisualPacing.MEDIUM
    narration_pacing: NarrationPacing = NarrationPacing.CONVERSATIONAL
    confidence: float = 0.8
    error: str | None = None
    duration_ms: int = 0


# ── Request ───────────────────────────────────────────────────────────────────

class StoryboardRequest(BaseModel):
    """Input schema for starting a storyboard-generation job."""
    script_id: str | None = None
    research_id: str | None = None
    topic: str = Field(..., min_length=3, max_length=500)
    # Script context (can be provided directly if script_id not given)
    script_sections: list[dict[str, Any]] = Field(default_factory=list)
    script_style: str = "educational"
    script_tone: str = "engaging"
    target_duration_minutes: int = Field(default=10, ge=1, le=120)
    target_audience: str = Field(default="general audience")
    language: str = Field(default="en", min_length=2, max_length=10)
    providers: list[StoryboardProviderName] = Field(
        default=[StoryboardProviderName.OPENAI, StoryboardProviderName.CLAUDE],
        min_length=1,
        max_length=4,
    )


# ── Full result (API response) ────────────────────────────────────────────────

class StoryboardResultSchema(BaseModel):
    """Full storyboard result returned by the API."""
    id: str
    script_id: str | None = None
    research_id: str | None = None
    topic: str
    title: str | None = None
    status: StoryboardStatus = StoryboardStatus.PENDING
    script_style: str = "educational"
    script_tone: str = "engaging"
    target_duration_minutes: int = 10
    target_audience: str = "general audience"
    language: str = "en"
    version: int = 1
    # Content
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    scene_timeline: list[dict[str, Any]] = Field(default_factory=list)
    narration_timing: list[dict[str, Any]] = Field(default_factory=list)
    visual_cues: list[dict[str, Any]] = Field(default_factory=list)
    # Metrics
    total_duration_seconds: int | None = None
    scene_count: int | None = None
    image_count: int | None = None
    editing_complexity_score: float | None = None
    estimated_render_time_minutes: int | None = None
    estimated_cost_usd: float | None = None
    visual_pacing: str | None = None
    narration_pacing: str | None = None
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
