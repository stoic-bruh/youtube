"""Heroicons provider (mock implementation)."""
from app.providers.asset.base import AssetProvider
from app.providers.asset.mock_base import MockAssetGenerator
from app.schemas.asset import AssetKind, AssetProviderResult


class HeroiconsProvider(AssetProvider):
    name = "heroicons"
    provider_type = "icon"
    supported_kinds = [AssetKind.ICON, AssetKind.SVG]

    async def _fetch_raw(
        self, query: str, asset_kind: AssetKind, *,
        prompt: str = "", negative_prompt: str = "",
        width: int = 48, height: int = 48, **kwargs,
    ) -> AssetProviderResult:
        return MockAssetGenerator().generate(
            self.name, query, AssetKind.ICON,
            prompt=prompt, negative_prompt=negative_prompt,
            width=width, height=height, **kwargs,
        )
