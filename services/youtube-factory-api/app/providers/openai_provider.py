"""OpenAI research provider.

Production: Uses GPT-4o to generate structured research JSON via a system prompt
that enforces the ProviderResult schema. Requires OPENAI_API_KEY.

Current implementation: high-quality mock with OpenAI-style confidence calibration.
Replace `_fetch_raw` with the real API call when implementing.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class OpenAIProvider(ResearchProvider):
    name: ClassVar[str] = "openai"
    description: ClassVar[str] = "GPT-4o structured research generation"
    default_weight: ClassVar[float] = 1.5  # highest weight — most reliable for structured output

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO (Phase 3 — OpenAI implementation):
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI(api_key=self.config.api_key)
        # response = await client.chat.completions.create(
        #     model="gpt-4o",
        #     response_format={"type": "json_object"},
        #     messages=[SYSTEM_PROMPT, {"role": "user", "content": request.topic}],
        # )
        # return ProviderResult(**json.loads(response.choices[0].message.content))
        await asyncio.sleep(0.3)  # simulate latency
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.78, 0.92),
            reference_count=6,
            keyword_count=10,
        )
