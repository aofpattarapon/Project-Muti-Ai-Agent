import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { countAuditEvents, listRecentAuditEvents } from "@/lib/audit/query";

const EVENT_TYPE_OPTIONS = [
  { value: "all", label: "All events" },
  { value: "login.success", label: "Login success" },
  { value: "login.failure", label: "Login failure" },
  { value: "login.blocked", label: "Login blocked" },
  { value: "login.inactive", label: "Login inactive" },
  { value: "logout", label: "Logout" },
  { value: "password_reset.requested", label: "Password reset requested" },
  { value: "password_reset.issued", label: "Password reset issued" },
  { value: "password_reset.completed", label: "Password reset completed" },
  { value: "password_reset.rejected", label: "Password reset rejected" },
  { value: "user.status_changed", label: "User status changed" },
  { value: "user.role_changed", label: "User role changed" },
  { value: "agent.task.paused", label: "Task paused (agent)" },
  { value: "agent.task.resumed.auto", label: "Task resumed (auto)" },
  { value: "agent.task.resumed.discord", label: "Task resumed (Discord)" },
  { value: "agent.task.resumed.web", label: "Task resumed (web operator)" },
];

const PAGE_SIZE = 10;

type AuditPageProps = {
  searchParams?: Promise<{
    type?: string;
    actor?: string;
    page?: string;
  }>;
};

function buildAuditQueryString(type: string, actor: string, page: number) {
  const params = new URLSearchParams();
  if (type && type !== "all") params.set("type", type);
  if (actor.trim()) params.set("actor", actor.trim());
  if (page > 1) params.set("page", String(page));
  return params.toString();
}

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const resolvedSearchParams = (await searchParams) ?? {};
  const selectedType = resolvedSearchParams.type?.trim() || "all";
  const actorFilter = resolvedSearchParams.actor?.trim() || "";
  const currentPage = Math.max(1, Number.parseInt(resolvedSearchParams.page ?? "1", 10) || 1);
  const offset = (currentPage - 1) * PAGE_SIZE;

  const filterSet = { type: selectedType, actor: actorFilter };
  const totalCount = countAuditEvents(filterSet);
  const events = listRecentAuditEvents({ ...filterSet, limit: PAGE_SIZE, offset });

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const previousPage = currentPage > 1 ? currentPage - 1 : null;
  const nextPage = currentPage < totalPages ? currentPage + 1 : null;

  const previousHref = previousPage
    ? `/audit?${buildAuditQueryString(selectedType, actorFilter, previousPage)}`
    : null;
  const nextHref = nextPage
    ? `/audit?${buildAuditQueryString(selectedType, actorFilter, nextPage)}`
    : null;

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
                Admin Audit
              </p>
              <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
                Authentication activity
              </h1>
              <p className="mt-3 text-sm leading-7 material-muted">
                Review recent login, logout, reset, and admin-change events recorded by the pilot app.
              </p>
            </div>
            <Link href="/dashboard" className="oc-btn-ghost shrink-0">
              Back to dashboard
            </Link>
          </div>
        </section>

        <section className="material-panel rounded-[2rem] p-6">
          <form className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <div>
              <label htmlFor="type" className="mb-2 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Event type
              </label>
              <select id="type" name="type" defaultValue={selectedType} className="oc-input">
                {EVENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="actor" className="mb-2 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Actor
              </label>
              <input
                id="actor"
                name="actor"
                type="text"
                defaultValue={actorFilter}
                placeholder="admin"
                className="oc-input"
              />
            </div>

            <div className="flex gap-3">
              <button type="submit" className="oc-btn-action">Apply filters</button>
              <Link href="/audit" className="oc-btn-ghost">Reset</Link>
            </div>
          </form>
        </section>

        <section className="material-panel overflow-hidden rounded-[2rem]">
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <h2 className="text-base font-semibold text-white">Recent events</h2>
            <span className="oc-badge">Page {currentPage} of {totalPages} · {totalCount} total</span>
          </div>

          {events.length === 0 ? (
            <div className="px-6 py-10 text-sm material-muted">
              No audit events matched the current filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="oc-table">
                <thead>
                  <tr>
                    {["Type", "Actor", "Detail", "Timestamp"].map((h) => <th key={h}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id} className="align-top">
                      <td>
                        <span className="oc-badge">{event.type}</span>
                      </td>
                      <td>{event.actor ?? "-"}</td>
                      <td className="oc-td-primary">{event.detail}</td>
                      <td>
                        {new Intl.DateTimeFormat("en-US", {
                          dateStyle: "medium",
                          timeStyle: "medium",
                        }).format(new Date(event.created_at))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-[rgba(255,255,255,0.06)] px-6 py-4">
            <div>
              {previousHref ? (
                <Link href={previousHref} className="oc-btn-ghost">Previous</Link>
              ) : (
                <span className="oc-btn-ghost" style={{ opacity: 0.3, pointerEvents: "none" }}>Previous</span>
              )}
            </div>
            <div>
              {nextHref ? (
                <Link href={nextHref} className="oc-btn-ghost">Next</Link>
              ) : (
                <span className="oc-btn-ghost" style={{ opacity: 0.3, pointerEvents: "none" }}>Next</span>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
