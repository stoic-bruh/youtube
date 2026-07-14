# YouTube Factory

A full-stack YouTube content pipeline application for automating video research, scripting, storyboarding, asset generation, and rendering.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, Tailwind CSS v4, Wouter, TanStack Query |
| Node API | Express 5 (TypeScript, ESM), Zod, Drizzle ORM |
| Python backend | FastAPI + Celery (background job processing) |
| Database | PostgreSQL (Drizzle schema in `lib/db`) |
| Queue | Redis |
| Monorepo | pnpm workspaces |

## Repository layout

```
artifacts/
  youtube-factory/    # React frontend
  api-server/         # Node.js/Express REST API
  mockup-sandbox/     # Design/prototyping sandbox
lib/
  api-spec/           # OpenAPI spec (orval codegen)
  api-client-react/   # Generated React Query hooks
  api-zod/            # Generated Zod schemas
  db/                 # Drizzle ORM schema & migrations
services/
  youtube-factory-api/ # Python FastAPI + Celery backend
```

## Running locally (Docker)

The full stack (Postgres, Redis, Python API, Node API, React) is orchestrated via `docker-compose.yml`.

```bash
docker-compose up
```

## Running on Replit (without Docker)

Start each service separately:

```bash
# Install dependencies (once)
pnpm install

# Node API (port from $PORT env var)
cd artifacts/api-server && pnpm dev

# React frontend (separate terminal)
cd artifacts/youtube-factory && pnpm dev
```

The Python backend requires its own setup (see `services/youtube-factory-api/`).

## Required environment variables

| Variable | Purpose | Status |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string — **required** for API startup | Set this before running the Node API |
| `SESSION_SECRET` | Express session signing key | ✅ Already set in Replit Secrets |
| `REDIS_URL` | Redis connection (Celery broker) | Only needed for Python backend |

> **PostgreSQL note:** The Replit environment includes `postgresql` (via nix packages). You can start a local Postgres instance with `pg_ctl start` or use Replit's built-in database integration to get a `DATABASE_URL` automatically.

## User preferences
