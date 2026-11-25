# TaskFlow — Next.js + FastAPI + PostgreSQL + Redis Demo

A full-stack collaborative Kanban board demo showcasing **Next.js (App Router)**, **FastAPI (Async)**, **PostgreSQL (ACID Transactions & Optimistic Locking)**, and **Redis (Read-Through Cache, Distributed Lock, and Rate Limiting)**.

## Architecture Highlights

1. **Next.js 15 (`frontend/`)**
   - TypeScript + Tailwind CSS Kanban UI supporting drag-and-drop and quick-move buttons.
   - Live telemetry bar showing PostgreSQL & Redis health and latency, `X-Cache: HIT | MISS` status, remaining rate-limit quota, and a one-click Redis cache flush button.
   - Real-time audit panel displaying transaction logs persisted in PostgreSQL.

2. **FastAPI (`backend/`)**
   - **PostgreSQL + SQLAlchemy 2.0 Async (`asyncpg`)**: Every task creation, move, update, and deletion is committed atomically alongside its `task_activities` audit record in a single ACID transaction, with optimistic locking via the `version` column.
   - **Redis (`redis.asyncio`)**:
     - **Read-Through Cache**: `GET /api/boards/{id}/tasks` caches board tasks and stats with automatic invalidation on writes and exposes `X-Cache: HIT | MISS` response headers.
     - **Distributed Lock**: `POST /api/tasks/{id}/move` acquires a lock with `SET key token NX PX` and releases it safely with a Lua script verifying ownership, preventing concurrent reorder race conditions.
     - **Fixed-Window Rate Limiter**: Uses `INCR` + `EXPIRE` per client host, returning `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers and `429 Too Many Requests` when exceeded.

## Quick Start

### Option 1: Run the entire stack with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Once running, open:
- Frontend Kanban UI: http://localhost:3000
- Backend API Docs (Swagger): http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

### Option 2: Run PostgreSQL & Redis in Docker, and run Backend/Frontend locally

```bash
docker compose up -d postgres redis

# Terminal 1: Start FastAPI
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start Next.js
cd frontend
npm install
npm run dev
```

## Running Tests & Build Verification

```bash
# Backend unit tests (in-memory SQLite + FakeRedis verifying transactions, caching, locks, and rate limiting)
cd backend
.venv/bin/pytest -v

# Frontend type-check and production build
cd frontend
npx tsc --noEmit
npm run build
```
