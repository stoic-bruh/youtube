"""Asset result repository."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.asset import AssetResult, AssetCacheEntry, AssetProviderMetadata
from app.repositories.base import BaseRepository


class AssetRepository(BaseRepository[AssetResult]):
    model = AssetResult

    async def get_by_storyboard(self, storyboard_id: str) -> list[AssetResult]:
        stmt = (
            select(AssetResult)
            .where(AssetResult.storyboard_id == storyboard_id)
            .order_by(AssetResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scene(self, storyboard_id: str, scene_id: str) -> list[AssetResult]:
        stmt = (
            select(AssetResult)
            .where(
                AssetResult.storyboard_id == storyboard_id,
                AssetResult.scene_id == scene_id,
            )
            .order_by(AssetResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[AssetResult]:
        stmt = select(AssetResult).where(AssetResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_provider(self, provider: str) -> list[AssetResult]:
        stmt = (
            select(AssetResult)
            .where(AssetResult.provider == provider)
            .order_by(AssetResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        asset = await self.get(id)
        if asset:
            logs: list[str] = list(asset.logs or [])
            logs.append(message)
            asset.logs = logs
            asset.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> AssetResult | None:
        asset = await self.get(id)
        if not asset:
            return None
        asset.status = status
        asset.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            asset.error_message = error_message
        if status == "ready":
            asset.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(asset.logs or [])
            logs.append(log_line)
            asset.logs = logs
        await self._db.flush()
        return asset


class AssetCacheRepository(BaseRepository[AssetCacheEntry]):
    model = AssetCacheEntry

    async def get_by_key(self, cache_key: str) -> AssetCacheEntry | None:
        stmt = select(AssetCacheEntry).where(
            AssetCacheEntry.cache_key == cache_key,
            AssetCacheEntry.is_valid == True,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def touch(self, cache_key: str) -> None:
        entry = await self.get_by_key(cache_key)
        if entry:
            entry.hit_count += 1
            entry.last_accessed_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def invalidate(self, cache_key: str) -> None:
        entry = await self.get_by_key(cache_key)
        if entry:
            entry.is_valid = False
            await self._db.flush()


class AssetProviderMetadataRepository(BaseRepository[AssetProviderMetadata]):
    model = AssetProviderMetadata

    async def get_by_name(self, provider_name: str) -> AssetProviderMetadata | None:
        stmt = select(AssetProviderMetadata).where(
            AssetProviderMetadata.provider_name == provider_name
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_enabled(self) -> list[AssetProviderMetadata]:
        stmt = select(AssetProviderMetadata).where(
            AssetProviderMetadata.is_enabled == True  # noqa: E712
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def record_request(
        self,
        provider_name: str,
        *,
        success: bool,
        latency_ms: int,
        cost_usd: float = 0.0,
        cache_hit: bool = False,
    ) -> None:
        meta = await self.get_by_name(provider_name)
        if not meta:
            return
        meta.total_requests += 1
        if success:
            meta.successful_requests += 1
        else:
            meta.failed_requests += 1
        if cache_hit:
            meta.cache_hits += 1
        meta.total_cost_usd = (meta.total_cost_usd or 0.0) + cost_usd
        if meta.avg_latency_ms is None:
            meta.avg_latency_ms = float(latency_ms)
        else:
            n = meta.total_requests
            meta.avg_latency_ms = ((meta.avg_latency_ms * (n - 1)) + latency_ms) / n
        if cost_usd > 0:
            if meta.avg_cost_usd is None:
                meta.avg_cost_usd = cost_usd
            else:
                meta.avg_cost_usd = (meta.avg_cost_usd + cost_usd) / 2
        meta.updated_at = datetime.now(timezone.utc)
        await self._db.flush()
