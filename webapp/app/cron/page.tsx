"use client";

import { useEffect, useState } from "react";

interface JobEntry {
  job: string;
  status: "ok" | "warn" | "error";
  summary: string;
  timestamp: string;
}

interface CronStatus {
  running: boolean;
  lastUpdated: string | null;
  jobs: JobEntry[];
  summary: {
    total: number;
    ok: number;
    warn: number;
    error: number;
    lastRun: string | null;
  };
}

const JOB_LABELS: Record<string, string> = {
  project_health_check:  "Project Health",
  daily_cost_summary:    "Cost Summary",
  dna_freshness_check:   "DNA Freshness",
  obsidian_sync:         "Obsidian Sync",
  weekly_pattern_review: "Pattern Review",
};

const JOB_INTERVALS: Record<string, string> = {
  project_health_check:  "every 1h",
  daily_cost_summary:    "every 24h",
  dna_freshness_check:   "every 6h",
  obsidian_sync:         "every 24h",
  weekly_pattern_review: "every 7d",
};

const ALL_JOBS = Object.keys(JOB_LABELS);

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function statusBadge(status: "ok" | "warn" | "error" | "unknown") {
  const map = {
    ok:      "oc-badge oc-badge-ok",
    warn:    "oc-badge oc-badge-warn",
    error:   "oc-badge oc-badge-bad",
    unknown: "oc-badge",
  };
  return map[status] ?? "oc-badge";
}

export default function CronPage() {
  const [data, setData]   = useState<CronStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const r = await fetch("/api/cron");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 30_000);
    return () => clearInterval(id);
  }, []);

  // Derive last-run per job
  const lastRunPerJob: Record<string, { status: string; timestamp: string; summary: string }> = {};
  if (data?.jobs) {
    for (const entry of [...data.jobs].reverse()) {
      if (!lastRunPerJob[entry.job]) {
        lastRunPerJob[entry.job] = {
          status:    entry.status,
          timestamp: entry.timestamp,
          summary:   entry.summary,
        };
      }
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Hermes Cron</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            24/7 background agent — powered by hermes3 (free local model)
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <span
              className="flex items-center gap-2 text-sm font-medium px-3 py-1 rounded-full border"
              style={
                data.running
                  ? { color: "var(--ok)", borderColor: "var(--ok)", background: "rgba(36,224,138,.08)" }
                  : { color: "var(--muted)", borderColor: "rgba(255,255,255,.1)" }
              }
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  background: data.running ? "var(--ok)" : "var(--muted)",
                  boxShadow: data.running ? "0 0 6px var(--ok)" : "none",
                }}
              />
              {data.running ? "Running" : "Offline"}
            </span>
          )}
          <button
            onClick={fetchStatus}
            className="oc-btn-ghost text-xs px-3 py-1"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading && (
        <p className="text-sm" style={{ color: "var(--muted)" }}>Loading…</p>
      )}

      {error && (
        <div className="rounded-xl p-4 border text-sm" style={{ borderColor: "var(--bad)", color: "var(--bad)", background: "rgba(255,92,92,.08)" }}>
          {error}
        </div>
      )}

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Total Runs", value: data.summary.total, color: "var(--primary)" },
            { label: "OK",         value: data.summary.ok,    color: "var(--ok)" },
            { label: "Warnings",   value: data.summary.warn,  color: "var(--warn)" },
            { label: "Errors",     value: data.summary.error, color: "var(--bad)" },
          ].map((card) => (
            <div
              key={card.label}
              className="material-panel rounded-2xl p-4 text-center"
              style={{ borderColor: "rgba(255,255,255,.06)" }}
            >
              <p className="text-2xl font-bold" style={{ color: card.color }}>
                {card.value}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{card.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Job grid */}
      <div className="material-panel rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b" style={{ borderColor: "rgba(255,255,255,.06)" }}>
          <h2 className="text-sm font-semibold text-white">Scheduled Jobs</h2>
        </div>
        <table className="oc-table w-full">
          <thead>
            <tr>
              <th>Job</th>
              <th>Interval</th>
              <th>Last Status</th>
              <th>Last Run</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {ALL_JOBS.map((job) => {
              const last = lastRunPerJob[job];
              const status = (last?.status ?? "unknown") as "ok" | "warn" | "error" | "unknown";
              return (
                <tr key={job}>
                  <td className="font-medium text-white">{JOB_LABELS[job] ?? job}</td>
                  <td style={{ color: "var(--muted)" }}>{JOB_INTERVALS[job]}</td>
                  <td>
                    <span className={statusBadge(status)}>
                      {status}
                    </span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{fmtTime(last?.timestamp ?? null)}</td>
                  <td
                    className="text-xs max-w-xs truncate"
                    style={{ color: "var(--muted)" }}
                    title={last?.summary}
                  >
                    {last?.summary ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Recent log */}
      {data && data.jobs.length > 0 && (
        <div className="material-panel rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b" style={{ borderColor: "rgba(255,255,255,.06)" }}>
            <h2 className="text-sm font-semibold text-white">
              Recent Log
              <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
                (last {data.jobs.length} entries)
              </span>
            </h2>
          </div>
          <div className="oc-log overflow-auto max-h-96 rounded-b-2xl p-4 space-y-3">
            {data.jobs.slice(0, 30).map((entry, i) => (
              <div key={i} className="flex gap-3 text-xs leading-relaxed">
                <span style={{ color: "var(--muted)", whiteSpace: "nowrap", flexShrink: 0 }}>
                  {fmtTime(entry.timestamp)}
                </span>
                <span
                  className="font-medium"
                  style={{
                    color:
                      entry.status === "ok"    ? "var(--ok)"   :
                      entry.status === "warn"  ? "var(--warn)" :
                      entry.status === "error" ? "var(--bad)"  : "var(--muted)",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  [{entry.status.toUpperCase()}]
                </span>
                <span style={{ color: "var(--muted)", flexShrink: 0, fontWeight: 600 }}>
                  {JOB_LABELS[entry.job] ?? entry.job}
                </span>
                <span style={{ color: "#94a3b8" }}>{entry.summary}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Setup instructions when offline */}
      {data && !data.running && (
        <div
          className="rounded-2xl p-5 text-sm space-y-2 border"
          style={{ borderColor: "rgba(79,140,255,.3)", background: "rgba(79,140,255,.06)" }}
        >
          <p className="font-semibold text-white">Hermes Cron is not running</p>
          <p style={{ color: "var(--muted)" }}>Start it with:</p>
          <pre className="oc-log rounded-lg p-3 text-xs overflow-x-auto">
{`# In sdlc directory:
python agents/hermes_cron.py

# Or run a single job for testing:
python agents/hermes_cron.py --run-now health
python agents/hermes_cron.py --run-now sync`}
          </pre>
          <p style={{ color: "var(--muted)" }}>
            Requires Ollama with <code className="font-mono text-xs">hermes3</code> model, or any configured LLM provider.
          </p>
        </div>
      )}
    </div>
  );
}
