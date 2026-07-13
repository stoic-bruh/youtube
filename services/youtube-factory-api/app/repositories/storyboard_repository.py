"""Storyboard result repository."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.storyboard_result import StoryboardResult
from app.repositories.base import BaseRepository


class StoryboardRepository(BaseRepository[StoryboardResult]):
    model = StoryboardResult

    async def get_by_status(self, status: str) -> list[StoryboardResult]:
        stmt = select(StoryboardResult).where(StoryboardResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_script_id(self, script_id: str) -> list[StoryboardResult]:
        stmt = (
            select(StoryboardResult)
            .where(StoryboardResult.script_id == script_id)
            .order_by(StoryboardResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_research_id(self, research_id: str) -> list[StoryboardResult]:
        stmt = (
            select(StoryboardResult)
            .where(StoryboardResult.research_id == research_id)
            .order_by(StoryboardResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        """Append a single log line to a storyboard record."""
        sb = await self.get(id)
        if sb:
            current_logs: list[str] = list(sb.logs or [])
            current_logs.append(message)
            sb.logs = current_logs
            sb.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> StoryboardResult | None:
        """Update status and optionally append a log line."""
        sb = await self.get(id)
        if not sb:
            return None
        sb.status = status
        sb.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            sb.error_message = error_message
        if status == "completed":
            sb.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(sb.logs or [])
            logs.append(log_line)
            sb.logs = logs
        await self._db.flush()
        return sb
