"""DuckDuckGo research provider.

Production: Uses the DuckDuckGo Instant Answer API (no key required) and/or
the duckduckgo-search Python library for organic results. Good for finding
current discussions, tutorials, and community resources.

Current: mock.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class DuckDuckGoProvider(ResearchProvider):
    name: ClassVar[str] = "duckduckgo"
    description: ClassVar[str] = "DuckDuckGo instant answers and search"
    default_weight: ClassVar[float] = 0.7  # weaker structural output, strong for recency

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: from duckduckgo_search import AsyncDDGS
        # async with AsyncDDGS() as ddgs:
        #     text_results = [r async for r in ddgs.text(request.topic, max_results=10)]
        #     instant_answer = await ddgs.answers(request.topic)
        await asyncio.sleep(0.2)
        result = generate_mock_result(
            self.name, request,
            confidence_range=(0.55, 0.70),
            reference_count=4,
            keyword_count=6,
        )
        # DuckDuckGo excels at keyword discovery — boost keyword count
        extra_kw_terms = [
            f"{request.topic} tutorial",
            f"{request.topic} for beginners",
            f"how to {request.topic}",
            f"best {request.topic} tools",
        ]
        from app.schemas.research import ResearchKeyword
        import random
        rng = random.Random(hash(request.topic + self.name))
        for term in extra_kw_terms:
            result.keywords.append(ResearchKeyword(
                term=term,
                relevance=round(rng.uniform(0.35, 0.65), 3),
                search_volume=rng.randint(500, 50000),
                difficulty=rng.choice(["low", "medium"]),
                semantic_tags=["longtail", "youtube"],
            ))
        return result
