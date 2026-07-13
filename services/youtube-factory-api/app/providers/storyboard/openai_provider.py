"""OpenAI storyboard provider (mock delegation until API key wired)."""
from __future__ import annotations

from typing import Any

from app.providers.storyboard.base import StoryboardProvider
from app.providers.storyboard.mock_base import generate_mock_storyboard
from app.schemas.storyboard import StoryboardProviderResult, StoryboardRequest


class OpenAIStoryboardProvider(StoryboardProvider):
    name = "openai"

    async def _fetch_raw(
        self,
        request: StoryboardRequest,
        script_data: dict[str, Any],
    ) -> StoryboardProviderResult:
        return generate_mock_storyboard("openai", request, script_data)
