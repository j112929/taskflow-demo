from __future__ import annotations

from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.redis_client import get_redis


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_redis() -> fakeredis.aioredis.FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Patch module-level _redis_client used by enforce_rate_limit
    from app import redis_client

    previous_redis = redis_client._redis_client
    redis_client._redis_client = fake_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()
        redis_client._redis_client = previous_redis
        await fake_redis.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_and_seed_boards(client: AsyncClient) -> None:
    health_res = await client.get("/api/health")
    assert health_res.status_code == 200
    body = health_res.json()
    assert body["status"] == "ok"
    assert body["postgres"]["ok"] is True
    assert body["redis"]["ok"] is True

    boards_res = await client.get("/api/boards")
    assert boards_res.status_code == 200
    boards = boards_res.json()
    assert len(boards) == 1
    assert boards[0]["name"] == "TaskFlow Architecture Demo"


@pytest.mark.asyncio
async def test_redis_read_through_cache_hit_miss_and_invalidation(client: AsyncClient) -> None:
    boards = (await client.get("/api/boards")).json()
    board_id = boards[0]["id"]

    # First read should be a cache MISS
    first = await client.get(f"/api/boards/{board_id}/tasks")
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert first.json()["cache_status"] == "MISS"
    initial_total = first.json()["stats"]["total"]

    # Second read should be a cache HIT
    second = await client.get(f"/api/boards/{board_id}/tasks")
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"
    assert second.json()["cache_status"] == "HIT"

    # Creating a task invalidates the board cache
    created = await client.post(
        f"/api/boards/{board_id}/tasks",
        json={"title": "Verify cache invalidation", "priority": "high", "assignee": "Tester"},
    )
    assert created.status_code == 201

    after_write = await client.get(f"/api/boards/{board_id}/tasks")
    assert after_write.status_code == 200
    assert after_write.headers["X-Cache"] == "MISS"
    assert after_write.json()["stats"]["total"] == initial_total + 1


@pytest.mark.asyncio
async def test_task_move_optimistic_lock_and_activity_log(client: AsyncClient) -> None:
    boards = (await client.get("/api/boards")).json()
    board_id = boards[0]["id"]

    created = await client.post(
        f"/api/boards/{board_id}/tasks",
        json={"title": "Move me", "status": "todo", "priority": "medium", "assignee": "Eve"},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["version"] == 1

    # Move from todo -> in_progress (exercises Redis distributed lock + PG transaction)
    moved = await client.post(
        f"/api/tasks/{task['id']}/move",
        json={"status": "in_progress", "position": 0},
    )
    assert moved.status_code == 200
    moved_task = moved.json()
    assert moved_task["status"] == "in_progress"
    assert moved_task["version"] == 2

    # Optimistic lock conflict when passing stale version
    conflict = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Stale update", "version": 1},
    )
    assert conflict.status_code == 409

    # Activity log captured both creation and move
    activities = (await client.get(f"/api/boards/{board_id}/activities")).json()
    actions = [entry["action"] for entry in activities]
    assert "task.created" in actions
    assert "task.moved" in actions


@pytest.mark.asyncio
async def test_distributed_lock_contention_returns_409(client: AsyncClient) -> None:
    boards = (await client.get("/api/boards")).json()
    board_id = boards[0]["id"]
    tasks_res = await client.get(f"/api/boards/{board_id}/tasks")
    task_id = tasks_res.json()["tasks"][0]["id"]

    from app import redis_client

    assert redis_client._redis_client is not None
    await redis_client._redis_client.set(f"taskflow:lock:board:{board_id}:reorder", "other-worker", px=5000)

    res = await client.post(
        f"/api/tasks/{task_id}/move",
        json={"status": "done", "position": 0},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_rate_limiter_enforces_limit(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 3)
    for _ in range(3):
        res = await client.get("/api/boards")
        assert res.status_code == 200

    blocked = await client.get("/api/boards")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
