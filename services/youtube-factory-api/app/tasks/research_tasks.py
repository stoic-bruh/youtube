"""Research stage Celery tasks. [PLACEHOLDER]"""
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="research.search_web", max_retries=3)
def search_web(self, query: str, num_results: int = 10) -> list[dict]:
    """Search the web for a query and return structured results. [PLACEHOLDER]
    TODO: Implement using Tavily / Serper / SerpAPI.
    """
    return [{"url": "placeholder", "title": "placeholder", "snippet": "placeholder"}]


@celery_app.task(bind=True, name="research.analyze_topic", max_retries=3)
def analyze_topic(self, topic: str) -> dict:
    """Analyze a topic using AI research. [PLACEHOLDER]
    TODO: Implement using ResearchService.research_topic().
    """
    return {"topic": topic, "summary": "placeholder", "key_points": []}


@celery_app.task(bind=True, name="research.fetch_trending", max_retries=2)
def fetch_trending(self, niche: str) -> list[str]:
    """Fetch trending topics in a niche. [PLACEHOLDER]
    TODO: Implement using YouTube Data API trending endpoint.
    """
    return []
