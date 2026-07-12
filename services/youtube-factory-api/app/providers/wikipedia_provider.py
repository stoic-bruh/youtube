"""Wikipedia research provider.

Production: Uses the Wikipedia REST API to fetch article summaries and full text,
then extracts structured information. No API key required.

Current: mock with Wikipedia-appropriate credibility scores.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchKeyword, ResearchReference, ResearchRequest, SourceType


class WikipediaProvider(ResearchProvider):
    name: ClassVar[str] = "wikipedia"
    description: ClassVar[str] = "Wikipedia article extraction"
    default_weight: ClassVar[float] = 0.9  # good for facts; lacks recency

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: async with httpx.AsyncClient() as client:
        #     search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(request.topic)}"
        #     summary_resp = await client.get(search_url)
        #     data = summary_resp.json()
        #     # extract: extract (summary), categories, sections, references
        await asyncio.sleep(0.25)
        result = generate_mock_result(
            self.name, request,
            confidence_range=(0.72, 0.84),
            reference_count=3,
            keyword_count=6,
        )
        # Wikipedia always contributes one high-credibility Wikipedia reference
        wiki_ref = ResearchReference(
            title=f"{request.topic.title()} — Wikipedia",
            url=f"https://en.wikipedia.org/wiki/{request.topic.replace(' ', '_')}",
            source_type=SourceType.WIKIPEDIA,
            author="Wikipedia contributors",
            snippet=f"Comprehensive encyclopedia article covering {request.topic}, including history, mechanisms, and applications.",
            credibility_score=0.88,
            citation_format=f"Wikipedia contributors. (2024). {request.topic.title()}. Wikipedia. https://en.wikipedia.org/wiki/{request.topic.replace(' ', '_')}",
            provider=self.name,
        )
        result.references = [wiki_ref] + result.references[:2]
        # Wikipedia summaries are more factual — boost fact count
        result.facts = result.facts[:5] if len(result.facts) >= 3 else result.facts
        return result
