"use client";

import { History } from "lucide-react";
import type { TaskActivity } from "@/lib/types";

interface ActivityLogProps {
  activities: TaskActivity[];
}

export function ActivityLog({ activities }: ActivityLogProps) {
  return (
    <aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <History className="h-4 w-4 text-indigo-600" />
          PostgreSQL Transaction Log
        </h2>
        <span className="text-[11px] text-slate-400">ACID Audit Trail</span>
      </div>

      {activities.length === 0 ? (
        <p className="text-xs text-slate-500">No activity recorded yet.</p>
      ) : (
        <ul className="space-y-2.5 max-h-[540px] overflow-y-auto pr-1">
          {activities.map((item) => (
            <li
              key={item.id}
              className="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] font-semibold text-indigo-600">
                  {item.action}
                </span>
                <span className="text-[10px] text-slate-400">
                  {new Date(item.created_at).toLocaleTimeString()}
                </span>
              </div>
              <p className="mt-1 text-slate-700">{item.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
