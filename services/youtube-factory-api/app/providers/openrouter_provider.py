"""OpenRouter research provider.

Production: Routes to multiple LLMs via OpenRouter (mistral, llama, etc.).
Uses openai-compatible API with OPENROUTER_API_KEY.

Current: mock.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class OpenRouterProvider(ResearchProvider):
    name: ClassVar[str] = "openrouter"
    description: ClassVar[str] = "OpenRouter LLM gateway research"
    default_weight: ClassVar[float] = 1.0

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: from openai import AsyncOpenAI
        # client = AsyncOpenAI(
        #     api_key=self.config.api_key,
        #     base_url="https://openrouter.ai/api/v1",
        # )
        # response = await client.chat.completions.create(
        #     model="mistralai/mixtral-8x7b-instruct",
        #     messages=build_messages(request),
        # )
        await asyncio.sleep(0.35)
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.60, 0.78),
            reference_count=4,
            keyword_count=8,
        )
