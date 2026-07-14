"""SRT/VTT/ASS caption file generation from sentence-level timestamps."""
from __future__ import annotations


def _srt_timestamp(ms: int) -> str:
    ms = max(ms, 0)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _vtt_timestamp(ms: int) -> str:
    ms = max(ms, 0)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _ass_timestamp(ms: int) -> str:
    ms = max(ms, 0)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, centis = divmod(rem, 1000)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}.{centis // 10:02d}"


def build_srt(sentences: list[dict]) -> str:
    lines = []
    for i, s in enumerate(sentences, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(s['start_ms'])} --> {_srt_timestamp(s['end_ms'])}")
        lines.append(s["text"].strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_vtt(sentences: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for s in sentences:
        lines.append(f"{_vtt_timestamp(s['start_ms'])} --> {_vtt_timestamp(s['end_ms'])}")
        lines.append(s["text"].strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


_ASS_HEADER = """[Script Info]
Title: Generated Captions
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Arial,72,&H00FFFFFF,&H00000000,&H80000000,1,3,1,2,60,60,80
Style: Karaoke,Arial,72,&H0000D7FF,&H00000000,&H80000000,1,3,1,2,60,60,80

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(sentences: list[dict], words: list[dict] | None = None, *, karaoke: bool = True) -> str:
    """Build an ASS subtitle file. When `karaoke` and word timestamps are
    available, emits real \\k karaoke tags timed to each word's duration."""
    body = []
    words = words or []
    for s in sentences:
        start, end = s["start_ms"], s["end_ms"]
        text = s["text"].strip()
        style = "Default"
        if karaoke:
            sentence_words = [w for w in words if start <= w["start_ms"] < end]
            if sentence_words:
                style = "Karaoke"
                parts = []
                for w in sentence_words:
                    duration_centis = max(int((w["end_ms"] - w["start_ms"]) / 10), 1)
                    parts.append(f"{{\\k{duration_centis}}}{w['word']}")
                text = " ".join(parts)
        body.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},{style},,0,0,0,,{text}"
        )
    return _ASS_HEADER + "\n".join(body) + "\n"
