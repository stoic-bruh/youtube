"""Project-specific repository."""
from sqlalchemy import select

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_by_status(self, status: str) -> list[Project]:
        stmt = select(Project).where(Project.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        stmt = select(Project.status, func.count(Project.id)).group_by(Project.status)
        rows = (await self._db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}
