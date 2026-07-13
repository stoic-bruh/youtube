"""AssetSearchEngine — searches stock providers in priority order."""
from __future__ import annotations

import logging

from app.providers.asset.registry import AssetProviderRegistry
from app.schemas.asset import AssetKind, AssetProviderName, AssetProviderResult

logger = logging.getLogger(__name__)

_DEFAULT_STOCK_ORDER = [
    AssetProviderName.WIKIMEDIA,
    AssetProviderName.PEXELS,
    AssetProviderName.PIXABAY,
    AssetProviderName.UNSPLASH,
]
_DEFAULT_VIDEO_ORDER = [
    AssetProviderName.PEXELS_VIDEO,
    AssetProviderName.PIXABAY_VIDEO,
    AssetProviderName.MIXKIT,
]
_DEFAULT_ICON_ORDER = [
    AssetProviderName.LUCIDE,
    AssetProviderName.HEROICONS,
    AssetProviderName.MATERIAL_ICONS,
]


class AssetSearchEngine:
    """Searches stock providers in priority order, returning the first acceptable result."""

    def __init__(self, registry: AssetProviderRegistry | None = None) -> None:
        self._registry = registry or AssetProviderRegistry()

    async def search(
        self,
        query: str,
        asset_kind: AssetKind,
        *,
        provider_preference: list[AssetProviderName] | None = None,
        width: int = 1920,
        height: int = 1080,
        min_quality: float = 0.6,
        min_relevance: float = 0.5,
    ) -> AssetProviderResult | None:
        """
        Search stock providers in preference order.
        Returns the first result that meets quality and relevance thresholds,
        or None if no acceptable asset is found.
        """
        if provider_preference:
            # Filter to only non-generator providers from the preference list
            ordered = [
                n for n in provider_preference
                if not self._registry.is_generator(n)
            ]
        elif asset_kind == AssetKind.VIDEO:
            ordered = list(_DEFAULT_VIDEO_ORDER)
        elif asset_kind == AssetKind.ICON:
            ordered = list(_DEFAULT_ICON_ORDER)
        else:
            ordered = list(_DEFAULT_STOCK_ORDER)

        for provider_name in ordered:
            provider = self._registry.get(provider_name)
            if provider is None:
                continue

            logger.debug("Searching %s for %r kind=%s", provider_name, query, asset_kind)
            result = await provider.fetch(
                query,
                asset_kind,
                prompt=query,
                width=width,
                height=height,
            )

            if not result.found:
                logger.debug("%s: no result for %r", provider_name, query)
                continue

            if result.quality_score < min_quality:
                logger.debug(
                    "%s: quality %.2f below threshold %.2f",
                    provider_name, result.quality_score, min_quality,
                )
                continue

            if result.relevance_score < min_relevance:
                logger.debug(
                    "%s: relevance %.2f below threshold %.2f",
                    provider_name, result.relevance_score, min_relevance,
                )
                continue

            logger.info(
                "Stock search HIT: provider=%s query=%r quality=%.2f relevance=%.2f",
                provider_name, query, result.quality_score, result.relevance_score,
            )
            return result

        logger.info("Stock search MISS for %r kind=%s", query, asset_kind)
        return None
