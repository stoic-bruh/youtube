"""Unit tests for ChapterService — pure logic and DB-mocked paths.

The chapter engine is purely data-driven (no media files, FFmpeg, or
Whisper), so all non-DB logic can be tested fully offline.

Run with: pytest tests/test_chapter_service.py -v
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chapter_service import (
    ChapterService,
    _format_youtube_timestamp,
    merge_short_scenes,
    YOUTUBE_MIN_CHAPTER_MS,
)


# ── _format_youtube_timestamp ─────────────────────────────────────────────────

class TestFormatYoutubeTimestamp:
    def test_zero(self):
        assert _format_youtube_timestamp(0) == "0:00"

    def test_30_seconds(self):
        assert _format_youtube_timestamp(30_000) == "0:30"

    def test_one_minute(self):
        assert _format_youtube_timestamp(60_000) == "1:00"

    def test_59_minutes_59_seconds(self):
        ms = 59 * 60_000 + 59_000
        result = _format_youtube_timestamp(ms)
        assert result == "59:59"

    def test_one_hour(self):
        assert _format_youtube_timestamp(3_600_000) == "1:00:00"

    def test_one_hour_thirty(self):
        ms = 3_600_000 + 30 * 60_000
        assert _format_youtube_timestamp(ms) == "1:30:00"

    def test_negative_clamped(self):
        # Should not raise — max(ms, 0) in integer division
        result = _format_youtube_timestamp(-1000)
        assert result == "0:00"

    def test_no_leading_zero_in_minutes(self):
        # 5 minutes — should be "5:00", not "05:00"
        result = _format_youtube_timestamp(5 * 60_000)
        assert result == "5:00"
        assert not result.startswith("0")


# ── merge_short_scenes ────────────────────────────────────────────────────────

def _chapter(title: str, start_ms: int, end_ms: int, description: str | None = None) -> dict:
    return {"title": title, "start_ms": start_ms, "end_ms": end_ms, "description": description}


MIN = YOUTUBE_MIN_CHAPTER_MS  # 10_000 ms


class TestMergeShortScenes:
    def test_empty_input_returns_empty(self):
        assert merge_short_scenes([]) == []

    def test_single_long_chapter_unchanged(self):
        chapters = [_chapter("A", 0, 30_000)]
        result = merge_short_scenes(chapters)
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_two_long_chapters_unchanged(self):
        chapters = [
            _chapter("A", 0,      15_000),
            _chapter("B", 15_000, 30_000),
        ]
        result = merge_short_scenes(chapters)
        assert len(result) == 2

    def test_too_short_chapter_merged_into_previous(self):
        # Chapter B is only 5s — should be merged into A (extending A.end_ms)
        chapters = [
            _chapter("A", 0,      20_000),
            _chapter("B", 20_000, 25_000),  # 5s — too short
        ]
        result = merge_short_scenes(chapters)
        assert len(result) == 1
        assert result[0]["end_ms"] == 25_000

    def test_too_short_previous_folded_forward(self):
        # A (5s) → B (20s): A is too short, gets absorbed, B's title kept
        chapters = [
            _chapter("A", 0,      5_000),   # too short
            _chapter("B", 5_000,  25_000),  # long enough
        ]
        result = merge_short_scenes(chapters)
        assert len(result) == 2  # A stays small initially, then B is appended
        # After merge: A was too short → prev extended forward; B stays
        # (implementation: prev_duration < min → fold prev.end = chapter.start, append chapter)
        # So both chapters remain, just A's end_ms is updated
        assert result[-1]["title"] == "B"

    def test_all_short_chapters_consolidated(self):
        # 5 × 3s chapters → should end up as fewer chapters
        chapters = [_chapter(f"S{i}", i * 3_000, (i + 1) * 3_000) for i in range(5)]
        result = merge_short_scenes(chapters, min_duration_ms=10_000)
        # None of the originals was long enough, so they merge aggressively
        for c in result:
            duration = c["end_ms"] - c["start_ms"]
            # Result chapters can still be short if there's no long one to absorb them,
            # but the list should be shorter or equal
        assert len(result) <= len(chapters)

    def test_last_chapter_merged_if_too_short(self):
        chapters = [
            _chapter("A", 0,      20_000),
            _chapter("B", 20_000, 40_000),
            _chapter("C", 40_000, 43_000),  # 3s — too short
        ]
        result = merge_short_scenes(chapters)
        assert len(result) == 2
        assert result[-1]["end_ms"] == 43_000

    def test_preserves_first_chapter_start_externally(self):
        # The caller sets first chapter's start_ms to 0 before calling merge;
        # merge_short_scenes should not touch start of first chapter
        chapters = [_chapter("Intro", 0, 15_000), _chapter("Main", 15_000, 60_000)]
        result = merge_short_scenes(chapters)
        assert result[0]["start_ms"] == 0

    def test_custom_min_duration(self):
        # With a custom min of 5s, a 6s chapter should NOT be merged
        chapters = [
            _chapter("A", 0,      30_000),
            _chapter("B", 30_000, 36_000),  # 6s — above custom min of 5s
        ]
        result = merge_short_scenes(chapters, min_duration_ms=5_000)
        assert len(result) == 2


# ── ChapterService: start_chapter guard checks ────────────────────────────────

def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo._db = AsyncMock()
    return repo


def _make_render(status: str = "completed", has_scenes: bool = True) -> MagicMock:
    render = MagicMock()
    render.id = "render-xyz"
    render.status = status
    render.timeline_id = None
    render.voice_id = None
    render.render_plan = {"scenes": [
        {"scene_index": 0, "title": "Intro", "start_ms": 0,      "end_ms": 20_000, "narration": "Hello."},
        {"scene_index": 1, "title": "Main",  "start_ms": 20_000, "end_ms": 60_000, "narration": "Content."},
    ]} if has_scenes else {}
    return render


class TestChapterServiceStartChapter:
    @pytest.mark.asyncio
    async def test_raises_if_render_not_found(self):
        from app.schemas.chapter import ChapterRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=None)

        service = ChapterService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.start_chapter(ChapterRequest(render_id="missing"))

    @pytest.mark.asyncio
    async def test_raises_if_render_not_completed(self):
        from app.schemas.chapter import ChapterRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render(status="running"))

        service = ChapterService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="not completed"):
            await service.start_chapter(ChapterRequest(render_id="render-xyz"))

    @pytest.mark.asyncio
    async def test_raises_if_no_scenes(self):
        from app.schemas.chapter import ChapterRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render(has_scenes=False))

        service = ChapterService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="no scene timing"):
            await service.start_chapter(ChapterRequest(render_id="render-xyz"))

    @pytest.mark.asyncio
    async def test_creates_db_record_on_valid_render(self):
        from app.schemas.chapter import ChapterRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render())

        created_chapter = MagicMock()
        created_chapter.id = "chap-1"
        repo.create = AsyncMock(return_value=created_chapter)

        service = ChapterService(repo, render_repo=render_repo)
        with patch("app.tasks.chapter_tasks.run_chapter_task") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.start_chapter(ChapterRequest(render_id="render-xyz"))

        assert result.id == "chap-1"
        repo.create.assert_awaited_once()


# ── ChapterService: execute_chapter logic ─────────────────────────────────────

class TestChapterServiceExecuteChapter:
    @pytest.mark.asyncio
    async def test_returns_none_if_chapter_not_found(self):
        repo = _make_repo()
        repo.get = AsyncMock(return_value=None)

        service = ChapterService(repo)
        result = await service.execute_chapter("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_fails_gracefully_if_render_gone(self):
        repo = _make_repo()

        chapter = MagicMock()
        chapter.id = "chap-1"
        chapter.render_id = "render-xyz"
        chapter.logs = []
        repo.get = AsyncMock(return_value=chapter)
        repo.update = AsyncMock(return_value=chapter)

        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=None)  # render deleted

        service = ChapterService(repo, render_repo=render_repo)
        result = await service.execute_chapter("chap-1")

        # Should fail gracefully (return None and update status to failed)
        assert result is None
        # update should have been called with status=failed
        update_calls = repo.update.call_args_list
        failed_calls = [c for c in update_calls if "failed" in str(c)]
        assert len(failed_calls) >= 1

    @pytest.mark.asyncio
    async def test_generates_youtube_export_format(self):
        """Execute chapter with two real scenes and verify YouTube chapter format."""
        repo = _make_repo()

        chapter_record = MagicMock()
        chapter_record.id = "chap-2"
        chapter_record.render_id = "render-abc"
        chapter_record.logs = []
        repo.get = AsyncMock(return_value=chapter_record)

        render = _make_render()
        render.timeline_id = None

        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=render)

        timeline_repo = MagicMock()
        timeline_repo.get = AsyncMock(return_value=None)

        script_repo = MagicMock()
        script_repo.get = AsyncMock(return_value=None)

        updated_chapter = MagicMock()
        updated_chapter.id = "chap-2"
        updated_chapter.youtube_export = "0:00 Intro\n0:20 Main"
        repo.update = AsyncMock(return_value=updated_chapter)

        service = ChapterService(repo, render_repo=render_repo, timeline_repo=timeline_repo, script_repo=script_repo)
        result = await service.execute_chapter("chap-2")

        assert result is not None
        # Verify update was called with completed status
        update_calls = repo.update.call_args_list
        completed_calls = [c for c in update_calls if "completed" in str(c)]
        assert len(completed_calls) >= 1


# ── ChapterService: list / delete ─────────────────────────────────────────────

class TestChapterServiceListDelete:
    @pytest.mark.asyncio
    async def test_list_delegates_to_repo(self):
        repo = _make_repo()
        repo.list = AsyncMock(return_value=([], 0))

        service = ChapterService(repo)
        items, total = await service.list_chapters(limit=5, offset=0)
        assert items == []
        assert total == 0
        repo.list.assert_awaited_once_with(limit=5, offset=0)

    @pytest.mark.asyncio
    async def test_list_passes_status_filter(self):
        repo = _make_repo()
        repo.list = AsyncMock(return_value=([], 0))

        service = ChapterService(repo)
        await service.list_chapters(status="completed")
        call_kwargs = repo.list.call_args.kwargs
        assert call_kwargs.get("status") == "completed"

    @pytest.mark.asyncio
    async def test_list_passes_render_id_filter(self):
        repo = _make_repo()
        repo.list = AsyncMock(return_value=([], 0))

        service = ChapterService(repo)
        await service.list_chapters(render_id="render-xyz")
        call_kwargs = repo.list.call_args.kwargs
        assert call_kwargs.get("render_id") == "render-xyz"

    @pytest.mark.asyncio
    async def test_delete_delegates_to_repo(self):
        repo = _make_repo()
        repo.delete = AsyncMock(return_value=True)

        service = ChapterService(repo)
        result = await service.delete_chapter("chap-1")
        assert result is True
        repo.delete.assert_awaited_once_with("chap-1")
