import fs from "fs";
import path from "path";
import { redirect } from "next/navigation";

import { listPausedTaskEvents } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";
import { AutoRefresh } from "@/app/workboard/_components/WorkboardClient";
import { ResumeButton } from "./_components/ResumeButton";

// ─── File readers (server-side, same logic as API routes) ─────────────────────

interface CooldownEntry {
  provider: string;
  model: string;
  reason: string;
  retry_after_at: string;
}

interface RuntimeStatus {
  last_tick: string | null;
  worker_alive: boolean;
  paused_count: number;
  ready_to_resume_count: number;
  cooldowns: CooldownEntry[];
  last_stats: { requeued: string[]; deferred: string[]; pruned: number } | null;
}

interface TickEntry {
  timestamp: string;
  requeued: string[];
  deferred: string[];
  pruned: number;
  dry_run: boolean;
}

interface RuntimeStatusWithAlive extends RuntimeStatus {
  workerAlive: boolean;
}

function readRuntimeStatus(): RuntimeStatusWithAlive {
  const base = process.env.OUTPUT_BASE_PATH ?? "/app/outputs";
  const file = path.join(base, "recovery", "runtime_status.json");
  let parsed: RuntimeStatus;
  try {
    if (!fs.existsSync(file)) throw new Error("missing");
    parsed = JSON.parse(fs.readFileSync(file, "utf-8")) as RuntimeStatus;
  } catch {
    parsed = { last_tick: null, worker_alive: false, paused_count: 0, ready_to_resume_count: 0, cooldowns: [], last_stats: null };
  }
  const workerAlive = parsed.last_tick
    ? Date.now() - new Date(parsed.last_tick).getTime() < 10 * 60 * 1000
    : false;
  return { ...parsed, workerAlive };
}

function readTickHistory(limit = 50): TickEntry[] {
  const base = process.env.OUTPUT_BASE_PATH ?? "/app/outputs";
  const file = path.join(base, "recovery", "tick_history.json");
  try {
    if (!fs.existsSync(file)) return [];
    const all = JSON.parse(fs.readFileSync(file, "utf-8")) as TickEntry[];
    return all.slice().reverse().slice(0, limit);
  } catch {
    return [];
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function fmtRelative(iso: string | null): string {
  if (!iso) return "—";
  try {
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  } catch { return iso; }
}

const REASON_LABEL: Record<string, string> = {
  rate_limited:   "Rate limited",
  context_limit:  "Context limit",
  auth_error:     "Auth error",
  timeout:        "Timeout",
  server_error:   "Server error",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function RecoveryPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (session.role !== "Admin") redirect("/dashboard");

  const status   = readRuntimeStatus();
  const ticks    = readTickHistory(30);
  const paused   = listPausedTaskEvents(100);
  const { workerAlive } = status;

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Recovery</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Quota-aware pause / resume — paused tasks, provider cooldowns, recovery worker health
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className="flex items-center gap-2 text-sm font-medium px-3 py-1 rounded-full border"
            style={
              workerAlive
                ? { color: "var(--ok)", borderColor: "var(--ok)", background: "rgba(36,224,138,.08)" }
                : { color: "var(--muted)", borderColor: "rgba(255,255,255,.1)" }
            }
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{
                background: workerAlive ? "var(--ok)" : "var(--muted)",
                boxShadow: workerAlive ? "0 0 6px var(--ok)" : "none",
              }}
            />
            {workerAlive ? "Running" : "Offline"}
          </span>
          <AutoRefresh intervalMs={30_000} />
        </div>
      </div>

      {/* ── Worker status bar ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Last tick",      value: fmtRelative(status.last_tick),              color: "var(--primary)" },
          { label: "Paused tasks",   value: String(status.paused_count),                color: paused.length > 0 ? "var(--warn)" : "var(--ok)" },
          { label: "Ready to resume",value: String(status.ready_to_resume_count),       color: "var(--primary)" },
          { label: "Active cooldowns",value: String(status.cooldowns?.length ?? 0),     color: (status.cooldowns?.length ?? 0) > 0 ? "var(--warn)" : "var(--ok)" },
        ].map((card) => (
          <div
            key={card.label}
            className="material-panel rounded-2xl p-4 text-center"
            style={{ borderColor: "rgba(255,255,255,.06)" }}
          >
            <p className="text-2xl font-bold" style={{ color: card.color }}>{card.value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{card.label}</p>
          </div>
        ))}
      </div>

      {status.last_stats && (
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          Last tick stats — requeued: {status.last_stats.requeued.length} &nbsp;·&nbsp;
          deferred: {status.last_stats.deferred.length} &nbsp;·&nbsp;
          pruned: {status.last_stats.pruned}
          &nbsp;&nbsp;({fmtTime(status.last_tick)})
        </p>
      )}

      {/* ── Paused task queue ── */}
      <div className="material-panel rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b" style={{ borderColor: "rgba(255,255,255,.06)" }}>
          <h2 className="text-sm font-semibold text-white">
            Paused Task Queue
            <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
              ({paused.length} task{paused.length !== 1 ? "s" : ""})
            </span>
          </h2>
        </div>

        {paused.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm" style={{ color: "var(--muted)" }}>
            No paused tasks
          </div>
        ) : (
          <table className="oc-table w-full">
            <thead>
              <tr>
                <th>Task</th>
                <th>Role</th>
                <th>Reason</th>
                <th>Provider / Model</th>
                <th>Retry After</th>
                <th>Policy</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {paused.map((task) => (
                <tr key={task.sdlcTaskId}>
                  <td className="font-medium text-white max-w-[180px] truncate" title={task.taskName}>
                    {task.taskName}
                  </td>
                  <td style={{ color: "var(--muted)" }}>{task.roleKey}</td>
                  <td>
                    <span className="oc-badge oc-badge-warn">
                      {REASON_LABEL[task.pauseReason] ?? (task.pauseReason || "—")}
                    </span>
                  </td>
                  <td className="text-xs" style={{ color: "var(--muted)" }}>
                    {task.pauseProvider || "—"}
                    {task.pauseModel ? ` / ${task.pauseModel.split("/").pop()}` : ""}
                  </td>
                  <td className="text-xs" style={{ color: "var(--muted)" }}>
                    {task.retryAfterAt ? fmtTime(task.retryAfterAt) : "—"}
                  </td>
                  <td>
                    {task.resumePolicy === "manual_token_fix" ? (
                      <span className="oc-badge oc-badge-bad">Manual</span>
                    ) : (
                      <span className="text-xs" style={{ color: "var(--muted)" }}>Auto</span>
                    )}
                  </td>
                  <td>
                    {task.resumePolicy === "manual_token_fix" ? (
                      <ResumeButton sdlcTaskId={task.sdlcTaskId} />
                    ) : (
                      <span className="text-xs" style={{ color: "var(--muted)" }}>Will auto-resume</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Active provider cooldowns ── */}
      <div className="material-panel rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b" style={{ borderColor: "rgba(255,255,255,.06)" }}>
          <h2 className="text-sm font-semibold text-white">Active Provider Cooldowns</h2>
        </div>
        {!status.cooldowns || status.cooldowns.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm" style={{ color: "var(--ok)" }}>
            No active cooldowns
          </div>
        ) : (
          <div className="p-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {status.cooldowns.map((cd, i) => (
              <div
                key={i}
                className="rounded-xl border p-4 space-y-1"
                style={{ borderColor: "rgba(255,200,60,.25)", background: "rgba(255,200,60,.04)" }}
              >
                <p className="text-sm font-semibold text-white">{cd.provider}</p>
                {cd.model && (
                  <p className="text-xs" style={{ color: "var(--muted)" }}>{cd.model}</p>
                )}
                <p className="text-xs" style={{ color: "var(--warn)" }}>
                  {REASON_LABEL[cd.reason] ?? cd.reason}
                </p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  Expires: {fmtTime(cd.retry_after_at)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Recovery tick log ── */}
      <div className="material-panel rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b" style={{ borderColor: "rgba(255,255,255,.06)" }}>
          <h2 className="text-sm font-semibold text-white">
            Recovery Tick Log
            <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
              (newest first)
            </span>
          </h2>
        </div>
        {ticks.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm" style={{ color: "var(--muted)" }}>
            No tick history yet
          </div>
        ) : (
          <table className="oc-table w-full">
            <thead>
              <tr>
                <th>Time</th>
                <th>Requeued</th>
                <th>Deferred</th>
                <th>Pruned</th>
              </tr>
            </thead>
            <tbody>
              {ticks.map((tick, i) => (
                <tr key={i}>
                  <td className="text-xs" style={{ color: "var(--muted)" }}>{fmtTime(tick.timestamp)}</td>
                  <td>
                    {tick.requeued.length > 0 ? (
                      <span className="oc-badge oc-badge-ok">{tick.requeued.length}</span>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    {tick.deferred.length > 0 ? (
                      <span className="oc-badge oc-badge-warn">{tick.deferred.length}</span>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    {tick.pruned > 0 ? (
                      <span className="text-xs" style={{ color: "var(--primary)" }}>{tick.pruned}</span>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Offline notice */}
      {!workerAlive && (
        <div
          className="rounded-2xl p-5 text-sm space-y-2 border"
          style={{ borderColor: "rgba(79,140,255,.3)", background: "rgba(79,140,255,.06)" }}
        >
          <p className="font-semibold text-white">Recovery Worker is not running</p>
          <p style={{ color: "var(--muted)" }}>Start it with:</p>
          <pre className="oc-log rounded-lg p-3 text-xs overflow-x-auto">
{`# In sdlc directory:
python agents/recovery_worker.py

# One tick for testing:
python agents/recovery_worker.py --run-now
python agents/recovery_worker.py --dry-run`}
          </pre>
        </div>
      )}

    </div>
  );
}
