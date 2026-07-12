"""ResearchService — placeholder interface.

Responsible for:
- Topic research via web search / AI
- Competitor analysis
- Trending content discovery
- Keyword extraction
- Source collection for script writing
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ResearchResult:
    topic: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    competitor_videos: list[dict] = field(default_factory=list)
    trending_angles: list[str] = field(default_factory=list)
    estimated_search_volume: int = 0


class ResearchService:
    """Placeholder implementation — real AI research to be implemented."""

    async def research_topic(self, topic: str, depth: str = "standard") -> ResearchResult:
        """Research a topic and return structured findings.

        Args:
            topic: The YouTube video topic to research.
            depth: Research depth — "quick" | "standard" | "deep".

        Returns:
            ResearchResult with key points, sources, and keywords.
        """
        # TODO: Implement using OpenAI + web search (Tavily / Serper)
        return ResearchResult(
            topic=topic,
            summary=f"[PLACEHOLDER] Research summary for: {topic}",
            key_points=["Key point 1", "Key point 2", "Key point 3"],
            sources=[{"url": "https://example.com", "title": "Source 1"}],
            keywords=[topic.lower(), "tutorial", "guide"],
            competitor_videos=[],
            trending_angles=["How-to angle", "Top 10 angle"],
            estimated_search_volume=0,
        )

    async def find_trending_topics(self, niche: str, limit: int = 10) -> list[str]:
        """Find trending topics in a given YouTube niche.

        Args:
            niche: The content niche to search within.
            limit: Maximum number of topics to return.

        Returns:
            List of trending topic strings.
        """
        # TODO: Implement using YouTube Data API + trend analysis
        return [f"[PLACEHOLDER] Trending topic {i + 1} for {niche}" for i in range(limit)]

    async def analyze_competitors(self, topic: str, limit: int = 5) -> list[dict]:
        """Analyze competitor videos for a topic.

        Args:
            topic: The topic to search for competitors.
            limit: Maximum number of competitor videos to analyze.

        Returns:
            List of competitor video data dicts.
        """
        # TODO: Implement using YouTube Data API
        return [{"title": f"[PLACEHOLDER] Competitor {i + 1}", "views": 0} for i in range(limit)]

    async def extract_keywords(self, text: str) -> list[str]:
        """Extract SEO-relevant keywords from text.

        Args:
            text: Input text to extract keywords from.

        Returns:
            List of keyword strings ranked by relevance.
        """
        # TODO: Implement using NLP / OpenAI
        return ["[PLACEHOLDER] keyword1", "keyword2", "keyword3"]
