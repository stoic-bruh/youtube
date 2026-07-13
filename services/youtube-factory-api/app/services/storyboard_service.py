"""StoryboardService — full async implementation.

Pipeline:
  Phase 1 — Fetch scenes from all providers in parallel
  Phase 2 — Merge scenes (primary provider wins; supplementary scenes appended)
  Phase 3 — Merge narration timing, visual cues, and production metadata
  Phase 4 — Compute production metrics (complexity, render time, cost)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.storyboard_result import StoryboardResult
from app.providers.storyboard.registry import StoryboardProviderRegistry
from app.repositories.storyboard_repository import StoryboardRepository
from app.schemas.storyboard import (
    NarrationTiming,
    Scene,
    SceneTimeline,
    StoryboardProviderResult,
    StoryboardRequest,
    StoryboardStatus,
    VisualCue,
)

logger = logging.getLogger(__name__)


def _ts() -> str:
    return f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}]"


class StoryboardService:
    def __init__(self, repo: StoryboardRepository) -> None:
        self._repo = repo

    # ── Public CRUD ────────────────────────────────────────────────────────────

    async def start_storyboard(self, request: StoryboardRequest) -> StoryboardResult:
        """Create a storyboard record and enqueue the Celery task."""
        job_id = str(uuid.uuid4())
        sb = await self._repo.create(
            id=str(uuid.uuid4()),
            script_id=request.script_id,
            research_id=request.research_id,
            topic=request.topic,
            status=StoryboardStatus.PENDING.value,
            script_style=request.script_style,
            script_tone=request.script_tone,
            target_duration_minutes=request.target_duration_minutes,
            target_audience=request.target_audience,
            language=request.language,
            version=1,
            providers=[p.value for p in request.providers],
            used_providers=[],
            scenes=[],
            scene_timeline=[],
            narration_timing=[],
            visual_cues=[],
            logs=[f"{_ts()} INFO  Storyboard job created — providers: {', '.join(p.value for p in request.providers)}"],
            job_id=job_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Enqueue Celery task (graceful if Celery unavailable)
        try:
            from app.tasks.storyboard_tasks import run_storyboard_task  # noqa: PLC0415
            run_storyboard_task.delay(sb.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not enqueue storyboard task: %s — will run inline", exc)
            asyncio.create_task(self.execute_storyboard(sb.id))

        return sb

    async def execute_storyboard(
        self,
        storyboard_id: str,
        script_data: dict[str, Any] | None = None,
    ) -> StoryboardResult | None:
        """Run the full scene-planning pipeline for an existing storyboard record."""
        sb = await self._repo.get(storyboard_id)
        if not sb:
            logger.warning("Storyboard %r not found", storyboard_id)
            return None

        request = StoryboardRequest(
            script_id=sb.script_id,
            research_id=sb.research_id,
            topic=sb.topic,
            script_style=sb.script_style,
            script_tone=sb.script_tone,
            target_duration_minutes=sb.target_duration_minutes,
            target_audience=sb.target_audience or "general audience",
            language=sb.language,
            providers=sb.providers,  # type: ignore[arg-type]
        )
        script_data = script_data or {}

        try:
            await self._log(storyboard_id, f"INFO  Starting storyboard generation for '{sb.topic}'")
            await self._log(storyboard_id, f"INFO  Style: {sb.script_style} | Providers: {', '.join(sb.providers)}")
            await self._repo.update_status(storyboard_id, StoryboardStatus.RUNNING.value)

            # ── Phase 1: Fetch from all providers ─────────────────────────
            await self._log(storyboard_id, "INFO  Phase 1/4 — Fetching scenes from providers in parallel")
            registry = StoryboardProviderRegistry(sb.providers)
            provider_results: list[StoryboardProviderResult] = await registry.fetch_all(request, script_data)

            ok = [r for r in provider_results if not r.error]
            failed = [r for r in provider_results if r.error]
            await self._log(storyboard_id, f"INFO  Providers: {len(ok)} OK, {len(failed)} failed")
            if failed:
                for r in failed:
                    await self._log(storyboard_id, f"WARN  Provider {r.provider_name} failed: {r.error}")

            if not ok:
                raise RuntimeError("All storyboard providers failed")

            # ── Phase 2: Primary provider selection + scene merge ──────────
            await self._log(storyboard_id, "INFO  Phase 2/4 — Selecting primary provider and merging scenes")
            primary = max(ok, key=lambda r: r.confidence)
            await self._log(storyboard_id, f"INFO  Primary provider: {primary.provider_name} (confidence {primary.confidence:.3f})")

            merged_scenes, extra_count = self._merge_scenes(primary, ok)
            if extra_count > 0:
                await self._log(storyboard_id, f"INFO  Added {extra_count} supplementary scenes from secondary providers")

            # ── Phase 3: Merge narration timing + visual cues ─────────────
            await self._log(storyboard_id, "INFO  Phase 3/4 — Merging narration timing and visual cues")
            merged_timing = self._merge_narration_timing(primary, ok)
            merged_cues = self._merge_visual_cues(primary, ok)
            merged_timeline = self._merge_timeline(primary, merged_scenes)
            await self._log(
                storyboard_id,
                f"INFO  Scenes: {len(merged_scenes)} | Timeline: {len(merged_timeline)} | "
                f"Cues: {len(merged_cues)} | Timing: {len(merged_timing)}",
            )

            # ── Phase 4: Production metrics ────────────────────────────────
            await self._log(storyboard_id, "INFO  Phase 4/4 — Computing production metrics")
            total_dur_s = sum(s.duration_ms for s in merged_scenes) // 1000
            image_count = sum(s.estimated_image_count for s in merged_scenes)
            complexity = self._calc_complexity(merged_scenes)
            render_min = max(1, round(image_count * 0.15 + len(merged_scenes) * 0.05))
            cost = round(image_count * 0.04 + len(merged_scenes) * 0.01, 2)
            await self._log(
                storyboard_id,
                f"INFO  Duration: {total_dur_s}s | Images: {image_count} | "
                f"Render: {render_min}min | Cost: ${cost:.2f} | Complexity: {complexity:.2f}",
            )

            await self._log(storyboard_id, "INFO  Storyboard complete — writing to database")

            # Serialise scenes to dicts
            scenes_dict = [s.model_dump() for s in merged_scenes]
            timeline_dict = [t.model_dump() for t in merged_timeline]
            timing_dict = [t.model_dump() for t in merged_timing]
            cues_dict = [c.model_dump() for c in merged_cues]

            sb = await self._repo.update(
                storyboard_id,
                status=StoryboardStatus.COMPLETED.value,
                title=primary.title,
                scenes=scenes_dict,
                scene_timeline=timeline_dict,
                narration_timing=timing_dict,
                visual_cues=cues_dict,
                total_duration_seconds=total_dur_s,
                scene_count=len(merged_scenes),
                image_count=image_count,
                editing_complexity_score=complexity,
                estimated_render_time_minutes=render_min,
                estimated_cost_usd=cost,
                visual_pacing=primary.visual_pacing.value,
                narration_pacing=primary.narration_pacing.value,
                used_providers=[r.provider_name for r in ok],
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.error("Storyboard %r failed: %s", storyboard_id, exc, exc_info=True)
            err = str(exc)
            await self._log(storyboard_id, f"ERROR Storyboard failed: {err}")
            sb = await self._repo.update(
                storyboard_id,
                status=StoryboardStatus.FAILED.value,
                error_message=err,
                updated_at=datetime.now(timezone.utc),
            )
        return sb

    async def get_storyboard(self, storyboard_id: str) -> StoryboardResult | None:
        return await self._repo.get(storyboard_id)

    async def list_storyboards(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[StoryboardResult], int]:
        rows, total = await self._repo.list(
            limit=limit, offset=offset, **({"status": status} if status else {})
        )
        return list(rows), total

    async def delete_storyboard(self, storyboard_id: str) -> bool:
        return await self._repo.delete(storyboard_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _log(self, storyboard_id: str, message: str) -> None:
        await self._repo.append_log(storyboard_id, f"{_ts()} {message}")

    def _merge_scenes(
        self,
        primary: StoryboardProviderResult,
        all_results: list[StoryboardProviderResult],
    ) -> tuple[list[Scene], int]:
        """Use primary scenes and supplement unique high-importance scenes from others."""
        merged = list(primary.scenes)
        seen_titles = {s.scene_title.lower() for s in merged}
        extra = 0
        for r in all_results:
            if r is primary:
                continue
            for s in r.scenes:
                if s.scene_title.lower() not in seen_titles and s.importance_score >= 0.8:
                    seen_titles.add(s.scene_title.lower())
                    # Re-number
                    s_copy = s.model_copy(update={"scene_number": len(merged) + 1})
                    merged.append(s_copy)
                    extra += 1
        return merged, extra

    def _merge_timeline(
        self,
        primary: StoryboardProviderResult,
        scenes: list[Scene],
    ) -> list[SceneTimeline]:
        """Rebuild timeline from merged scenes."""
        return [
            SceneTimeline(
                scene_number=s.scene_number,
                scene_title=s.scene_title,
                start_time_ms=s.start_time_ms,
                end_time_ms=s.end_time_ms,
                duration_ms=s.duration_ms,
                shot_type=s.shot_type,
                transition_type=s.transition_type,
                visual_type=s.visual_type,
                importance_score=s.importance_score,
            )
            for s in scenes
        ]

    def _merge_narration_timing(
        self,
        primary: StoryboardProviderResult,
        all_results: list[StoryboardProviderResult],
    ) -> list[NarrationTiming]:
        seen: set[int] = {t.scene_number for t in primary.narration_timing}
        merged = list(primary.narration_timing)
        for r in all_results:
            if r is primary:
                continue
            for t in r.narration_timing:
                if t.scene_number not in seen:
                    seen.add(t.scene_number)
                    merged.append(t)
        return sorted(merged, key=lambda t: t.start_ms)

    def _merge_visual_cues(
        self,
        primary: StoryboardProviderResult,
        all_results: list[StoryboardProviderResult],
    ) -> list[VisualCue]:
        seen_times: set[tuple[int, str]] = {(c.time_ms, c.cue_type) for c in primary.visual_cues}
        merged = list(primary.visual_cues)
        for r in all_results:
            if r is primary:
                continue
            for c in r.visual_cues:
                key = (c.time_ms, c.cue_type)
                if key not in seen_times:
                    seen_times.add(key)
                    merged.append(c)
        return sorted(merged, key=lambda c: c.time_ms)

    @staticmethod
    def _calc_complexity(scenes: list[Scene]) -> float:
        n = len(scenes) or 1
        anim = sum(len(s.animation_suggestions) for s in scenes)
        dissolves = sum(1 for s in scenes if s.transition_type.value != "cut")
        images = sum(s.estimated_image_count for s in scenes)
        return round(min(1.0, (
            0.3 * min(1, n / 40)
            + 0.3 * min(1, anim / (n * 2))
            + 0.2 * min(1, dissolves / n)
            + 0.2 * min(1, images / (n * 2))
        )), 3)
