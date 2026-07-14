"""Chapter result repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models.chapter_result import ChapterResult
from app.repositories.base import BaseRepository


class ChapterRepository(BaseRepository[ChapterResult]):
    model = ChapterResult

    async def get_by_render_id(self, render_id: str) -> ChapterResult | None:
        stmt = (
            select(ChapterResult)
            .where(ChapterResult.render_id == render_id)
            .order_by(ChapterResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()
