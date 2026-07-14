"""Abstract base for Subtitle transcription providers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.subtitle import SubtitleProviderResult


class SubtitleProvider(ABC):
    """Real transcription provider — no provider in this registry may return
    fabricated timestamps; each either does genuine work or raises/returns an
    error so the registry can fall back honestly."""

    name: str

    @abstractmethod
    async def transcribe(
        self,
        video_path: str,
        language: str,
        *,
        context: dict | None = None,
    ) -> SubtitleProviderResult:
        """Return a SubtitleProviderResult, or one with `error` set on failure."""
        raise NotImplementedError
