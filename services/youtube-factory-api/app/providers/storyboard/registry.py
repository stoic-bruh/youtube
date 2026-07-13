"""Storyboard provider registry — semaphore-bounded parallel fetch."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.providers.storyboard.base import StoryboardProvider
from app.providers.storyboard.claude_provider import ClaudeStoryboardProvider
from app.providers.storyboard.gemini_provider import GeminiStoryboardProvider
from app.providers.storyboard.openai_provider import OpenAIStoryboardProvider
from app.providers.storyboard.openrouter_provider import OpenRouterStoryboardProvider
from app.schemas.storyboard import StoryboardProviderResult, StoryboardRequest

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 4

_PROVIDER_MAP: dict[str, type[StoryboardProvider]] = {
    "openai": OpenAIStoryboardProvider,
    "gemini": GeminiStoryboardProvider,
    "claude": ClaudeStoryboardProvider,
    "openrouter": OpenRouterStoryboardProvider,
}


class StoryboardProviderRegistry:
    """Runs multiple storyboard providers in parallel with concurrency control."""

    def __init__(self, provider_names: list[str]) -> None:
        self._providers: list[StoryboardProvider] = []
        for name in provider_names:
            cls = _PROVIDER_MAP.get(name.lower())
            if cls:
                self._providers.append(cls())
            else:
                logger.warning("Unknown storyboard provider: %r — skipping", name)

    async def fetch_all(
        self,
        request: StoryboardRequest,
        script_data: dict[str, Any],
    ) -> list[StoryboardProviderResult]:
        """Run all configured providers concurrently and return all results."""
        sem = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _bounded(p: StoryboardProvider) -> StoryboardProviderResult:
            async with sem:
                return await p.fetch(request, script_data)

        results = await asyncio.gather(
            *[_bounded(p) for p in self._providers], return_exceptions=False
        )
        return list(results)
