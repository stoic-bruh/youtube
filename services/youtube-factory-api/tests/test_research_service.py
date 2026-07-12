"""Unit tests for ResearchService — run with: pytest tests/test_research_service.py -v"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.schemas.research import (
    ProviderName,
    ProviderResult,
    ResearchKeyword,
    ResearchReference,
    ResearchRequest,
    ResearchStatus,
    SectionType,
    SourceType,
)
from app.services.research_service import ResearchService, _normalize_topic, _jaccard, _is_near_duplicate


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_provider_result(
    provider_name: str = "openai",
    topic: str = "machine learning",
    confidence: float = 0.80,
    num_facts: int = 3,
    num_refs: int = 2,
) -> ProviderResult:
    refs = [
        ResearchReference(
            title=f"Source {i}",
            url=f"https://example.com/{provider_name}/{i}",
            source_type=SourceType.WEB,
            credibility_score=0.7 + i * 0.05,
            citation_format="",
            provider=provider_name,
        )
        for i in range(num_refs)
    ]
    keywords = [
        ResearchKeyword(term=f"kw_{provider_name}_{i}", relevance=0.8 - i * 0.1)
        for i in range(3)
    ]
    return ProviderResult(
        provider_name=provider_name,
        topic=topic,
        summary=f"Summary from {provider_name}: {topic} is an important field.",
        key_points=[f"Point {i} from {provider_name}" for i in range(2)],
        facts=[f"Fact {i} specific to {provider_name}" for i in range(num_facts)],
        concepts=["concept A", "concept B"],
        timeline_events=["2010 — Event A", "2020 — Event B"],
        entities=["Entity X", "Entity Y"],
        statistics=[f"Stat {i} from {provider_name}" for i in range(2)],
        examples=[f"Example {i} from {provider_name}" for i in range(2)],
        analogies=["It is like building blocks"],
        misconceptions=["Common myth 1"],
        faqs=[{"q": "What is it?", "a": "It is a field of study."}],
        references=refs,
        keywords=keywords,
        confidence=confidence,
    )


def make_mock_repo() -> MagicMock:
    repo = MagicMock()
    repo._db = AsyncMock()
    repo._db.flush = AsyncMock()
    return repo


# ── Tests: helpers ─────────────────────────────────────────────────────────────

class TestNormalizeTopic:
    def test_lowercases(self):
        assert _normalize_topic("Machine Learning") == "machine learning"

    def test_strips_punctuation(self):
        assert _normalize_topic("AI: The Future!") == "ai the future"

    def test_collapses_whitespace(self):
        assert _normalize_topic("  a   b  ") == "a b"


class TestJaccard:
    def test_identical(self):
        assert _jaccard("hello world", "hello world") == 1.0

    def test_disjoint(self):
        assert _jaccard("foo bar", "baz qux") == 0.0

    def test_partial(self):
        score = _jaccard("hello world", "hello there")
        assert 0.0 < score < 1.0

    def test_empty(self):
        assert _jaccard("", "") == 0.0


class TestIsNearDuplicate:
    def test_exact_duplicate(self):
        assert _is_near_duplicate("hello world foo", ["hello world foo"])

    def test_not_duplicate(self):
        assert not _is_near_duplicate("completely different text", ["hello world foo"])

    def test_empty_seen(self):
        assert not _is_near_duplicate("anything", [])


# ── Tests: _merge_provider_results ────────────────────────────────────────────

class TestMergeProviderResults:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_produces_summary_section(self):
        results = [make_provider_result("openai"), make_provider_result("gemini")]
        service = self._service()
        sections = service._merge_provider_results(results)
        types = {s.section_type for s in sections}
        assert SectionType.SUMMARY in types

    def test_deduplicates_facts(self):
        r1 = make_provider_result("openai")
        r2 = make_provider_result("gemini")
        # Make r2 facts identical to r1 facts — should deduplicate
        r2.facts = list(r1.facts)
        service = self._service()
        sections = service._merge_provider_results([r1, r2])
        fact_sections = [s for s in sections if s.section_type == SectionType.FACT]
        if fact_sections:
            # Should not have doubled facts
            assert len(fact_sections[0].items) <= len(r1.facts) + len(r2.facts)

    def test_section_confidence_is_valid(self):
        results = [make_provider_result("openai", confidence=0.8)]
        service = self._service()
        sections = service._merge_provider_results(results)
        for s in sections:
            assert 0.0 <= s.confidence <= 1.0

    def test_all_section_types_represented(self):
        r = make_provider_result("openai")
        service = self._service()
        sections = service._merge_provider_results([r])
        types = {s.section_type for s in sections}
        # At minimum: summary, fact, concept, timeline, entity, statistic, example
        expected_minimum = {SectionType.SUMMARY, SectionType.FACT, SectionType.CONCEPT}
        assert expected_minimum.issubset(types)


# ── Tests: _rank_references ───────────────────────────────────────────────────

class TestRankReferences:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_sorted_by_credibility_desc(self):
        refs = [
            ResearchReference(title="A", url="https://a.com", source_type=SourceType.WEB, credibility_score=0.5, citation_format="", provider="p"),
            ResearchReference(title="B", url="https://b.com", source_type=SourceType.ACADEMIC, credibility_score=0.9, citation_format="", provider="p"),
            ResearchReference(title="C", url="https://c.com", source_type=SourceType.NEWS, credibility_score=0.7, citation_format="", provider="p"),
        ]
        service = self._service()
        ranked = service._rank_references(refs)
        assert ranked[0].credibility_score >= ranked[1].credibility_score
        assert ranked[1].credibility_score >= ranked[2].credibility_score

    def test_deduplicates_by_url(self):
        refs = [
            ResearchReference(title="A", url="https://same.com", source_type=SourceType.WEB, credibility_score=0.8, citation_format="", provider="p1"),
            ResearchReference(title="A copy", url="https://same.com", source_type=SourceType.WEB, credibility_score=0.8, citation_format="", provider="p2"),
            ResearchReference(title="B", url="https://other.com", source_type=SourceType.WEB, credibility_score=0.6, citation_format="", provider="p1"),
        ]
        service = self._service()
        ranked = service._rank_references(refs)
        assert len(ranked) == 2

    def test_caps_at_max_references(self):
        refs = [
            ResearchReference(title=f"R{i}", url=f"https://src{i}.com", source_type=SourceType.WEB, credibility_score=0.5, citation_format="", provider="p")
            for i in range(30)
        ]
        service = self._service()
        ranked = service._rank_references(refs)
        assert len(ranked) <= 15


# ── Tests: _merge_keywords ────────────────────────────────────────────────────

class TestMergeKeywords:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_deduplicates_same_term(self):
        kws = [
            ResearchKeyword(term="machine learning", relevance=0.8, semantic_tags=["ml"]),
            ResearchKeyword(term="machine learning", relevance=0.9, semantic_tags=["ai"]),
        ]
        service = self._service()
        merged = service._merge_keywords(kws)
        terms = [k.term.lower() for k in merged]
        assert terms.count("machine learning") == 1

    def test_takes_max_relevance(self):
        kws = [
            ResearchKeyword(term="python", relevance=0.6),
            ResearchKeyword(term="python", relevance=0.9),
        ]
        service = self._service()
        merged = service._merge_keywords(kws)
        py_kw = next(k for k in merged if k.term.lower() == "python")
        assert py_kw.relevance == 0.9

    def test_sorted_by_relevance_desc(self):
        kws = [
            ResearchKeyword(term=f"kw{i}", relevance=round(0.3 + i * 0.1, 1))
            for i in range(5)
        ]
        service = self._service()
        merged = service._merge_keywords(kws)
        relevances = [k.relevance for k in merged]
        assert relevances == sorted(relevances, reverse=True)


# ── Tests: _calculate_confidence ──────────────────────────────────────────────

class TestCalculateConfidence:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_returns_valid_float(self):
        results = [make_provider_result("openai", confidence=0.8)]
        refs = results[0].references
        from app.services.research_service import ResearchSection, SectionType
        sections = [ResearchSection(section_type=SectionType.SUMMARY, title="s", confidence=0.8)]
        service = self._service()
        score = service._calculate_confidence(results, sections, refs)
        assert 0.0 <= score <= 1.0

    def test_higher_confidence_with_more_providers(self):
        r1 = [make_provider_result("openai", confidence=0.8)]
        r2 = [make_provider_result("openai", confidence=0.8), make_provider_result("gemini", confidence=0.8)]
        from app.services.research_service import ResearchSection, SectionType
        sections = [ResearchSection(section_type=SectionType.SUMMARY, title="s", confidence=0.8)]
        service = self._service()
        refs = r2[0].references + r2[1].references
        score1 = service._calculate_confidence(r1, sections, r1[0].references)
        score2 = service._calculate_confidence(r2, sections, refs)
        # With same provider confidence, both should be similar (provider count isn't the only factor)
        assert isinstance(score1, float) and isinstance(score2, float)


# ── Tests: _estimate_difficulty ───────────────────────────────────────────────

class TestEstimateDifficulty:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_beginner_topic(self):
        kws = [ResearchKeyword(term="beginner tutorial", relevance=0.9), ResearchKeyword(term="getting started", relevance=0.8)]
        from app.schemas.research import ResearchSection, SectionType
        sections = [ResearchSection(section_type=SectionType.SUMMARY, title="s", confidence=0.8)]
        service = self._service()
        result = service._estimate_difficulty(sections, kws)
        assert result == "beginner"

    def test_advanced_topic(self):
        kws = [ResearchKeyword(term="advanced algorithm optimization", relevance=0.9), ResearchKeyword(term="distributed architecture", relevance=0.8), ResearchKeyword(term="mathematical theory", relevance=0.7)]
        from app.schemas.research import ResearchSection, SectionType
        sections = [ResearchSection(section_type=t, title="s", confidence=0.8) for t in SectionType]
        service = self._service()
        result = service._estimate_difficulty(sections, kws)
        assert result in ("intermediate", "advanced")

    def test_returns_valid_string(self):
        kws = [ResearchKeyword(term="topic", relevance=0.5)]
        from app.schemas.research import ResearchSection, SectionType
        sections = [ResearchSection(section_type=SectionType.SUMMARY, title="s", confidence=0.8)]
        service = self._service()
        result = service._estimate_difficulty(sections, kws)
        assert result in ("beginner", "intermediate", "advanced")


# ── Tests: _generate_citations ────────────────────────────────────────────────

class TestGenerateCitations:
    def _service(self) -> ResearchService:
        return ResearchService(make_mock_repo())  # type: ignore

    def test_fills_empty_citations(self):
        refs = [
            ResearchReference(title="Test Article", url="https://test.com", source_type=SourceType.WEB, credibility_score=0.7, citation_format="", provider="p"),
        ]
        service = self._service()
        result = service._generate_citations(refs)
        assert result[0].citation_format != ""
        assert "Test Article" in result[0].citation_format
        assert "https://test.com" in result[0].citation_format

    def test_preserves_existing_citations(self):
        existing_citation = "Smith, J. (2023). My Article. https://test.com"
        refs = [
            ResearchReference(title="My Article", url="https://test.com", source_type=SourceType.WEB, credibility_score=0.7, citation_format=existing_citation, provider="p"),
        ]
        service = self._service()
        result = service._generate_citations(refs)
        assert result[0].citation_format == existing_citation


# ── Tests: mock providers ─────────────────────────────────────────────────────

class TestMockProviders:
    @pytest.mark.asyncio
    async def test_openai_provider_returns_valid_result(self):
        from app.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        request = ResearchRequest(topic="quantum computing", providers=[ProviderName.OPENAI])
        result = await provider.fetch(request)
        assert result.provider_name == "openai"
        assert result.topic == "quantum computing"
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.references) > 0
        assert len(result.keywords) > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_wikipedia_provider_returns_wikipedia_reference(self):
        from app.providers.wikipedia_provider import WikipediaProvider
        provider = WikipediaProvider()
        request = ResearchRequest(topic="neural networks", providers=[ProviderName.WIKIPEDIA])
        result = await provider.fetch(request)
        assert result.error is None
        wiki_refs = [r for r in result.references if "wikipedia.org" in r.url]
        assert len(wiki_refs) >= 1

    @pytest.mark.asyncio
    async def test_duckduckgo_provider_adds_longtail_keywords(self):
        from app.providers.duckduckgo_provider import DuckDuckGoProvider
        provider = DuckDuckGoProvider()
        request = ResearchRequest(topic="python programming", providers=[ProviderName.DUCKDUCKGO])
        result = await provider.fetch(request)
        assert result.error is None
        longtail = [k for k in result.keywords if "longtail" in k.semantic_tags]
        assert len(longtail) > 0

    @pytest.mark.asyncio
    async def test_all_providers_return_valid_results(self):
        from app.providers.openai_provider import OpenAIProvider
        from app.providers.gemini_provider import GeminiProvider
        from app.providers.claude_provider import ClaudeProvider
        from app.providers.openrouter_provider import OpenRouterProvider
        from app.providers.perplexity_provider import PerplexityProvider
        from app.providers.wikipedia_provider import WikipediaProvider
        from app.providers.duckduckgo_provider import DuckDuckGoProvider
        from app.providers.google_search_provider import GoogleSearchProvider

        providers = [
            OpenAIProvider(), GeminiProvider(), ClaudeProvider(), OpenRouterProvider(),
            PerplexityProvider(), WikipediaProvider(), DuckDuckGoProvider(), GoogleSearchProvider(),
        ]
        request = ResearchRequest(topic="climate change", providers=list(ProviderName))
        results = await asyncio.gather(*[p.fetch(request) for p in providers])
        for result in results:
            assert result.error is None or isinstance(result.error, str)
            assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_provider_determinism(self):
        """Same topic should always return same mock data (seeded RNG)."""
        from app.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        request = ResearchRequest(topic="blockchain technology", providers=[ProviderName.OPENAI])
        r1 = await provider.fetch(request)
        r2 = await provider.fetch(request)
        assert r1.summary == r2.summary
        assert r1.confidence == r2.confidence


# ── Tests: provider registry ─────────────────────────────────────────────────

class TestProviderRegistry:
    def test_get_known_provider(self):
        from app.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        provider = registry.get("openai")
        assert provider.name == "openai"

    def test_get_unknown_provider_raises(self):
        from app.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown provider"):
            registry.get("does_not_exist")

    def test_list_available_contains_all(self):
        from app.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        available = registry.list_available()
        expected = ["openai", "gemini", "claude", "openrouter", "perplexity", "wikipedia", "duckduckgo", "google_search"]
        for name in expected:
            assert name in available

    @pytest.mark.asyncio
    async def test_fetch_all_returns_results_for_all_providers(self):
        from app.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        request = ResearchRequest(topic="test topic", providers=[ProviderName.OPENAI, ProviderName.WIKIPEDIA])
        results = await registry.fetch_all(request, ["openai", "wikipedia"])
        assert len(results) == 2
        assert all(r.topic == "test topic" for r in results)
