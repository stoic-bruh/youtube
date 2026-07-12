"""Job-specific repository."""
from sqlalchemy import select

from app.models.job import Job
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    model = Job

    async def get_pending(self, limit: int = 10) -> list[Job]:
        stmt = select(Job).where(Job.status == "pending").limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_pipeline(self, pipeline_id: str) -> list[Job]:
        stmt = select(Job).where(Job.pipeline_id == pipeline_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        rows = (await self._db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}
