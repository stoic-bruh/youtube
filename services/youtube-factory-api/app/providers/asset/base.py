"""Abstract base for asset providers — retry/timeout wrapper."""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from app.schemas.asset import AssetKind, AssetProviderResult

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 2


class AssetProvider(ABC):
    """Abstract asset provider. Subclasses implement _fetch_raw()."""

    name: str = "base"
    provider_type: str = "stock"          # stock | generate | icon
    supported_kinds: list[AssetKind] = [AssetKind.IMAGE]
    timeout: float = _DEFAULT_TIMEOUT

    async def fetch(
        self,
        query: str,
        asset_kind: AssetKind,
        *,
        prompt: str = "",
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        **kwargs,
    ) -> AssetProviderResult:
        """Public entry point — applies timeout and retry around _fetch_raw()."""
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self._fetch_raw(
                        query,
                        asset_kind,
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        width=width,
                        height=height,
                        **kwargs,
                    ),
                    timeout=self.timeout,
                )
                result.generation_time_ms = int((time.monotonic() - t0) * 1000)
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

        return AssetProviderResult(
            provider_name=self.name,
            found=False,
            asset_kind=asset_kind,
            error=f"Provider failed after {_MAX_RETRIES + 1} attempts: {last_error}",
        )

    @abstractmethod
    async def _fetch_raw(
        self,
        query: str,
        asset_kind: AssetKind,
        *,
        prompt: str = "",
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        **kwargs,
    ) -> AssetProviderResult:
        """Subclasses implement this to call the actual provider."""
        ...
