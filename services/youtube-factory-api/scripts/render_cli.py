"""Standalone render CLI — turns a RenderPlan JSON document into a real MP4.

Usage:
    python3 render_cli.py <plan.json> <output.mp4> [--preview <preview.mp4>]

Reads a `RenderPlan` (see app.schemas.render.RenderPlan) as JSON from
`plan.json`, runs it through the same `MoviePyRenderer` used by the FastAPI
service/Celery worker (app/services/render/moviepy_backend.py), and writes
the resulting `{"output": ..., "stats": ..., "preview_output": ...}` JSON to
stdout.

This lets the Node `api-server` (which owns Timeline/Voice/Asset data via
Drizzle, not SQLAlchemy) trigger a genuine MoviePy/FFmpeg render without
needing the Python service's own database or a running FastAPI/Celery stack —
it only needs a resolved RenderPlan document, which
`artifacts/api-server/src/routes/render.ts` builds from the Node-side Timeline
+ Voice + Asset rows (mirroring `app/services/render/plan_builder.py`).
"""
from __future__ import annotations

import asyncio
import json
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: render_cli.py <plan.json> <output.mp4> [--preview <preview.mp4>]", file=sys.stderr)
        return 2

    plan_path, output_path = sys.argv[1], sys.argv[2]
    preview_path: str | None = None
    if "--preview" in sys.argv:
        preview_path = sys.argv[sys.argv.index("--preview") + 1]

    from app.schemas.render import RenderPlan
    from app.services.render.moviepy_backend import MoviePyRenderer

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)
    plan = RenderPlan.model_validate(plan_data)

    renderer = MoviePyRenderer()

    progress_events: list[dict] = []

    def on_progress(p) -> None:
        progress_events.append({"phase": p.phase, "percent": p.percent, "message": p.message})
        print(f"[render:{p.phase}] {p.percent}% {p.message}", file=sys.stderr)

    async def _run() -> dict:
        output, stats = await renderer.render(plan, output_path, on_progress=on_progress)
        result: dict = {
            "output": output.model_dump(mode="json"),
            "stats": stats.model_dump(mode="json"),
            "progress": progress_events,
        }
        if preview_path:
            preview_output = await renderer.render_preview(plan, preview_path, on_progress=on_progress)
            result["preview_output"] = preview_output.model_dump(mode="json")
        return result

    result = asyncio.run(_run())
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
