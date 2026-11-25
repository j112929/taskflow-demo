from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskPriority, TaskStatus


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=255)


class BoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: str = Field(default="Unassigned", min_length=1, max_length=64)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority | None = None
    assignee: str | None = Field(default=None, min_length=1, max_length=64)
    version: int | None = Field(default=None, ge=1, description="Optional optimistic lock version")


class TaskMove(BaseModel):
    status: TaskStatus
    position: int = Field(default=0, ge=0)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    position: int
    version: int
    assignee: str
    created_at: datetime
    updated_at: datetime


class BoardStatsOut(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int


class BoardTasksResponse(BaseModel):
    board: BoardOut
    tasks: list[TaskOut]
    stats: BoardStatsOut
    cache_status: str
    cache_ttl_seconds: int


class TaskActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    task_id: int | None
    action: str
    detail: str
    created_at: datetime


class ServiceHealth(BaseModel):
    ok: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthOut(BaseModel):
    status: str
    postgres: ServiceHealth
    redis: ServiceHealth
