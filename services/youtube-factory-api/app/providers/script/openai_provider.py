"""OpenAI script provider — mock implementation using the deterministic generator."""
from __future__ import annotations

from app.providers.script.base import ScriptProvider
from app.providers.script.mock_base import generate_mock_script
from app.schemas.script import ScriptProviderResult, ScriptRequest


class OpenAIScriptProvider(ScriptProvider):
    """OpenAI GPT-4o script provider.

    Uses the mock generator until a real API key is configured.
    """

    name: str = "openai"

    async def _fetch_raw(self, request: ScriptRequest) -> ScriptProviderResult:
        return generate_mock_script(request, self.name)
