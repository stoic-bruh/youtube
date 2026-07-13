"""Asset provider registry — routes requests to the right provider."""
from __future__ import annotations

import logging

from app.providers.asset.base import AssetProvider
from app.providers.asset.flux_provider import FluxProvider
from app.providers.asset.sdxl_provider import SDXLProvider
from app.providers.asset.gpt_image_provider import GPTImageProvider
from app.providers.asset.gemini_image_provider import GeminiImageProvider
from app.providers.asset.ideogram_provider import IdeogramProvider
from app.providers.asset.wikimedia_provider import WikimediaProvider
from app.providers.asset.unsplash_provider import UnsplashProvider
from app.providers.asset.pixabay_provider import PixabayProvider
from app.providers.asset.pexels_provider import PexelsProvider
from app.providers.asset.pexels_video_provider import PexelsVideoProvider
from app.providers.asset.pixabay_video_provider import PixabayVideoProvider
from app.providers.asset.mixkit_provider import MixkitProvider
from app.providers.asset.lucide_provider import LucideProvider
from app.providers.asset.heroicons_provider import HeroiconsProvider
from app.providers.asset.material_icons_provider import MaterialIconsProvider
from app.schemas.asset import AssetKind, AssetProviderName

logger = logging.getLogger(__name__)

_PROVIDER_MAP: dict[str, type[AssetProvider]] = {
    AssetProviderName.FLUX: FluxProvider,
    AssetProviderName.SDXL: SDXLProvider,
    AssetProviderName.GPT_IMAGE: GPTImageProvider,
    AssetProviderName.GEMINI_IMAGE: GeminiImageProvider,
    AssetProviderName.IDEOGRAM: IdeogramProvider,
    AssetProviderName.WIKIMEDIA: WikimediaProvider,
    AssetProviderName.UNSPLASH: UnsplashProvider,
    AssetProviderName.PIXABAY: PixabayProvider,
    AssetProviderName.PEXELS: PexelsProvider,
    AssetProviderName.PEXELS_VIDEO: PexelsVideoProvider,
    AssetProviderName.PIXABAY_VIDEO: PixabayVideoProvider,
    AssetProviderName.MIXKIT: MixkitProvider,
    AssetProviderName.LUCIDE: LucideProvider,
    AssetProviderName.HEROICONS: HeroiconsProvider,
    AssetProviderName.MATERIAL_ICONS: MaterialIconsProvider,
}

# Providers that can generate (vs. search)
_GENERATOR_PROVIDERS = {
    AssetProviderName.FLUX,
    AssetProviderName.SDXL,
    AssetProviderName.GPT_IMAGE,
    AssetProviderName.GEMINI_IMAGE,
    AssetProviderName.IDEOGRAM,
}

# Providers that return stock video
_VIDEO_PROVIDERS = {
    AssetProviderName.PEXELS_VIDEO,
    AssetProviderName.PIXABAY_VIDEO,
    AssetProviderName.MIXKIT,
}

# Providers that return icons
_ICON_PROVIDERS = {
    AssetProviderName.LUCIDE,
    AssetProviderName.HEROICONS,
    AssetProviderName.MATERIAL_ICONS,
}


class AssetProviderRegistry:
    """Routes asset requests to the appropriate provider by kind and name."""

    def get(self, name: str | AssetProviderName) -> AssetProvider | None:
        """Return an instantiated provider by name, or None if unknown."""
        cls = _PROVIDER_MAP.get(name)
        if cls is None:
            logger.warning("Unknown asset provider: %r — skipping", name)
            return None
        return cls()

    def get_stock_providers(self, asset_kind: AssetKind) -> list[AssetProvider]:
        """Return all stock (non-generating) providers for the given kind."""
        if asset_kind == AssetKind.VIDEO:
            names = list(_VIDEO_PROVIDERS)
        elif asset_kind == AssetKind.ICON:
            names = list(_ICON_PROVIDERS)
        elif asset_kind in (AssetKind.IMAGE, AssetKind.SVG, AssetKind.CHART, AssetKind.MAP):
            names = [
                AssetProviderName.WIKIMEDIA,
                AssetProviderName.PEXELS,
                AssetProviderName.PIXABAY,
                AssetProviderName.UNSPLASH,
            ]
        else:
            names = []
        return [p for name in names if (p := self.get(name)) is not None]

    def get_generator_providers(self) -> list[AssetProvider]:
        """Return AI image-generation providers in quality order."""
        names = [
            AssetProviderName.FLUX,
            AssetProviderName.SDXL,
            AssetProviderName.GPT_IMAGE,
            AssetProviderName.GEMINI_IMAGE,
            AssetProviderName.IDEOGRAM,
        ]
        return [p for name in names if (p := self.get(name)) is not None]

    def is_generator(self, name: str) -> bool:
        return name in _GENERATOR_PROVIDERS

    def is_video_provider(self, name: str) -> bool:
        return name in _VIDEO_PROVIDERS

    def is_icon_provider(self, name: str) -> bool:
        return name in _ICON_PROVIDERS
