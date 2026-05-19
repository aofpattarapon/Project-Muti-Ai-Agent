import Link from "next/link";
import { redirect } from "next/navigation";

import {
  countPendingApprovalItems,
  findProjectHotCache,
  listApprovalItems,
  listRecentAgentActivityLogs,
} from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";
import { ApprovalActions, AutoRefresh, PipelineHeader } from "./_components/WorkboardClient";

const PIPELINE_ORDER = ["ceo", "pm", "ba", "sa", "uxui", "dev", "frontend", "backend", "qa", "devops"];

const ROLE_META: Record<string, { label: string; emoji: string; color: string }> = {
  ceo:      { label: "CEO",     emoji: "👑", color: "border-l-yellow-400" },
  pm:       { label: "PM",      emoji: "📋", color: "border-l-blue-400" },
  ba:       { label: "BA",      emoji: "📊", color: "border-l-cyan-400" },
  sa:       { label: "SA",      emoji: "🏗️", color: "border-l-indigo-400" },
  uxui:     { label: "UX/UI",   emoji: "🎨", color: "border-l-pink-400" },
  frontend: { label: "Frontend",emoji: "💻", color: "border-l-violet-400" },
  backend:  { label: "Backend", emoji: "⚙️", color: "border-l-violet-400" },
  dev:      { label: "DEV",     emoji: "💻", color: "border-l-violet-400" },
  qa:       { label: "QA",      emoji: "🧪", color: "border-l-green-400" },
  devops:   { label: "DevOps",  emoji: "🚀", color: "border-l-orange-400" },
};

const STATUS_BADGE: Record<string, string> = {
  in_progress:      "bg-blue-500/20 text-blue-300",
  waiting_approval: "bg-amber-500/20 text-amber-300",
  approved:         "bg-emerald-500/20 text-emerald-300",
  rework_requested: "bg-orange-500/20 text-orange-300",
  rejected:         "bg-red-500/20 text-red-300",
  completed:        "bg-violet-500/20 text-violet-300",
  blocked:          "bg-red-700/20 text-red-400",
};

function buildProjectCards() {
  const logs = listRecentAgentActivityLogs(300);
  const allApprovals = listApprovalItems();

  // Group by taskName → derive project context
  const taskMap = new Map<string, {
    taskName: string;
    latestStatus: string;
    latestRoleKey: string;
    latestSummary: string;
    artifactRef: string | null;
    channelTarget: string | null;
    updatedAt: string;
    history: typeof logs;
    pendingApproval: (typeof allApprovals)[0] | null;
  }>();

  for (const log of logs) {
    const existing = taskMap.get(log.taskName);
    if (!existing) {
      const pa = allApprovals.find(
        (a) => a.taskName === log.taskName && a.status === "waiting_approval"
      ) ?? null;
      taskMap.set(log.taskName, {
        taskName: log.taskName,
        latestStatus: log.status,
        latestRoleKey: log.roleKey,
        latestSummary: log.summary,
        artifactRef: log.artifactRef,
        channelTarget: log.channelTarget,
        updatedAt: log.createdAt,
        history: [log],
        pendingApproval: pa,
      });
    } else {
      existing.history.push(log);
    }
  }

  const tasks = Array.from(taskMap.values()).sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );

  // Group by role for pipeline lanes
  const lanes = PIPELINE_ORDER.map((role) => ({
    role,
    meta: ROLE_META[role] ?? { label: role.toUpperCase(), emoji: "🤖", color: "border-l-slate-400" },
    items: tasks.filter(
      (t) => t.latestRoleKey === role || t.latestRoleKey === role
    ),
  })).filter((l) => l.items.length > 0);

  return { tasks, lanes, logs };
}

export default async function WorkboardPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (session.role !== "Admin") redirect("/dashboard");

  const { tasks, lanes, logs } = buildProjectCards();
  const pendingApprovals = listApprovalItems("waiting_approval");
  const currentProject = findProjectHotCache("current_project");
  const waitingCount = countPendingApprovalItems();

  // Detect current stage from most recent active task
  const currentRole = logs.find((l) => l.status === "in_progress" || l.status === "waiting_approval")?.roleKey;

  return (
    <main className="px-4 py-6 text-slate-100 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-[1600px] space-y-6">

        {/* ── Header ── */}
        <section className="material-panel rounded-[2rem] px-8 py-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-400">
                SDLC Pipeline Board
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
                {currentProject?.title ?? "Multi-AI Agent Workboard"}
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                {currentProject?.summary ?? "Jira-style view of the full agent pipeline — auto-synced with Discord."}
              </p>
              <div className="mt-4">
                <AutoRefresh intervalMs={12000} />
              </div>
            </div>
            <div className="flex flex-wrap gap-3 lg:shrink-0">
              <a href="/api/workboard/export?format=csv"
                className="material-chip rounded-2xl px-4 py-2 text-sm font-medium text-violet-200 hover:border-violet-400 transition">
                Export CSV
              </a>
              <a href="/api/workboard/export?format=json"
                className="material-chip rounded-2xl px-4 py-2 text-sm font-medium text-sky-200 hover:border-sky-400 transition">
                Export JSON
              </a>
              <Link href="/approvals"
                className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-300 hover:bg-amber-500/20 transition">
                🔔 Approvals ({waitingCount})
              </Link>
            </div>
          </div>

          {/* Pipeline progress bar */}
          <div className="mt-6">
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              Current Stage
            </p>
            <PipelineHeader currentRole={currentRole} />
          </div>
        </section>

        {/* ── Stats ── */}
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: "Active project",    value: currentProject?.title ?? "None",   sub: currentProject?.status ?? "idle" },
            { label: "Tasks tracked",     value: String(tasks.length),              sub: "across all pipeline stages" },
            { label: "Waiting approval",  value: String(waitingCount),              sub: "paused for human decision" },
            { label: "Events ingested",   value: String(logs.length),               sub: "bot activity in last 300 logs" },
          ].map((stat) => (
            <article key={stat.label} className="material-panel-soft rounded-[1.75rem] p-6">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{stat.label}</p>
              <p className="mt-3 truncate text-2xl font-bold text-white">{stat.value}</p>
              <p className="mt-1 text-xs text-slate-400">{stat.sub}</p>
            </article>
          ))}
        </section>

        {/* ── Pipeline Kanban Board ── */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500">Pipeline lanes</p>
              <h2 className="mt-1 text-xl font-bold text-white">CEO → PM → BA → SA → UX/UI → DEV → QA → DevOps</h2>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {lanes.map((lane) => (
              <section key={lane.role} className="material-panel rounded-[1.75rem] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{lane.meta.emoji}</span>
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-200">
                      {lane.meta.label}
                    </h3>
                  </div>
                  <span className="rounded-full bg-white/8 px-2.5 py-0.5 text-xs font-semibold text-slate-300">
                    {lane.items.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {lane.items.map((task) => (
                    <article
                      key={task.taskName}
                      className={`material-panel-soft rounded-[1.25rem] border-l-4 p-4 ${lane.meta.color}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-semibold leading-snug text-white">
                          {task.taskName}
                        </h4>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS_BADGE[task.latestStatus] ?? "bg-slate-500/20 text-slate-300"}`}>
                          {task.latestStatus.replace(/_/g, " ")}
                        </span>
                      </div>

                      <p className="mt-2 text-xs leading-5 text-slate-400 line-clamp-3">
                        {task.latestSummary}
                      </p>

                      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                        {task.channelTarget && (
                          <span>📡 {task.channelTarget}</span>
                        )}
                        {task.artifactRef && (
                          <span>📎 {task.artifactRef}</span>
                        )}
                        <span>🕐 {new Date(task.updatedAt).toLocaleTimeString()}</span>
                      </div>

                      {/* Trail */}
                      <div className="mt-3 border-t border-white/5 pt-3">
                        <p className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Trail</p>
                        <ul className="space-y-1">
                          {task.history.slice(0, 3).map((log) => (
                            <li key={log.id} className="flex items-center gap-1.5 text-xs text-slate-500">
                              <span className="font-semibold text-slate-400">{log.roleKey}</span>
                              <span>→</span>
                              <span>{log.eventType}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Approve buttons if waiting */}
                      {task.pendingApproval && (
                        <ApprovalActions
                          id={task.pendingApproval.id}
                          roleKey={task.pendingApproval.roleKey}
                          taskName={task.pendingApproval.taskName}
                        />
                      )}
                    </article>
                  ))}
                </div>
              </section>
            ))}

            {lanes.length === 0 && (
              <div className="col-span-4 py-20 text-center text-slate-500">
                <p className="text-4xl">🤖</p>
                <p className="mt-4 text-lg font-medium text-slate-400">No agent activity yet</p>
                <p className="mt-2 text-sm">Start a project in Discord: <code className="rounded bg-white/8 px-2 py-0.5">!new ProjectName | description</code></p>
              </div>
            )}
          </div>
        </section>

        {/* ── Bottom: Pending approvals + Activity feed ── */}
        <section className="grid gap-6 lg:grid-cols-2">

          {/* Pending approvals */}
          <article className="material-panel rounded-[2rem] p-8">
            <div className="flex items-center justify-between mb-5">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">Needs action</p>
                <h2 className="mt-1 text-xl font-bold text-white">Approval queue</h2>
              </div>
              <Link href="/approvals"
                className="material-chip rounded-2xl px-3 py-1.5 text-xs font-medium text-amber-200 hover:border-amber-400 transition">
                View all
              </Link>
            </div>
            <div className="space-y-4">
              {pendingApprovals.length === 0 ? (
                <p className="text-sm text-slate-500">✅ Nothing waiting for approval.</p>
              ) : pendingApprovals.slice(0, 6).map((item) => (
                <article key={item.id} className="material-panel-soft rounded-[1.25rem] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">{item.taskName}</h3>
                    <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-300">
                      {item.roleKey}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-400">{item.summary}</p>
                  <ApprovalActions id={item.id} roleKey={item.roleKey} taskName={item.taskName} />
                </article>
              ))}
            </div>
          </article>

          {/* Activity feed */}
          <article className="material-panel rounded-[2rem] p-8 overflow-hidden">
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest text-slate-500">Live feed</p>
              <h2 className="mt-1 text-xl font-bold text-white">Agent activity stream</h2>
            </div>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {logs.slice(0, 25).map((log) => (
                <article key={log.id} className="material-panel-soft rounded-[1.25rem] p-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="rounded-full bg-white/8 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-300">
                      {log.roleKey}
                    </span>
                    <span className="text-xs font-medium text-white">{log.taskName}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[log.status] ?? "bg-slate-500/20 text-slate-300"}`}>
                      {log.status.replace(/_/g, " ")}
                    </span>
                    <span className="ml-auto text-[10px] text-slate-600">
                      {new Date(log.createdAt).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-400 line-clamp-2">{log.summary}</p>
                </article>
              ))}
            </div>
          </article>

        </section>
      </div>
    </main>
  );
}
