import { redirect } from "next/navigation";

import { listRecentAuditEvents } from "@/lib/audit/events";
import {
  countAgentActivityLogs,
  countAgentActivityLogsByStatus,
  countPendingApprovalItems,
  findProjectHotCache,
  listAgentRoleConfigs,
  listSystemConfigs,
} from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";
import { canViewAdminControls, roleSections } from "@/lib/rbac/permissions";

export default async function DashboardPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  const sections = roleSections[session.role];
  const recentEvents = listRecentAuditEvents(6);
  const agentConfigs = listAgentRoleConfigs();
  const systemConfigs = listSystemConfigs();
  const currentProject = findProjectHotCache("current_project");
  const activityCount = countAgentActivityLogs();
  const statusCounts = countAgentActivityLogsByStatus().slice(0, 6);
  const pendingApprovals = countPendingApprovalItems();
  const claudeDesignCount = agentConfigs.filter((config) => config.claudeDesignAccess).length;
  const harnessCount = agentConfigs.filter((config) => config.harnessEnabled).length;
  const hotCacheCount = agentConfigs.filter((config) => config.hotCacheEnabled).length;

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-rose-300">
                Pilot Dashboard
              </p>
              <h1 className="material-title text-4xl font-semibold tracking-tight">
                Welcome back, {session.name}
              </h1>
              <p className="material-muted max-w-2xl text-sm leading-7">
                You are signed in as{" "}
                <span className="font-semibold text-white">{session.role}</span>.
                This dashboard keeps the pilot intentionally small while proving authenticated
                access, role gating, and logout behavior.
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className="material-panel-soft rounded-[1.75rem] p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Agents</p>
            <p className="mt-3 text-3xl font-semibold text-white">{agentConfigs.length}</p>
            <p className="mt-2 text-sm text-slate-400">
              {claudeDesignCount} with Claude design, {harnessCount} harness-enabled
            </p>
          </article>
          <article className="material-panel-soft rounded-[1.75rem] p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Configs</p>
            <p className="mt-3 text-3xl font-semibold text-white">{systemConfigs.length}</p>
            <p className="mt-2 text-sm text-slate-400">
              System and orchestration controls tracked in back-office
            </p>
          </article>
          <article className="material-panel-soft rounded-[1.75rem] p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Project logs</p>
            <p className="mt-3 text-3xl font-semibold text-white">{activityCount}</p>
            <p className="mt-2 text-sm text-slate-400">
              {hotCacheCount} roles participating in hot cache sync
            </p>
          </article>
          <article className="material-panel-soft rounded-[1.75rem] p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Approvals</p>
            <p className="mt-3 text-lg font-semibold text-white">
              {pendingApprovals} waiting
            </p>
            <p className="mt-2 text-sm text-slate-400">
              {currentProject?.title ?? "No pinned project context"}
            </p>
          </article>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="material-panel rounded-[2rem] p-8">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                  Allowed Sections
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">
                  Role-aware access
                </h2>
              </div>
              <span className="oc-badge" style={{ color: "#60a5fa", background: "rgba(96,165,250,0.1)", borderColor: "rgba(96,165,250,0.25)", fontSize: "0.8rem", padding: "0.3rem 0.9rem" }}>
                {session.role}
              </span>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              {sections.map((section) => (
                <article
                  key={section}
                  className="material-panel-soft rounded-[1.5rem] p-5"
                >
                  <h3 className="text-base font-semibold text-white">{section}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    This pilot keeps the content simple while making the permitted area
                    obvious for the current role.
                  </p>
                </article>
              ))}
            </div>

            {canViewAdminControls(session.role) ? (
              <div className="mt-6 rounded-[1.5rem] border border-emerald-500/30 bg-emerald-500/10 p-5 text-sm text-emerald-100">
                Admin controls are visible because this role has the broadest access set in the
                pilot. Use the left menu to move between Overview, Workboard, Agents, Approvals,
                Project Logs, Project Memory, Back-office, Users, and Audit.
              </div>
            ) : (
              <div className="mt-6 rounded-[1.5rem] border border-amber-500/30 bg-amber-500/10 p-5 text-sm text-amber-100">
                Restricted administrative controls stay unavailable for this role.
              </div>
            )}
          </div>

          <aside className="material-panel rounded-[2rem] p-8">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              Audit Trail
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">Recent events</h2>
            <ul className="mt-6 space-y-4">
              {recentEvents.length === 0 ? (
                <li className="rounded-[1.5rem] border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  No events yet. Sign in or out to generate pilot audit activity.
                </li>
              ) : (
                recentEvents.map((event) => (
                  <li key={`${event.type}-${event.createdAt}`} className="material-panel-soft rounded-[1.5rem] p-4">
                    <p className="text-sm font-semibold text-white">{event.type}</p>
                    <p className="mt-1 text-sm text-slate-400">{event.detail}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                      {event.actor ? `${event.actor} • ` : ""}
                      {new Date(event.createdAt).toLocaleString()}
                    </p>
                  </li>
                ))
              )}
            </ul>
          </aside>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          <article className="material-panel rounded-[2rem] p-8">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              Current project
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">
              Hot cache snapshot
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-400">
              {currentProject?.summary ?? "No active project has been pinned into hot cache yet."}
            </p>
            <p className="mt-5 text-sm text-slate-500">
              Review details from the left menu in Project Memory, Project Logs, or Workboard.
            </p>
          </article>

          <article className="material-panel rounded-[2rem] p-8">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              Jira-ready board
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">
              Agent work states
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {statusCounts.map((status) => (
                <div
                  key={status.status}
                  className="material-panel-soft rounded-[1.5rem] p-4"
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    {status.status}
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {status.count}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-slate-400">
              Review the Workboard page for the read-only Jira-style flow, role handoffs, and
              pending approval queue.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}
