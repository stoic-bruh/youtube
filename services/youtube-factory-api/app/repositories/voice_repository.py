"""Voice result repository."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.voice_result import VoiceResult
from app.repositories.base import BaseRepository


class VoiceRepository(BaseRepository[VoiceResult]):
    model = VoiceResult

    async def get_by_status(self, status: str) -> list[VoiceResult]:
        stmt = select(VoiceResult).where(VoiceResult.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_script_id(self, script_id: str) -> list[VoiceResult]:
        stmt = (
            select(VoiceResult)
            .where(VoiceResult.script_id == script_id)
            .order_by(VoiceResult.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def append_log(self, id: str, message: str) -> None:
        """Append a single log line to a voice record."""
        voice = await self.get(id)
        if voice:
            current_logs: list[str] = list(voice.logs or [])
            current_logs.append(message)
            voice.logs = current_logs
            voice.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: str | None = None,
        log_line: str | None = None,
    ) -> VoiceResult | None:
        """Update status and optionally append a log line."""
        voice = await self.get(id)
        if not voice:
            return None
        voice.status = status
        voice.updated_at = datetime.now(timezone.utc)
        if error_message is not None:
            voice.error_message = error_message
        if status == "completed":
            voice.completed_at = datetime.now(timezone.utc)
        if log_line:
            logs = list(voice.logs or [])
            logs.append(log_line)
            voice.logs = logs
        await self._db.flush()
        return voice
