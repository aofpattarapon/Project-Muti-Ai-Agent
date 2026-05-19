"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const PIPELINE = [
  { key: "ceo",     label: "CEO",      emoji: "👑" },
  { key: "pm",      label: "PM",       emoji: "📋" },
  { key: "ba",      label: "BA",       emoji: "📊" },
  { key: "sa",      label: "SA",       emoji: "🏗️" },
  { key: "uxui",    label: "UX/UI",    emoji: "🎨" },
  { key: "dev",     label: "DEV",      emoji: "💻" },
  { key: "qa",      label: "QA",       emoji: "🧪" },
  { key: "devops",  label: "DevOps",   emoji: "🚀" },
];

const STATUS_COLOR: Record<string, string> = {
  in_progress:       "bg-blue-500/20 text-blue-300 border-blue-500/30",
  waiting_approval:  "bg-amber-500/20 text-amber-300 border-amber-500/30",
  approved:          "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  rework_requested:  "bg-orange-500/20 text-orange-300 border-orange-500/30",
  rejected:          "bg-red-500/20 text-red-300 border-red-500/30",
  completed:         "bg-violet-500/20 text-violet-300 border-violet-500/30",
  blocked:           "bg-red-700/20 text-red-400 border-red-700/30",
};

export function PipelineHeader({ currentRole }: { currentRole?: string }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-2">
      {PIPELINE.map((stage, i) => {
        const active = currentRole === stage.key || currentRole?.startsWith(stage.key);
        return (
          <div key={stage.key} className="flex items-center">
            <div className={`flex flex-col items-center min-w-[70px] px-2 py-2 rounded-xl transition-all ${
              active
                ? "bg-violet-600/30 border border-violet-500/50 scale-105"
                : "opacity-50"
            }`}>
              <span className="text-lg">{stage.emoji}</span>
              <span className={`text-[11px] font-semibold tracking-wide mt-0.5 ${active ? "text-violet-200" : "text-slate-500"}`}>
                {stage.label}
              </span>
            </div>
            {i < PIPELINE.length - 1 && (
              <div className={`w-6 h-[2px] mx-0.5 rounded-full ${active ? "bg-violet-500/50" : "bg-slate-700"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function AutoRefresh({ intervalMs = 12000 }: { intervalMs?: number }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [countdown, setCountdown] = useState(intervalMs / 1000);

  useEffect(() => {
    const tick = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          startTransition(() => router.refresh());
          return intervalMs / 1000;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [router, intervalMs, startTransition]);

  return (
    <span className="text-xs text-slate-500 tabular-nums">
      auto-refresh in {countdown}s
    </span>
  );
}

export function ApprovalActions({
  id,
  roleKey,
  taskName,
}: {
  id: number;
  roleKey: string;
  taskName: string;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [done, setDone] = useState(false);
  const router = useRouter();

  const decide = useCallback(
    async (decision: "approved" | "rejected" | "rework_requested") => {
      setLoading(decision);
      const form = new FormData();
      form.set("decision", decision);
      form.set("role_key", roleKey);
      form.set("task_name", taskName);
      form.set("decision_note", note);
      await fetch(`/api/admin/approvals/${id}/decision`, { method: "POST", body: form });
      setDone(true);
      setLoading(null);
      router.refresh();
    },
    [id, roleKey, taskName, note, router],
  );

  if (done) {
    return <p className="text-xs text-emerald-400 mt-3">✅ Decision submitted — syncing to Discord...</p>;
  }

  return (
    <div className="mt-4 space-y-2 border-t border-white/6 pt-4">
      <p className="text-[11px] uppercase tracking-widest text-slate-500">Web approval</p>
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note / revision comment..."
        className="w-full rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-violet-500"
      />
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => decide("approved")}
          disabled={!!loading}
          className="rounded-lg bg-emerald-600/20 border border-emerald-500/40 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-600/30 disabled:opacity-40 transition"
        >
          {loading === "approved" ? "..." : "✅ Approve"}
        </button>
        <button
          onClick={() => decide("rework_requested")}
          disabled={!!loading}
          className="rounded-lg bg-orange-600/20 border border-orange-500/40 px-3 py-1.5 text-xs font-semibold text-orange-300 hover:bg-orange-600/30 disabled:opacity-40 transition"
        >
          {loading === "rework_requested" ? "..." : "🔄 Revise"}
        </button>
        <button
          onClick={() => decide("rejected")}
          disabled={!!loading}
          className="rounded-lg bg-red-600/20 border border-red-500/40 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-600/30 disabled:opacity-40 transition"
        >
          {loading === "rejected" ? "..." : "❌ Reject"}
        </button>
      </div>
    </div>
  );
}
