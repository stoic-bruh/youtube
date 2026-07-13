"""AssetService — the Asset Intelligence Engine decision core."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetResult
from app.providers.asset.registry import AssetProviderRegistry
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import (
    AssetKind,
    AssetLicense,
    AssetProviderName,
    AssetRequest,
    AssetResultSchema,
    AssetStatus,
    SingleAssetRequest,
)
from app.services.asset_cache import AssetCache
from app.services.asset_downloader import AssetDownloader
from app.services.asset_search_engine import AssetSearchEngine

logger = logging.getLogger(__name__)

_STALE_PENDING_MINUTES = 30


def _ts() -> str:
    return f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]"


class AssetService:
    """
    Asset Intelligence Engine.

    Decision flow per scene asset:
      1. Check local cache  (cache_key = hash(kind + query + dims))
      2. Search stock providers (wikimedia → pexels → pixabay → unsplash / video / icon)
      3. If acceptable stock asset found → download → cache → return
      4. Otherwise → generate with AI (flux → sdxl → gpt_image → gemini → ideogram)
      5. Cache → return
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AssetRepository(db)
        self._cache = AssetCache(db)
        self._search = AssetSearchEngine()
        self._downloader = AssetDownloader()
        self._registry = AssetProviderRegistry()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def list_assets(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        storyboard_id: str | None = None,
        scene_id: str | None = None,
        status: str | None = None,
        asset_kind: str | None = None,
        provider: str | None = None,
    ) -> tuple[list[AssetResult], int]:
        filters: dict = {}
        if storyboard_id:
            filters["storyboard_id"] = storyboard_id
        if scene_id:
            filters["scene_id"] = scene_id
        if status:
            filters["status"] = status
        if asset_kind:
            filters["asset_kind"] = asset_kind
        if provider:
            filters["provider"] = provider
        rows, total = await self._repo.list(limit=limit, offset=offset, **filters)
        return list(rows), total

    async def get_asset(self, asset_id: str) -> AssetResult | None:
        return await self._repo.get(asset_id)

    async def delete_asset(self, asset_id: str) -> bool:
        return await self._repo.delete(asset_id)

    async def start_acquisition(self, request: AssetRequest) -> list[AssetResult]:
        """
        Immediately create pending asset records for all requested scenes.
        The actual acquisition runs asynchronously via the Celery task.
        """
        # Build scene list from the storyboard's scenes JSON or use provided scene_ids
        scene_ids = request.scene_ids or await self._get_scene_ids(request.storyboard_id)

        created: list[AssetResult] = []
        for scene_id in scene_ids:
            for kind in request.asset_kinds:
                asset = await self._repo.create(
                    id=str(uuid.uuid4()),
                    storyboard_id=request.storyboard_id,
                    scene_id=scene_id,
                    asset_kind=kind.value,
                    status=AssetStatus.PENDING.value,
                    logs=[f"{_ts()} INFO  Asset acquisition queued — kind: {kind.value}"],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                created.append(asset)
        return created

    async def acquire_asset(self, request: SingleAssetRequest) -> AssetResult:
        """
        Execute the full Asset Intelligence Engine decision flow for one asset.
        This is called from the Celery task.
        """
        # Check for existing record
        existing = await self._find_existing(
            request.storyboard_id, request.scene_id, request.asset_kind
        )
        if existing:
            asset = existing
        else:
            asset = await self._repo.create(
                id=str(uuid.uuid4()),
                storyboard_id=request.storyboard_id,
                scene_id=request.scene_id,
                asset_kind=request.asset_kind.value,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                status=AssetStatus.PENDING.value,
                logs=[f"{_ts()} INFO  Asset acquisition started"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        await self._run_decision_engine(asset, request)
        return asset

    async def execute_asset(self, asset_id: str) -> AssetResult | None:
        """
        Run the decision engine for an already-created pending asset record.
        Called from the Celery task.
        """
        asset = await self._repo.get(asset_id)
        if not asset:
            logger.warning("Asset %s not found", asset_id)
            return None

        query = asset.prompt or f"scene {asset.scene_id}"
        request = SingleAssetRequest(
            storyboard_id=asset.storyboard_id,
            scene_id=asset.scene_id,
            asset_kind=AssetKind(asset.asset_kind),
            prompt=asset.prompt or query,
            negative_prompt=asset.negative_prompt or "",
        )
        await self._run_decision_engine(asset, request)
        return asset

    # ── Decision Engine ────────────────────────────────────────────────────────

    async def _run_decision_engine(
        self,
        asset: AssetResult,
        request: SingleAssetRequest,
    ) -> None:
        """
        Phase 1: Cache check
        Phase 2: Stock search
        Phase 3: AI generation (fallback)
        """
        await self._set_status(asset, AssetStatus.SEARCHING)
        query = request.search_query or request.prompt or f"scene {request.scene_id}"

        # ── Phase 1: Cache check ──────────────────────────────────────────────
        cache_key = self._cache.make_key(
            request.asset_kind, query, request.width, request.height
        )
        cached = await self._cache.get(cache_key)
        if cached:
            await self._apply_cache_hit(asset, cached)
            return

        # ── Phase 2: Stock search (skip for video/icon generated by user pref) ─
        stock_result = None
        if not request.force_generate and request.asset_kind != AssetKind.CHART:
            await self._log(asset, f"{_ts()} INFO  Searching stock providers for {query!r}")
            stock_result = await self._search.search(
                query,
                request.asset_kind,
                provider_preference=request.provider_preference,
                width=request.width,
                height=request.height,
            )

        if stock_result and stock_result.found:
            await self._log(asset, f"{_ts()} INFO  Stock hit from {stock_result.provider_name}")
            await self._set_status(asset, AssetStatus.DOWNLOADING)
            local_path, thumb_path = await self._downloader.download(stock_result)
            await self._cache.put(cache_key, stock_result, local_path=local_path, thumbnail_path=thumb_path)
            await self._apply_provider_result(asset, stock_result, local_path, thumb_path)
            return

        # ── Phase 3: AI generation ────────────────────────────────────────────
        await self._log(asset, f"{_ts()} INFO  No stock asset found — generating with AI")
        await self._set_status(asset, AssetStatus.GENERATING)

        gen_providers = self._registry.get_generator_providers()
        if not gen_providers:
            await self._fail(asset, "No generation providers available")
            return

        # Try generators in order: FLUX → SDXL → GPT_IMAGE → GEMINI → IDEOGRAM
        gen_result = None
        for gen_provider in gen_providers:
            gen_result = await gen_provider.fetch(
                query,
                request.asset_kind,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                width=request.width,
                height=request.height,
            )
            if gen_result.found:
                await self._log(asset, f"{_ts()} INFO  Generated with {gen_provider.name}")
                break
            await self._log(asset, f"{_ts()} WARN  Generator {gen_provider.name} failed: {gen_result.error}")

        if not gen_result or not gen_result.found:
            await self._fail(asset, "All AI generation providers failed")
            return

        local_path, thumb_path = await self._downloader.download(gen_result)
        await self._cache.put(cache_key, gen_result, local_path=local_path, thumbnail_path=thumb_path)
        await self._apply_provider_result(asset, gen_result, local_path, thumb_path)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _apply_cache_hit(self, asset: AssetResult, cached) -> None:
        await self._log(asset, f"{_ts()} INFO  Cache HIT — provider: {cached.provider}")
        asset.provider = cached.provider
        asset.source_url = cached.source_url
        asset.local_cache_path = cached.local_path
        asset.thumbnail_path = cached.thumbnail_path
        asset.file_size_bytes = cached.file_size_bytes
        asset.width = cached.width
        asset.height = cached.height
        if cached.width and cached.height:
            from math import gcd
            d = gcd(cached.width, cached.height)
            asset.aspect_ratio = f"{cached.width // d}:{cached.height // d}"
        asset.license = cached.license
        asset.tags = cached.tags or []
        asset.quality_score = cached.quality_score
        asset.status = AssetStatus.CACHED.value
        asset.completed_at = datetime.now(timezone.utc)
        asset.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _apply_provider_result(
        self,
        asset: AssetResult,
        result,
        local_path: str,
        thumb_path: str | None,
    ) -> None:
        asset.provider = result.provider_name
        asset.provider_asset_id = result.provider_asset_id
        asset.source_url = result.source_url
        asset.license = result.license.value if result.license else AssetLicense.UNKNOWN.value
        asset.generation_parameters = result.generation_parameters or {}
        asset.width = result.width
        asset.height = result.height
        asset.aspect_ratio = result.aspect_ratio
        asset.cost_estimate_usd = result.cost_estimate_usd
        asset.generation_time_ms = result.generation_time_ms
        asset.file_size_bytes = result.file_size_bytes
        asset.local_cache_path = local_path
        asset.thumbnail_path = thumb_path
        asset.tags = result.tags or []
        asset.quality_score = result.quality_score
        asset.relevance_score = result.relevance_score
        asset.status = AssetStatus.READY.value
        asset.completed_at = datetime.now(timezone.utc)
        asset.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _set_status(self, asset: AssetResult, status: AssetStatus) -> None:
        asset.status = status.value
        asset.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _log(self, asset: AssetResult, message: str) -> None:
        logs = list(asset.logs or [])
        logs.append(message)
        asset.logs = logs
        asset.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _fail(self, asset: AssetResult, reason: str) -> None:
        await self._log(asset, f"{_ts()} ERROR {reason}")
        asset.status = AssetStatus.FAILED.value
        asset.error_message = reason
        asset.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def _find_existing(
        self,
        storyboard_id: str,
        scene_id: str,
        asset_kind: AssetKind,
    ) -> AssetResult | None:
        from sqlalchemy import select
        from app.models.asset import AssetResult as AR
        stmt = (
            select(AR)
            .where(
                AR.storyboard_id == storyboard_id,
                AR.scene_id == scene_id,
                AR.asset_kind == asset_kind.value,
                AR.status.in_(["ready", "cached"]),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_scene_ids(self, storyboard_id: str) -> list[str]:
        """Extract scene IDs from a storyboard record."""
        from sqlalchemy import select, text
        from app.models.storyboard_result import StoryboardResult
        stmt = select(StoryboardResult).where(StoryboardResult.id == storyboard_id)
        result = await self._db.execute(stmt)
        sb = result.scalar_one_or_none()
        if not sb or not sb.scenes:
            return []
        scenes = sb.scenes if isinstance(sb.scenes, list) else []
        ids: list[str] = []
        for i, scene in enumerate(scenes):
            if isinstance(scene, dict):
                ids.append(scene.get("scene_id") or scene.get("id") or f"scene_{i + 1:03d}")
            else:
                ids.append(f"scene_{i + 1:03d}")
        return ids
