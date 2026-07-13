---
name: YouTube Factory pipeline conventions
description: Provider/service/repo layering pattern, the render stage's Node/Python split, and a since-fixed FastAPI DELETE bug.
---

## Provider/service/repo layering
Each pipeline stage (research, script, storyboard, assets, timeline, voice, render) follows the same layering: a `providers/` fallback-ordered adapter layer, a `services/` orchestration layer, and a `repository` persistence layer. Follow this pattern for any new stage.

**Why:** keeps stages consistent and swappable; every stage before Render is fully reimplemented in Node/Express (simulated providers writing straight to Postgres) precisely because this layering made that reimplementation mechanical.

## Render stage: Node builds the plan, Python still owns the pixels
Render is the one stage that can't be reimplemented in Node — it needs real MoviePy/FFmpeg. The Express `render.ts` route mirrors the Python `plan_builder.py` field-for-field to build a RenderPlan JSON from Node-owned Timeline/Voice/Asset rows, writes it to disk, and shells out to a standalone Python CLI (`services/youtube-factory-api/scripts/render_cli.py`) that calls `MoviePyRenderer` directly — no Celery/Redis/uvicorn required in dev. Output files are served back via a `GET /renders/:id/file` streaming route (not stored in DB).

**Why:** avoids standing up Python's async task infra just for one stage while still producing genuinely encoded MP4s; a source comment in `plan_builder.py` explicitly asks future devs to keep the Node builder in sync with it — check that file whenever `RenderPlan`'s shape changes.

**How to apply:** if the RenderPlan schema changes on the Python side, update `buildRenderPlan` in `render.ts` to match, and re-verify with a real pipeline run (not just the synthetic-plan CLI test) since Node-side field mismatches only surface once real Timeline/Voice rows are fed through.

## FastAPI DELETE + response_model=204 bug — fixed
This FastAPI version crashes router import if a DELETE endpoint has `status_code=204` without `response_model=None`. This affected 8 endpoints across the router (assets, projects, render, research, script, storyboard, timelines, voice) and has been fixed by adding `response_model=None` to all of them — the router now imports cleanly (51 routes). Any *new* DELETE endpoint added to this service must include `response_model=None` alongside `status_code=204` or it will reintroduce the same import crash.
