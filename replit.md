# YouTube Factory

An autonomous YouTube video creation platform. Users create projects with a topic, run the full AI pipeline (research → script → scene planning → image generation → voice generation → video editing → subtitles → thumbnail → SEO → upload), and have complete videos published to YouTube automatically.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — Node.js API server (port 5000, `/api/`)
- `pnpm --filter @workspace/youtube-factory run dev` — React frontend (port auto-assigned, `/`)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

### Docker (full stack including Python)
- `docker compose up` — start all services (Postgres, Redis, FastAPI, Celery, Node, React)
- `docker compose up youtube-factory-api celery-worker-pipeline` — Python backend only

### Python FastAPI service (local dev without Docker)
```bash
cd services/youtube-factory-api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Stack

- **Frontend**: React + TypeScript + Vite + Tailwind + shadcn/ui
- **Node.js API**: Express 5 + Drizzle ORM (serves OpenAPI-generated routes at `/api/`)
- **Python API**: FastAPI + SQLAlchemy async (serves at `/api/v1/` via Docker)
- **DB**: PostgreSQL + Drizzle ORM (Node.js) + SQLAlchemy (Python)
- **Queue**: Celery + Redis (6 queues: pipeline, research, script, media, upload)
- **Video**: MoviePy + FFmpeg
- **Containerization**: Docker Compose
- **Codegen**: Orval (OpenAPI → React Query hooks + Zod schemas)

## Where things live

- `lib/api-spec/openapi.yaml` — single source of truth for all API contracts
- `lib/db/src/schema/` — Drizzle schema (projects, pipelines, jobs, logs, settings)
- `artifacts/api-server/src/routes/` — Express route handlers
- `artifacts/youtube-factory/src/` — React frontend
- `services/youtube-factory-api/` — Python FastAPI service
  - `app/models/` — SQLAlchemy ORM models
  - `app/repositories/` — Repository pattern (BaseRepository + domain repos)
  - `app/services/` — AI service interfaces (all placeholder, ready to implement)
  - `app/tasks/` — Celery task definitions (pipeline, research, script, media, upload)
  - `app/api/v1/endpoints/` — FastAPI route handlers

## Pipeline Stages (in order)

1. `research` — topic research via AI + web search
2. `script` — video script writing (hook, body, CTA)
3. `scene_planning` — break script into scenes with image prompts
4. `image_generation` — generate scene images (DALL-E / Stable Diffusion)
5. `voice_generation` — generate narration audio (OpenAI TTS / ElevenLabs)
6. `video_editing` — compose video from images + audio (MoviePy)
7. `subtitle_generation` — transcribe and time-align subtitles (Whisper)
8. `thumbnail_generation` — generate thumbnail variants
9. `seo_generation` — generate titles, description, tags, chapters
10. `upload` — upload to YouTube via Data API v3

## Service Interfaces (all placeholder — implement one at a time)

All services in `services/youtube-factory-api/app/services/`:
- `ResearchService` — research_topic(), find_trending_topics(), analyze_competitors()
- `ScriptService` — generate_script(), improve_script(), estimate_duration()
- `ScenePlanner` — plan_scenes(), generate_image_prompts()
- `ImageGenerator` — generate_for_scene(), generate_for_plan(), upscale()
- `VoiceGenerator` — generate_narration(), generate_section_audio(), normalize_audio()
- `VideoEditor` — compose_video(), add_background_music(), render_preview()
- `SubtitleGenerator` — generate_from_audio(), burn_into_video(), export_srt()
- `ThumbnailGenerator` — generate(), add_title_overlay(), optimize()
- `SEOGenerator` — generate_seo_package(), optimize_title(), generate_chapters()
- `UploadService` — upload_video(), set_thumbnail(), update_metadata()
- `AnalyticsService` — get_video_metrics(), get_channel_metrics(), get_top_performing_videos()

## Architecture decisions

- **Contract-first**: OpenAPI spec defines all routes before implementation. Orval generates React Query hooks and Zod validators.
- **Repository Pattern**: BaseRepository<T> provides typed CRUD. Domain repos extend with query-specific methods.
- **Clean Architecture**: Services have no framework dependencies. Repositories inject AsyncSession. FastAPI endpoints depend on repositories, not services directly.
- **Celery chain pattern**: Pipeline stages are chained Celery tasks. Each task receives context dict from the prior stage and passes enriched context forward.
- **Placeholder-first**: All AI service methods return typed placeholder data. Zero AI dependencies until implementing a specific service.
- **Dual backend**: Node.js serves codegen-compatible routes for the React frontend. Python serves the AI pipeline. Docker Compose unifies them.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- `pnpm add` at the root installs to root only. Use `pnpm --filter @workspace/<pkg> add <dep>` for package-specific deps.
- After any OpenAPI spec change, always run codegen before touching frontend code.
- `zod.looseObject()` is Zod v4 only. Use `additionalProperties: {}` for free-form object fields in the OpenAPI spec to avoid Orval generating v4 syntax.
- The Python service uses `asyncpg` driver — DATABASE_URL must use `postgresql+asyncpg://` not plain `postgresql://`.
- Docker Compose `celery-worker-media` runs with `--concurrency=1` because video rendering is CPU-heavy.
