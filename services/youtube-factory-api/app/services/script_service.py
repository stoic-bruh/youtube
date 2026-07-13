"""ScriptService — production-ready script-generation orchestration.

Architecture:
  1. start_script(request)  → create DB record → enqueue Celery task → return record
  2. execute_script(id)     → update status → fetch providers → merge → persist
  3. get / list / delete    → thin repo wrappers

Merge pipeline:
  fetch_all_providers → _select_primary_result → _merge_sections
  → _calculate_metrics → _generate_production_metadata → persist
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from app.models.script_result import ScriptResult
from app.providers.script.registry import ScriptProviderRegistry
from app.repositories.script_repository import ScriptRepository
from app.schemas.script import (
    NarrationTiming,
    ScriptProviderResult,
    ScriptRequest,
    ScriptResultSchema,
    ScriptSection,
    ScriptSectionType,
    ScriptStatus,
)

logger = logging.getLogger(__name__)

# Compatibility alias: several placeholder downstream services (ScenePlanner,
# VoiceGenerator, SEOGenerator, ThumbnailGenerator) type-hint against a
# `Script` type that predates the real `ScriptResult` ORM model. Keep it
# importable here so those untouched placeholder modules keep working.
Script = Any

_CACHE_ENABLED = True
_MIN_CONFIDENCE = 0.4


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("[%H:%M:%S]")


def _count_words(text: str) -> int:
    import re
    return len(re.sub(r"\s+", " ", text.strip()).split()) if text.strip() else 0


class ScriptService:
    """Orchestrates the full script-generation pipeline."""

    def __init__(self, repo: ScriptRepository) -> None:
        self._repo = repo
        self._registry = ScriptProviderRegistry()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def start_script(self, request: ScriptRequest) -> ScriptResult:
        """Create a DB record with status=pending and enqueue the Celery task."""
        job_id = str(uuid.uuid4())
        script = await self._repo.create(
            research_id=request.research_id,
            topic=request.topic,
            status=ScriptStatus.PENDING.value,
            style=request.style.value,
            tone=request.tone.value,
            language=request.language,
            target_audience=request.target_audience,
            target_duration_minutes=request.target_duration_minutes,
            version=1,
            providers=[p.value for p in request.providers],
            used_providers=[],
            sections=[],
            narration_timing=[],
            emphasis_markers=[],
            pauses=[],
            pronunciation_hints=[],
            visual_cues=[],
            versions=[],
            logs=[f"{_ts()} INFO  Script job created. Job ID: {job_id}"],
            job_id=job_id,
        )
        logger.info("Script job created id=%s topic=%r", script.id, request.topic)

        try:
            from app.tasks.script_tasks import run_script_task
            run_script_task.delay(script.id)
        except Exception as exc:
            logger.warning("Celery not available — script will not auto-process: %s", exc)

        return script

    async def execute_script(self, script_id: str) -> ScriptResult | None:
        """Main execution entry point called by the Celery worker."""
        script = await self._repo.get(script_id)
        if not script:
            logger.error("Script %s not found", script_id)
            return None

        logs: list[str] = list(script.logs or [])

        def log(level: str, msg: str) -> None:
            line = f"{_ts()} {level.upper():<5} {msg}"
            logs.append(line)
            logger.info(msg)

        try:
            await self._set_status(script, ScriptStatus.RUNNING, logs)
            log("INFO", f"Starting script generation for topic: '{script.topic}'")
            log("INFO", f"Style: {script.style} | Tone: {script.tone} | Duration: {script.target_duration_minutes}min")
            log("INFO", f"Requested providers: {script.providers}")

            request = ScriptRequest(
                research_id=script.research_id,
                topic=script.topic,
                style=script.style,  # type: ignore[arg-type]
                tone=script.tone,  # type: ignore[arg-type]
                language=script.language,
                target_audience=script.target_audience or "general audience",
                target_duration_minutes=script.target_duration_minutes,
                providers=script.providers,  # type: ignore[arg-type]
            )

            # ── Phase 1: fetch providers ──────────────────────────────────────
            log("INFO", "Phase 1/4 — Fetching from script providers in parallel")
            t0 = time.monotonic()
            provider_results = await self._registry.fetch_all(
                request,
                provider_names=script.providers,
                max_concurrent=4,
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            successful = [r for r in provider_results if not r.error]
            failed = [r for r in provider_results if r.error]
            used_providers = [r.provider_name for r in successful]

            log("INFO", f"Providers completed in {elapsed}ms — {len(successful)} OK, {len(failed)} failed")
            for f in failed:
                log("WARN", f"Provider {f.provider_name!r} failed: {f.error}")

            if not successful:
                raise RuntimeError("All script providers failed — cannot proceed")

            # ── Phase 2: merge ─────────────────────────────────────────────────
            log("INFO", "Phase 2/4 — Selecting primary provider and merging section content")
            primary = self._select_primary_result(successful)
            sections = self._merge_sections(primary, successful)
            log("INFO", f"Merged {len(sections)} sections from {len(successful)} provider(s)")

            # ── Phase 3: metrics ──────────────────────────────────────────────
            log("INFO", "Phase 3/4 — Calculating word count, duration, and scene metrics")
            metrics = self._calculate_metrics(primary, sections)
            log("INFO",
                f"Word count: {metrics['word_count']} | "
                f"Duration: {metrics['estimated_duration_seconds']}s | "
                f"Scenes: {metrics['scene_count']}")

            # ── Phase 4: production metadata ──────────────────────────────────
            log("INFO", "Phase 4/4 — Aggregating production metadata from all providers")
            narration_timing = self._merge_narration_timing(successful)
            emphasis_markers = self._merge_emphasis(successful)
            pauses = self._merge_pauses(successful)
            pronunciation_hints = self._merge_pronunciation(successful)
            visual_cues = self._merge_visual_cues(successful)
            log("INFO",
                f"Timing entries: {len(narration_timing)} | "
                f"Emphasis markers: {len(emphasis_markers)} | "
                f"Visual cues: {len(visual_cues)}")

            # ── Persist ───────────────────────────────────────────────────────
            logs.append(f"{_ts()} INFO  Script generation complete — writing to database")

            updated = await self._repo.update(
                script_id,
                status=ScriptStatus.COMPLETED.value,
                title=primary.title,
                hook=primary.hook,
                introduction=primary.introduction,
                outro=primary.outro,
                call_to_action=primary.call_to_action,
                sections=[s.model_dump() for s in sections],
                narration_timing=[t.model_dump() for t in narration_timing],
                emphasis_markers=[e.model_dump() for e in emphasis_markers],
                pauses=[p.model_dump() for p in pauses],
                pronunciation_hints=[h.model_dump() for h in pronunciation_hints],
                visual_cues=[v.model_dump() for v in visual_cues],
                used_providers=used_providers,
                logs=logs,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                **metrics,
            )
            logger.info("Script %s completed successfully", script_id)
            return updated

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logs.append(f"{_ts()} ERROR Script failed: {error_msg}")
            await self._repo.update(
                script_id,
                status=ScriptStatus.FAILED.value,
                error_message=error_msg,
                logs=logs,
                updated_at=datetime.now(timezone.utc),
            )
            logger.error("Script %s failed: %s", script_id, error_msg, exc_info=True)
            return None

    async def get_script(self, script_id: str) -> ScriptResult | None:
        return await self._repo.get(script_id)

    async def list_scripts(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[ScriptResult], int]:
        kwargs: dict = {}
        if status:
            kwargs["status"] = status
        return await self._repo.list(limit=limit, offset=offset, **kwargs)

    async def delete_script(self, script_id: str) -> bool:
        return await self._repo.delete(script_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _set_status(
        self, script: ScriptResult, status: ScriptStatus, logs: list[str]
    ) -> None:
        script.status = status.value
        script.updated_at = datetime.now(timezone.utc)
        script.logs = logs
        await self._repo._db.flush()

    def _select_primary_result(self, results: list[ScriptProviderResult]) -> ScriptProviderResult:
        """Pick the provider result with highest confidence as the primary source."""
        return max(results, key=lambda r: r.confidence)

    def _merge_sections(
        self,
        primary: ScriptProviderResult,
        all_results: list[ScriptProviderResult],
    ) -> list[ScriptSection]:
        """Merge sections: keep primary's structure, append unique sections from others."""
        merged: list[ScriptSection] = list(primary.sections)
        seen_titles = {s.title.lower() for s in merged}

        for result in all_results:
            if result.provider_name == primary.provider_name:
                continue
            for section in result.sections:
                key = section.title.lower()
                if key not in seen_titles:
                    seen_titles.add(key)
                    merged.append(section)

        # Re-index order
        for i, section in enumerate(merged):
            section.order = i

        return merged

    def _calculate_metrics(
        self,
        primary: ScriptProviderResult,
        sections: list[ScriptSection],
    ) -> dict:
        """Calculate word count and duration metrics from merged content."""
        hook_wc = _count_words(primary.hook)
        intro_wc = _count_words(primary.introduction)
        cta_wc = _count_words(primary.call_to_action)
        outro_wc = _count_words(primary.outro)
        section_wc = sum(s.word_count for s in sections)
        total_wc = hook_wc + intro_wc + section_wc + cta_wc + outro_wc

        avg_wpm = primary.pacing_wpm if primary.pacing_wpm > 0 else 130.0
        est_dur_s = int((total_wc / avg_wpm) * 60)
        read_s = int((total_wc / 200.0) * 60)  # silent reading
        scene_count = len(sections) + 3  # +hook +intro +outro

        return dict(
            word_count=total_wc,
            estimated_duration_seconds=est_dur_s,
            reading_time_seconds=read_s,
            scene_count=scene_count,
            pacing_wpm=round(avg_wpm, 1),
        )

    def _merge_narration_timing(
        self, results: list[ScriptProviderResult]
    ) -> list[NarrationTiming]:
        """Use primary's timing; append any additional entries from others."""
        primary = self._select_primary_result(results)
        seen_titles = {t.section_title for t in primary.narration_timing}
        merged = list(primary.narration_timing)
        for r in results:
            if r.provider_name == primary.provider_name:
                continue
            for t in r.narration_timing:
                if t.section_title not in seen_titles:
                    seen_titles.add(t.section_title)
                    merged.append(t)
        return merged

    def _merge_emphasis(self, results: list[ScriptProviderResult]) -> list:
        primary = self._select_primary_result(results)
        seen_positions = {e.position for e in primary.emphasis_markers}
        merged = list(primary.emphasis_markers)
        for r in results:
            if r.provider_name == primary.provider_name:
                continue
            for e in r.emphasis_markers:
                if e.position not in seen_positions:
                    seen_positions.add(e.position)
                    merged.append(e)
        return merged[:20]

    def _merge_pauses(self, results: list[ScriptProviderResult]) -> list:
        primary = self._select_primary_result(results)
        seen_positions = {p.position for p in primary.pauses}
        merged = list(primary.pauses)
        for r in results:
            if r.provider_name == primary.provider_name:
                continue
            for p in r.pauses:
                if p.position not in seen_positions:
                    seen_positions.add(p.position)
                    merged.append(p)
        return merged[:15]

    def _merge_pronunciation(self, results: list[ScriptProviderResult]) -> list:
        seen_words: set[str] = set()
        merged: list = []
        for r in results:
            for h in r.pronunciation_hints:
                if h.word.lower() not in seen_words:
                    seen_words.add(h.word.lower())
                    merged.append(h)
        return merged[:10]

    def _merge_visual_cues(self, results: list[ScriptProviderResult]) -> list:
        primary = self._select_primary_result(results)
        seen_times = {v.time_ms for v in primary.visual_cues}
        merged = list(primary.visual_cues)
        for r in results:
            if r.provider_name == primary.provider_name:
                continue
            for v in r.visual_cues:
                if v.time_ms not in seen_times:
                    seen_times.add(v.time_ms)
                    merged.append(v)
        merged.sort(key=lambda v: v.time_ms)
        return merged[:20]
