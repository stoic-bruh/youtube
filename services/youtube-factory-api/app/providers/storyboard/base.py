"""Abstract base for storyboard providers — retry/timeout wrapper."""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.storyboard import StoryboardProviderResult, StoryboardRequest

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0
_MAX_RETRIES = 2


class StoryboardProvider(ABC):
    """Abstract storyboard provider.  Subclasses implement _fetch_raw()."""

    name: str = "base"
    timeout: float = _DEFAULT_TIMEOUT

    async def fetch(
        self,
        request: StoryboardRequest,
        script_data: dict[str, Any],
    ) -> StoryboardProviderResult:
        """Public entry point — applies timeout and retry around _fetch_raw()."""
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self._fetch_raw(request, script_data),
                    timeout=self.timeout,
                )
                result.duration_ms = int((time.monotonic() - t0) * 1000)
                return result
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "%s timed out (attempt %d/%d)", self.name, attempt + 1, _MAX_RETRIES + 1
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "%s error (attempt %d/%d): %s",
                    self.name, attempt + 1, _MAX_RETRIES + 1, exc,
                )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)

        return StoryboardProviderResult(
            provider_name=self.name,
            topic=request.topic,
            error=f"Provider failed after {_MAX_RETRIES + 1} attempts: {last_error}",
            confidence=0.0,
        )

    @abstractmethod
    async def _fetch_raw(
        self,
        request: StoryboardRequest,
        script_data: dict[str, Any],
    ) -> StoryboardProviderResult:
        """Subclasses override this to call the actual AI provider."""
        ...
