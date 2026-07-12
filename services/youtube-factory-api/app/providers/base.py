"""Abstract base class and protocol for all research providers."""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from app.schemas.research import ProviderResult, ResearchRequest


@dataclass
class ProviderConfig:
    """Runtime configuration injected into each provider."""

    api_key: str = ""
    base_url: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    extra: dict = field(default_factory=dict)


class ResearchProvider(ABC):
    """Abstract base for all research providers.

    Contract:
    - Each provider implements `_fetch_raw` with provider-specific logic.
    - The base class handles timeout, retry, and timing.
    - Providers should never raise; they return ProviderResult with error set on failure.
    """

    name: ClassVar[str] = "base"
    description: ClassVar[str] = "Abstract provider"
    supports_streaming: ClassVar[bool] = False
    default_weight: ClassVar[float] = 1.0  # used when merging results

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self.config = config or ProviderConfig()

    async def fetch(self, request: ResearchRequest) -> ProviderResult:
        """Fetch research with retry and timeout handling."""
        last_error: str = ""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                start = time.monotonic()
                result = await asyncio.wait_for(
                    self._fetch_raw(request),
                    timeout=self.config.timeout_seconds,
                )
                result.duration_ms = int((time.monotonic() - start) * 1000)
                return result
            except asyncio.TimeoutError:
                last_error = f"timeout after {self.config.timeout_seconds}s (attempt {attempt})"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc} (attempt {attempt})"
            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay_seconds * attempt)

        return ProviderResult(
            provider_name=self.name,
            topic=request.topic,
            error=f"All {self.config.max_retries} retries failed. Last error: {last_error}",
            confidence=0.0,
        )

    @abstractmethod
    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        """Provider-specific fetch logic. May raise; will be caught by `fetch`."""
        ...

    @property
    def is_available(self) -> bool:
        """Return True if the provider is properly configured and available."""
        return True
