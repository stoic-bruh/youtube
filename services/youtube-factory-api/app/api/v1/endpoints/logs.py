"""Log entry endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.log_entry import LogEntry

router = APIRouter()


@router.get("")
async def list_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    level: str | None = Query(None),
    service: str | None = Query(None),
    limit: int = Query(100, le=500),
) -> dict:
    stmt = select(LogEntry).order_by(LogEntry.timestamp.desc()).limit(limit)
    if level:
        stmt = stmt.where(LogEntry.level == level)
    if service:
        stmt = stmt.where(LogEntry.service == service)

    rows = (await db.execute(stmt)).scalars().all()

    count_stmt = select(func.count()).select_from(LogEntry)
    if level:
        count_stmt = count_stmt.where(LogEntry.level == level)
    if service:
        count_stmt = count_stmt.where(LogEntry.service == service)
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        {
            "id": r.id,
            "level": r.level,
            "message": r.message,
            "service": r.service,
            "projectId": r.project_id,
            "jobId": r.job_id,
            "meta": r.meta,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]
    return {"items": items, "total": total}
