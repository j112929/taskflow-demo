"use client";

import { useCallback, useEffect, useState } from "react";
import { Layers, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  ApiMeta,
  Board,
  BoardStats,
  HealthResponse,
  Task,
  TaskActivity,
  TaskPriority,
  TaskStatus,
} from "@/lib/types";
import { ActivityLog } from "./ActivityLog";
import { TaskCard } from "./TaskCard";
import { TelemetryBar } from "./TelemetryBar";

const COLUMNS: { key: TaskStatus; label: string; accent: string }[] = [
  { key: "todo", label: "To Do", accent: "bg-slate-400" },
  { key: "in_progress", label: "In Progress", accent: "bg-indigo-500" },
  { key: "done", label: "Done", accent: "bg-emerald-500" },
];

export function TaskFlowBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<BoardStats>({ total: 0, todo: 0, in_progress: 0, done: 0 });
  const [activities, setActivities] = useState<TaskActivity[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [meta, setMeta] = useState<ApiMeta>({
    cacheStatus: null,
    rateLimitRemaining: null,
    rateLimitLimit: null,
  });
  const [cacheTtl, setCacheTtl] = useState(30);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draggedTaskId, setDraggedTaskId] = useState<number | null>(null);

  // Create task form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [assignee, setAssignee] = useState("Alex");

  // Create board inline state
  const [newBoardName, setNewBoardName] = useState("");

  const loadBoardData = useCallback(async (boardId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, boardTasksRes, activitiesRes] = await Promise.all([
        api.getHealth(),
        api.getBoardTasks(boardId),
        api.getBoardActivities(boardId),
      ]);
      setHealth(healthRes.data);
      setTasks(boardTasksRes.data.tasks);
      setStats(boardTasksRes.data.stats);
      setCacheTtl(boardTasksRes.data.cache_ttl_seconds);
      setMeta({
        cacheStatus: boardTasksRes.meta.cacheStatus ?? boardTasksRes.data.cache_status,
        rateLimitRemaining: boardTasksRes.meta.rateLimitRemaining,
        rateLimitLimit: boardTasksRes.meta.rateLimitLimit,
      });
      setActivities(activitiesRes.data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load board from FastAPI backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function init() {
      try {
        const [healthRes, boardsRes] = await Promise.all([api.getHealth(), api.listBoards()]);
        if (!active) return;
        setHealth(healthRes.data);
        setBoards(boardsRes.data);
        if (boardsRes.data.length > 0) {
          setSelectedBoardId(boardsRes.data[0].id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Cannot connect to FastAPI backend. Ensure API, PostgreSQL, and Redis are running."
        );
        setLoading(false);
      }
    }
    init();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (selectedBoardId !== null) {
      loadBoardData(selectedBoardId);
    }
  }, [selectedBoardId, loadBoardData]);

  async function handleCreateTask(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBoardId || !title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createTask(selectedBoardId, {
        title: title.trim(),
        description: description.trim(),
        status: "todo",
        priority,
        assignee: assignee.trim() || "Unassigned",
      });
      setTitle("");
      setDescription("");
      await loadBoardData(selectedBoardId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create task");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateBoard(e: React.FormEvent) {
    e.preventDefault();
    if (!newBoardName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { data: created } = await api.createBoard({
        name: newBoardName.trim(),
        description: "Custom workspace board",
      });
      setBoards((prev) => [...prev, created]);
      setNewBoardName("");
      setSelectedBoardId(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create board");
    } finally {
      setBusy(false);
    }
  }

  async function handleMoveTask(taskId: number, targetStatus: TaskStatus) {
    if (!selectedBoardId) return;
    setBusy(true);
    setError(null);
    try {
      await api.moveTask(taskId, { status: targetStatus, position: 0 });
      await loadBoardData(selectedBoardId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to move task");
    } finally {
      setBusy(false);
      setDraggedTaskId(null);
    }
  }

  async function handleDeleteTask(taskId: number) {
    if (!selectedBoardId) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteTask(taskId);
      await loadBoardData(selectedBoardId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete task");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearCache() {
    if (!selectedBoardId) return;
    setBusy(true);
    setError(null);
    try {
      await api.clearBoardCache(selectedBoardId);
      await loadBoardData(selectedBoardId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to clear Redis cache");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
              <Layers className="h-5 w-5" />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">TaskFlow</h1>
            <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
              Next.js + FastAPI + PostgreSQL + Redis
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Click &ldquo;Refresh Board&rdquo; twice to see Redis{" "}
            <code className="rounded bg-slate-200/70 px-1">MISS → HIT</code>; move or create tasks to
            observe Redis distributed locking, cache invalidation, and PostgreSQL ACID audit logs.
          </p>
        </div>

        {/* Board switcher + quick create */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedBoardId ?? ""}
            onChange={(e) => setSelectedBoardId(Number(e.target.value))}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 shadow-sm"
          >
            {boards.map((board) => (
              <option key={board.id} value={board.id}>
                {board.name}
              </option>
            ))}
          </select>

          <form onSubmit={handleCreateBoard} className="flex items-center gap-1.5">
            <input
              type="text"
              value={newBoardName}
              onChange={(e) => setNewBoardName(e.target.value)}
              placeholder="New board..."
              className="w-36 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={busy || !newBoardName.trim()}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              + Board
            </button>
          </form>
        </div>
      </header>

      {/* Live Infrastructure Telemetry */}
      <TelemetryBar
        health={health}
        meta={meta}
        cacheTtlSeconds={cacheTtl}
        loading={loading || busy}
        onRefresh={() => selectedBoardId && loadBoardData(selectedBoardId)}
        onClearCache={handleClearCache}
      />

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* Create Task Form */}
      <form
        onSubmit={handleCreateTask}
        className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-12"
      >
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="New task title..."
          required
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 md:col-span-4"
        />
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 md:col-span-4"
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as TaskPriority)}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm outline-none focus:border-indigo-500 md:col-span-1"
        >
          <option value="low">Low</option>
          <option value="medium">Med</option>
          <option value="high">High</option>
        </select>
        <input
          type="text"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
          placeholder="Assignee"
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 md:col-span-1"
        />
        <button
          type="submit"
          disabled={busy || !selectedBoardId || !title.trim()}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50 md:col-span-2"
        >
          <Plus className="h-4 w-4" />
          Add Task
        </button>
      </form>

      {/* Main Grid: 3 Kanban Columns + PostgreSQL Activity Log */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:col-span-3">
          {COLUMNS.map((col) => {
            const columnTasks = tasks.filter((t) => t.status === col.key);
            const count =
              col.key === "todo"
                ? stats.todo
                : col.key === "in_progress"
                ? stats.in_progress
                : stats.done;

            return (
              <section
                key={col.key}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (draggedTaskId !== null) {
                    handleMoveTask(draggedTaskId, col.key);
                  }
                }}
                className="flex min-h-[420px] flex-col rounded-xl border border-slate-200 bg-slate-100/70 p-3.5"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${col.accent}`} />
                    <h2 className="text-sm font-semibold text-slate-800">{col.label}</h2>
                  </div>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">
                    {count}
                  </span>
                </div>

                <div className="flex flex-1 flex-col gap-3">
                  {columnTasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      busy={busy}
                      onMove={handleMoveTask}
                      onDelete={handleDeleteTask}
                      onDragStart={setDraggedTaskId}
                    />
                  ))}
                  {columnTasks.length === 0 && (
                    <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-slate-300 p-4 text-center text-xs text-slate-400">
                      Drop tasks here
                    </div>
                  )}
                </div>
              </section>
            );
          })}
        </div>

        <ActivityLog activities={activities} />
      </div>
    </main>
  );
}
