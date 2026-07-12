"""VideoEditor — placeholder interface.

Responsible for:
- Compositing scenes into a final video using MoviePy
- Synchronizing audio narration with scene images
- Adding transitions, background music, and effects
- Rendering final output at target resolution/quality
"""
from dataclasses import dataclass, field
from pathlib import Path

from app.services.image_generator import GeneratedImage
from app.services.voice_generator import VoiceAudio
from app.services.scene_planner import ScenePlan


@dataclass
class VideoOutput:
    local_path: str
    duration_seconds: float
    width: int = 1920
    height: int = 1080
    fps: int = 30
    file_size_bytes: int = 0
    format: str = "mp4"
    codec: str = "h264"


@dataclass
class EditConfig:
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    transition_duration: float = 0.5
    transition_type: str = "crossfade"  # crossfade | cut | fade
    add_background_music: bool = False
    background_music_path: str = ""
    music_volume: float = 0.15
    ken_burns_effect: bool = True  # subtle zoom/pan on images


class VideoEditor:
    """Placeholder implementation — real MoviePy editing to be implemented."""

    async def compose_video(
        self,
        scene_plan: ScenePlan,
        images: list[GeneratedImage],
        narration: VoiceAudio,
        config: EditConfig | None = None,
    ) -> VideoOutput:
        """Compose a final video from scenes, images, and narration.

        Args:
            scene_plan: ScenePlan defining scene order and timing.
            images: List of GeneratedImage, one per scene.
            narration: Full narration VoiceAudio track.
            config: EditConfig with render settings.

        Returns:
            VideoOutput pointing to the rendered file.
        """
        # TODO: Implement using MoviePy:
        #   1. Load each image as ImageClip with scene.duration_seconds
        #   2. Apply Ken Burns effect (zoom/pan) if config.ken_burns_effect
        #   3. Concatenate clips with transitions
        #   4. Overlay narration audio
        #   5. Mix in background music at low volume if enabled
        #   6. Export with ffmpeg
        cfg = config or EditConfig()
        return VideoOutput(
            local_path="/tmp/output_video.mp4",
            duration_seconds=scene_plan.total_duration_seconds,
            width=cfg.resolution[0],
            height=cfg.resolution[1],
            fps=cfg.fps,
        )

    async def add_background_music(
        self,
        video: VideoOutput,
        music_path: str,
        volume: float = 0.15,
    ) -> VideoOutput:
        """Mix background music into an existing video.

        Args:
            video: VideoOutput to add music to.
            music_path: Path to audio file (mp3/wav).
            volume: Music volume as fraction of narration (0.0 – 1.0).

        Returns:
            VideoOutput pointing to the new file.
        """
        # TODO: Implement using MoviePy AudioFileClip + CompositeAudioClip
        return VideoOutput(**{**video.__dict__, "local_path": video.local_path.replace(".mp4", "_music.mp4")})

    async def render_preview(self, video: VideoOutput, duration: float = 30.0) -> VideoOutput:
        """Render a short preview clip for review.

        Args:
            video: Full VideoOutput.
            duration: Preview duration in seconds.

        Returns:
            VideoOutput for the preview clip.
        """
        # TODO: Implement using MoviePy subclip
        return VideoOutput(**{**video.__dict__, "local_path": video.local_path.replace(".mp4", "_preview.mp4"), "duration_seconds": duration})
