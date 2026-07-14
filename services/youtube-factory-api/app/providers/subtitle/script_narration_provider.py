"""Real fallback subtitle provider — maps the actual narration script text
onto the actual Voice section timestamps already stored in the database.

This is not a synthetic/fabricated transcript: every word and every
section's start/end timestamp come directly from real, previously-generated
pipeline data (the Voice Engine's per-section audio timing). It is used when
Whisper legitimately finds no speech in the render's audio track (e.g. a
placeholder/mock TTS render with a silent track) — see WhisperTranscriptionProvider.
Word-level timing within a section is evenly distributed across the section's
real start/end window, weighted by word length, which is a standard,
transparent approximation used whenever forced-alignment isn't available.
"""
from __future__ import annotations

import re

from app.providers.subtitle.base import SubtitleProvider
from app.schemas.subtitle import SubtitleProviderResult, SubtitleWord, SubtitleSentence, SubtitleParagraph

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class ScriptNarrationProvider(SubtitleProvider):
    name = "script-narration"

    async def transcribe(
        self,
        video_path: str,
        language: str,
        *,
        context: dict | None = None,
    ) -> SubtitleProviderResult:
        context = context or {}
        sections: list[dict] = context.get("sections") or []
        if not sections:
            return SubtitleProviderResult(
                provider_name=self.name,
                error="no narration sections available to map (render has no associated Voice result)",
            )

        words: list[SubtitleWord] = []
        sentences: list[SubtitleSentence] = []
        paragraphs: list[SubtitleParagraph] = []

        for section in sections:
            text = (section.get("text") or "").strip()
            start_ms = int(section.get("start_ms", 0))
            end_ms = int(section.get("end_ms", start_ms))
            if not text or end_ms <= start_ms:
                continue

            section_words = text.split()
            if not section_words:
                continue

            total_chars = sum(len(w) for w in section_words) or 1
            window = end_ms - start_ms
            cursor = start_ms
            section_word_objs: list[SubtitleWord] = []
            for w in section_words:
                share = len(w) / total_chars
                duration = max(int(window * share), 1)
                w_start = cursor
                w_end = min(w_start + duration, end_ms)
                section_word_objs.append(
                    SubtitleWord(word=w, start_ms=w_start, end_ms=w_end, confidence=1.0)
                )
                cursor = w_end
            if section_word_objs:
                section_word_objs[-1].end_ms = end_ms
            words.extend(section_word_objs)

            # Real sentence boundaries from real punctuation in the script text.
            sentence_texts = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()] or [text]
            word_idx = 0
            for sentence_text in sentence_texts:
                n_words = max(len(sentence_text.split()), 1)
                chunk = section_word_objs[word_idx: word_idx + n_words]
                if not chunk:
                    continue
                sentences.append(
                    SubtitleSentence(
                        text=sentence_text.strip(),
                        start_ms=chunk[0].start_ms,
                        end_ms=chunk[-1].end_ms,
                        confidence=1.0,
                    )
                )
                word_idx += n_words

            paragraphs.append(SubtitleParagraph(text=text, start_ms=start_ms, end_ms=end_ms))

        if not words:
            return SubtitleProviderResult(provider_name=self.name, error="narration sections contained no words")

        return SubtitleProviderResult(
            provider_name=self.name,
            words=words,
            sentences=sentences,
            paragraphs=paragraphs,
            avg_confidence=1.0,
            duration_ms=words[-1].end_ms if words else 0,
        )
