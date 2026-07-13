"""Unit tests for the Script Service, providers, and repository."""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.schemas.script import (
    ScriptRequest,
    ScriptStyle,
    ScriptTone,
    ScriptProviderName,
    ScriptSection,
    ScriptSectionType,
    ScriptStatus,
    ScriptProviderResult,
)
from app.providers.script.mock_base import generate_mock_script, _count_words, _seed, SeededRandom
from app.providers.script.openai_provider import OpenAIScriptProvider
from app.providers.script.gemini_provider import GeminiScriptProvider
from app.providers.script.claude_provider import ClaudeScriptProvider
from app.providers.script.openrouter_provider import OpenRouterScriptProvider


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_request() -> ScriptRequest:
    return ScriptRequest(
        topic="machine learning",
        style=ScriptStyle.EDUCATIONAL,
        tone=ScriptTone.ENGAGING,
        language="en",
        target_audience="general audience",
        target_duration_minutes=10,
        providers=[ScriptProviderName.OPENAI, ScriptProviderName.CLAUDE],
    )


@pytest.fixture
def mock_script_result() -> ScriptProviderResult:
    return ScriptProviderResult(
        provider_name="openai",
        topic="machine learning",
        title="Understanding Machine Learning",
        hook="Here is a compelling hook about machine learning...",
        introduction="An introduction to machine learning...",
        outro="Thank you for watching...",
        call_to_action="Like and subscribe...",
        sections=[
            ScriptSection(
                section_type=ScriptSectionType.MAIN_POINT,
                title="What is Machine Learning",
                content="Machine learning is a field of artificial intelligence...",
                word_count=50,
                duration_seconds=23.0,
                order=0,
            )
        ],
        word_count=500,
        estimated_duration_seconds=230,
        reading_time_seconds=150,
        scene_count=5,
        pacing_wpm=130.0,
        confidence=0.91,
    )


def make_mock_repo(script_obj=None):
    """Build a mock ScriptRepository with sensible defaults."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=script_obj)
    repo.create = AsyncMock(return_value=script_obj)
    repo.update = AsyncMock(return_value=script_obj)
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock(return_value=([], 0))
    repo._db = MagicMock()
    repo._db.flush = AsyncMock()
    return repo


def make_db_script(script_id: str = "test-id") -> MagicMock:
    """Create a minimal mock DB ScriptResult object."""
    obj = MagicMock()
    obj.id = script_id
    obj.topic = "machine learning"
    obj.research_id = None
    obj.status = "pending"
    obj.style = "educational"
    obj.tone = "engaging"
    obj.language = "en"
    obj.target_audience = "general audience"
    obj.target_duration_minutes = 10
    obj.providers = ["openai", "claude"]
    obj.used_providers = []
    obj.logs = ["[00:00:00] INFO  Script job created."]
    obj.sections = []
    obj.job_id = "job-123"
    obj.created_at = datetime.now(timezone.utc)
    obj.updated_at = datetime.now(timezone.utc)
    return obj


# ── Mock base tests ────────────────────────────────────────────────────────────

class TestMockBase:
    def test_seed_is_deterministic(self):
        s1 = _seed("openai", "quantum computing", "educational")
        s2 = _seed("openai", "quantum computing", "educational")
        assert s1 == s2

    def test_seed_differs_by_provider(self):
        s1 = _seed("openai", "quantum computing", "educational")
        s2 = _seed("claude", "quantum computing", "educational")
        assert s1 != s2

    def test_seed_differs_by_topic(self):
        s1 = _seed("openai", "quantum computing", "educational")
        s2 = _seed("openai", "blockchain", "educational")
        assert s1 != s2

    def test_count_words(self):
        assert _count_words("hello world foo") == 3
        assert _count_words("") == 0
        assert _count_words("  ") == 0

    def test_generate_mock_script_is_deterministic(self, sample_request):
        r1 = generate_mock_script(sample_request, "openai")
        r2 = generate_mock_script(sample_request, "openai")
        assert r1.title == r2.title
        assert r1.hook == r2.hook
        assert r1.word_count == r2.word_count

    def test_generate_mock_script_differs_by_provider(self, sample_request):
        r1 = generate_mock_script(sample_request, "openai")
        r2 = generate_mock_script(sample_request, "claude")
        # Same structure but different confidence (and possibly different selections)
        assert r1.provider_name == "openai"
        assert r2.provider_name == "claude"
        assert r1.confidence != r2.confidence

    def test_generate_mock_script_has_required_fields(self, sample_request):
        result = generate_mock_script(sample_request, "openai")
        assert result.hook
        assert result.introduction
        assert result.outro
        assert result.call_to_action
        assert len(result.sections) >= 1
        assert result.word_count > 0
        assert result.estimated_duration_seconds > 0
        assert result.scene_count > 0
        assert 0.0 <= result.confidence <= 1.0

    def test_generate_mock_script_sections_have_word_counts(self, sample_request):
        result = generate_mock_script(sample_request, "openai")
        for s in result.sections:
            assert s.word_count >= 0
            assert s.duration_seconds >= 0.0

    def test_generate_mock_script_narration_timing(self, sample_request):
        result = generate_mock_script(sample_request, "openai")
        assert len(result.narration_timing) > 0
        for t in result.narration_timing:
            assert t.start_ms >= 0
            assert t.end_ms >= t.start_ms
            assert t.wpm > 0

    def test_different_styles_produce_different_structures(self):
        req_edu = ScriptRequest(topic="ai", style=ScriptStyle.EDUCATIONAL, providers=[ScriptProviderName.OPENAI])
        req_doc = ScriptRequest(topic="ai", style=ScriptStyle.DOCUMENTARY, providers=[ScriptProviderName.OPENAI])
        req_shorts = ScriptRequest(topic="ai", style=ScriptStyle.SHORTS, target_duration_minutes=1, providers=[ScriptProviderName.OPENAI])
        r_edu = generate_mock_script(req_edu, "openai")
        r_doc = generate_mock_script(req_doc, "openai")
        r_shorts = generate_mock_script(req_shorts, "openai")
        # Shorts should be shorter
        assert r_shorts.word_count < r_edu.word_count

    def test_all_styles_generate_without_error(self):
        for style in ScriptStyle:
            req = ScriptRequest(
                topic="test topic",
                style=style,
                target_duration_minutes=5,
                providers=[ScriptProviderName.OPENAI],
            )
            result = generate_mock_script(req, "openai")
            assert result.error is None
            assert result.word_count > 0


# ── Provider tests ─────────────────────────────────────────────────────────────

class TestScriptProviders:
    @pytest.mark.anyio
    async def test_openai_provider_returns_result(self, sample_request):
        provider = OpenAIScriptProvider()
        result = await provider._fetch_raw(sample_request)
        assert result.error is None
        assert result.provider_name == "openai"
        assert result.word_count > 0

    @pytest.mark.anyio
    async def test_gemini_provider_returns_result(self, sample_request):
        provider = GeminiScriptProvider()
        result = await provider._fetch_raw(sample_request)
        assert result.error is None
        assert result.provider_name == "gemini"

    @pytest.mark.anyio
    async def test_claude_provider_returns_result(self, sample_request):
        provider = ClaudeScriptProvider()
        result = await provider._fetch_raw(sample_request)
        assert result.error is None
        assert result.provider_name == "claude"

    @pytest.mark.anyio
    async def test_openrouter_provider_returns_result(self, sample_request):
        provider = OpenRouterScriptProvider()
        result = await provider._fetch_raw(sample_request)
        assert result.error is None
        assert result.provider_name == "openrouter"

    @pytest.mark.anyio
    async def test_provider_fetch_wraps_errors(self):
        provider = OpenAIScriptProvider()
        provider.max_retries = 0

        async def fail(req: ScriptRequest) -> ScriptProviderResult:
            raise RuntimeError("Simulated failure")

        provider._fetch_raw = fail  # type: ignore
        result = await provider.fetch(ScriptRequest(topic="test", providers=[ScriptProviderName.OPENAI]))
        assert result.error is not None
        assert "Simulated failure" in result.error


# ── Registry tests ─────────────────────────────────────────────────────────────

class TestScriptProviderRegistry:
    @pytest.mark.anyio
    async def test_registry_fetches_multiple_providers(self, sample_request):
        from app.providers.script.registry import ScriptProviderRegistry
        registry = ScriptProviderRegistry()
        results = await registry.fetch_all(
            sample_request,
            provider_names=["openai", "claude"],
            max_concurrent=2,
        )
        assert len(results) == 2
        assert all(r.error is None for r in results)

    @pytest.mark.anyio
    async def test_registry_returns_error_result_for_unknown_provider(self, sample_request):
        from app.providers.script.registry import ScriptProviderRegistry
        registry = ScriptProviderRegistry()
        results = await registry.fetch_all(
            sample_request,
            provider_names=["nonexistent_provider"],
        )
        assert len(results) == 1
        assert results[0].error is not None


# ── Service tests ──────────────────────────────────────────────────────────────

class TestScriptService:
    @pytest.mark.anyio
    async def test_start_script_creates_record(self, sample_request):
        from app.services.script_service import ScriptService
        db_obj = make_db_script()
        repo = make_mock_repo(db_obj)
        service = ScriptService(repo)

        with patch("app.services.script_service.ScriptProviderRegistry"):
            with patch("app.tasks.script_tasks.run_script_task") as mock_task:
                mock_task.delay = MagicMock()
                result = await service.start_script(sample_request)

        assert result is db_obj
        repo.create.assert_called_once()
        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["topic"] == "machine learning"
        assert call_kwargs["status"] == ScriptStatus.PENDING.value

    @pytest.mark.anyio
    async def test_execute_script_runs_full_pipeline(self, sample_request, mock_script_result):
        from app.services.script_service import ScriptService
        db_obj = make_db_script("script-456")
        repo = make_mock_repo(db_obj)
        service = ScriptService(repo)

        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(return_value=[mock_script_result, mock_script_result])
        service._registry = mock_registry

        result = await service.execute_script("script-456")

        repo.update.assert_called()
        call_kwargs = repo.update.call_args[1]
        assert call_kwargs["status"] == ScriptStatus.COMPLETED.value
        assert "word_count" in call_kwargs

    @pytest.mark.anyio
    async def test_execute_script_marks_failed_when_all_providers_fail(self):
        from app.services.script_service import ScriptService
        db_obj = make_db_script("script-fail")
        repo = make_mock_repo(db_obj)
        service = ScriptService(repo)

        failed_result = ScriptProviderResult(
            provider_name="openai", topic="test", error="Provider down"
        )
        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(return_value=[failed_result])
        service._registry = mock_registry

        result = await service.execute_script("script-fail")

        assert result is None
        repo.update.assert_called()
        call_kwargs = repo.update.call_args[1]
        assert call_kwargs["status"] == ScriptStatus.FAILED.value

    @pytest.mark.anyio
    async def test_execute_script_returns_none_for_missing_id(self):
        from app.services.script_service import ScriptService
        repo = make_mock_repo(None)
        service = ScriptService(repo)
        result = await service.execute_script("nonexistent")
        assert result is None

    @pytest.mark.anyio
    async def test_get_script_delegates_to_repo(self):
        from app.services.script_service import ScriptService
        db_obj = make_db_script()
        repo = make_mock_repo(db_obj)
        service = ScriptService(repo)
        result = await service.get_script("test-id")
        assert result is db_obj
        repo.get.assert_called_once_with("test-id")

    @pytest.mark.anyio
    async def test_list_scripts_delegates_to_repo(self):
        from app.services.script_service import ScriptService
        db_obj = make_db_script()
        repo = make_mock_repo()
        repo.list = AsyncMock(return_value=([db_obj], 1))
        service = ScriptService(repo)
        items, total = await service.list_scripts(limit=10, offset=0)
        assert total == 1
        assert items[0] is db_obj

    @pytest.mark.anyio
    async def test_delete_script_delegates_to_repo(self):
        from app.services.script_service import ScriptService
        repo = make_mock_repo()
        service = ScriptService(repo)
        deleted = await service.delete_script("test-id")
        assert deleted is True
        repo.delete.assert_called_once_with("test-id")

    def test_select_primary_picks_highest_confidence(self, mock_script_result):
        from app.services.script_service import ScriptService
        repo = make_mock_repo()
        service = ScriptService(repo)
        low = ScriptProviderResult(provider_name="gemini", topic="ml", confidence=0.6)
        high = ScriptProviderResult(provider_name="openai", topic="ml", confidence=0.95)
        primary = service._select_primary_result([low, high])
        assert primary.provider_name == "openai"

    def test_merge_sections_deduplicates_titles(self, mock_script_result):
        from app.services.script_service import ScriptService
        repo = make_mock_repo()
        service = ScriptService(repo)

        section_a = ScriptSection(
            section_type=ScriptSectionType.MAIN_POINT,
            title="Unique Section from Other",
            content="Extra content",
            order=1,
        )
        other = ScriptProviderResult(
            provider_name="claude",
            topic="ml",
            sections=[mock_script_result.sections[0], section_a],
            confidence=0.7,
        )
        merged = service._merge_sections(mock_script_result, [mock_script_result, other])
        titles = [s.title for s in merged]
        # No duplicates
        assert len(titles) == len(set(titles))
        # Extra unique section included
        assert "Unique Section from Other" in titles

    def test_calculate_metrics_returns_expected_keys(self, mock_script_result):
        from app.services.script_service import ScriptService
        repo = make_mock_repo()
        service = ScriptService(repo)
        metrics = service._calculate_metrics(mock_script_result, mock_script_result.sections)
        assert "word_count" in metrics
        assert "estimated_duration_seconds" in metrics
        assert "reading_time_seconds" in metrics
        assert "scene_count" in metrics
        assert "pacing_wpm" in metrics
        assert metrics["word_count"] > 0

    def test_merge_pronunciation_deduplicates(self, mock_script_result, sample_request):
        from app.services.script_service import ScriptService
        from app.providers.script.mock_base import generate_mock_script
        repo = make_mock_repo()
        service = ScriptService(repo)
        r1 = generate_mock_script(sample_request, "openai")
        r2 = generate_mock_script(sample_request, "claude")
        merged = service._merge_pronunciation([r1, r2])
        words = [h.word for h in merged]
        assert len(words) == len(set(words))
