"use client";

import { ArrowLeft, ArrowRight, Trash2, User } from "lucide-react";
import type { Task, TaskStatus } from "@/lib/types";

interface TaskCardProps {
  task: Task;
  busy: boolean;
  onMove: (taskId: number, status: TaskStatus) => void;
  onDelete: (taskId: number) => void;
  onDragStart: (taskId: number) => void;
}

const PRIORITY_STYLES: Record<Task["priority"], string> = {
  high: "bg-rose-50 text-rose-700 ring-rose-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-slate-100 text-slate-600 ring-slate-200",
};

const PREV_STATUS: Record<TaskStatus, TaskStatus | null> = {
  todo: null,
  in_progress: "todo",
  done: "in_progress",
};

const NEXT_STATUS: Record<TaskStatus, TaskStatus | null> = {
  todo: "in_progress",
  in_progress: "done",
  done: null,
};

export function TaskCard({
  task,
  busy,
  onMove,
  onDelete,
  onDragStart,
}: TaskCardProps) {
  const prevStatus = PREV_STATUS[task.status];
  const nextStatus = NEXT_STATUS[task.status];

  return (
    <div
      draggable={!busy}
      onDragStart={() => onDragStart(task.id)}
      className="group cursor-grab rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm transition hover:border-slate-300 hover:shadow active:cursor-grabbing"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ${PRIORITY_STYLES[task.priority]}`}
          >
            {task.priority}
          </span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
            v{task.version}
          </span>
        </div>
        <button
          type="button"
          onClick={() => onDelete(task.id)}
          disabled={busy}
          aria-label={`Delete ${task.title}`}
          className="rounded p-1 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <h3 className="text-sm font-semibold text-slate-900">{task.title}</h3>
      {task.description && (
        <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-600">
          {task.description}
        </p>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5">
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <User className="h-3 w-3" />
          {task.assignee}
        </span>

        <div className="flex items-center gap-1">
          {prevStatus && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onMove(task.id, prevStatus)}
              title={`Move to ${prevStatus}`}
              className="rounded-md border border-slate-200 p-1 text-slate-600 transition hover:bg-slate-100 disabled:opacity-40"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
            </button>
          )}
          {nextStatus && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onMove(task.id, nextStatus)}
              title={`Move to ${nextStatus}`}
              className="rounded-md border border-slate-200 p-1 text-slate-600 transition hover:bg-slate-100 disabled:opacity-40"
            >
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
