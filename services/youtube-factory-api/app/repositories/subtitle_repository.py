"""Subtitle result repository."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.subtitle_result import SubtitleResult
from app.repositories.base import BaseRepository


class SubtitleRepository(BaseRepository[SubtitleResult]):
    model = SubtitleResult

    async def get_by_render_id(self, render_id: str) -> SubtitleResult | None:
        stmt = (
            select(SubtitleResult)
            .where(SubtitleResult.render_id == render_id)
            .order_by(SubtitleResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> SubtitleResult | None:
        subtitle = await self.get(id)
        if not subtitle:
            return None
        subtitle.status = status
        subtitle.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            subtitle.error_message = error_message
        if status == "completed":
            subtitle.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        return subtitle
