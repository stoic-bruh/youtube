"""Render result repository."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.render import RenderResult
from app.repositories.base import BaseRepository


class RenderRepository(BaseRepository[RenderResult]):
    model = RenderResult

    async def get_by_status(self, status: str) -> list[RenderResult]:
        stmt = select(RenderResult).where(RenderResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_timeline_id(self, timeline_id: str) -> list[RenderResult]:
        stmt = (
            select(RenderResult)
            .where(RenderResult.timeline_id == timeline_id)
            .order_by(RenderResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        render = await self.get(id)
        if render:
            current_logs: list[str] = list(render.logs or [])
            current_logs.append(message)
            render.logs = current_logs
            render.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        progress: int | None = None,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> RenderResult | None:
        render = await self.get(id)
        if not render:
            return None
        render.status = status
        render.updated_at = datetime.now(timezone.utc)
        if progress is not None:
            render.progress = progress
        if error_message is not None:
            render.error_message = error_message
        if status == "completed":
            render.completed_at = datetime.now(timezone.utc)
            render.progress = 100
        if log_line:
            logs = list(render.logs or [])
            logs.append(log_line)
            render.logs = logs
        await self._db.flush()
        return render
