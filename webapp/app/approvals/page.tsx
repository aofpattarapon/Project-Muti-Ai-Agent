import Link from "next/link";
import { redirect } from "next/navigation";

import { listApprovalItems } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

export default async function ApprovalsPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const pending = listApprovalItems("waiting_approval");
  const history = listApprovalItems().filter((item) => item.status !== "waiting_approval").slice(0, 20);

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
            Approval Center
          </p>
          <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
            Pending approvals and rework
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
            Items in <span className="font-medium text-slate-300">waiting_approval</span> do not continue
            automatically. They stay paused until an approval decision is made in the system or
            sent back through the Discord/OpenClaw runtime approval wiring.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/workboard" className="oc-btn-ghost">
              Open workboard
            </Link>
            <a href="/api/workboard/export?format=json" className="oc-btn-ghost">
              Export approval context
            </a>
          </div>
        </section>

        <section className="space-y-4">
          {pending.length === 0 ? (
            <article className="material-panel rounded-[2rem] p-8">
              <p className="text-sm material-muted">
                No items are waiting for approval right now.
              </p>
            </article>
          ) : (
            pending.map((item) => (
              <article key={item.id} className="material-panel rounded-[2rem] p-8">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-2xl font-semibold text-white">{item.taskName}</h2>
                  <span className="oc-badge warn-text" style={{ background: "rgba(245,158,11,0.12)", borderColor: "rgba(245,158,11,0.28)", color: "var(--warn)" }}>
                    {item.status}
                  </span>
                  <span className="oc-badge">{item.roleKey}</span>
                </div>
                <p className="mt-4 text-sm leading-7 material-muted">{item.summary}</p>

                <dl className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    { label: "Requested by", value: item.requestedBy },
                    { label: "Artifact", value: item.artifactRef ?? "-" },
                    { label: "Output", value: item.outputSummary ?? "-" },
                    { label: "Channel", value: item.channelTarget ?? "-" },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</dt>
                      <dd className="mt-2 text-sm text-slate-200">{value}</dd>
                    </div>
                  ))}
                </dl>

                <form
                  action={`/api/admin/approvals/${item.id}/decision`}
                  method="post"
                  className="mt-6 grid gap-4 xl:grid-cols-[0.8fr_1.2fr_auto]"
                >
                  <input type="hidden" name="role_key" value={item.roleKey} />
                  <input type="hidden" name="task_name" value={item.taskName} />
                  <select name="decision" defaultValue="approved" className="oc-input">
                    <option value="approved">Approve</option>
                    <option value="rejected">Reject</option>
                    <option value="rework_requested">Request rework</option>
                  </select>
                  <textarea
                    name="decision_note"
                    placeholder="If rejected or rework is needed, explain what should change."
                    className="oc-input min-h-28"
                  />
                  <button type="submit" className="oc-btn-action">
                    Submit decision
                  </button>
                </form>
              </article>
            ))
          )}
        </section>

        <section className="material-panel rounded-[2rem] p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Decision history
          </p>
          <div className="mt-6 overflow-x-auto">
            <table className="oc-table">
              <thead>
                <tr>
                  {["Role", "Task", "Decision", "Note", "Approver", "When"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td className="oc-td-primary">{item.roleKey}</td>
                    <td>{item.taskName}</td>
                    <td>{item.status}</td>
                    <td>{item.decisionNote ?? "-"}</td>
                    <td>{item.approver ?? "-"}</td>
                    <td>{new Date(item.updatedAt).toLocaleString()}</td>
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
