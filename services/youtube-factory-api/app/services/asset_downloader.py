"""AssetDownloader — downloads assets to local cache storage."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app.schemas.asset import AssetProviderResult

logger = logging.getLogger(__name__)

_CACHE_ROOT = Path(os.getenv("ASSET_CACHE_DIR", "/tmp/asset_cache"))


class AssetDownloader:
    """Simulates downloading a remote asset to local storage."""

    def __init__(self, cache_root: Path | None = None) -> None:
        self._root = cache_root or _CACHE_ROOT

    def local_path(self, result: AssetProviderResult) -> str:
        """Compute the local file path for a result."""
        if not result.source_url or not result.provider_asset_id:
            return ""
        provider_dir = self._root / (result.provider_name or "unknown")
        provider_dir.mkdir(parents=True, exist_ok=True)
        ext = _ext_from_url(result.source_url)
        return str(provider_dir / f"{result.provider_asset_id}.{ext}")

    def thumbnail_path(self, result: AssetProviderResult) -> str | None:
        """Compute the thumbnail path for a result (images only)."""
        if result.asset_kind.value in ("icon", "svg"):
            return None
        if not result.provider_asset_id:
            return None
        provider_dir = self._root / (result.provider_name or "unknown")
        return str(provider_dir / f"thumb_{result.provider_asset_id}.jpg")

    async def download(self, result: AssetProviderResult) -> tuple[str, str | None]:
        """
        Simulate downloading the asset. In mock mode, just returns the paths
        without actually fetching the URL (no API keys required).

        Returns:
            (local_path, thumbnail_path)
        """
        local = self.local_path(result)
        thumb = self.thumbnail_path(result)

        if local:
            # Ensure parent directory exists
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "Mock download: %s → %s (%.1f KB)",
                result.source_url,
                local,
                (result.file_size_bytes or 0) / 1024,
            )
        return local, thumb


def _ext_from_url(url: str) -> str:
    path = url.split("?")[0]
    if "." in path.split("/")[-1]:
        return path.rsplit(".", 1)[-1].lower()[:4]
    return "bin"
