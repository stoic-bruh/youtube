"""Production asset bundle repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models.production_asset import ProductionAsset
from app.repositories.base import BaseRepository


class ProductionAssetRepository(BaseRepository[ProductionAsset]):
    model = ProductionAsset

    async def get_by_render_id(self, render_id: str) -> ProductionAsset | None:
        stmt = select(ProductionAsset).where(ProductionAsset.render_id == render_id)
        result = await self._db.execute(stmt)
        return result.scalars().first()
