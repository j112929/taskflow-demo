import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Board, Task, TaskActivity, TaskStatus
from app.redis_client import (
    board_tasks_cache_key,
    enforce_rate_limit,
    get_cached_json,
    get_redis,
    invalidate_board_cache,
    set_cached_json,
)
from app.schemas import (
    BoardCreate,
    BoardOut,
    BoardStatsOut,
    BoardTasksResponse,
    TaskActivityOut,
    TaskOut,
)
from app.seed import ensure_seed_data

router = APIRouter(prefix="/api/boards", tags=["boards"])


def _compute_stats(tasks: list[TaskOut]) -> BoardStatsOut:
    todo = sum(1 for t in tasks if t.status == TaskStatus.TODO)
    in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    done = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    return BoardStatsOut(total=len(tasks), todo=todo, in_progress=in_progress, done=done)


@router.get("", response_model=list[BoardOut], dependencies=[Depends(enforce_rate_limit)])
async def list_boards(db: AsyncSession = Depends(get_db)) -> list[Board]:
    """List all boards, seeding a demo board on first access."""
    await ensure_seed_data(db)
    result = await db.execute(select(Board).order_by(Board.id.asc()))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=BoardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_board(payload: BoardCreate, db: AsyncSession = Depends(get_db)) -> Board:
    """Create a new Kanban board and record an initial PostgreSQL activity log."""
    board = Board(name=payload.name.strip(), description=payload.description.strip())
    db.add(board)
    await db.flush()

    db.add(
        TaskActivity(
            board_id=board.id,
            task_id=None,
            action="board.created",
            detail=f"Created board '{board.name}'",
        )
    )
    await db.commit()
    await db.refresh(board)
    return board


@router.get(
    "/{board_id}/tasks",
    response_model=BoardTasksResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def get_board_tasks(
    board_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> BoardTasksResponse:
    """Fetch board details, tasks, and stats using Redis read-through caching."""
    cache_key = board_tasks_cache_key(board_id)
    cached = await get_cached_json(redis, cache_key)
    if cached is not None:
        cached["cache_status"] = "HIT"
        response.headers["X-Cache"] = "HIT"
        return BoardTasksResponse.model_validate(cached)

    board = await db.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    result = await db.execute(
        select(Task)
        .where(Task.board_id == board_id)
        .order_by(Task.status.asc(), Task.position.asc(), Task.id.asc())
    )
    tasks = [TaskOut.model_validate(task) for task in result.scalars().all()]

    payload = BoardTasksResponse(
        board=BoardOut.model_validate(board),
        tasks=tasks,
        stats=_compute_stats(tasks),
        cache_status="MISS",
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    await set_cached_json(redis, cache_key, payload.model_dump(mode="json"), settings.cache_ttl_seconds)
    response.headers["X-Cache"] = "MISS"
    return payload


@router.get(
    "/{board_id}/activities",
    response_model=list[TaskActivityOut],
    dependencies=[Depends(enforce_rate_limit)],
)
async def list_board_activities(
    board_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[TaskActivity]:
    """Return recent transactional audit entries stored in PostgreSQL."""
    board = await db.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    capped_limit = max(1, min(limit, 50))
    result = await db.execute(
        select(TaskActivity)
        .where(TaskActivity.board_id == board_id)
        .order_by(TaskActivity.id.desc())
        .limit(capped_limit)
    )
    return list(result.scalars().all())


@router.post("/{board_id}/cache/invalidate", status_code=status.HTTP_200_OK)
async def clear_board_cache(
    board_id: int,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, str | int]:
    """Manually invalidate the board's Redis cache key for testing cache MISS -> HIT behavior."""
    board = await db.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    await invalidate_board_cache(redis, board_id)
    return {"status": "invalidated", "board_id": board_id}
