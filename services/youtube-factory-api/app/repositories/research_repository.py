"""Research result repository."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.research_result import ResearchResult
from app.repositories.base import BaseRepository

CACHE_TTL_HOURS = 168  # 7 days


class ResearchRepository(BaseRepository[ResearchResult]):
    model = ResearchResult

    async def get_cached(self, topic_normalized: str) -> ResearchResult | None:
        """Find a recent completed research for the same normalized topic (cache hit)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
        stmt = (
            select(ResearchResult)
            .where(ResearchResult.topic_normalized == topic_normalized)
            .where(ResearchResult.status == "completed")
            .where(ResearchResult.completed_at >= cutoff)
            .order_by(ResearchResult.completed_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> list[ResearchResult]:
        stmt = select(ResearchResult).where(ResearchResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        """Append a single log line to a research record (efficient partial update)."""
        research = await self.get(id)
        if research:
            current_logs: list[str] = list(research.logs or [])
            current_logs.append(message)
            research.logs = current_logs
            research.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> ResearchResult | None:
        """Update status and optionally append a log line."""
        research = await self.get(id)
        if not research:
            return None
        research.status = status
        research.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            research.error_message = error_message
        if status == "completed":
            research.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(research.logs or [])
            logs.append(log_line)
            research.logs = logs
        await self._db.flush()
        return research
