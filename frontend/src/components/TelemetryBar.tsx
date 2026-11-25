"use client";

import { Activity, Database, Flame, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import type { ApiMeta, HealthResponse } from "@/lib/types";

interface TelemetryBarProps {
  health: HealthResponse | null;
  meta: ApiMeta;
  cacheTtlSeconds: number;
  loading: boolean;
  onRefresh: () => void;
  onClearCache: () => void;
}

export function TelemetryBar({
  health,
  meta,
  cacheTtlSeconds,
  loading,
  onRefresh,
  onClearCache,
}: TelemetryBarProps) {
  const isCacheHit = meta.cacheStatus === "HIT";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5 text-xs font-medium">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
              health?.postgres.ok
                ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                : "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
            }`}
          >
            <Database className="h-3.5 w-3.5" />
            PostgreSQL: {health?.postgres.ok ? `OK (${health.postgres.latency_ms}ms)` : "Offline"}
          </span>

          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
              health?.redis.ok
                ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                : "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
            }`}
          >
            <Flame className="h-3.5 w-3.5" />
            Redis: {health?.redis.ok ? `OK (${health.redis.latency_ms}ms)` : "Offline"}
          </span>

          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
              isCacheHit
                ? "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200"
                : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            X-Cache: {meta.cacheStatus ?? "N/A"} (TTL {cacheTtlSeconds}s)
          </span>

          {meta.rateLimitRemaining !== null && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-slate-700 ring-1 ring-slate-200">
              <ShieldCheck className="h-3.5 w-3.5" />
              Rate Limit: {meta.rateLimitRemaining}/{meta.rateLimitLimit ?? "30"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClearCache}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear Redis Cache
          </button>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Board
          </button>
        </div>
      </div>
    </div>
  );
}
