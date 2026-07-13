"""AssetCache — content-addressed cache for acquired assets."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetCacheEntry
from app.repositories.asset_repository import AssetCacheRepository
from app.schemas.asset import AssetKind, AssetProviderResult

logger = logging.getLogger(__name__)


def _make_key(asset_kind: AssetKind, query: str, width: int, height: int) -> str:
    """Stable content-addressed cache key."""
    raw = f"{asset_kind}|{query.strip().lower()}|{width}x{height}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


class AssetCache:
    """Wraps AssetCacheRepository with helper methods for the decision engine."""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = AssetCacheRepository(db)
        self._db = db

    def make_key(
        self,
        asset_kind: AssetKind,
        query: str,
        width: int = 1920,
        height: int = 1080,
    ) -> str:
        return _make_key(asset_kind, query, width, height)

    async def get(self, cache_key: str) -> AssetCacheEntry | None:
        """Return a valid cache entry, or None on miss."""
        entry = await self._repo.get_by_key(cache_key)
        if entry:
            await self._repo.touch(cache_key)
            logger.debug("Cache HIT key=%s provider=%s", cache_key[:16], entry.provider)
        return entry

    async def put(
        self,
        cache_key: str,
        result: AssetProviderResult,
        *,
        local_path: str | None = None,
        thumbnail_path: str | None = None,
    ) -> AssetCacheEntry:
        """Store an asset provider result in the cache."""
        existing = await self._repo.get_by_key(cache_key)
        if existing:
            return existing

        entry = AssetCacheEntry(
            cache_key=cache_key,
            asset_kind=result.asset_kind.value,
            provider=result.provider_name,
            source_url=result.source_url,
            local_path=local_path,
            thumbnail_path=thumbnail_path,
            file_size_bytes=result.file_size_bytes,
            width=result.width,
            height=result.height,
            license=result.license.value if result.license else "unknown",
            tags=result.tags,
            quality_score=result.quality_score,
            hit_count=1,
            is_valid=True,
            created_at=datetime.now(timezone.utc),
            last_accessed_at=datetime.now(timezone.utc),
        )
        self._db.add(entry)
        await self._db.flush()
        logger.debug("Cache PUT key=%s provider=%s", cache_key[:16], result.provider_name)
        return entry
