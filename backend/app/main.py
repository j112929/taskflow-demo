from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.redis_client import close_redis, init_redis
from app.routers import boards, health, tasks


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize PostgreSQL tables and Redis connection pool on startup."""
    await init_db()
    await init_redis()
    try:
        yield
    finally:
        await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="TaskFlow full-stack demo with Next.js, FastAPI, PostgreSQL, and Redis.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Cache", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

app.include_router(health.router)
app.include_router(boards.router)
app.include_router(tasks.router)
