"""Subtitle provider registry — tries providers in fallback order and keeps
the first result that actually contains transcribed words."""
from __future__ import annotations

import logging

from app.providers.subtitle.base import SubtitleProvider
from app.providers.subtitle.script_narration_provider import ScriptNarrationProvider
from app.providers.subtitle.whisper_provider import WhisperTranscriptionProvider
from app.schemas.subtitle import SubtitleProviderResult

logger = logging.getLogger(__name__)


class SubtitleProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SubtitleProvider] = {
            "whisper": WhisperTranscriptionProvider(),
            "script-narration": ScriptNarrationProvider(),
        }

    async def fetch_with_fallback(
        self,
        video_path: str,
        language: str,
        provider_names: list[str],
        *,
        context: dict | None = None,
    ) -> tuple[SubtitleProviderResult, list[SubtitleProviderResult]]:
        attempts: list[SubtitleProviderResult] = []
        for name in provider_names:
            provider = self._providers.get(name)
            if not provider:
                attempts.append(SubtitleProviderResult(provider_name=name, error="unknown provider"))
                continue
            try:
                result = await provider.transcribe(video_path, language, context=context)
            except Exception as exc:  # provider crashed — record and fall back
                result = SubtitleProviderResult(provider_name=name, error=f"{type(exc).__name__}: {exc}")
            attempts.append(result)
            if not result.error and result.words:
                return result, attempts
        # all providers failed — return the last attempt so the caller can surface its error
        return attempts[-1], attempts
