"""SubtitleGenerator — placeholder interface.

Responsible for:
- Generating SRT/VTT subtitle files from audio
- Word-level timestamp alignment using Whisper
- Subtitle styling (font, color, position)
- Burning subtitles into video (optional)
"""
from dataclasses import dataclass, field

from app.services.voice_generator import VoiceAudio
from app.services.video_editor import VideoOutput


@dataclass
class SubtitleEntry:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class Subtitles:
    entries: list[SubtitleEntry] = field(default_factory=list)
    language: str = "en"
    format: str = "srt"  # srt | vtt | ass

    def to_srt(self) -> str:
        """Serialize subtitles to SRT format string."""
        lines = []
        for entry in self.entries:
            start = self._format_time(entry.start_seconds)
            end = self._format_time(entry.end_seconds)
            lines.append(f"{entry.index}\n{start} --> {end}\n{entry.text}\n")
        return "\n".join(lines)

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class SubtitleGenerator:
    """Placeholder implementation — real subtitle generation to be implemented."""

    async def generate_from_audio(
        self,
        audio: VoiceAudio,
        language: str = "en",
        model: str = "whisper-1",
    ) -> Subtitles:
        """Generate subtitles by transcribing audio with word timestamps.

        Args:
            audio: VoiceAudio to transcribe.
            language: ISO 639-1 language code.
            model: Whisper model variant.

        Returns:
            Subtitles with timestamped entries.
        """
        # TODO: Implement using OpenAI Whisper API with verbose_json response format
        #       to extract word-level timestamps, then group into subtitle entries
        placeholder_entries = [
            SubtitleEntry(index=i + 1, start_seconds=i * 5.0, end_seconds=(i + 1) * 5.0, text=f"[PLACEHOLDER] Subtitle line {i + 1}")
            for i in range(10)
        ]
        return Subtitles(entries=placeholder_entries, language=language)

    async def burn_into_video(
        self,
        video: VideoOutput,
        subtitles: Subtitles,
        style: str = "bottom-white",
    ) -> VideoOutput:
        """Hard-code subtitles into the video (burned-in captions).

        Args:
            video: VideoOutput to add subtitles to.
            subtitles: Subtitles to burn in.
            style: Subtitle style — "bottom-white" | "bottom-yellow" | "center".

        Returns:
            VideoOutput pointing to the subtitled file.
        """
        # TODO: Implement using MoviePy TextClip or FFmpeg subtitle filter
        return VideoOutput(**{**video.__dict__, "local_path": video.local_path.replace(".mp4", "_subtitled.mp4")})

    async def export_srt(self, subtitles: Subtitles, output_path: str) -> str:
        """Write subtitles to an .srt file.

        Args:
            subtitles: Subtitles to export.
            output_path: File path to write to.

        Returns:
            Path to the written file.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(subtitles.to_srt())
        return output_path
