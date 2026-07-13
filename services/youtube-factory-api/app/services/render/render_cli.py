"""Standalone Render Engine CLI — renders a RenderPlan JSON file to an MP4.

Deliberately imports nothing from `app.api.*` / `app.main` (the FastAPI
router chain), only the renderer + schema modules, so it stays runnable even
while the known pre-existing DELETE-endpoint startup bug prevents the full
FastAPI app from booting (see repo memory). This is what the Node
`api-server` Express service invokes via subprocess to perform genuine
MoviePy/FFmpeg rendering, since it is the service actually wired to a
running workflow end-to-end.

Usage:
    python -m app.services.render.render_cli \
        --plan /tmp/plan.json --output /tmp/out.mp4 [--preview /tmp/preview.mp4]

Emits newline-delimited JSON progress events on stdout:
    {"phase": "compose", "percent": 30, "message": "..."}
and a final line:
    {"done": true, "output": {...}, "stats": {...}, "preview": {...}|null}
or on failure:
    {"done": true, "error": "..."}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.schemas.render import RenderPlan
from app.services.render.base import RenderProgress
from app.services.render.moviepy_backend import MoviePyRenderer


def _print_event(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


async def _main(plan_path: str, output_path: str, preview_path: str | None) -> int:
    with open(plan_path, "r") as f:
        plan = RenderPlan.model_validate(json.load(f))

    renderer = MoviePyRenderer()

    def on_progress(p: RenderProgress) -> None:
        _print_event({"phase": p.phase, "percent": p.percent, "message": p.message})

    try:
        output, stats = await renderer.render(plan, output_path, on_progress=on_progress)
        preview_result = None
        if preview_path:
            preview_result = await renderer.render_preview(plan, preview_path, on_progress=on_progress)
        _print_event(
            {
                "done": True,
                "output": output.model_dump(),
                "stats": stats.model_dump(),
                "preview": preview_result.model_dump() if preview_result else None,
            }
        )
        return 0
    except Exception as exc:  # noqa: BLE001 — surface any failure to the caller
        _print_event({"done": True, "error": f"{type(exc).__name__}: {exc}"})
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a RenderPlan JSON document to MP4.")
    parser.add_argument("--plan", required=True, help="Path to a RenderPlan JSON file")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--preview", required=False, default=None, help="Optional preview MP4 path")
    args = parser.parse_args()
    exit_code = asyncio.run(_main(args.plan, args.output, args.preview))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
