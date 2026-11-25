export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";

export interface Board {
  id: number;
  name: string;
  description: string;
  created_at: string;
}

export interface Task {
  id: number;
  board_id: number;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  position: number;
  version: number;
  assignee: string;
  created_at: string;
  updated_at: string;
}

export interface BoardStats {
  total: number;
  todo: number;
  in_progress: number;
  done: number;
}

export interface BoardTasksResponse {
  board: Board;
  tasks: Task[];
  stats: BoardStats;
  cache_status: string;
  cache_ttl_seconds: number;
}

export interface TaskActivity {
  id: number;
  board_id: number;
  task_id: number | null;
  action: string;
  detail: string;
  created_at: string;
}

export interface ServiceHealth {
  ok: boolean;
  latency_ms: number | null;
  error: string | null;
}

export interface HealthResponse {
  status: string;
  postgres: ServiceHealth;
  redis: ServiceHealth;
}

export interface ApiMeta {
  cacheStatus: string | null;
  rateLimitRemaining: string | null;
  rateLimitLimit: string | null;
}
