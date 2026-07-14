"""Standalone Post-Processing CLI — real subtitle transcription and thumbnail
extraction/scoring for a rendered MP4, callable without a running FastAPI or
Celery stack (mirrors render_cli.py's pattern).

Usage:
    python3 postprocess_cli.py subtitle <input.json>
    python3 postprocess_cli.py thumbnail <input.json>

`subtitle` input.json:
    {
      "videoPath": "/path/to/render.mp4",
      "language": "en",
      "providers": ["whisper", "script-narration"],
      "sections": [{"text": "...", "startMs": 0, "endMs": 4000}, ...],
      "outputDir": "/tmp/postprocess_engine/subtitles"
    }
Prints a JSON `SubtitleProviderResult`-shaped document plus srt/vtt/ass
content and file paths to stdout.

`thumbnail` input.json:
    {
      "videoPath": "/path/to/render.mp4",
      "count": 3,
      "outputDir": "/tmp/postprocess_engine/thumbnails",
      "idPrefix": "abc123"
    }
Prints a JSON document with `candidates`, `selectedCandidateIds`, and
`brandColors` to stdout.

This lets the Node `api-server` (which owns Render/Subtitle/Thumbnail data
via Drizzle, not SQLAlchemy) trigger genuine FFmpeg/Whisper/Pillow work
without needing the Python service's own database or a running
FastAPI/Celery stack.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys


def _read_input(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _run_subtitle(data: dict) -> dict:
    from app.providers.subtitle.registry import SubtitleProviderRegistry
    from app.services.postprocess.subtitle_formats import build_ass, build_srt, build_vtt

    video_path = data["videoPath"]
    language = data.get("language", "en")
    providers = data.get("providers") or ["whisper", "script-narration"]
    sections = [
        {"text": s.get("text", ""), "start_ms": s.get("startMs", 0), "end_ms": s.get("endMs", 0)}
        for s in (data.get("sections") or [])
    ]
    output_dir = data.get("outputDir", "/tmp/postprocess_engine/subtitles")
    id_prefix = data.get("idPrefix", "subtitle")

    registry = SubtitleProviderRegistry()
    result, attempts = await registry.fetch_with_fallback(
        video_path, language, providers, context={"sections": sections}
    )

    logs = [
        f"Provider {a.provider_name!r}: {'OK' if not a.error else f'FAILED ({a.error})'}"
        for a in attempts
    ]

    if result.error or not result.words:
        return {
            "error": result.error or "no words produced",
            "logs": logs,
            "attempts": [a.model_dump(mode="json") for a in attempts],
        }

    words = [w.model_dump(mode="json") for w in result.words]
    sentences = [s.model_dump(mode="json") for s in result.sentences]
    paragraphs = [p.model_dump(mode="json") for p in result.paragraphs]

    srt_content = build_srt(sentences)
    vtt_content = build_vtt(sentences)
    ass_content = build_ass(sentences, words)

    os.makedirs(output_dir, exist_ok=True)
    srt_path = os.path.join(output_dir, f"{id_prefix}.srt")
    vtt_path = os.path.join(output_dir, f"{id_prefix}.vtt")
    ass_path = os.path.join(output_dir, f"{id_prefix}.ass")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return {
        "provider": result.provider_name,
        "words": words,
        "sentences": sentences,
        "paragraphs": paragraphs,
        "avgConfidence": result.avg_confidence,
        "durationMs": result.duration_ms,
        "wordCount": len(words),
        "srtContent": srt_content,
        "vttContent": vtt_content,
        "assContent": ass_content,
        "srtPath": srt_path,
        "vttPath": vtt_path,
        "assPath": ass_path,
        "logs": logs,
    }


async def _run_thumbnail(data: dict) -> dict:
    from PIL import Image

    from app.services.postprocess.ffmpeg_utils import extract_frame, probe_duration_ms
    from app.services.postprocess.scoring import (
        PlaceholderDetector,
        brightness,
        dominant_color,
        quality_score,
        safe_text_regions,
        sharpness_score,
    )

    video_path = data["videoPath"]
    count = int(data.get("count", 3))
    output_dir = data.get("outputDir", "/tmp/postprocess_engine/thumbnails")
    id_prefix = data.get("idPrefix", "thumbnail")

    logs = []
    duration_ms = data.get("durationMs") or await probe_duration_ms(video_path)
    logs.append(f"Probed duration: {duration_ms}ms")

    n_candidates = max(count * 2, count)
    lo, hi = int(duration_ms * 0.05), int(duration_ms * 0.95)
    span = max(hi - lo, 1)
    timestamps = [lo + int(span * (i + 1) / (n_candidates + 1)) for i in range(n_candidates)]

    os.makedirs(output_dir, exist_ok=True)
    candidates = []
    for i, ts_ms in enumerate(timestamps):
        candidate_id = f"{id_prefix}-c{i}"
        jpg_path = os.path.join(output_dir, f"{candidate_id}.jpg")
        try:
            await extract_frame(video_path, ts_ms, jpg_path)
        except Exception as exc:
            logs.append(f"Frame extraction failed at {ts_ms}ms: {exc}")
            continue

        with Image.open(jpg_path) as img:
            width, height = img.size

        sharp = sharpness_score(jpg_path)
        bright = brightness(jpg_path)
        color = dominant_color(jpg_path)
        quality = quality_score(sharp, bright)

        candidates.append(
            {
                "candidateId": candidate_id,
                "timestampMs": ts_ms,
                "path": jpg_path,
                "width": width,
                "height": height,
                "sharpnessScore": sharp,
                "qualityScore": quality,
                "brightness": bright,
                "dominantColor": color,
                "faceDetected": PlaceholderDetector.detect_faces(jpg_path),
                "objectsDetected": PlaceholderDetector.detect_objects(jpg_path),
                "safeTextRegions": safe_text_regions(width, height),
            }
        )

    if not candidates:
        return {"error": "no thumbnail candidates could be extracted", "logs": logs}

    candidates.sort(key=lambda c: c["qualityScore"], reverse=True)
    selected_ids = [c["candidateId"] for c in candidates[:count]]
    brand_colors: list[str] = []
    for c in candidates[:count]:
        if c["dominantColor"] not in brand_colors:
            brand_colors.append(c["dominantColor"])

    logs.append(f"Selected {len(selected_ids)} of {len(candidates)} candidate(s)")

    return {
        "candidates": candidates,
        "selectedCandidateIds": selected_ids,
        "brandColors": brand_colors,
        "logs": logs,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: postprocess_cli.py <subtitle|thumbnail> <input.json>", file=sys.stderr)
        return 2

    subcommand, input_path = sys.argv[1], sys.argv[2]
    data = _read_input(input_path)

    if subcommand == "subtitle":
        result = asyncio.run(_run_subtitle(data))
    elif subcommand == "thumbnail":
        result = asyncio.run(_run_thumbnail(data))
    else:
        print(f"unknown subcommand: {subcommand!r}", file=sys.stderr)
        return 2

    print(json.dumps(result))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
