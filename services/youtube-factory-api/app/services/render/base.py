"""Abstract renderer backend interface.

Keeping this as a narrow abstract contract means MoviePy can be swapped for a
different renderer (e.g. a native FFmpeg filter-graph renderer, or a cloud
rendering API) in the future without touching RenderService, the Celery task,
or the API layer — they all depend on this interface, not on MoviePy directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from app.schemas.render import RenderOutput, RenderPlan, RenderStats


@dataclass
class RenderProgress:
    phase: str
    percent: int
    message: str = ""


ProgressCallback = Callable[[RenderProgress], None]


class RendererBackend(ABC):
    """Abstract base for any engine that can turn a RenderPlan into a video file."""

    name: str = "base"

    @abstractmethod
    async def render(
        self,
        plan: RenderPlan,
        output_path: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[RenderOutput, RenderStats]:
        """Render the full video described by `plan` to `output_path`.

        Returns:
            (RenderOutput, RenderStats) describing the produced file.
        """

    @abstractmethod
    async def render_preview(
        self,
        plan: RenderPlan,
        output_path: str,
        *,
        max_duration_seconds: float = 20.0,
        on_progress: ProgressCallback | None = None,
    ) -> RenderOutput:
        """Render a short preview clip covering the first `max_duration_seconds`."""
