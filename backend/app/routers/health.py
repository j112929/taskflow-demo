import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.redis_client import get_redis
from app.schemas import HealthOut, ServiceHealth

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> HealthOut:
    """Check live PostgreSQL and Redis connectivity with round-trip latency."""
    pg_health = await _check_postgres(db)
    redis_health = await _check_redis(redis)
    overall = "ok" if pg_health.ok and redis_health.ok else "degraded"
    return HealthOut(status=overall, postgres=pg_health, redis=redis_health)


async def _check_postgres(db: AsyncSession) -> ServiceHealth:
    start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(ok=True, latency_ms=latency_ms)
    except Exception as exc:
        return ServiceHealth(ok=False, error=str(exc))


async def _check_redis(redis: aioredis.Redis) -> ServiceHealth:
    start = time.perf_counter()
    try:
        await redis.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(ok=True, latency_ms=latency_ms)
    except Exception as exc:
        return ServiceHealth(ok=False, error=str(exc))
