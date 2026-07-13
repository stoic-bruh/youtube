"""OpenAI TTS voice provider — mock implementation using the deterministic generator."""
from __future__ import annotations

from app.providers.voice.base import VoiceProvider
from app.providers.voice.mock_base import generate_mock_voice
from app.schemas.voice import VoiceProviderResult, VoiceRequest


class OpenAITTSProvider(VoiceProvider):
    """OpenAI text-to-speech provider.

    Uses the mock generator until a real OPENAI_API_KEY-backed TTS call is
    wired in (see app.core.config.Settings.VOICE_PROVIDER).
    """

    name: str = "openai-tts"

    async def _fetch_raw(self, request: VoiceRequest, sections: list[dict]) -> VoiceProviderResult:
        return generate_mock_voice(request, self.name, sections)
