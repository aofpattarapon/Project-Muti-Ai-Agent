import Link from "next/link";
import { redirect } from "next/navigation";

import { listRecentAgentActivityLogs } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

export default async function ProjectLogsPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const logs = listRecentAgentActivityLogs(100);

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
            Agent Activity
          </p>
          <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
            Project-visible role logs
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
            Role output, approval states, and live sync entries written into the project database
            by the back-office and orchestration endpoints.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/workboard" className="oc-btn-ghost">
              Open workboard
            </Link>
            <a href="/api/project-logs/export?format=csv" className="oc-btn-ghost">
              Export CSV
            </a>
            <a href="/api/project-logs/export?format=json" className="oc-btn-ghost">
              Export JSON
            </a>
            {(session.role === "Admin" || session.role === "CEO" || session.role === "DevOps" || session.role === "QA") && (
              <a href="/api/audit/export" className="oc-btn-action">
                Export Audit CSV
              </a>
            )}
          </div>
        </section>

        <section className="material-panel overflow-hidden rounded-[2rem]">
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <h2 className="text-base font-semibold text-white">Latest role logs</h2>
            <span className="oc-badge">{logs.length} rows</span>
          </div>

          <div className="overflow-x-auto">
            <table className="oc-table">
              <thead>
                <tr>
                  {["Role", "Event", "Task", "Status", "Summary", "Artifact", "Target", "When"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="oc-td-primary">{log.roleKey}</td>
                    <td>{log.eventType}</td>
                    <td>{log.taskName}</td>
                    <td>{log.status}</td>
                    <td>{log.summary}</td>
                    <td>{log.artifactRef ?? "-"}</td>
                    <td>{log.channelTarget ?? "-"}</td>
                    <td>{new Date(log.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
