"""Perplexity research provider.

Production: Uses Perplexity's sonar-large model which performs real-time web search.
Best for up-to-date references. Requires PERPLEXITY_API_KEY.

Current: mock with slightly higher reference credibility (web-search source).
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class PerplexityProvider(ResearchProvider):
    name: ClassVar[str] = "perplexity"
    description: ClassVar[str] = "Perplexity sonar real-time web research"
    default_weight: ClassVar[float] = 1.2

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: from openai import AsyncOpenAI
        # client = AsyncOpenAI(
        #     api_key=self.config.api_key,
        #     base_url="https://api.perplexity.ai",
        # )
        # response = await client.chat.completions.create(
        #     model="llama-3.1-sonar-large-128k-online",
        #     messages=[{"role": "user", "content": f"Research this YouTube topic: {request.topic}"}],
        # )
        # # Extract citations from response.citations
        await asyncio.sleep(0.6)
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.68, 0.84),
            reference_count=6,
            keyword_count=7,
        )
