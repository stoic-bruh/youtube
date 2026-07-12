"""Google Custom Search research provider.

Production: Uses Google Custom Search API (requires GOOGLE_API_KEY + GOOGLE_CSE_ID).
Best for authoritative, indexed web results with rich snippet data.

Current: mock with Google-style high-credibility results.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class GoogleSearchProvider(ResearchProvider):
    name: ClassVar[str] = "google_search"
    description: ClassVar[str] = "Google Custom Search Engine"
    default_weight: ClassVar[float] = 1.1

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: async with httpx.AsyncClient() as client:
        #     params = {
        #         "key": self.config.api_key,
        #         "cx": self.config.extra.get("cse_id"),
        #         "q": request.topic,
        #         "num": 10,
        #     }
        #     resp = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
        #     items = resp.json().get("items", [])
        await asyncio.sleep(0.3)
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.70, 0.86),
            reference_count=7,
            keyword_count=8,
        )
