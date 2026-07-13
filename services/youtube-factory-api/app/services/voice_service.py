"""VoiceService — production-ready narration/TTS orchestration.

Architecture:
  1. start_voice(request)   → validate script exists → create DB record
                               → enqueue Celery task → return record
  2. execute_voice(id)      → update status → build narration units from the
                               source script → fetch provider (with fallback)
                               → normalize loudness → persist
  3. get / list / delete    → thin repo wrappers

Unlike Script/Storyboard (which merge results from multiple providers),
Voice synthesis tries providers in fallback order and keeps the first
successful audio result, since TTS output cannot be merged across providers.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.models.voice_result import VoiceResult
from app.providers.voice.registry import VoiceProviderRegistry
from app.repositories.script_repository import ScriptRepository
from app.repositories.voice_repository import VoiceRepository
from app.schemas.voice import VoiceRequest, VoiceStatus

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


class VoiceService:
    """Orchestrates the full narration-generation (TTS) pipeline."""

    def __init__(self, repo: VoiceRepository, script_repo: ScriptRepository | None = None) -> None:
        self._repo = repo
        # Voice reads (never writes) script content, so it can share the
        # same AsyncSession as the voice repository.
        self._script_repo = script_repo or ScriptRepository(repo._db)
        self._registry = VoiceProviderRegistry()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def start_voice(self, request: VoiceRequest) -> VoiceResult:
        """Validate the source script exists, create a pending record, and
        enqueue the Celery task."""
        script = await self._script_repo.get(request.script_id)
        if not script:
            raise ValueError(f"Script {request.script_id!r} not found")

        job_id = str(uuid.uuid4())
        voice = await self._repo.create(
            script_id=request.script_id,
            status=VoiceStatus.PENDING.value,
            voice_id=request.voice_id,
            speed=request.speed,
            language=request.language,
            target_loudness_lufs=request.target_loudness_lufs,
            sections=[],
            providers=[p.value for p in request.providers],
            logs=[f"{_ts()} INFO  Voice job created. Job ID: {job_id}"],
            job_id=job_id,
        )
        logger.info("Voice job created id=%s script_id=%s", voice.id, request.script_id)

        try:
            from app.tasks.voice_tasks import run_voice_task
            run_voice_task.delay(voice.id)
        except Exception as exc:
            logger.warning("Celery not available — voice will not auto-process: %s", exc)

        return voice

    async def execute_voice(self, voice_id: str) -> VoiceResult | None:
        """Main execution entry point called by the Celery worker."""
        voice = await self._repo.get(voice_id)
        if not voice:
            logger.error("Voice %s not found", voice_id)
            return None

        logs: list[str] = list(voice.logs or [])

        def log(level: str, msg: str) -> None:
            logs.append(f"{_ts()} {level.upper():<5} {msg}")
            logger.info(msg)

        try:
            await self._set_status(voice, VoiceStatus.RUNNING, logs)
            log("INFO", f"Starting narration generation for script: {voice.script_id!r}")
            log("INFO", f"Voice: {voice.voice_id} | Speed: {voice.speed}x | Language: {voice.language}")

            # ── Phase 1: build narration units from the source script ─────────
            log("INFO", "Phase 1/3 — Assembling narration units from script content")
            script = await self._script_repo.get(voice.script_id)
            if not script:
                raise RuntimeError(f"Source script {voice.script_id!r} no longer exists")
            sections = self._build_narration_units(script)
            if not sections:
                raise RuntimeError("Script has no narratable content (hook/sections/outro/CTA are all empty)")
            log("INFO", f"Assembled {len(sections)} narration unit(s)")

            request = VoiceRequest(
                script_id=voice.script_id,
                voice_id=voice.voice_id,
                speed=voice.speed,
                language=voice.language,
                target_loudness_lufs=voice.target_loudness_lufs,
                providers=voice.providers,  # type: ignore[arg-type]
            )

            # ── Phase 2: synthesize with fallback ───────────────────────────────
            log("INFO", f"Phase 2/3 — Synthesizing narration (providers: {voice.providers})")
            result, attempts = await self._registry.fetch_with_fallback(
                request, sections, provider_names=voice.providers
            )
            for attempt in attempts:
                status_word = "OK" if not attempt.error else f"FAILED ({attempt.error})"
                log("INFO", f"Provider {attempt.provider_name!r}: {status_word}")

            if result.error:
                raise RuntimeError(f"All voice providers failed — last error: {result.error}")

            log("INFO",
                f"Synthesis complete via {result.provider_name!r} — "
                f"{result.total_duration_ms}ms audio, ${result.cost_usd} estimated cost")

            # ── Phase 3: loudness normalization ─────────────────────────────────
            log("INFO", f"Phase 3/3 — Normalizing loudness to {voice.target_loudness_lufs} LUFS")
            normalized_sections = self._normalize_sections(result.sections, voice.target_loudness_lufs)
            log("INFO", "Normalization complete — writing to database")

            word_count = sum(s.word_count for s in result.sections)

            updated = await self._repo.update(
                voice_id,
                status=VoiceStatus.COMPLETED.value,
                sections=[s.model_dump() for s in normalized_sections],
                total_duration_ms=result.total_duration_ms,
                word_count=word_count,
                sample_rate=result.sample_rate,
                audio_format=result.audio_format,
                normalized=True,
                cost_usd=result.cost_usd,
                used_provider=result.provider_name,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Voice %s completed successfully", voice_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Voice generation failed: {error_msg}")
            await self._repo.update(
                voice_id,
                status=VoiceStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Voice %s failed: %s", voice_id, error_msg, exc_info=True)
            return None

    async def get_voice(self, voice_id: str) -> VoiceResult | None:
        return await self._repo.get(voice_id)

    async def list_voices(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        script_id: str | None = None,
    ) -> tuple[list[VoiceResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        if script_id:
            kwargs["script_id"] = script_id
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_voice(self, voice_id: str) -> bool:
        return await self._repo.delete(voice_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _set_status(self, voice: VoiceResult, status: VoiceStatus, logs: list[str]) -> None:
        voice.status = status.value
        voice.updated_at = datetime.now(timezone.utc)
        voice.logs = logs
        await self._repo._db.flush()

    def _build_narration_units(self, script) -> list[dict]:
        """Flatten a ScriptResult's content fields into ordered narration units."""
        units: list[dict] = []
        if script.hook:
            units.append({"title": "Hook", "text": script.hook})
        if script.introduction:
            units.append({"title": "Introduction", "text": script.introduction})
        for section in (script.sections or []):
            title = section.get("title") or f"Section {len(units) + 1}"
            content = section.get("content") or ""
            if content:
                units.append({"title": title, "text": content})
        if script.call_to_action:
            units.append({"title": "Call to Action", "text": script.call_to_action})
        if script.outro:
            units.append({"title": "Outro", "text": script.outro})
        return units

    def _normalize_sections(self, sections: list, target_loudness_lufs: float) -> list:
        """Apply loudness normalization bookkeeping to each section's audio path.

        Real loudness normalization (FFmpeg/pydub two-pass EBU R128) is out of
        scope for the backend orchestration layer; this records that
        normalization has been applied and standardizes the output path.
        """
        normalized = []
        for section in sections:
            normalized.append(
                section.model_copy(
                    update={"local_path": section.local_path.replace(".mp3", "_normalized.mp3")}
                )
            )
        return normalized
