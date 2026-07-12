"""Provider registry — manages available providers and creates instances on demand."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.providers.base import ProviderConfig, ResearchProvider
from app.schemas.research import ProviderName, ProviderResult, ResearchRequest

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular deps
_PROVIDER_MAP: dict[str, type[ResearchProvider]] | None = None


def _build_provider_map() -> dict[str, type[ResearchProvider]]:
    from app.providers.openai_provider import OpenAIProvider
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.claude_provider import ClaudeProvider
    from app.providers.openrouter_provider import OpenRouterProvider
    from app.providers.perplexity_provider import PerplexityProvider
    from app.providers.wikipedia_provider import WikipediaProvider
    from app.providers.duckduckgo_provider import DuckDuckGoProvider
    from app.providers.google_search_provider import GoogleSearchProvider

    return {
        ProviderName.OPENAI: OpenAIProvider,
        ProviderName.GEMINI: GeminiProvider,
        ProviderName.CLAUDE: ClaudeProvider,
        ProviderName.OPENROUTER: OpenRouterProvider,
        ProviderName.PERPLEXITY: PerplexityProvider,
        ProviderName.WIKIPEDIA: WikipediaProvider,
        ProviderName.DUCKDUCKGO: DuckDuckGoProvider,
        ProviderName.GOOGLE_SEARCH: GoogleSearchProvider,
    }


class ProviderRegistry:
    """Instantiates and manages research providers."""

    def __init__(self) -> None:
        self._instances: dict[str, ResearchProvider] = {}

    def get(self, name: str, config: ProviderConfig | None = None) -> ResearchProvider:
        """Get or create a provider instance by name."""
        global _PROVIDER_MAP
        if _PROVIDER_MAP is None:
            _PROVIDER_MAP = _build_provider_map()

        if name not in self._instances:
            cls = _PROVIDER_MAP.get(name)
            if cls is None:
                raise ValueError(f"Unknown provider: {name!r}. Available: {list(_PROVIDER_MAP)}")
            self._instances[name] = cls(config)
        return self._instances[name]

    def list_available(self) -> list[str]:
        global _PROVIDER_MAP
        if _PROVIDER_MAP is None:
            _PROVIDER_MAP = _build_provider_map()
        return list(_PROVIDER_MAP.keys())

    async def fetch_all(
        self,
        request: ResearchRequest,
        provider_names: list[str],
        *,
        max_concurrent: int = 4,
    ) -> list[ProviderResult]:
        """Fetch from multiple providers concurrently, bounded by semaphore."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded_fetch(name: str) -> ProviderResult:
            async with semaphore:
                provider = self.get(name)
                logger.info("Fetching from provider: %s", name)
                return await provider.fetch(request)

        tasks = [_bounded_fetch(name) for name in provider_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: list[ProviderResult] = []
        for name, result in zip(provider_names, results):
            if isinstance(result, Exception):
                out.append(ProviderResult(
                    provider_name=name,
                    topic=request.topic,
                    error=str(result),
                    confidence=0.0,
                ))
            else:
                out.append(result)
        return out
