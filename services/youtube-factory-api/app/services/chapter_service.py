"""ChapterService — Post-Processing chapter orchestration.

Chapters are derived purely from structured pipeline data already produced
by earlier stages (Timeline scenes, merged into the render's RenderPlan with
exact real start/end timestamps, plus the source Script's section titles for
richer descriptions). No media analysis is required, so this stage runs
in-process with no external tools.

Architecture (mirrors Voice/Render/Subtitle/Thumbnail):
  1. start_chapter(request) → validate render exists & is completed → create
                               DB record → enqueue Celery task → return record
  2. execute_chapter(id)    → read RenderResult.render_plan.scenes (real,
                               already-rendered timing) → merge sub-minimum
                               scenes → build ChapterEntry list + YouTube
                               export text → persist
  3. get / list / delete    → thin repo wrappers
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.models.chapter_result import ChapterResult
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.render_repository import RenderRepository
from app.repositories.script_repository import ScriptRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.chapter import ChapterRequest, ChapterStatus

logger = logging.getLogger(__name__)

# YouTube requires the first chapter to start at 0:00 and every chapter to be
# at least 10 seconds long.
YOUTUBE_MIN_CHAPTER_MS = 10_000


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


def _format_youtube_timestamp(ms: int) -> str:
    total_seconds = max(ms, 0) // 1000
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def merge_short_scenes(raw_chapters: list[dict], min_duration_ms: int = YOUTUBE_MIN_CHAPTER_MS) -> list[dict]:
    """Merge chapters shorter than YouTube's minimum into the following
    chapter (or the previous one, if it's the last chapter)."""
    if not raw_chapters:
        return []
    merged: list[dict] = [dict(raw_chapters[0])]
    for chapter in raw_chapters[1:]:
        duration = chapter["end_ms"] - chapter["start_ms"]
        prev = merged[-1]
        prev_duration = prev["end_ms"] - prev["start_ms"]
        if prev_duration < min_duration_ms:
            # fold the too-short previous chapter into this one, keeping its title
            prev["end_ms"] = chapter["start_ms"]
            merged.append(dict(chapter))
        elif duration < min_duration_ms:
            # too-short chapter — extend the previous one to cover it
            prev["end_ms"] = chapter["end_ms"]
        else:
            merged.append(dict(chapter))
    # If the very last chapter ended up too short, fold it back into its predecessor.
    if len(merged) > 1 and (merged[-1]["end_ms"] - merged[-1]["start_ms"]) < min_duration_ms:
        last = merged.pop()
        merged[-1]["end_ms"] = last["end_ms"]
    return merged


class ChapterService:
    def __init__(
        self,
        repo: ChapterRepository,
        render_repo: RenderRepository | None = None,
        timeline_repo: TimelineRepository | None = None,
        script_repo: ScriptRepository | None = None,
    ) -> None:
        self._repo = repo
        self._render_repo = render_repo or RenderRepository(repo._db)
        self._timeline_repo = timeline_repo or TimelineRepository(repo._db)
        self._script_repo = script_repo or ScriptRepository(repo._db)

    async def start_chapter(self, request: ChapterRequest) -> ChapterResult:
        render = await self._render_repo.get(request.render_id)
        if not render:
            raise ValueError(f"Render {request.render_id!r} not found")
        if render.status != "completed":
            raise ValueError(f"Render {request.render_id!r} is not completed (status={render.status!r})")
        if not (render.render_plan or {}).get("scenes"):
            raise ValueError(f"Render {request.render_id!r} has no scene timing to derive chapters from")

        job_id = str(uuid.uuid4())
        chapter = await self._repo.create(
            render_id=request.render_id,
            status=ChapterStatus.PENDING.value,
            logs=[f"{_ts()} INFO  Chapter job created. Job ID: {job_id}"],
        )
        logger.info("Chapter job created id=%s render_id=%s", chapter.id, request.render_id)

        try:
            from app.tasks.chapter_tasks import run_chapter_task
            run_chapter_task.delay(chapter.id)
        except Exception as exc:
            logger.warning("Celery not available — chapter will not auto-process: %s", exc)

        return chapter

    async def execute_chapter(self, chapter_id: str) -> ChapterResult | None:
        chapter = await self._repo.get(chapter_id)
        if not chapter:
            logger.error("Chapter %s not found", chapter_id)
            return None

        logs: list[str] = list(chapter.logs or [])

        def log(level: str, msg: str) -> None:
            logs.append(f"{_ts()} {level.upper():<5} {msg}")
            logger.info(msg)

        try:
            await self._repo.update(chapter_id, status=ChapterStatus.RUNNING.value, logs=logs)
            log("INFO", f"Starting chapter derivation for render={chapter.render_id!r}")

            render = await self._render_repo.get(chapter.render_id)
            if not render:
                raise RuntimeError(f"Source render {chapter.render_id!r} no longer exists")
            scenes = list((render.render_plan or {}).get("scenes") or [])
            if not scenes:
                raise RuntimeError("Render has no scene timing to derive chapters from")

            timeline = await self._timeline_repo.get(render.timeline_id) if render.timeline_id else None
            script = await self._script_repo.get(timeline.script_id) if timeline and timeline.script_id else None
            script_sections_by_title = {
                (s.get("title") or "").strip().lower(): s
                for s in (script.sections or [])
            } if script else {}

            log("INFO", f"Phase 1/2 — Building {len(scenes)} raw chapter(s) from real scene timing")
            raw_chapters = []
            for scene in sorted(scenes, key=lambda s: s.get("scene_index", 0)):
                title = scene.get("title") or f"Chapter {scene.get('scene_index', 0) + 1}"
                start_ms = int(scene.get("start_ms", 0))
                end_ms = int(scene.get("end_ms", start_ms))
                section = script_sections_by_title.get(title.strip().lower())
                narration = scene.get("narration") or ""
                description = (section.get("content") if section else None) or narration or None
                if description:
                    description = description[:280]
                raw_chapters.append({"title": title, "start_ms": start_ms, "end_ms": end_ms, "description": description})

            if raw_chapters:
                raw_chapters[0]["start_ms"] = 0

            log("INFO", "Phase 2/2 — Merging sub-10s scenes to satisfy YouTube's minimum chapter length")
            merged = merge_short_scenes(raw_chapters)
            log("INFO", f"{len(raw_chapters)} raw scene(s) -> {len(merged)} YouTube-valid chapter(s)")

            youtube_lines = [f"{_format_youtube_timestamp(c['start_ms'])} {c['title']}" for c in merged]
            youtube_export = "\n".join(youtube_lines)

            sources = {
                "render_id": chapter.render_id,
                "timeline_id": render.timeline_id,
                "script_id": timeline.script_id if timeline else None,
                "voice_id": render.voice_id,
            }

            updated = await self._repo.update(
                chapter_id,
                status=ChapterStatus.COMPLETED.value,
                chapters=merged,
                youtube_export=youtube_export,
                sources=sources,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            logger.info("Chapter %s completed successfully", chapter_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Chapter generation failed: {error_msg}")
            await self._repo.update(
                chapter_id,
                status=ChapterStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Chapter %s failed: %s", chapter_id, error_msg, exc_info=True)
            return None

    async def get_chapter(self, chapter_id: str) -> ChapterResult | None:
        return await self._repo.get(chapter_id)

    async def list_chapters(
        self, limit: int = 50, offset: int = 0, status: str | None = None, render_id: str | None = None,
    ) -> tuple[list[ChapterResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        if render_id:
            kwargs["render_id"] = render_id
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_chapter(self, chapter_id: str) -> bool:
        return await self._repo.delete(chapter_id)
