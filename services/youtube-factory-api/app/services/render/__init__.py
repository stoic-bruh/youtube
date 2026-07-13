"""Render Engine — RenderPlan -> real MP4 via a swappable RendererBackend.

Modules:
  - base.py:               RendererBackend abstract interface + RenderProgress callback.
  - moviepy_backend.py:     Real MoviePy/FFmpeg implementation of RendererBackend.
  - placeholder_assets.py:  Synthesizes placeholder image/audio media for scenes
                            that have no real downloaded asset/narration file yet
                            (upstream Asset/Voice providers are simulated — see
                            repo convention — so the renderer itself still runs a
                            genuine MoviePy/FFmpeg composite over stand-in media).
  - plan_builder.py:        Builds a RenderPlan from TimelineResult + VoiceResult
                            + AssetCollection rows (mirrors the Node builder in
                            artifacts/api-server/src/routes/render.ts).
  - render_cli.py:          Standalone CLI entrypoint that renders a RenderPlan
                            JSON file to an MP4 without importing the FastAPI
                            router chain (used by the Node Express service via
                            subprocess, and directly runnable for smoke tests).
"""
