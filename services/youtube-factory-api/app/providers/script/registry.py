"""Registry that loads and coordinates all script providers."""
from __future__ import annotations

import asyncio
import logging

from app.providers.script.base import ScriptProvider
from app.providers.script.claude_provider import ClaudeScriptProvider
from app.providers.script.gemini_provider import GeminiScriptProvider
from app.providers.script.openai_provider import OpenAIScriptProvider
from app.providers.script.openrouter_provider import OpenRouterScriptProvider
from app.schemas.script import ScriptProviderResult, ScriptRequest

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[ScriptProvider]] = {
    "openai": OpenAIScriptProvider,
    "gemini": GeminiScriptProvider,
    "claude": ClaudeScriptProvider,
    "openrouter": OpenRouterScriptProvider,
}


class ScriptProviderRegistry:
    """Lazily instantiates and runs script providers in parallel."""

    def __init__(self) -> None:
        self._instances: dict[str, ScriptProvider] = {}

    def _get_provider(self, name: str) -> ScriptProvider | None:
        if name not in _REGISTRY:
            logger.warning("Unknown script provider: %r", name)
            return None
        if name not in self._instances:
            self._instances[name] = _REGISTRY[name]()
        return self._instances[name]

    async def fetch_all(
        self,
        request: ScriptRequest,
        provider_names: list[str],
        max_concurrent: int = 4,
    ) -> list[ScriptProviderResult]:
        """Fetch from all named providers concurrently, bounded by semaphore."""
        sem = asyncio.Semaphore(max_concurrent)

        async def _fetch_one(name: str) -> ScriptProviderResult:
            provider = self._get_provider(name)
            if not provider:
                return ScriptProviderResult(
                    provider_name=name,
                    topic=request.topic,
                    error=f"Unknown provider: {name!r}",
                )
            async with sem:
                return await provider.fetch(request)

        tasks = [asyncio.create_task(_fetch_one(n)) for n in provider_names]
        return list(await asyncio.gather(*tasks))
