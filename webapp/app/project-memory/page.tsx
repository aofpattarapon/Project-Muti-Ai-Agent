import { redirect } from "next/navigation";

import { findSystemConfigByKey, listProjectHotCache } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

export default async function ProjectMemoryPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const entries = listProjectHotCache();
  const clearPolicy = findSystemConfigByKey("project.hot_cache_clear_policy");

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
            Hot Cache
          </p>
          <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
            Project memory
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
            Shared active-project memory for all agents. Keep this cache until a confirmed new
            project starts. If an agent is unsure whether the task is a new project, it should ask
            first instead of clearing memory automatically.
          </p>
          <p className="mt-4 text-sm material-muted">
            Clear policy:{" "}
            <span className="font-medium text-slate-200">
              {clearPolicy?.value ?? "not-configured"}
            </span>
          </p>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <article className="material-panel rounded-[2rem] p-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Backend-managed cache
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Read-only active context</h2>
            <div className="mt-4 space-y-4 text-sm leading-7 material-muted">
              <p>
                Hot cache is no longer editable from the UI. It is updated by orchestration sync or
                admin automation only, so agents share a stable active-project memory without manual
                drift.
              </p>
              <p>
                Agents should reuse this memory when the project is clearly the same, and only ask
                whether to clear it when they suspect a new project has started.
              </p>
            </div>
          </article>

          <article className="space-y-4">
            {entries.map((entry) => (
              <section key={entry.cacheKey} className="material-panel rounded-[2rem] p-8">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-2xl font-semibold text-white">{entry.title}</h2>
                  <span className="oc-badge">{entry.cacheKey}</span>
                </div>
                <p className="mt-4 text-sm leading-7 material-muted">{entry.summary}</p>
                <dl className="mt-6 grid gap-4 sm:grid-cols-2">
                  {[
                    { label: "Scope",       value: entry.scope },
                    { label: "Status",      value: entry.status },
                    { label: "Source role", value: entry.sourceRole },
                    { label: "Updated",     value: new Date(entry.updatedAt).toLocaleString() },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</dt>
                      <dd className="mt-2 text-sm text-slate-200">{value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </article>
        </section>
      </div>
    </main>
  );
}
