"""Real Whisper (faster-whisper) transcription provider.

Does genuine work: extracts the render's real audio track via FFmpeg, runs a
real CTranslate2-backed Whisper model over it, and returns real word-level
timestamps with real model confidence scores. If the audio track contains no
detectable speech (e.g. a silent/placeholder narration track), it reports
zero words rather than fabricating a transcript — the registry then falls
back to `ScriptNarrationProvider`.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile

from app.providers.subtitle.base import SubtitleProvider
from app.schemas.subtitle import SubtitleProviderResult, SubtitleWord, SubtitleSentence, SubtitleParagraph
from app.services.postprocess.ffmpeg_utils import extract_audio, audio_rms_energy

logger = logging.getLogger(__name__)

_SENTENCE_END_RE = re.compile(r"[.!?]+\s*$")
_SILENCE_RMS_THRESHOLD = 50.0  # empirical PCM16 magnitude floor for "no speech"
_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")


class WhisperTranscriptionProvider(SubtitleProvider):
    name = "whisper"

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper model=%s (CPU)", _MODEL_SIZE)
            self._model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(
        self,
        video_path: str,
        language: str,
        *,
        context: dict | None = None,
    ) -> SubtitleProviderResult:
        import asyncio

        with tempfile.TemporaryDirectory(prefix="subtitle_whisper_") as tmp_dir:
            wav_path = os.path.join(tmp_dir, "audio.wav")
            try:
                await extract_audio(video_path, wav_path)
            except Exception as exc:
                return SubtitleProviderResult(provider_name=self.name, error=f"audio extraction failed: {exc}")

            rms = await audio_rms_energy(wav_path)
            if rms < _SILENCE_RMS_THRESHOLD:
                return SubtitleProviderResult(
                    provider_name=self.name,
                    error=f"audio track has no detectable speech (rms={rms:.2f} < {_SILENCE_RMS_THRESHOLD})",
                )

            def _run_whisper() -> tuple[list, float]:
                model = self._load_model()
                segments, info = model.transcribe(wav_path, language=language, word_timestamps=True)
                return list(segments), float(getattr(info, "duration", 0.0))

            try:
                segments, duration_s = await asyncio.to_thread(_run_whisper)
            except Exception as exc:
                return SubtitleProviderResult(provider_name=self.name, error=f"transcription failed: {exc}")

            words: list[SubtitleWord] = []
            sentences: list[SubtitleSentence] = []
            sentence_buf: list = []

            for segment in segments:
                for w in segment.words or []:
                    word = SubtitleWord(
                        word=w.word.strip(),
                        start_ms=int(w.start * 1000),
                        end_ms=int(w.end * 1000),
                        confidence=round(float(getattr(w, "probability", 0.0)), 4),
                    )
                    words.append(word)
                    sentence_buf.append(word)
                    if _SENTENCE_END_RE.search(word.word) and sentence_buf:
                        sentences.append(self._flush_sentence(sentence_buf))
                        sentence_buf = []
            if sentence_buf:
                sentences.append(self._flush_sentence(sentence_buf))

            if not words:
                return SubtitleProviderResult(provider_name=self.name, error="transcription produced zero words")

            paragraphs = self._group_paragraphs(sentences)
            avg_conf = round(sum(w.confidence for w in words) / len(words), 4) if words else 0.0

            return SubtitleProviderResult(
                provider_name=self.name,
                words=words,
                sentences=sentences,
                paragraphs=paragraphs,
                avg_confidence=avg_conf,
                duration_ms=int(duration_s * 1000),
            )

    @staticmethod
    def _flush_sentence(word_buf: list[SubtitleWord]) -> SubtitleSentence:
        text = " ".join(w.word for w in word_buf)
        avg_conf = round(sum(w.confidence for w in word_buf) / len(word_buf), 4)
        return SubtitleSentence(
            text=text,
            start_ms=word_buf[0].start_ms,
            end_ms=word_buf[-1].end_ms,
            confidence=avg_conf,
        )

    @staticmethod
    def _group_paragraphs(sentences: list[SubtitleSentence], *, max_sentences: int = 3) -> list[SubtitleParagraph]:
        paragraphs: list[SubtitleParagraph] = []
        for i in range(0, len(sentences), max_sentences):
            chunk = sentences[i: i + max_sentences]
            if not chunk:
                continue
            paragraphs.append(
                SubtitleParagraph(
                    text=" ".join(s.text for s in chunk),
                    start_ms=chunk[0].start_ms,
                    end_ms=chunk[-1].end_ms,
                )
            )
        return paragraphs
