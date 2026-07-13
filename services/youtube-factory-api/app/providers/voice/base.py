"""Abstract base class for voice (TTS) providers."""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from app.schemas.voice import VoiceProviderResult, VoiceRequest

logger = logging.getLogger(__name__)

# Default provider config
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_RETRY_DELAY_S = 1.0


class VoiceProvider(ABC):
    """Abstract base for all voice-synthesis (TTS) providers.

    Concrete providers override :meth:`_fetch_raw` and leave the retry /
    timeout / error-wrapping logic here in :meth:`fetch`.
    """

    name: str = "base"
    timeout_s: float = _DEFAULT_TIMEOUT_S
    max_retries: int = _DEFAULT_MAX_RETRIES
    retry_delay_s: float = _DEFAULT_RETRY_DELAY_S

    @abstractmethod
    async def _fetch_raw(
        self, request: VoiceRequest, sections: list[dict]
    ) -> VoiceProviderResult:
        """Synthesise narration audio (no retry / timeout logic).

        Args:
            request: The voice-generation request (voice_id, speed, etc.).
            sections: Ordered list of `{"title": str, "text": str}` narration
                units to synthesise (script hook/sections/outro/CTA).
        """

    async def fetch(self, request: VoiceRequest, sections: list[dict]) -> VoiceProviderResult:
        """Synthesise narration with retry / timeout.  Always returns a result —
        errors are captured inside :attr:`VoiceProviderResult.error`."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                t0 = time.monotonic()
                result = await asyncio.wait_for(
                    self._fetch_raw(request, sections), timeout=self.timeout_s
                )
                result.duration_ms = int((time.monotonic() - t0) * 1000)
                result.provider_name = self.name
                return result
            except asyncio.TimeoutError:
                last_exc = TimeoutError(f"Voice provider {self.name!r} timed out after {self.timeout_s}s")
                logger.warning("Voice provider %r timed out (attempt %d)", self.name, attempt)
            except Exception as exc:
                last_exc = exc
                logger.warning("Voice provider %r failed (attempt %d): %s", self.name, attempt, exc)

            if attempt <= self.max_retries:
                await asyncio.sleep(self.retry_delay_s * attempt)

        return VoiceProviderResult(
            provider_name=self.name,
            error=str(last_exc),
        )
