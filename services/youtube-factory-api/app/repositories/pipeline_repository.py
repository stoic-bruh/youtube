"""Pipeline-specific repository."""
from sqlalchemy import select

from app.models.pipeline import Pipeline
from app.repositories.base import BaseRepository


class PipelineRepository(BaseRepository[Pipeline]):
    model = Pipeline

    async def get_by_project(self, project_id: str) -> list[Pipeline]:
        stmt = select(Pipeline).where(Pipeline.project_id == project_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self) -> list[Pipeline]:
        stmt = select(Pipeline).where(Pipeline.status.in_(["queued", "running"]))
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
