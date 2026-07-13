"""Comprehensive unit tests for the Asset Intelligence Engine."""
from __future__ import annotations

import pytest

from app.providers.asset.mock_base import MockAssetGenerator
from app.providers.asset.wikimedia_provider import WikimediaProvider
from app.providers.asset.flux_provider import FluxProvider
from app.providers.asset.lucide_provider import LucideProvider
from app.providers.asset.pexels_video_provider import PexelsVideoProvider
from app.providers.asset.registry import AssetProviderRegistry
from app.services.asset_search_engine import AssetSearchEngine
from app.services.asset_cache import _make_key
from app.schemas.asset import (
    AssetKind,
    AssetLicense,
    AssetProviderName,
    AssetProviderResult,
    AssetRequest,
    AssetResultSchema,
    AssetStatus,
    SingleAssetRequest,
)


# ── Mock generator tests ─────────────────────────────────────────────────────────

class TestMockGenerator:
    def test_generates_valid_result_for_stock_provider(self):
        result = MockAssetGenerator().generate("wikimedia", "mountain landscape", AssetKind.IMAGE)
        assert isinstance(result, AssetProviderResult)
        assert result.provider_name == "wikimedia"
        # Deterministic seed for this query happens to find a result
        if result.found:
            assert result.width and result.height
            assert result.aspect_ratio
            assert result.cost_estimate_usd == 0.0

    def test_generator_provider_always_has_cost_and_params(self):
        result = MockAssetGenerator().generate("flux", "a red bicycle", AssetKind.IMAGE)
        assert result.found is True
        assert result.cost_estimate_usd > 0
        assert "steps" in result.generation_parameters
        assert "seed" in result.generation_parameters
        assert result.license == AssetLicense.GENERATED

    def test_icon_provider_dimensions_are_small(self):
        result = MockAssetGenerator().generate("lucide", "search icon", AssetKind.ICON)
        if result.found:
            assert result.width <= 128 and result.height <= 128
            assert result.license in {AssetLicense.MIT, AssetLicense.CC0}

    def test_video_provider_uses_video_dims(self):
        result = MockAssetGenerator().generate("pexels_video", "ocean waves", AssetKind.VIDEO)
        if result.found:
            assert (result.width, result.height) in [(1920, 1080), (1280, 720), (3840, 2160)]

    def test_deterministic_for_same_seed(self):
        r1 = MockAssetGenerator().generate("flux", "a cat", AssetKind.IMAGE)
        r2 = MockAssetGenerator().generate("flux", "a cat", AssetKind.IMAGE)
        assert r1.provider_asset_id == r2.provider_asset_id
        assert r1.cost_estimate_usd == r2.cost_estimate_usd

    def test_different_scene_index_changes_output(self):
        r1 = MockAssetGenerator().generate("flux", "a cat", AssetKind.IMAGE, scene_index=0)
        r2 = MockAssetGenerator().generate("flux", "a cat", AssetKind.IMAGE, scene_index=1)
        assert r1.provider_asset_id != r2.provider_asset_id

    def test_not_found_result_has_no_dimensions(self):
        # Search many seeds until we deterministically find a miss for a stock provider
        found_a_miss = False
        for i in range(50):
            r = MockAssetGenerator().generate("unsplash", "test query", AssetKind.IMAGE, scene_index=i)
            if not r.found:
                found_a_miss = True
                assert r.width is None
                assert r.error
                break
        assert found_a_miss


# ── Provider tests ────────────────────────────────────────────────────────────

class TestProviders:
    @pytest.mark.asyncio
    async def test_wikimedia_provider_fetch(self):
        provider = WikimediaProvider()
        result = await provider.fetch("space nebula", AssetKind.IMAGE)
        assert result.provider_name == "wikimedia"
        assert result.generation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_flux_provider_fetch(self):
        provider = FluxProvider()
        result = await provider.fetch("cyberpunk city", AssetKind.IMAGE, prompt="cyberpunk city at night")
        assert result.provider_name == "flux"
        assert result.found is True

    @pytest.mark.asyncio
    async def test_lucide_icon_provider_fetch(self):
        provider = LucideProvider()
        result = await provider.fetch("play button", AssetKind.ICON)
        assert result.provider_name == "lucide"

    @pytest.mark.asyncio
    async def test_pexels_video_provider_fetch(self):
        provider = PexelsVideoProvider()
        result = await provider.fetch("city traffic", AssetKind.VIDEO)
        assert result.provider_name == "pexels_video"

    def test_provider_declares_supported_kinds(self):
        assert AssetKind.IMAGE in WikimediaProvider.supported_kinds
        assert AssetKind.ICON in LucideProvider.supported_kinds


# ── Registry tests ────────────────────────────────────────────────────────────

class TestRegistry:
    def test_get_known_provider(self):
        registry = AssetProviderRegistry()
        provider = registry.get(AssetProviderName.FLUX)
        assert provider is not None
        assert provider.name == "flux"

    def test_get_unknown_provider_returns_none(self):
        registry = AssetProviderRegistry()
        assert registry.get("not_a_real_provider") is None

    def test_get_stock_providers_for_image(self):
        registry = AssetProviderRegistry()
        providers = registry.get_stock_providers(AssetKind.IMAGE)
        names = {p.name for p in providers}
        assert names == {"wikimedia", "pexels", "pixabay", "unsplash"}

    def test_get_stock_providers_for_video(self):
        registry = AssetProviderRegistry()
        providers = registry.get_stock_providers(AssetKind.VIDEO)
        names = {p.name for p in providers}
        assert names == {"pexels_video", "pixabay_video", "mixkit"}

    def test_get_stock_providers_for_icon(self):
        registry = AssetProviderRegistry()
        providers = registry.get_stock_providers(AssetKind.ICON)
        names = {p.name for p in providers}
        assert names == {"lucide", "heroicons", "material_icons"}

    def test_get_generator_providers_default_order(self):
        registry = AssetProviderRegistry()
        providers = registry.get_generator_providers()
        names = [p.name for p in providers]
        assert names == ["flux", "sdxl", "gpt_image", "gemini_image", "ideogram"]

    def test_get_generator_providers_honors_preference(self):
        registry = AssetProviderRegistry()
        providers = registry.get_generator_providers([AssetProviderName.IDEOGRAM, AssetProviderName.SDXL])
        names = [p.name for p in providers]
        # Preferred providers come first, in the order given, remaining fill in default order
        assert names[:2] == ["ideogram", "sdxl"]
        assert set(names) == {"flux", "sdxl", "gpt_image", "gemini_image", "ideogram"}

    def test_get_generator_providers_ignores_non_generator_preference(self):
        registry = AssetProviderRegistry()
        providers = registry.get_generator_providers([AssetProviderName.WIKIMEDIA, AssetProviderName.FLUX])
        names = [p.name for p in providers]
        # wikimedia isn't a generator so it's dropped, flux is preferred first
        assert names[0] == "flux"
        assert "wikimedia" not in names

    def test_is_generator_is_video_is_icon(self):
        registry = AssetProviderRegistry()
        assert registry.is_generator(AssetProviderName.FLUX) is True
        assert registry.is_generator(AssetProviderName.WIKIMEDIA) is False
        assert registry.is_video_provider(AssetProviderName.MIXKIT) is True
        assert registry.is_icon_provider(AssetProviderName.LUCIDE) is True


# ── Search engine tests ────────────────────────────────────────────────────────

class TestSearchEngine:
    @pytest.mark.asyncio
    async def test_search_returns_result_or_none(self):
        engine = AssetSearchEngine()
        result = await engine.search("mountain sunrise", AssetKind.IMAGE)
        assert result is None or isinstance(result, AssetProviderResult)

    @pytest.mark.asyncio
    async def test_search_respects_provider_preference_order(self):
        engine = AssetSearchEngine()
        # Force through only wikimedia by excluding all others via preference
        result = await engine.search(
            "test scene", AssetKind.IMAGE, provider_preference=[AssetProviderName.WIKIMEDIA],
        )
        if result is not None:
            assert result.provider_name == "wikimedia"

    @pytest.mark.asyncio
    async def test_search_filters_out_generators_from_preference(self):
        engine = AssetSearchEngine()
        # Even if a generator is included in preference, search should never return it
        result = await engine.search(
            "abstract shapes", AssetKind.IMAGE,
            provider_preference=[AssetProviderName.FLUX, AssetProviderName.WIKIMEDIA],
        )
        if result is not None:
            assert result.provider_name != "flux"

    @pytest.mark.asyncio
    async def test_search_video_kind_uses_video_providers(self):
        engine = AssetSearchEngine()
        result = await engine.search("drone footage of city", AssetKind.VIDEO)
        if result is not None:
            assert result.provider_name in {"pexels_video", "pixabay_video", "mixkit"}

    @pytest.mark.asyncio
    async def test_search_enforces_quality_threshold(self):
        engine = AssetSearchEngine()
        result = await engine.search(
            "impossible quality bar", AssetKind.IMAGE, min_quality=1.5, min_relevance=0.0,
        )
        assert result is None


# ── Cache key tests ────────────────────────────────────────────────────────────

class TestCacheKey:
    def test_cache_key_is_deterministic(self):
        k1 = _make_key(AssetKind.IMAGE, "mountain sunrise", 1920, 1080)
        k2 = _make_key(AssetKind.IMAGE, "mountain sunrise", 1920, 1080)
        assert k1 == k2

    def test_cache_key_is_case_and_whitespace_insensitive(self):
        k1 = _make_key(AssetKind.IMAGE, "Mountain Sunrise", 1920, 1080)
        k2 = _make_key(AssetKind.IMAGE, "  mountain sunrise  ", 1920, 1080)
        assert k1 == k2

    def test_cache_key_differs_by_kind(self):
        k1 = _make_key(AssetKind.IMAGE, "mountain sunrise", 1920, 1080)
        k2 = _make_key(AssetKind.VIDEO, "mountain sunrise", 1920, 1080)
        assert k1 != k2

    def test_cache_key_differs_by_dimensions(self):
        k1 = _make_key(AssetKind.IMAGE, "mountain sunrise", 1920, 1080)
        k2 = _make_key(AssetKind.IMAGE, "mountain sunrise", 1280, 720)
        assert k1 != k2

    def test_cache_key_length(self):
        key = _make_key(AssetKind.IMAGE, "test", 1920, 1080)
        assert len(key) == 64


# ── Schema tests ────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_asset_request_defaults(self):
        req = AssetRequest(storyboard_id="sb-1")
        assert req.asset_kinds == [AssetKind.IMAGE]
        assert AssetProviderName.WIKIMEDIA in req.providers
        assert req.force_generate is False

    def test_single_asset_request_defaults(self):
        req = SingleAssetRequest(storyboard_id="sb-1", scene_id="scene_001", prompt="a scenic view")
        assert req.asset_kind == AssetKind.IMAGE
        assert req.width == 1920
        assert req.height == 1080

    def test_asset_result_schema_from_attributes(self):
        result = AssetResultSchema(
            id="asset-1",
            storyboard_id="sb-1",
            scene_id="scene_001",
            asset_kind=AssetKind.IMAGE,
            status=AssetStatus.PENDING,
        )
        assert result.status == AssetStatus.PENDING
        assert result.tags == []
        assert result.logs == []

    def test_enum_values(self):
        assert AssetKind.IMAGE.value == "image"
        assert AssetStatus.CACHED.value == "cached"
        assert AssetLicense.PUBLIC_DOMAIN.value == "public_domain"
        assert AssetProviderName.FLUX.value == "flux"

    def test_provider_result_defaults(self):
        result = AssetProviderResult(provider_name="test")
        assert result.found is False
        assert result.asset_kind == AssetKind.IMAGE
        assert result.license == AssetLicense.UNKNOWN
        assert result.tags == []
