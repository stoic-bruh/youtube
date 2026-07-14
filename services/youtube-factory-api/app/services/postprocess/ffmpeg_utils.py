"""Real FFmpeg/FFprobe subprocess helpers used by the Post-Processing Engine.

These do genuine media I/O (no mocking): audio is really demuxed to WAV for
transcription, frames are really decoded to JPEG for thumbnail scoring, and
duration is really probed from the container.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil

logger = logging.getLogger(__name__)


def _ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _ffprobe_bin() -> str:
    return shutil.which("ffprobe") or "ffprobe"


async def _run(cmd: list[str]) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout, stderr


async def probe_duration_ms(video_path: str) -> int:
    """Return the real container duration in milliseconds via ffprobe."""
    cmd = [
        _ffprobe_bin(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    code, stdout, stderr = await _run(cmd)
    if code != 0:
        raise RuntimeError(f"ffprobe failed ({code}): {stderr.decode(errors='ignore')}")
    data = json.loads(stdout.decode() or "{}")
    duration_s = float(data.get("format", {}).get("duration", 0.0))
    return int(round(duration_s * 1000))


async def extract_audio(video_path: str, out_wav_path: str, *, sample_rate: int = 16000) -> str:
    """Demux the real audio track to a mono 16kHz WAV file for transcription."""
    cmd = [
        _ffmpeg_bin(), "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
        out_wav_path,
    ]
    code, _stdout, stderr = await _run(cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed ({code}): {stderr.decode(errors='ignore')[-500:]}")
    return out_wav_path


async def extract_frame(video_path: str, timestamp_ms: int, out_jpg_path: str) -> str:
    """Decode the real video frame nearest `timestamp_ms` to a JPEG file."""
    timestamp_s = max(timestamp_ms, 0) / 1000.0
    cmd = [
        _ffmpeg_bin(), "-y", "-ss", f"{timestamp_s:.3f}", "-i", video_path,
        "-frames:v", "1", "-q:v", "2", out_jpg_path,
    ]
    code, _stdout, stderr = await _run(cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed ({code}): {stderr.decode(errors='ignore')[-500:]}")
    return out_jpg_path


async def audio_rms_energy(wav_path: str) -> float:
    """Real average absolute PCM sample magnitude, used to detect silent tracks."""
    import wave
    import struct

    with wave.open(wav_path, "rb") as wf:
        n_frames = wf.getnframes()
        if n_frames == 0:
            return 0.0
        raw = wf.readframes(n_frames)
        sample_width = wf.getsampwidth()
        if sample_width != 2:
            return 0.0
        count = len(raw) // 2
        samples = struct.unpack(f"<{count}h", raw[: count * 2])
        if not samples:
            return 0.0
        return sum(abs(s) for s in samples) / len(samples)
