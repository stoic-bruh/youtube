"""Synthesizes placeholder scene images and silent narration audio.

Upstream stages (Asset Intelligence Engine, Voice Engine) run against
simulated/mock providers in this environment — no real API keys are wired, so
`AssetResult.local_path` / `VoiceResult.sections[].local_path` are bookkeeping
paths without real bytes on disk (see repo convention notes). The Render
Engine itself must still be *real*: it runs genuine MoviePy/FFmpeg
compositing, Ken Burns motion, transitions, and audio mixing — just over
stand-in media generated here when a real source file isn't present on disk.
"""
from __future__ import annotations

import math
import os
import wave

from PIL import Image, ImageDraw, ImageFont

_PALETTE = [
    (0x1E, 0x1B, 0x4B),
    (0x30, 0x27, 0x66),
    (0x1F, 0x4E, 0x5F),
    (0x2D, 0x5A, 0x3D),
    (0x5C, 0x33, 0x17),
    (0x4A, 0x1B, 0x3D),
]


def _wrap_text(text: str, width_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:8]


_FONT_CACHE: dict[tuple[bool, int], ImageFont.ImageFont] = {}

_CANDIDATE_FONTS = [
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
    "LiberationSans-Bold.ttf",
    "LiberationSans-Regular.ttf",
]


def _load_font(*, bold: bool, size: int) -> ImageFont.ImageFont:
    key = (bold, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    names = [n for n in _CANDIDATE_FONTS if ("Bold" in n) == bold] or _CANDIDATE_FONTS
    for name in names:
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[key] = font
            return font
        except Exception:
            continue
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def generate_placeholder_image(
    path: str,
    *,
    width: int,
    height: int,
    title: str,
    caption: str,
    scene_index: int,
) -> str:
    """Render a deterministic gradient placeholder frame with the scene's
    title/caption burned in, so the timeline is visually distinguishable
    scene-to-scene even without real acquired imagery."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    base = _PALETTE[scene_index % len(_PALETTE)]
    img = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(img)

    # Simple vertical gradient overlay for depth.
    for y in range(height):
        t = y / max(height - 1, 1)
        shade = int(20 * math.sin(t * math.pi))
        line_color = tuple(min(255, max(0, c + shade)) for c in base)
        draw.line([(0, y), (width, y)], fill=line_color)

    font_title = _load_font(bold=True, size=int(height * 0.06))
    font_caption = _load_font(bold=False, size=int(height * 0.035))

    margin = int(width * 0.08)
    draw.text((margin, int(height * 0.08)), f"Scene {scene_index + 1}", font=font_title, fill=(255, 255, 255))
    draw.text((margin, int(height * 0.16)), title[:60], font=font_title, fill=(255, 255, 255))

    lines = _wrap_text(caption, width_chars=int(width / (height * 0.035 * 0.62)))
    y = int(height * 0.62)
    line_height = int(height * 0.045)
    for line in lines:
        draw.text((margin, y), line, font=font_caption, fill=(230, 230, 230))
        y += line_height

    img.save(path, "PNG")
    return path


def generate_silence_wav(path: str, *, duration_ms: int, sample_rate: int = 44100) -> str:
    """Write a silent mono WAV file of the given duration — used as a stand-in
    narration/music track when no real audio file exists on disk yet."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n_frames = max(1, int(sample_rate * duration_ms / 1000))
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return path


def resolve_media_path(candidate: str | None, fallback_generator) -> str:
    """Return `candidate` if it points at a real file on disk, otherwise call
    `fallback_generator()` to synthesize a placeholder and return that path."""
    if candidate and os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
        return candidate
    return fallback_generator()
