from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response, status

from app.config import settings

# Atomic release: delete key only if the lock token matches the caller's token.
_UNLOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_redis_client: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Create the shared async Redis client."""
    global _redis_client
    _redis_client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the shared async Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> aioredis.Redis:
    """FastAPI dependency returning the active Redis client."""
    if _redis_client is None:
        raise RuntimeError("Redis client has not been initialized")
    return _redis_client


def board_tasks_cache_key(board_id: int) -> str:
    return f"taskflow:board:{board_id}:tasks:v1"


async def get_cached_json(redis: aioredis.Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_json(redis: aioredis.Redis, key: str, payload: Any, ttl_seconds: int) -> None:
    await redis.set(key, json.dumps(payload, default=str), ex=ttl_seconds)


async def invalidate_board_cache(redis: aioredis.Redis, board_id: int) -> None:
    await redis.delete(board_tasks_cache_key(board_id))


@asynccontextmanager
async def distributed_lock(
    redis: aioredis.Redis,
    lock_key: str,
    ttl_ms: int | None = None,
) -> AsyncIterator[str]:
    """Acquire a short-lived Redis distributed lock using SET NX PX and release via Lua."""
    token = str(uuid.uuid4())
    effective_ttl = ttl_ms or settings.lock_ttl_ms
    acquired = await redis.set(lock_key, token, nx=True, px=effective_ttl)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Board reorder is currently locked by another request; please retry.",
        )
    try:
        yield token
    finally:
        await redis.eval(_UNLOCK_LUA, 1, lock_key, token)


async def enforce_rate_limit(request: Request, response: Response) -> None:
    """Fixed-window Redis rate limiter keyed by client host."""
    redis = get_redis()
    client_ip = request.client.host if request.client else "unknown"
    key = f"taskflow:ratelimit:{client_ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.rate_limit_window_seconds)

    remaining = max(0, settings.rate_limit_requests - count)
    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    if count > settings.rate_limit_requests:
        ttl = await redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry in {max(1, ttl)}s.",
            headers={"Retry-After": str(max(1, ttl))},
        )
