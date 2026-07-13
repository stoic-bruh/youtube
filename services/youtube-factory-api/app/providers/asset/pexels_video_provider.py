"""Pexels Videos stock video provider (mock implementation)."""
from app.providers.asset.base import AssetProvider
from app.providers.asset.mock_base import MockAssetGenerator
from app.schemas.asset import AssetKind, AssetProviderResult


class PexelsVideoProvider(AssetProvider):
    name = "pexels_video"
    provider_type = "stock"
    supported_kinds = [AssetKind.VIDEO]

    async def _fetch_raw(
        self, query: str, asset_kind: AssetKind, *,
        prompt: str = "", negative_prompt: str = "",
        width: int = 1920, height: int = 1080, **kwargs,
    ) -> AssetProviderResult:
        return MockAssetGenerator().generate(
            self.name, query, AssetKind.VIDEO,
            prompt=prompt, negative_prompt=negative_prompt,
            width=width, height=height, **kwargs,
        )
