"""Deterministic mock TTS generator.

Seeded by (provider_name, script_id, voice_id) so output is reproducible.
Simulates a real TTS provider by estimating per-section duration from word
count and speaking rate, and writing a fake local audio path — matching the
convention used by the mock storyboard/script generators until real
provider integrations (OpenAI TTS / ElevenLabs API keys) are wired in.
"""
from __future__ import annotations

import hashlib
import random
import re

from app.schemas.voice import SectionAudio, VoiceProviderResult, VoiceRequest

_BASE_WPM = 155.0  # average narration speaking rate at speed=1.0


def _seed(provider_name: str, script_id: str, voice_id: str) -> int:
    raw = f"{provider_name}:{script_id}:{voice_id}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


def _count_words(text: str) -> int:
    return len(re.sub(r"\s+", " ", text.strip()).split()) if text.strip() else 0


def generate_mock_voice(
    request: VoiceRequest,
    provider_name: str,
    sections: list[dict],
) -> VoiceProviderResult:
    """Produce a deterministic mock voice-generation result.

    Args:
        request: The originating VoiceRequest (voice_id, speed, script_id).
        provider_name: Name of the calling provider (used to seed + tag output).
        sections: Ordered `{"title": str, "text": str}` narration units.
    """
    rng = random.Random(_seed(provider_name, request.script_id, request.voice_id))
    wpm = _BASE_WPM * request.speed

    audio_sections: list[SectionAudio] = []
    cursor_ms = 0
    total_words = 0

    for i, section in enumerate(sections):
        text = section.get("text", "") or ""
        title = section.get("title", f"Section {i + 1}")
        word_count = _count_words(text)
        total_words += word_count
        duration_s = (word_count / wpm) * 60.0 if wpm > 0 else 0.0
        # Small deterministic jitter (+/-3%) so providers don't produce
        # identical timings, mirroring real-world TTS variance.
        jitter = 1.0 + rng.uniform(-0.03, 0.03)
        duration_ms = max(1, int(duration_s * 1000 * jitter))
        start_ms = cursor_ms
        end_ms = start_ms + duration_ms
        cursor_ms = end_ms

        audio_sections.append(
            SectionAudio(
                section_index=i,
                section_title=title,
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=duration_ms,
                word_count=word_count,
                local_path=f"/tmp/voice/{provider_name}/{request.script_id}/section_{i:04d}.mp3",
                sample_rate=44100,
            )
        )

    cost_per_1k_chars = 0.015 if provider_name == "openai-tts" else 0.03
    total_chars = sum(len(s.text) for s in audio_sections)
    cost_usd = round((total_chars / 1000.0) * cost_per_1k_chars, 4)

    return VoiceProviderResult(
        provider_name=provider_name,
        sections=audio_sections,
        total_duration_ms=cursor_ms,
        sample_rate=44100,
        audio_format="mp3",
        cost_usd=cost_usd,
        confidence=0.9,
    )
