"""Registry that loads voice providers and coordinates fallback."""
from __future__ import annotations

import logging

from app.providers.voice.base import VoiceProvider
from app.providers.voice.elevenlabs_provider import ElevenLabsProvider
from app.providers.voice.openai_tts_provider import OpenAITTSProvider
from app.schemas.voice import VoiceProviderResult, VoiceRequest

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[VoiceProvider]] = {
    "openai-tts": OpenAITTSProvider,
    "elevenlabs": ElevenLabsProvider,
}


class VoiceProviderRegistry:
    """Lazily instantiates voice providers and tries them in fallback order.

    Unlike script/storyboard generation, TTS audio from different providers
    cannot be meaningfully merged — so voice synthesis tries each requested
    provider in order and uses the first one that succeeds.
    """

    def __init__(self) -> None:
        self._instances: dict[str, VoiceProvider] = {}

    def _get_provider(self, name: str) -> VoiceProvider | None:
        if name not in _REGISTRY:
            logger.warning("Unknown voice provider: %r", name)
            return None
        if name not in self._instances:
            self._instances[name] = _REGISTRY[name]()
        return self._instances[name]

    async def fetch_with_fallback(
        self,
        request: VoiceRequest,
        sections: list[dict],
        provider_names: list[str],
    ) -> tuple[VoiceProviderResult, list[VoiceProviderResult]]:
        """Try providers in order; return the first success plus all attempts.

        Returns:
            (best_result, all_attempts) — best_result is the first successful
            provider result, or the last failed result if every provider failed.
        """
        attempts: list[VoiceProviderResult] = []
        for name in provider_names:
            provider = self._get_provider(name)
            if not provider:
                attempts.append(VoiceProviderResult(provider_name=name, error=f"Unknown provider: {name!r}"))
                continue
            result = await provider.fetch(request, sections)
            attempts.append(result)
            if not result.error:
                return result, attempts

        # All providers failed — return the last attempt as the "best" (still errored)
        return attempts[-1], attempts
