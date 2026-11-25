import type {
  ApiMeta,
  Board,
  BoardTasksResponse,
  HealthResponse,
  Task,
  TaskActivity,
  TaskPriority,
  TaskStatus,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<{ data: T; meta: ApiMeta }> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
  });

  const meta: ApiMeta = {
    cacheStatus: res.headers.get("X-Cache"),
    rateLimitRemaining: res.headers.get("X-RateLimit-Remaining"),
    rateLimitLimit: res.headers.get("X-RateLimit-Limit"),
  };

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = await res.json();
      if (errBody?.detail) detail = String(errBody.detail);
    } catch {
      // keep generic error
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) {
    return { data: undefined as T, meta };
  }

  const data = (await res.json()) as T;
  return { data, meta };
}

export const api = {
  getHealth: () => request<HealthResponse>("/api/health"),
  listBoards: () => request<Board[]>("/api/boards"),
  createBoard: (payload: { name: string; description: string }) =>
    request<Board>("/api/boards", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBoardTasks: (boardId: number) =>
    request<BoardTasksResponse>(`/api/boards/${boardId}/tasks`),
  getBoardActivities: (boardId: number) =>
    request<TaskActivity[]>(`/api/boards/${boardId}/activities?limit=20`),
  clearBoardCache: (boardId: number) =>
    request<{ status: string; board_id: number }>(
      `/api/boards/${boardId}/cache/invalidate`,
      { method: "POST" }
    ),
  createTask: (
    boardId: number,
    payload: {
      title: string;
      description: string;
      status: TaskStatus;
      priority: TaskPriority;
      assignee: string;
    }
  ) =>
    request<Task>(`/api/boards/${boardId}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (
    taskId: number,
    payload: {
      title?: string;
      description?: string;
      priority?: TaskPriority;
      assignee?: string;
      version?: number;
    }
  ) =>
    request<Task>(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  moveTask: (taskId: number, payload: { status: TaskStatus; position: number }) =>
    request<Task>(`/api/tasks/${taskId}/move`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteTask: (taskId: number) =>
    request<void>(`/api/tasks/${taskId}`, { method: "DELETE" }),
};
