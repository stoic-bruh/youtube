"""Timeline repository."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.timeline import TimelineResult
from app.repositories.base import BaseRepository


class TimelineRepository(BaseRepository[TimelineResult]):
    model = TimelineResult

    async def get_by_storyboard(self, storyboard_id: str) -> list[TimelineResult]:
        stmt = (
            select(TimelineResult)
            .where(TimelineResult.storyboard_id == storyboard_id)
            .order_by(TimelineResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[TimelineResult]:
        stmt = select(TimelineResult).where(TimelineResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        timeline = await self.get(id)
        if timeline:
            logs: list[str] = list(timeline.logs or [])
            logs.append(message)
            timeline.logs = logs
            timeline.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> TimelineResult | None:
        timeline = await self.get(id)
        if not timeline:
            return None
        timeline.status = status
        timeline.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            timeline.error_message = error_message
        if status == "completed":
            timeline.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(timeline.logs or [])
            logs.append(log_line)
            timeline.logs = logs
        await self._db.flush()
        return timeline
