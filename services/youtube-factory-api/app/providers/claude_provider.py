"""Claude (Anthropic) research provider.

Production: Uses claude-3-5-sonnet via the anthropic SDK.
Requires ANTHROPIC_API_KEY.

Current: mock.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class ClaudeProvider(ResearchProvider):
    name: ClassVar[str] = "claude"
    description: ClassVar[str] = "Anthropic Claude 3.5 Sonnet research"
    default_weight: ClassVar[float] = 1.4

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: from anthropic import AsyncAnthropic
        # client = AsyncAnthropic(api_key=self.config.api_key)
        # message = await client.messages.create(
        #     model="claude-3-5-sonnet-20241022",
        #     max_tokens=4096,
        #     messages=[{"role": "user", "content": build_research_prompt(request)}],
        # )
        await asyncio.sleep(0.5)
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.76, 0.90),
            reference_count=5,
            keyword_count=9,
        )
