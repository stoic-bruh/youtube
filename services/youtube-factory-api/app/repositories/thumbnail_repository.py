"""Thumbnail result repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models.thumbnail_result import ThumbnailResult
from app.repositories.base import BaseRepository


class ThumbnailRepository(BaseRepository[ThumbnailResult]):
    model = ThumbnailResult

    async def get_by_render_id(self, render_id: str) -> ThumbnailResult | None:
        stmt = (
            select(ThumbnailResult)
            .where(ThumbnailResult.render_id == render_id)
            .order_by(ThumbnailResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()
