"""Unit tests for subtitle post-processing utilities.

Tests the pure-logic functions in subtitle_formats.py and the service helpers
that do not require a running database or real media files.

Run with: pytest tests/test_subtitle_service.py -v
"""
from __future__ import annotations

import pytest

from app.services.postprocess.subtitle_formats import (
    build_ass,
    build_srt,
    build_vtt,
    _srt_timestamp,
    _vtt_timestamp,
    _ass_timestamp,
)


# ── Timestamp helpers ─────────────────────────────────────────────────────────

class TestSrtTimestamp:
    def test_zero(self):
        assert _srt_timestamp(0) == "00:00:00,000"

    def test_one_second(self):
        assert _srt_timestamp(1000) == "00:00:01,000"

    def test_one_minute(self):
        assert _srt_timestamp(60_000) == "00:01:00,000"

    def test_one_hour(self):
        assert _srt_timestamp(3_600_000) == "01:00:00,000"

    def test_mixed(self):
        # 1h 2m 3s 456ms
        ms = 3_600_000 + 2 * 60_000 + 3_000 + 456
        assert _srt_timestamp(ms) == "01:02:03,456"

    def test_negative_clamped_to_zero(self):
        assert _srt_timestamp(-500) == "00:00:00,000"


class TestVttTimestamp:
    def test_zero(self):
        assert _vtt_timestamp(0) == "00:00:00.000"

    def test_uses_dot_separator(self):
        result = _vtt_timestamp(1500)
        assert "." in result
        assert "," not in result

    def test_one_hour(self):
        assert _vtt_timestamp(3_600_000) == "01:00:00.000"


class TestAssTimestamp:
    def test_zero(self):
        assert _ass_timestamp(0) == "0:00:00.00"

    def test_one_second(self):
        assert _ass_timestamp(1000) == "0:00:01.00"

    def test_centiseconds(self):
        # 1250ms → 1.25s → centiseconds=25
        assert _ass_timestamp(1250) == "0:00:01.25"

    def test_one_hour(self):
        assert _ass_timestamp(3_600_000) == "1:00:00.00"


# ── build_srt ─────────────────────────────────────────────────────────────────

def make_sentences(count: int = 2) -> list[dict]:
    return [
        {
            "text": f"Sentence {i + 1}.",
            "start_ms": i * 3_000,
            "end_ms": i * 3_000 + 2_500,
        }
        for i in range(count)
    ]


class TestBuildSrt:
    def test_starts_with_index_1(self):
        result = build_srt(make_sentences(1))
        assert result.startswith("1\n")

    def test_sequential_indices(self):
        result = build_srt(make_sentences(3))
        lines = result.splitlines()
        indices = [l for l in lines if l.strip().isdigit()]
        assert [int(x) for x in indices] == [1, 2, 3]

    def test_arrow_separator(self):
        result = build_srt(make_sentences(1))
        assert " --> " in result

    def test_comma_in_timestamp(self):
        result = build_srt(make_sentences(1))
        # SRT uses commas for milliseconds
        assert "," in result.split(" --> ")[0]

    def test_blank_line_between_entries(self):
        result = build_srt(make_sentences(2))
        # Entries are separated by blank lines
        assert "\n\n" in result

    def test_ends_with_newline(self):
        result = build_srt(make_sentences(1))
        assert result.endswith("\n")

    def test_empty_input(self):
        result = build_srt([])
        # No crash, may be near-empty
        assert isinstance(result, str)

    def test_text_preserved(self):
        sentences = [{"text": "Hello world.", "start_ms": 0, "end_ms": 2000}]
        result = build_srt(sentences)
        assert "Hello world." in result


# ── build_vtt ─────────────────────────────────────────────────────────────────

class TestBuildVtt:
    def test_starts_with_webvtt(self):
        result = build_vtt(make_sentences(1))
        assert result.startswith("WEBVTT")

    def test_dot_in_timestamp(self):
        result = build_vtt(make_sentences(1))
        # VTT uses dots for milliseconds
        timestamp_line = [l for l in result.splitlines() if " --> " in l][0]
        left = timestamp_line.split(" --> ")[0]
        assert "." in left and "," not in left

    def test_arrow_separator(self):
        result = build_vtt(make_sentences(1))
        assert " --> " in result

    def test_text_preserved(self):
        sentences = [{"text": "VTT caption.", "start_ms": 0, "end_ms": 1000}]
        result = build_vtt(sentences)
        assert "VTT caption." in result

    def test_ends_with_newline(self):
        assert build_vtt(make_sentences(1)).endswith("\n")


# ── build_ass ─────────────────────────────────────────────────────────────────

class TestBuildAss:
    def test_contains_script_info(self):
        result = build_ass(make_sentences(1))
        assert "[Script Info]" in result

    def test_contains_v4_styles(self):
        result = build_ass(make_sentences(1))
        assert "[V4+ Styles]" in result

    def test_contains_events(self):
        result = build_ass(make_sentences(1))
        assert "[Events]" in result

    def test_dialogue_lines_match_sentences(self):
        sentences = make_sentences(3)
        result = build_ass(sentences)
        dialogue_lines = [l for l in result.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) == 3

    def test_text_preserved(self):
        sentences = [{"text": "ASS test.", "start_ms": 0, "end_ms": 1000}]
        result = build_ass(sentences)
        assert "ASS test." in result

    def test_karaoke_style_when_words_provided(self):
        sentences = [{"text": "hello world", "start_ms": 0, "end_ms": 2000}]
        words = [
            {"word": "hello", "start_ms": 0,    "end_ms": 1000},
            {"word": "world", "start_ms": 1000, "end_ms": 2000},
        ]
        result = build_ass(sentences, words)
        # With word timestamps, karaoke tags (\k) should appear
        assert r"\k" in result

    def test_no_karaoke_without_words(self):
        sentences = [{"text": "no karaoke", "start_ms": 0, "end_ms": 1000}]
        result = build_ass(sentences, words=None)
        # Without word-level timestamps, no \k tags expected for matching words
        dialogue_lines = [l for l in result.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) == 1
        # Text should still appear in the dialogue
        assert "no karaoke" in dialogue_lines[0]

    def test_karaoke_false_skips_tags(self):
        sentences = [{"text": "no karaoke", "start_ms": 0, "end_ms": 1000}]
        words = [{"word": "no", "start_ms": 0, "end_ms": 500}, {"word": "karaoke", "start_ms": 500, "end_ms": 1000}]
        result = build_ass(sentences, words, karaoke=False)
        assert r"\k" not in result


# ── Scoring utilities ─────────────────────────────────────────────────────────

class TestQualityScore:
    """quality_score is pure arithmetic — no image files needed."""

    def _score(self, sharpness: float, bright: float) -> float:
        from app.services.postprocess.scoring import quality_score
        return quality_score(sharpness, bright)

    def test_returns_float(self):
        assert isinstance(self._score(20.0, 128.0), float)

    def test_range_is_0_to_100(self):
        for sharp in [0.0, 10.0, 40.0, 100.0]:
            for bright in [0.0, 64.0, 128.0, 192.0, 255.0]:
                assert 0.0 <= self._score(sharp, bright) <= 100.0

    def test_maximum_at_sharp_40_bright_128(self):
        max_score = self._score(40.0, 128.0)
        lower_sharp = self._score(10.0, 128.0)
        assert max_score >= lower_sharp

    def test_zero_sharpness_gives_nonzero_if_bright_128(self):
        # brightness component alone can contribute up to 30
        score = self._score(0.0, 128.0)
        assert score > 0.0

    def test_extremes_penalized(self):
        # Brightness 0 (too dark) or 255 (blown out) should score lower than 128
        middle = self._score(20.0, 128.0)
        dark   = self._score(20.0, 0.0)
        bright = self._score(20.0, 255.0)
        assert middle > dark
        assert middle > bright


class TestSafeTextRegions:
    def _regions(self, width: int = 1280, height: int = 720):
        from app.services.postprocess.scoring import safe_text_regions
        return safe_text_regions(width, height)

    def test_returns_two_regions(self):
        assert len(self._regions()) == 2

    def test_regions_have_required_keys(self):
        for r in self._regions():
            assert "region" in r
            assert "x" in r
            assert "y" in r
            assert "width" in r
            assert "height" in r

    def test_region_names(self):
        names = {r["region"] for r in self._regions()}
        assert names == {"lower-third", "upper-third"}

    def test_dimensions_within_frame(self):
        w, h = 1920, 1080
        for r in self._regions(w, h):
            assert r["x"] >= 0
            assert r["y"] >= 0
            assert r["x"] + r["width"] <= w
            assert r["y"] + r["height"] <= h

    def test_scales_with_resolution(self):
        small = self._regions(640, 360)
        large = self._regions(1920, 1080)
        for s_r, l_r in zip(small, large):
            assert l_r["width"] > s_r["width"]
            assert l_r["height"] > s_r["height"]
