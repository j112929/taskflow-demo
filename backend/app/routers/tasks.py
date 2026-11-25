import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Board, Task, TaskActivity
from app.redis_client import (
    distributed_lock,
    enforce_rate_limit,
    get_redis,
    invalidate_board_cache,
)
from app.schemas import TaskCreate, TaskMove, TaskOut, TaskUpdate

router = APIRouter(prefix="/api", tags=["tasks"])


async def _normalize_column_positions(db: AsyncSession, board_id: int, column_status: str) -> list[Task]:
    result = await db.execute(
        select(Task)
        .where(Task.board_id == board_id, Task.status == column_status)
        .order_by(Task.position.asc(), Task.id.asc())
    )
    column_tasks = list(result.scalars().all())
    for idx, item in enumerate(column_tasks):
        item.position = idx
    return column_tasks


@router.post(
    "/boards/{board_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_task(
    board_id: int,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> Task:
    """Create a task and audit activity inside one PostgreSQL transaction, then invalidate Redis cache."""
    board = await db.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    max_pos = await db.scalar(
        select(func.coalesce(func.max(Task.position), -1)).where(
            Task.board_id == board_id,
            Task.status == payload.status.value,
        )
    )
    task = Task(
        board_id=board_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status=payload.status.value,
        priority=payload.priority.value,
        position=(max_pos if max_pos is not None else -1) + 1,
        assignee=payload.assignee.strip(),
    )
    db.add(task)
    await db.flush()

    db.add(
        TaskActivity(
            board_id=board_id,
            task_id=task.id,
            action="task.created",
            detail=f"Created '{task.title}' in {task.status} ({task.priority})",
        )
    )
    await db.commit()
    await db.refresh(task)
    await invalidate_board_cache(redis, board_id)
    return task


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskOut,
    dependencies=[Depends(enforce_rate_limit)],
)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> Task:
    """Update task fields with optional optimistic locking and transactional audit logging."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if payload.version is not None and payload.version != task.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Optimistic lock conflict: expected version {task.version}, got {payload.version}.",
        )

    changes: list[str] = []
    if payload.title is not None and payload.title.strip() != task.title:
        task.title = payload.title.strip()
        changes.append("title")
    if payload.description is not None and payload.description.strip() != task.description:
        task.description = payload.description.strip()
        changes.append("description")
    if payload.priority is not None and payload.priority.value != task.priority:
        task.priority = payload.priority.value
        changes.append(f"priority->{task.priority}")
    if payload.assignee is not None and payload.assignee.strip() != task.assignee:
        task.assignee = payload.assignee.strip()
        changes.append(f"assignee->{task.assignee}")

    if changes:
        task.version += 1
        db.add(
            TaskActivity(
                board_id=task.board_id,
                task_id=task.id,
                action="task.updated",
                detail=f"Updated '{task.title}': {', '.join(changes)} (v{task.version})",
            )
        )
        await db.commit()
        await db.refresh(task)
        await invalidate_board_cache(redis, task.board_id)

    return task


@router.post(
    "/tasks/{task_id}/move",
    response_model=TaskOut,
    dependencies=[Depends(enforce_rate_limit)],
)
async def move_task(
    task_id: int,
    payload: TaskMove,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> Task:
    """Move/reorder a task under a Redis distributed lock and a PostgreSQL transaction."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    lock_key = f"taskflow:lock:board:{task.board_id}:reorder"
    async with distributed_lock(redis, lock_key):
        # Re-fetch inside lock to guarantee fresh state before computing positions.
        await db.refresh(task)
        previous_status = task.status
        target_status = payload.status.value

        target_result = await db.execute(
            select(Task)
            .where(
                Task.board_id == task.board_id,
                Task.status == target_status,
                Task.id != task.id,
            )
            .order_by(Task.position.asc(), Task.id.asc())
        )
        target_tasks = list(target_result.scalars().all())
        insert_at = min(payload.position, len(target_tasks))
        target_tasks.insert(insert_at, task)

        task.status = target_status
        task.version += 1
        for idx, item in enumerate(target_tasks):
            item.position = idx

        if previous_status != target_status:
            await _normalize_column_positions(db, task.board_id, previous_status)

        db.add(
            TaskActivity(
                board_id=task.board_id,
                task_id=task.id,
                action="task.moved",
                detail=f"Moved '{task.title}' from {previous_status} to {target_status} (pos {insert_at})",
            )
        )
        await db.commit()
        await db.refresh(task)

    await invalidate_board_cache(redis, task.board_id)
    return task


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_rate_limit)],
)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    """Delete a task and log the deletion atomically in PostgreSQL, then invalidate cache."""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    board_id = task.board_id
    title = task.title
    previous_status = task.status

    await db.delete(task)
    await db.flush()
    await _normalize_column_positions(db, board_id, previous_status)

    db.add(
        TaskActivity(
            board_id=board_id,
            task_id=task_id,
            action="task.deleted",
            detail=f"Deleted '{title}' from {previous_status}",
        )
    )
    await db.commit()
    await invalidate_board_cache(redis, board_id)
