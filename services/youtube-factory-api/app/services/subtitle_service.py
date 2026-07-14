"""SubtitleService — Post-Processing subtitle orchestration.

Architecture (mirrors Voice/Render):
  1. start_subtitle(request) → validate the source render exists & is
                                completed → create DB record → enqueue Celery
                                task → return record
  2. execute_subtitle(id)    → resolve the render's video file + narration
                                context → transcribe with provider fallback
                                (Whisper -> script-narration) → build
                                SRT/VTT/ASS → persist
  3. get / list / delete     → thin repo wrappers
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from app.models.subtitle_result import SubtitleResult
from app.providers.subtitle.registry import SubtitleProviderRegistry
from app.repositories.render_repository import RenderRepository
from app.repositories.subtitle_repository import SubtitleRepository
from app.repositories.voice_repository import VoiceRepository
from app.schemas.subtitle import SubtitleRequest, SubtitleStatus
from app.services.postprocess.subtitle_formats import build_ass, build_srt, build_vtt

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.environ.get("POSTPROCESS_OUTPUT_DIR", "/tmp/postprocess_engine/subtitles")

_DEFAULT_STYLE = {
    "fontFamily": "Arial",
    "fontSize": 72,
    "primaryColor": "#FFFFFF",
    "outlineColor": "#000000",
    "backgroundColor": "#00000080",
    "position": "bottom-center",
}

_CAPTION_PRESETS = [
    {"id": "classic", "label": "Classic", "burned": False, "fontSize": 48, "position": "bottom-center"},
    {"id": "bold-center", "label": "Bold Center", "burned": True, "fontSize": 72, "position": "middle-center"},
    {"id": "karaoke-yellow", "label": "Karaoke", "burned": True, "fontSize": 64, "highlightColor": "#FFD700", "position": "bottom-center"},
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


class SubtitleService:
    def __init__(self, repo: SubtitleRepository, render_repo: RenderRepository | None = None, voice_repo: VoiceRepository | None = None) -> None:
        self._repo = repo
        self._render_repo = render_repo or RenderRepository(repo._db)
        self._voice_repo = voice_repo or VoiceRepository(repo._db)
        self._registry = SubtitleProviderRegistry()

    async def start_subtitle(self, request: SubtitleRequest) -> SubtitleResult:
        render = await self._render_repo.get(request.render_id)
        if not render:
            raise ValueError(f"Render {request.render_id!r} not found")
        if render.status != "completed":
            raise ValueError(f"Render {request.render_id!r} is not completed (status={render.status!r})")
        if not (render.render_output or {}).get("local_path"):
            raise ValueError(f"Render {request.render_id!r} has no output file to transcribe")

        job_id = str(uuid.uuid4())
        subtitle = await self._repo.create(
            render_id=request.render_id,
            status=SubtitleStatus.PENDING.value,
            language=request.language,
            providers=[p.value for p in request.providers],
            logs=[f"{_ts()} INFO  Subtitle job created. Job ID: {job_id}"],
        )
        logger.info("Subtitle job created id=%s render_id=%s", subtitle.id, request.render_id)

        try:
            from app.tasks.subtitle_tasks import run_subtitle_task
            run_subtitle_task.delay(subtitle.id)
        except Exception as exc:
            logger.warning("Celery not available — subtitle will not auto-process: %s", exc)

        return subtitle

    async def execute_subtitle(self, subtitle_id: str) -> SubtitleResult | None:
        subtitle = await self._repo.get(subtitle_id)
        if not subtitle:
            logger.error("Subtitle %s not found", subtitle_id)
            return None

        logs: list[str] = list(subtitle.logs or [])

        def log(level: str, msg: str) -> None:
            logs.append(f"{_ts()} {level.upper():<5} {msg}")
            logger.info(msg)

        try:
            await self._repo.update(subtitle_id, status=SubtitleStatus.RUNNING.value, logs=logs)
            log("INFO", f"Starting transcription for render={subtitle.render_id!r}")

            render = await self._render_repo.get(subtitle.render_id)
            if not render:
                raise RuntimeError(f"Source render {subtitle.render_id!r} no longer exists")
            video_path = (render.render_output or {}).get("local_path")
            if not video_path or not os.path.isfile(video_path):
                raise RuntimeError(f"Render output file not found: {video_path!r}")

            voice = await self._voice_repo.get(render.voice_id) if render.voice_id else None
            sections = [
                {
                    "text": s.get("text", ""),
                    "start_ms": s.get("start_ms", s.get("startMs", 0)),
                    "end_ms": s.get("end_ms", s.get("endMs", 0)),
                }
                for s in (voice.sections or [])
            ] if voice else []

            log("INFO", f"Phase 1/2 — Transcribing (providers: {subtitle.providers})")
            result, attempts = await self._registry.fetch_with_fallback(
                video_path, subtitle.language, subtitle.providers, context={"sections": sections}
            )
            for attempt in attempts:
                status_word = "OK" if not attempt.error else f"FAILED ({attempt.error})"
                log("INFO", f"Provider {attempt.provider_name!r}: {status_word}")

            if result.error or not result.words:
                raise RuntimeError(f"All subtitle providers failed — last error: {result.error}")

            log("INFO", f"Transcription complete via {result.provider_name!r} — {len(result.words)} word(s)")

            log("INFO", "Phase 2/2 — Generating SRT/VTT/ASS exports")
            sentences_dicts = [s.model_dump() for s in result.sentences]
            words_dicts = [w.model_dump() for w in result.words]
            srt_content = build_srt(sentences_dicts)
            vtt_content = build_vtt(sentences_dicts)
            ass_content = build_ass(sentences_dicts, words_dicts)

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            srt_path = os.path.join(OUTPUT_DIR, f"{subtitle_id}.srt")
            vtt_path = os.path.join(OUTPUT_DIR, f"{subtitle_id}.vtt")
            ass_path = os.path.join(OUTPUT_DIR, f"{subtitle_id}.ass")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            with open(vtt_path, "w", encoding="utf-8") as f:
                f.write(vtt_content)
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)
            log("INFO", f"Wrote {srt_path}, {vtt_path}, {ass_path}")

            speaker_metadata = [{"speakerId": "speaker-1", "label": "Narrator", "wordCount": len(result.words)}]

            updated = await self._repo.update(
                subtitle_id,
                status=SubtitleStatus.COMPLETED.value,
                used_provider=result.provider_name,
                words=words_dicts,
                sentences=sentences_dicts,
                paragraphs=[p.model_dump() for p in result.paragraphs],
                srt_content=srt_content,
                vtt_content=vtt_content,
                ass_content=ass_content,
                srt_path=srt_path,
                vtt_path=vtt_path,
                ass_path=ass_path,
                style=_DEFAULT_STYLE,
                caption_presets=_CAPTION_PRESETS,
                burned_metadata={"enabled": False, "presetId": "classic"},
                animated_caption_metadata={"enabled": True, "animation": "word-pop", "presetId": "bold-center"},
                karaoke_metadata={"enabled": True, "highlightColor": "#FFD700", "presetId": "karaoke-yellow"},
                speaker_metadata=speaker_metadata,
                avg_confidence=result.avg_confidence,
                word_count=len(result.words),
                duration_ms=result.duration_ms,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Subtitle %s completed successfully", subtitle_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Subtitle generation failed: {error_msg}")
            await self._repo.update(
                subtitle_id,
                status=SubtitleStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Subtitle %s failed: %s", subtitle_id, error_msg, exc_info=True)
            return None

    async def get_subtitle(self, subtitle_id: str) -> SubtitleResult | None:
        return await self._repo.get(subtitle_id)

    async def list_subtitles(
        self, limit: int = 50, offset: int = 0, status: str | None = None, render_id: str | None = None,
    ) -> tuple[list[SubtitleResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        if render_id:
            kwargs["render_id"] = render_id
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_subtitle(self, subtitle_id: str) -> bool:
        subtitle = await self._repo.get(subtitle_id)
        if subtitle:
            for path in (subtitle.srt_path, subtitle.vtt_path, subtitle.ass_path):
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        return await self._repo.delete(subtitle_id)
