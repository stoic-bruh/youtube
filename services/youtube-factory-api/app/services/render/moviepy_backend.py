"""Real MoviePy/FFmpeg renderer backend.

Implements RendererBackend.render() by compositing a RenderPlan into an
actual MP4 file on disk using MoviePy 2.x (which shells out to FFmpeg for
encoding). This is genuine media composition: Ken Burns pan/zoom on image
clips, crossfade/fade/cut transitions between scenes, narration + background
music audio mixing, and export at the requested resolution/fps/aspect ratio
with safe-crop/letterbox/blur-pad framing.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
    afx,
)

from app.schemas.render import RenderOutput, RenderPlan, RenderScene, RenderStats
from app.services.render.base import ProgressCallback, RendererBackend, RenderProgress
from app.services.render.placeholder_assets import (
    generate_placeholder_image,
    generate_silence_wav,
    resolve_media_path,
)

logger = logging.getLogger(__name__)


def _emit(on_progress: ProgressCallback | None, phase: str, percent: int, message: str = "") -> None:
    if on_progress:
        on_progress(RenderProgress(phase=phase, percent=percent, message=message))
    logger.info("[render:%s] %d%% %s", phase, percent, message)


def _fit_frame(clip, width: int, height: int, crop_mode: str):
    """Resize `clip` to exactly (width, height) honoring the requested crop mode."""
    src_w, src_h = clip.size
    target_ratio = width / height
    src_ratio = src_w / src_h

    if crop_mode == "letterbox":
        if src_ratio > target_ratio:
            resized = clip.resized(width=width)
        else:
            resized = clip.resized(height=height)
        resized = resized.with_position("center")
        return CompositeVideoClip([resized], size=(width, height), bg_color=(0, 0, 0)).with_duration(clip.duration)

    if crop_mode == "blur_pad":
        # Background: cover-fill, darkened to read as a soft backdrop (MoviePy's
        # CPU vfx pipeline has no GaussianBlur filter, so we approximate the
        # "blurred pad" look with a darkened cover-fill instead of true blur);
        # foreground: contain-fit, centered on top.
        bg = clip.resized(width=width) if src_ratio < target_ratio else clip.resized(height=height)
        bg = bg.cropped(x_center=bg.w / 2, y_center=bg.h / 2, width=min(bg.w, width), height=min(bg.h, height))
        bg = bg.image_transform(lambda frame: (frame * 0.45).astype(frame.dtype)) if hasattr(bg, "image_transform") else bg
        fg = clip.resized(width=width) if src_ratio > target_ratio else clip.resized(height=height)
        fg = fg.with_position("center")
        return CompositeVideoClip([bg, fg], size=(width, height)).with_duration(clip.duration)

    # safe_crop (default) — cover-fill then center-crop to the exact target box.
    if src_ratio > target_ratio:
        resized = clip.resized(height=height)
    else:
        resized = clip.resized(width=width)
    cropped = resized.cropped(x_center=resized.w / 2, y_center=resized.h / 2, width=width, height=height)
    return cropped


def _ken_burns_clip(image_path: str, duration_s: float, size: tuple[int, int], zoom_start: float, zoom_end: float, pan: str):
    """Build an ImageClip with a subtle zoom/pan (Ken Burns) animation."""
    base = ImageClip(image_path).with_duration(duration_s)
    w, h = size

    def _resize_at(t: float) -> float:
        progress = t / duration_s if duration_s > 0 else 0
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        return zoom

    animated = base.resized(lambda t: _resize_at(t) * max(w / base.w, h / base.h))

    if pan in ("left", "right", "up", "down"):
        def _pos(t: float):
            progress = t / duration_s if duration_s > 0 else 0
            shift = 0.06 * progress  # fraction of frame drifted over the clip
            cw, ch = animated.size if callable(getattr(animated, "size", None)) else (w, h)
            if pan == "right":
                return (-shift * w, "center")
            if pan == "left":
                return (shift * w - w * 0.06, "center")
            if pan == "down":
                return ("center", -shift * h)
            return ("center", shift * h - h * 0.06)

        animated = animated.with_position(_pos)
        frame = CompositeVideoClip([animated], size=size).with_duration(duration_s)
    else:
        animated = animated.with_position("center")
        frame = CompositeVideoClip([animated], size=size).with_duration(duration_s)
    return frame


class MoviePyRenderer(RendererBackend):
    """Production RendererBackend built on MoviePy + FFmpeg."""

    name = "moviepy"

    def __init__(self, *, work_dir: str = "/tmp/render_engine") -> None:
        self.work_dir = work_dir
        os.makedirs(self.work_dir, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────

    async def render(
        self,
        plan: RenderPlan,
        output_path: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[RenderOutput, RenderStats]:
        t0 = time.monotonic()
        _emit(on_progress, "compose", 5, f"Building {len(plan.scenes)} scene clip(s)")

        video = self._build_video(plan, on_progress)
        audio = self._build_audio(plan, video.duration, on_progress)
        if audio is not None:
            video = video.with_audio(audio)

        _emit(on_progress, "encode", 70, f"Encoding to {output_path}")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        video.write_videofile(
            output_path,
            fps=plan.fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=2,
            logger=None,
        )
        elapsed = time.monotonic() - t0
        file_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
        duration_s = float(video.duration)
        video.close()

        _emit(on_progress, "done", 100, "Render complete")

        output = RenderOutput(
            local_path=output_path,
            file_size_bytes=file_size,
            duration_seconds=duration_s,
            width=plan.width,
            height=plan.height,
            fps=plan.fps,
            codec="libx264",
            audio_codec="aac",
            format="mp4",
        )
        stats = RenderStats(
            render_time_seconds=round(elapsed, 3),
            frames_encoded=int(duration_s * plan.fps),
            encode_fps=round((duration_s * plan.fps) / elapsed, 2) if elapsed > 0 else 0.0,
            realtime_factor=round(duration_s / elapsed, 3) if elapsed > 0 else 0.0,
            retries=0,
        )
        return output, stats

    async def render_preview(
        self,
        plan: RenderPlan,
        output_path: str,
        *,
        max_duration_seconds: float = 20.0,
        on_progress: ProgressCallback | None = None,
    ) -> RenderOutput:
        _emit(on_progress, "preview", 10, "Building preview clip")
        video = self._build_video(plan, on_progress)
        preview = video.subclipped(0, min(max_duration_seconds, video.duration))
        audio = self._build_audio(plan, preview.duration, on_progress)
        if audio is not None:
            preview = preview.with_audio(audio.subclipped(0, preview.duration))

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        preview.write_videofile(
            output_path, fps=plan.fps, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None,
        )
        file_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
        duration_s = float(preview.duration)
        preview.close()
        video.close()
        _emit(on_progress, "preview", 100, "Preview complete")
        return RenderOutput(
            local_path=output_path,
            file_size_bytes=file_size,
            duration_seconds=duration_s,
            width=plan.width,
            height=plan.height,
            fps=plan.fps,
            codec="libx264",
            audio_codec="aac",
            format="mp4",
        )

    # ── Internal composition ──────────────────────────────────────────────

    def _resolve_scene_image(self, scene: RenderScene, plan: RenderPlan) -> str:
        clip = scene.clips[0] if scene.clips else None
        candidate = clip.source_path if clip else None
        return resolve_media_path(
            candidate,
            lambda: generate_placeholder_image(
                os.path.join(self.work_dir, f"{plan.timeline_id}_scene{scene.scene_index}.png"),
                width=plan.width,
                height=plan.height,
                title=scene.title or f"Scene {scene.scene_index + 1}",
                caption=scene.narration,
                scene_index=scene.scene_index,
            ),
        )

    def _build_video(self, plan: RenderPlan, on_progress: ProgressCallback | None):
        size = (plan.width, plan.height)
        clips = []
        total = max(len(plan.scenes), 1)
        for i, scene in enumerate(sorted(plan.scenes, key=lambda s: s.scene_index)):
            duration_s = max(scene.duration_ms, 500) / 1000.0
            image_path = self._resolve_scene_image(scene, plan)
            clip_cfg = scene.clips[0] if scene.clips else None
            pan = clip_cfg.pan_direction if clip_cfg else ("right" if scene.scene_index % 2 == 0 else "left")
            zoom_start = clip_cfg.zoom_start if clip_cfg else 1.0
            zoom_end = clip_cfg.zoom_end if clip_cfg else 1.08
            ken_burns = clip_cfg.ken_burns if clip_cfg else True

            if ken_burns:
                frame = _ken_burns_clip(image_path, duration_s, size, zoom_start, zoom_end, pan)
            else:
                frame = _fit_frame(ImageClip(image_path).with_duration(duration_s), size[0], size[1], plan.crop_mode.value if hasattr(plan.crop_mode, "value") else plan.crop_mode)

            transition = scene.transition_out
            if transition and transition.type.value != "cut" and transition.duration_ms > 0:
                fade_s = min(transition.duration_ms / 1000.0, duration_s / 2)
                if transition.type.value == "crossfade":
                    frame = frame.with_effects([vfx.CrossFadeIn(fade_s)]) if i > 0 else frame
                    frame = frame.with_effects([vfx.CrossFadeOut(fade_s)])
                elif transition.type.value == "fade":
                    frame = frame.with_effects([vfx.FadeIn(fade_s), vfx.FadeOut(fade_s)])

            clips.append(frame)
            _emit(on_progress, "compose", 5 + int(55 * (i + 1) / total), f"Scene {i + 1}/{total} composed")

        if not clips:
            raise RuntimeError("RenderPlan has no scenes to render")

        method = "compose" if any(c.duration for c in clips) else "chain"
        video = concatenate_videoclips(clips, method="compose", padding=-0.15 if len(clips) > 1 else 0)
        return video

    def _build_audio(self, plan: RenderPlan, video_duration_s: float, on_progress: ProgressCallback | None):
        tracks = []
        narration_tracks = [t for t in plan.audio_tracks if t.kind == "narration"]
        if narration_tracks:
            for t in narration_tracks:
                path = resolve_media_path(
                    t.source_path,
                    lambda t=t: generate_silence_wav(
                        os.path.join(self.work_dir, f"{plan.timeline_id}_narration_{t.start_ms}.wav"),
                        duration_ms=max(t.end_ms - t.start_ms, 500),
                    ),
                )
                clip = AudioFileClip(path).with_start(t.start_ms / 1000.0).with_volume_scaled(t.volume)
                tracks.append(clip)
        else:
            path = generate_silence_wav(
                os.path.join(self.work_dir, f"{plan.timeline_id}_narration_full.wav"),
                duration_ms=int(video_duration_s * 1000),
            )
            tracks.append(AudioFileClip(path))

        if plan.add_background_music:
            music_path = resolve_media_path(
                plan.background_music_path,
                lambda: generate_silence_wav(
                    os.path.join(self.work_dir, f"{plan.timeline_id}_music.wav"),
                    duration_ms=int(video_duration_s * 1000),
                ),
            )
            music = AudioFileClip(music_path).with_volume_scaled(plan.music_volume)
            if music.duration < video_duration_s:
                music = music.with_effects([afx.AudioLoop(duration=video_duration_s)])
            tracks.append(music.subclipped(0, video_duration_s))

        if not tracks:
            return None
        _emit(on_progress, "audio", 65, f"Mixing {len(tracks)} audio track(s)")
        return CompositeAudioClip(tracks)
