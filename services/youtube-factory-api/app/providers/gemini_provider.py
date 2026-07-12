"""Gemini research provider.

Production: Uses Google Gemini 1.5 Pro via the google-generativeai SDK.
Requires GEMINI_API_KEY.

Current: mock.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.providers.base import ResearchProvider
from app.providers.mock_base import generate_mock_result
from app.schemas.research import ProviderResult, ResearchRequest


class GeminiProvider(ResearchProvider):
    name: ClassVar[str] = "gemini"
    description: ClassVar[str] = "Google Gemini 1.5 Pro research"
    default_weight: ClassVar[float] = 1.3

    async def _fetch_raw(self, request: ResearchRequest) -> ProviderResult:
        # TODO: import google.generativeai as genai
        # genai.configure(api_key=self.config.api_key)
        # model = genai.GenerativeModel("gemini-1.5-pro")
        # response = await model.generate_content_async(build_prompt(request))
        await asyncio.sleep(0.4)
        return generate_mock_result(
            self.name, request,
            confidence_range=(0.74, 0.88),
            reference_count=5,
            keyword_count=9,
        )
