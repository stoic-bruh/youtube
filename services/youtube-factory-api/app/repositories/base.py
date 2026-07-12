"""Generic async repository base class (Repository Pattern)."""
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD base repository for SQLAlchemy async models."""

    model: Type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, id: Any) -> ModelT | None:
        return await self._db.get(self.model, id)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> tuple[Sequence[ModelT], int]:
        stmt = select(self.model)
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self._db.execute(count_stmt)).scalar_one()

        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._db.execute(stmt)).scalars().all()
        return rows, total

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(**kwargs)
        self._db.add(instance)
        await self._db.flush()
        await self._db.refresh(instance)
        return instance

    async def update(self, id: Any, **kwargs: Any) -> ModelT | None:
        instance = await self.get(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self._db.flush()
        await self._db.refresh(instance)
        return instance

    async def delete(self, id: Any) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False
        await self._db.delete(instance)
        await self._db.flush()
        return True
