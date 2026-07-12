"""Shared mock-data utilities used by all mock providers.

Real provider implementations will replace _fetch_raw() without touching anything else.
The mock generates topic-aware, deterministic-yet-varied data using a seeded PRNG so
that the same topic always returns the same mock content (important for cache tests).
"""
from __future__ import annotations

import asyncio
import hashlib
import random
from typing import Any

from app.schemas.research import (
    ProviderResult,
    ResearchKeyword,
    ResearchReference,
    ResearchRequest,
    SourceType,
)

# ── Shared vocabulary ─────────────────────────────────────────────────────────

_DIFFICULTIES = ["low", "medium", "high"]
_SOURCE_TYPES = [SourceType.WEB, SourceType.WIKIPEDIA, SourceType.ACADEMIC, SourceType.NEWS]

_REFERENCE_DOMAINS: dict[str, tuple[SourceType, float]] = {
    "wikipedia.org": (SourceType.WIKIPEDIA, 0.88),
    "scholar.google.com": (SourceType.ACADEMIC, 0.92),
    "nature.com": (SourceType.ACADEMIC, 0.95),
    "medium.com": (SourceType.WEB, 0.55),
    "arxiv.org": (SourceType.ACADEMIC, 0.87),
    "bbc.com": (SourceType.NEWS, 0.82),
    "wired.com": (SourceType.WEB, 0.72),
    "techcrunch.com": (SourceType.NEWS, 0.70),
    "reuters.com": (SourceType.NEWS, 0.85),
    "nytimes.com": (SourceType.NEWS, 0.84),
    "youtube.com": (SourceType.WEB, 0.60),
    "github.com": (SourceType.WEB, 0.78),
}

_DOMAINS = list(_REFERENCE_DOMAINS.keys())


def _seed(provider_name: str, topic: str) -> random.Random:
    """Return a seeded Random for deterministic mock output per (provider, topic)."""
    h = hashlib.md5(f"{provider_name}:{topic.lower().strip()}".encode()).hexdigest()
    return random.Random(int(h[:8], 16))


def _apa_citation(title: str, author: str | None, url: str, published_at: str | None) -> str:
    author_part = f"{author}." if author else "Anonymous."
    year_part = f"({published_at[:4]})." if published_at and len(published_at) >= 4 else "(n.d.)."
    return f"{author_part} {year_part} {title}. Retrieved from {url}"


# ── Core generator ────────────────────────────────────────────────────────────

def generate_mock_result(
    provider_name: str,
    request: ResearchRequest,
    confidence_range: tuple[float, float] = (0.65, 0.85),
    reference_count: int = 5,
    keyword_count: int = 8,
) -> ProviderResult:
    """Generate realistic mock research data for any topic."""
    rng = _seed(provider_name, request.topic)
    topic = request.topic

    # ── Summary ───────────────────────────────────────────────────────────────
    audience = request.target_audience or "general audience"
    summary = (
        f"{topic.capitalize()} is a compelling subject for a {request.video_length_minutes}-minute "
        f"YouTube video targeting {audience}. This {request.style} treatment explores the core "
        f"mechanisms, real-world implications, and common misconceptions surrounding {topic}, "
        f"offering {request.tone} content suitable for both newcomers and practitioners."
    )

    # ── Key points / facts ────────────────────────────────────────────────────
    key_points = [
        f"{topic.capitalize()} has significantly evolved over the past decade, reshaping how professionals approach related problems.",
        f"The primary mechanism behind {topic} involves a multi-step process that is often misunderstood by beginners.",
        f"Leading experts in the field of {topic} have recently published findings that challenge conventional wisdom.",
        f"Practical applications of {topic} span multiple industries including technology, healthcare, and finance.",
        f"The adoption rate of {topic} has grown at over 40% year-over-year in enterprise environments.",
        f"Understanding {topic} requires familiarity with several prerequisite concepts that are often overlooked.",
    ]
    rng.shuffle(key_points)
    key_points = key_points[: rng.randint(4, 6)]

    facts = [
        f"The term '{topic}' was first formally defined in academic literature in the early 2000s.",
        f"Over 60% of professionals who work with {topic} report that self-learning was their primary education path.",
        f"The global market for solutions related to {topic} exceeded $50B in 2023.",
        f"Research shows that {topic} reduces processing time by an average of 35% compared to traditional approaches.",
        f"More than 500 peer-reviewed papers on {topic} are published annually.",
        f"Countries leading in {topic} research include the US, China, UK, Germany, and Canada.",
    ]
    rng.shuffle(facts)
    facts = facts[: rng.randint(3, 5)]

    concepts = [
        f"Core framework of {topic}",
        f"Historical evolution of {topic}",
        f"Key stakeholders in {topic} ecosystems",
        f"Measurement and evaluation in {topic}",
        f"Regulatory landscape affecting {topic}",
        f"Open problems in {topic} research",
    ]
    rng.shuffle(concepts)
    concepts = concepts[:4]

    timeline_events = [
        f"1990s — Early theoretical foundations for {topic} established in academia",
        f"2005 — First widely-adopted commercial application of {topic} released",
        f"2012 — Landmark study demonstrates effectiveness of {topic} at scale",
        f"2017 — Open-source tooling democratizes access to {topic}",
        f"2021 — Regulatory frameworks for {topic} begin to emerge globally",
        f"2024 — State-of-the-art {topic} systems achieve human-level performance on benchmark tasks",
    ]
    timeline_events = timeline_events[: rng.randint(4, 6)]

    entities = [
        f"Stanford AI Lab",
        f"OpenAI",
        f"MIT Media Lab",
        f"Google DeepMind",
        f"European Research Council",
        f"IEEE {topic.title()} Working Group",
        f"Dr. Yann LeCun",
        f"Dr. Fei-Fei Li",
    ]
    rng.shuffle(entities)
    entities = entities[:5]

    statistics = [
        f"78% of surveyed practitioners consider {topic} critical to their organization's strategy",
        f"Average implementation cost for {topic} solutions: $250K–$2M for enterprise deployments",
        f"Projected CAGR for {topic}-related market: 28.4% from 2024–2030",
        f"Time-to-competency for {topic}: 6–18 months for practitioners with adjacent skills",
        f"Error rate reduction after adopting {topic}: median 41% across case studies",
    ]
    rng.shuffle(statistics)
    statistics = statistics[: rng.randint(3, 5)]

    examples = [
        f"Company X reduced operational costs by 30% by applying {topic} to their supply chain",
        f"A hospital system used {topic} to cut diagnostic errors by 22% in a 2-year pilot",
        f"A fintech startup achieved 10x user growth by embedding {topic} into their core product",
        f"An open-source project leveraging {topic} gained 40K GitHub stars within 6 months of launch",
    ]
    rng.shuffle(examples)
    examples = examples[:3]

    analogies = [
        f"{topic.capitalize()} is like building a skyscraper: the foundation (data quality) must be solid before adding floors (model complexity)",
        f"Think of {topic} as a GPS for decision-making — it can show you the best route, but you still need to drive the car",
        f"Learning {topic} is like learning a new language: immersion and practice matter far more than memorizing rules",
    ]
    rng.shuffle(analogies)
    analogies = analogies[:2]

    misconceptions = [
        f"Misconception: {topic.capitalize()} requires a PhD to understand. Reality: solid fundamentals are accessible to motivated learners",
        f"Misconception: {topic.capitalize()} always outperforms traditional methods. Reality: it depends heavily on problem structure and data quality",
        f"Misconception: Implementing {topic} is a one-time project. Reality: it requires continuous monitoring and iteration",
    ]
    rng.shuffle(misconceptions)
    misconceptions = misconceptions[:2]

    faqs = [
        {"q": f"What is {topic}?", "a": f"{topic.capitalize()} refers to a broad set of techniques and methodologies that address specific problem domains through a combination of theory and practical application."},
        {"q": f"How long does it take to learn {topic}?", "a": f"Foundational competency in {topic} typically requires 3–6 months of dedicated study, while expert-level mastery can take 2–5 years."},
        {"q": f"Is {topic} suitable for small businesses?", "a": f"Yes — modern tooling has made {topic} accessible to organizations of all sizes, though ROI timelines and implementation complexity vary."},
        {"q": f"What are the main challenges with {topic}?", "a": f"Common challenges include data quality issues, talent scarcity, integration with legacy systems, and managing stakeholder expectations."},
        {"q": f"What is the difference between {topic} and related approaches?", "a": f"While related approaches share methodological overlap with {topic}, key differentiators lie in scale, interpretability, and deployment context."},
    ]
    faqs = faqs[: rng.randint(3, 5)]

    # ── References ────────────────────────────────────────────────────────────
    refs: list[ResearchReference] = []
    selected_domains = rng.choices(_DOMAINS, k=reference_count)
    for i, domain in enumerate(selected_domains):
        src_type, cred = _REFERENCE_DOMAINS[domain]
        title = f"{'Understanding' if i % 2 == 0 else 'Advances in'} {topic.title()}: {'A Comprehensive Review' if i == 0 else f'Vol. {i}'}"
        author = rng.choice([None, "Smith, J.", "Zhang, L.", "Müller, K.", "Patel, R.", "Okonkwo, A."])
        year = rng.randint(2018, 2024)
        published_at = f"{year}-{rng.randint(1,12):02d}-01"
        snippet = f"This source provides authoritative coverage of {topic} with emphasis on {rng.choice(['theoretical foundations','practical applications','empirical results','case studies'])}."
        url = f"https://{domain}/{topic.replace(' ', '-').lower()}/{year}"
        citation = _apa_citation(title, author, url, published_at)
        refs.append(ResearchReference(
            title=title,
            url=url,
            source_type=src_type,
            author=author,
            published_at=published_at,
            snippet=snippet,
            credibility_score=round(cred + rng.uniform(-0.05, 0.05), 3),
            citation_format=citation,
            provider=provider_name,
        ))

    # ── Keywords ──────────────────────────────────────────────────────────────
    base_terms = topic.lower().split() + [
        "machine learning", "data", "automation", "optimization", "scalability",
        "framework", "implementation", "benchmark", "evaluation", "research",
        "tutorial", "beginner guide", "advanced", "best practices", "2024",
    ]
    rng.shuffle(base_terms)
    base_terms = list(dict.fromkeys(base_terms))[:keyword_count]
    keywords: list[ResearchKeyword] = []
    for j, term in enumerate(base_terms):
        relevance = round(rng.uniform(0.5, 1.0) if j < 3 else rng.uniform(0.3, 0.7), 3)
        vol = rng.randint(1000, 500000)
        kw = ResearchKeyword(
            term=term,
            relevance=relevance,
            search_volume=vol,
            difficulty=rng.choice(_DIFFICULTIES),
            semantic_tags=[f"{topic.split()[0]}", "youtube", rng.choice(["beginner", "advanced", "tutorial"])],
        )
        keywords.append(kw)

    confidence = round(rng.uniform(*confidence_range), 3)

    return ProviderResult(
        provider_name=provider_name,
        topic=topic,
        summary=summary,
        key_points=key_points,
        facts=facts,
        concepts=concepts,
        timeline_events=timeline_events,
        entities=entities,
        statistics=statistics,
        examples=examples,
        analogies=analogies,
        misconceptions=misconceptions,
        faqs=faqs,
        references=refs,
        keywords=keywords,
        confidence=confidence,
    )
