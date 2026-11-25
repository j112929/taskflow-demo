from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Board, Task, TaskActivity, TaskPriority, TaskStatus


async def ensure_seed_data(db: AsyncSession) -> None:
    """Seed an initial demo board and sample tasks once when the database is empty."""
    board_count = await db.scalar(select(func.count(Board.id)))
    if board_count and board_count > 0:
        return

    board = Board(
        name="TaskFlow Architecture Demo",
        description="Next.js + FastAPI + PostgreSQL (ACID Transactions) + Redis (Cache, Lock & Rate Limit)",
    )
    db.add(board)
    await db.flush()

    sample_tasks = [
        Task(
            board_id=board.id,
            title="Design PostgreSQL relational schema & audit log",
            description="Persist boards, tasks, and transactional task_activities in a single ACID commit.",
            status=TaskStatus.DONE.value,
            priority=TaskPriority.HIGH.value,
            position=0,
            assignee="Alice",
        ),
        Task(
            board_id=board.id,
            title="Implement Redis read-through board cache",
            description="Cache GET /boards/{id}/tasks with 30s TTL and expose X-Cache: HIT|MISS headers.",
            status=TaskStatus.IN_PROGRESS.value,
            priority=TaskPriority.HIGH.value,
            position=0,
            assignee="Bob",
        ),
        Task(
            board_id=board.id,
            title="Add Redis distributed lock for task reordering",
            description="Guard concurrent column moves with SET NX PX and atomic Lua script unlock.",
            status=TaskStatus.TODO.value,
            priority=TaskPriority.MEDIUM.value,
            position=0,
            assignee="Carol",
        ),
        Task(
            board_id=board.id,
            title="Wire Next.js Kanban UI & live telemetry",
            description="Display cache hit status, rate limit budget, and PostgreSQL transaction log.",
            status=TaskStatus.TODO.value,
            priority=TaskPriority.LOW.value,
            position=1,
            assignee="Dave",
        ),
    ]
    db.add_all(sample_tasks)
    await db.flush()

    db.add(
        TaskActivity(
            board_id=board.id,
            task_id=None,
            action="board.seeded",
            detail=f"Initialized '{board.name}' with {len(sample_tasks)} demo tasks.",
        )
    )
    await db.commit()
