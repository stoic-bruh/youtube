"""Script result repository."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.script_result import ScriptResult
from app.repositories.base import BaseRepository


class ScriptRepository(BaseRepository[ScriptResult]):
    model = ScriptResult

    async def get_by_status(self, status: str) -> list[ScriptResult]:
        stmt = select(ScriptResult).where(ScriptResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_research_id(self, research_id: str) -> list[ScriptResult]:
        stmt = (
            select(ScriptResult)
            .where(ScriptResult.research_id == research_id)
            .order_by(ScriptResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        """Append a single log line to a script record."""
        script = await self.get(id)
        if script:
            current_logs: list[str] = list(script.logs or [])
            current_logs.append(message)
            script.logs = current_logs
            script.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> ScriptResult | None:
        """Update status and optionally append a log line."""
        script = await self.get(id)
        if not script:
            return None
        script.status = status
        script.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            script.error_message = error_message
        if status == "completed":
            script.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(script.logs or [])
            logs.append(log_line)
            script.logs = logs
        await self._db.flush()
        return script
