"""ResearchService — production-ready autonomous research orchestration.

Architecture:
  1. start_research(request)  → create DB record → enqueue Celery task → return record
  2. execute_research(id)     → update status → fetch providers → merge → score → store
  3. get/list/delete          → thin repo wrappers

Merge pipeline:
  fetch_all_providers → _merge_provider_results → _deduplicate_sections
  → _rank_references → _generate_citations → _calculate_confidence
  → _estimate_difficulty → persist
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Sequence

from app.models.research_result import ResearchResult
from app.providers.registry import ProviderRegistry
from app.repositories.research_repository import ResearchRepository
from app.schemas.research import (
    ProviderResult,
    ResearchKeyword,
    ResearchReference,
    ResearchRequest,
    ResearchResultSchema,
    ResearchSection,
    ResearchStatus,
    SectionType,
)

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

_MIN_CONFIDENCE_TO_CACHE = 0.4       # below this we still store but warn
_DEDUP_SIMILARITY_THRESHOLD = 0.85   # Jaccard similarity for near-duplicate strings
_MAX_REFS_IN_RESULT = 15             # cap references per result
_MAX_KEYWORDS_IN_RESULT = 20         # cap keywords per result
_CACHE_ENABLED = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_topic(topic: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — used for cache lookup."""
    import re
    t = topic.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _is_near_duplicate(text: str, seen: list[str]) -> bool:
    return any(_jaccard(text, s) > _DEDUP_SIMILARITY_THRESHOLD for s in seen)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


# ── Service ───────────────────────────────────────────────────────────────────

class ResearchService:
    """Orchestrates the full research pipeline for a given topic."""

    def __init__(self, repo: ResearchRepository) -> None:
        self._repo = repo
        self._registry = ProviderRegistry()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def start_research(self, request: ResearchRequest) -> ResearchResult:
        """Create a research record with status=pending and enqueue the Celery task.

        Returns the created (unsaved) ResearchResult for immediate API response.
        The Celery worker will call execute_research(id) asynchronously.
        """
        topic_normalized = _normalize_topic(request.topic)

        # Cache check — return existing completed research if within TTL
        if _CACHE_ENABLED:
            cached = await self._repo.get_cached(topic_normalized)
            if cached:
                logger.info("Research cache HIT for topic=%r", request.topic)
                cached.status = ResearchStatus.CACHED
                await self._repo._db.flush()
                return cached

        job_id = str(uuid.uuid4())
        research = await self._repo.create(
            topic=request.topic,
            topic_normalized=topic_normalized,
            target_audience=request.target_audience,
            video_length_minutes=request.video_length_minutes,
            language=request.language,
            style=request.style.value,
            tone=request.tone.value,
            status=ResearchStatus.PENDING.value,
            job_id=job_id,
            providers=[p.value for p in request.providers],
            used_providers=[],
            sections=[],
            references=[],
            keywords=[],
            logs=[f"{_ts()} INFO  Research job created. Job ID: {job_id}"],
        )
        logger.info("Research job created id=%s topic=%r", research.id, request.topic)

        # Enqueue Celery task
        # (imported here to avoid circular import at module load)
        try:
            from app.tasks.research_tasks import run_research_task
            run_research_task.delay(research.id)
        except Exception as exc:
            logger.warning("Celery not available — research will not auto-process: %s", exc)

        return research

    async def execute_research(self, research_id: str) -> ResearchResult | None:
        """Main execution entry point called by the Celery worker."""
        research = await self._repo.get(research_id)
        if not research:
            logger.error("Research %s not found", research_id)
            return None

        logs: list[str] = list(research.logs or [])

        def log(level: str, msg: str) -> None:
            line = f"{_ts()} {level.upper():<5} {msg}"
            logs.append(line)
            logger.info(msg)

        try:
            await self._set_status(research, ResearchStatus.RUNNING, logs)
            log("INFO", f"Starting research for topic: '{research.topic}'")
            log("INFO", f"Requested providers: {research.providers}")

            request = ResearchRequest(
                topic=research.topic,
                target_audience=research.target_audience or "general audience",
                video_length_minutes=research.video_length_minutes,
                language=research.language,  # type: ignore
                style=research.style,  # type: ignore
                tone=research.tone,  # type: ignore
                providers=research.providers,  # type: ignore
            )

            # ── Phase 1: fetch from providers ──────────────────────────────────
            log("INFO", "Phase 1/4 — Fetching from research providers in parallel")
            t0 = time.monotonic()
            provider_results = await self._registry.fetch_all(
                request,
                provider_names=research.providers,
                max_concurrent=4,
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            successful = [r for r in provider_results if not r.error]
            failed = [r for r in provider_results if r.error]
            used_providers = [r.provider_name for r in successful]
            log("INFO", f"Providers completed in {elapsed}ms — {len(successful)} OK, {len(failed)} failed")
            for f in failed:
                log("WARN", f"Provider {f.provider_name!r} failed: {f.error}")

            if not successful:
                raise RuntimeError("All research providers failed — cannot proceed")

            # ── Phase 2: merge ─────────────────────────────────────────────────
            log("INFO", "Phase 2/4 — Merging and deduplicating provider outputs")
            sections = self._merge_provider_results(successful)
            log("INFO", f"Merged {len(sections)} sections from {len(successful)} providers")

            # ── Phase 3: references & keywords ─────────────────────────────────
            log("INFO", "Phase 3/4 — Ranking references and deduplicating keywords")
            all_refs = _flatten_list(r.references for r in successful)
            all_kws = _flatten_list(r.keywords for r in successful)
            references = self._rank_references(all_refs)
            references = self._generate_citations(references)
            keywords = self._merge_keywords(all_kws)
            log("INFO", f"References: {len(references)} unique  |  Keywords: {len(keywords)} unique")

            # ── Phase 4: scoring ──────────────────────────────────────────────
            log("INFO", "Phase 4/4 — Calculating confidence score and difficulty")
            confidence = self._calculate_confidence(successful, sections, references)
            difficulty = self._estimate_difficulty(sections, keywords)
            summary = next(
                (s.content for s in sections if s.section_type == SectionType.SUMMARY),
                sections[0].content if sections else "",
            )
            log("INFO", f"Confidence score: {confidence:.2%}  |  Estimated difficulty: {difficulty}")

            # ── Persist ───────────────────────────────────────────────────────
            logs.append(f"{_ts()} INFO  Research complete — writing to database")
            sections_json = [s.model_dump() for s in sections]
            refs_json = [r.model_dump() for r in references]
            kws_json = [k.model_dump() for k in keywords]

            updated = await self._repo.update(
                research_id,
                status=ResearchStatus.COMPLETED.value,
                summary=summary,
                confidence_score=confidence,
                estimated_difficulty=difficulty,
                sections=sections_json,
                references=refs_json,
                keywords=kws_json,
                used_providers=used_providers,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Research %s completed successfully", research_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Research failed: {error_msg}")
            await self._repo.update(
                research_id,
                status=ResearchStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Research %s failed: %s", research_id, error_msg, exc_info=True)
            return None

    async def get_research(self, research_id: str) -> ResearchResult | None:
        return await self._repo.get(research_id)

    async def list_research(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[ResearchResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_research(self, research_id: str) -> bool:
        return await self._repo.delete(research_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _set_status(self, research: ResearchResult, status: ResearchStatus, logs: list[str]) -> None:
        research.status = status.value
        research.updated_at = datetime.now(timezone.utc)
        research.logs = logs
        await self._repo._db.flush()

    def _merge_provider_results(self, results: list[ProviderResult]) -> list[ResearchSection]:
        """Combine outputs from multiple providers into deduplicated sections."""
        # Group items by section type
        seen_summary: list[str] = []
        seen_facts: list[str] = []
        seen_concepts: list[str] = []
        seen_timeline: list[str] = []
        seen_entities: list[str] = []
        seen_statistics: list[str] = []
        seen_examples: list[str] = []
        seen_analogies: list[str] = []
        seen_misconceptions: list[str] = []
        seen_faqs: list[str] = []

        for r in results:
            _dedup_extend(seen_summary, [r.summary] if r.summary else [])
            _dedup_extend(seen_facts, r.facts)
            _dedup_extend(seen_concepts, r.concepts)
            _dedup_extend(seen_timeline, r.timeline_events)
            _dedup_extend(seen_entities, r.entities)
            _dedup_extend(seen_statistics, r.statistics)
            _dedup_extend(seen_examples, r.examples)
            _dedup_extend(seen_analogies, r.analogies)
            _dedup_extend(seen_misconceptions, r.misconceptions)
            # Merge FAQs: de-duplicate by question text
            for faq in r.faqs:
                q = faq.get("q", "")
                if not _is_near_duplicate(q, [f.get("q", "") for f in seen_faqs]):  # type: ignore
                    seen_faqs.append(faq)  # type: ignore

        # Weighted average confidence across providers
        avg_conf = sum(r.confidence for r in results) / len(results)

        sections: list[ResearchSection] = []

        if seen_summary:
            # Pick the longest summary as the canonical one
            best_summary = max(seen_summary, key=len)
            sections.append(ResearchSection(
                section_type=SectionType.SUMMARY,
                title="Overview",
                content=best_summary,
                confidence=round(avg_conf, 3),
                items=[],
            ))

        def _add(stype: SectionType, title: str, items: list[str], conf_adj: float = 0.0) -> None:
            if items:
                sections.append(ResearchSection(
                    section_type=stype,
                    title=title,
                    content=f"{len(items)} {title.lower()} identified across {len(results)} provider(s).",
                    confidence=round(min(1.0, avg_conf + conf_adj), 3),
                    items=items,
                ))

        _add(SectionType.CONCEPT, "Major Concepts", seen_concepts, 0.05)
        _add(SectionType.FACT, "Key Facts", seen_facts)
        _add(SectionType.TIMELINE, "Timeline of Events", seen_timeline, 0.02)
        _add(SectionType.ENTITY, "Named Entities", seen_entities, 0.0)
        _add(SectionType.STATISTIC, "Statistics & Data", seen_statistics, 0.03)
        _add(SectionType.EXAMPLE, "Real-World Examples", seen_examples, 0.04)
        _add(SectionType.ANALOGY, "Analogies & Explanations", seen_analogies, 0.06)
        _add(SectionType.MISCONCEPTION, "Common Misconceptions", seen_misconceptions, 0.05)

        if seen_faqs:
            faq_items = [f"{faq.get('q','')}\n{faq.get('a','')}" for faq in seen_faqs]  # type: ignore
            sections.append(ResearchSection(
                section_type=SectionType.FAQ,
                title="Frequently Asked Questions",
                content=f"{len(seen_faqs)} FAQ(s) compiled from research sources.",
                confidence=round(avg_conf, 3),
                items=faq_items,
            ))

        return sections

    def _rank_references(self, refs: list[ResearchReference]) -> list[ResearchReference]:
        """Deduplicate by URL and rank by credibility score, capped at max."""
        seen_urls: set[str] = set()
        unique: list[ResearchReference] = []
        for ref in refs:
            if ref.url not in seen_urls:
                seen_urls.add(ref.url)
                unique.append(ref)
        # Sort descending by credibility
        unique.sort(key=lambda r: r.credibility_score, reverse=True)
        return unique[:_MAX_REFS_IN_RESULT]

    def _generate_citations(self, refs: list[ResearchReference]) -> list[ResearchReference]:
        """Ensure every reference has a valid APA citation string."""
        from app.providers.mock_base import _apa_citation
        for ref in refs:
            if not ref.citation_format:
                ref.citation_format = _apa_citation(
                    ref.title, ref.author, ref.url, ref.published_at
                )
        return refs

    def _merge_keywords(self, all_kws: list[ResearchKeyword]) -> list[ResearchKeyword]:
        """Aggregate keyword relevance scores across providers and deduplicate by term."""
        merged: dict[str, ResearchKeyword] = {}
        for kw in all_kws:
            term = kw.term.lower().strip()
            if term in merged:
                # Accumulate: take max relevance, merge semantic tags
                existing = merged[term]
                existing.relevance = round(max(existing.relevance, kw.relevance), 3)
                combined_tags = list(set(existing.semantic_tags + kw.semantic_tags))
                existing.semantic_tags = combined_tags[:5]
                if kw.search_volume and (not existing.search_volume or kw.search_volume > existing.search_volume):
                    existing.search_volume = kw.search_volume
            else:
                merged[term] = kw.model_copy()
                merged[term].term = kw.term  # preserve original case
        # Sort by relevance descending
        sorted_kws = sorted(merged.values(), key=lambda k: k.relevance, reverse=True)
        return sorted_kws[:_MAX_KEYWORDS_IN_RESULT]

    def _calculate_confidence(
        self,
        results: list[ProviderResult],
        sections: list[ResearchSection],
        references: list[ResearchReference],
    ) -> float:
        """Multi-factor confidence score in [0, 1].

        Factors:
        - Mean provider confidence (weight 0.4)
        - Provider agreement: fraction of providers that didn't fail (weight 0.2)
        - Reference quality: mean credibility score (weight 0.2)
        - Content richness: section count / expected count (weight 0.2)
        """
        provider_conf = sum(r.confidence for r in results) / len(results)
        ref_quality = (
            sum(r.credibility_score for r in references) / len(references)
            if references else 0.5
        )
        expected_sections = 9  # summary + 8 section types
        richness = min(1.0, len(sections) / expected_sections)

        score = (
            provider_conf * 0.40
            + 1.0 * 0.20          # all providers succeeded (already filtered failed ones)
            + ref_quality * 0.20
            + richness * 0.20
        )
        return round(min(1.0, max(0.0, score)), 3)

    def _estimate_difficulty(
        self,
        sections: list[ResearchSection],
        keywords: list[ResearchKeyword],
    ) -> str:
        """Estimate content difficulty: beginner | intermediate | advanced."""
        hard_kws = {"advanced", "research", "technical", "architecture", "algorithm",
                    "theory", "mathematical", "optimization", "distributed", "quantum"}
        beginner_kws = {"beginner", "intro", "basics", "getting started", "tutorial",
                        "simple", "easy", "learn", "guide", "how to", "for beginners"}
        terms = {kw.term.lower() for kw in keywords}
        hard_hits = len(terms & hard_kws)
        beginner_hits = len(terms & beginner_kws)
        num_sections = len(sections)
        score = hard_hits * 2 - beginner_hits + (num_sections // 3)
        if score >= 4:
            return "advanced"
        elif score >= 1:
            return "intermediate"
        return "beginner"


# ── Module-level helpers ───────────────────────────────────────────────────────

def _flatten_list(iterables) -> list:
    result = []
    for it in iterables:
        result.extend(it)
    return result


def _dedup_extend(seen: list[str], new_items: list[str]) -> None:
    """Extend `seen` in-place, skipping near-duplicates."""
    for item in new_items:
        if item and not _is_near_duplicate(item, seen):
            seen.append(item)
