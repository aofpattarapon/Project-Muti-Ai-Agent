import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { listSystemConfigs } from "@/lib/agents/query";

const SYSTEM_CONFIG_CATEGORIES = [
  { key: "orchestration", label: "Orchestration", description: "Flow routing, stage movement, and task coordination behavior." },
  { key: "approvals",     label: "Approvals",     description: "Human approval gates, rework policy, and decision handling." },
  { key: "reporting",     label: "Reporting",     description: "Report-Agent, Report-Output, and project visibility settings." },
  { key: "models",        label: "Models",        description: "Primary, escalation, and design provider preferences." },
  { key: "harness",       label: "Harness",       description: "Agent contract, discipline, and credit-saving workflow controls." },
  { key: "sync",          label: "Sync",          description: "OpenClaw, Discord, and runtime token-based integration points." },
  { key: "project",       label: "Project Memory",description: "Hot cache and active project memory lifecycle." },
  { key: "security",      label: "Security",      description: "Secrets, access, and runtime permission boundaries." },
  { key: "test",          label: "Test",          description: "Pilot mode and controlled validation settings." },
] as const;

export default async function BackofficePage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const systemConfigs = listSystemConfigs();
  const groupedConfigs = SYSTEM_CONFIG_CATEGORIES.map((category) => ({
    category,
    items: systemConfigs.filter((config) => config.category === category.key),
  })).filter((group) => group.items.length > 0);
  const syncEnabled = systemConfigs.find((c) => c.configKey === "reporting.agent_sync_ingest_enabled");
  const syncToken   = systemConfigs.find((c) => c.configKey === "reporting.agent_sync_ingest_token");

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
                Back-office
              </p>
              <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
                System configuration center
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
                Add, edit, and delete project-level orchestration, reporting, model, approval, and
                harness configuration values from a single administrative surface.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard" className="oc-btn-ghost">Back to dashboard</Link>
              <Link href="/agents" className="oc-btn-ghost">Open agent control</Link>
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <article className="material-panel rounded-[2rem] p-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              New config
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Add system config</h2>

            <form action="/api/admin/system-configs/create" method="post" className="mt-6 grid gap-4 lg:grid-cols-2">
              <input name="config_key" placeholder="config.key" className="oc-input" />
              <select name="category" defaultValue="orchestration" className="oc-input">
                {SYSTEM_CONFIG_CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
              <input name="value" placeholder="value" className="oc-input lg:col-span-2" />
              <textarea name="description" placeholder="Description" className="oc-input min-h-28 lg:col-span-2" />
              <button type="submit" className="oc-btn-action lg:col-span-2">Create config</button>
            </form>
          </article>

          <article className="material-panel rounded-[2rem] p-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Phase 9.5 Sync
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Project log ingest</h2>
            <div className="mt-4 space-y-4 text-sm leading-7 material-muted">
              <p>
                OpenClaw or any orchestration worker can now push role output into the project at{" "}
                <span className="font-mono text-xs text-slate-300">POST /api/agent-activity/ingest</span>.
              </p>
              <p>
                Enabled: <span className="font-medium text-slate-200">{syncEnabled?.value ?? "false"}</span>
              </p>
              <p>
                Token:{" "}
                <span className="font-mono text-xs text-slate-300">
                  {syncToken?.value ?? "not-configured"}
                </span>
              </p>
            </div>
          </article>
        </section>

        <section className="material-panel rounded-[2rem] p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Config registry
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Current config registry</h2>
          <p className="mt-3 text-sm material-muted">
            Each category acts like a sub-function of the back-office so orchestration, approvals,
            reporting, models, sync, project memory, and harness settings stay separated.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {SYSTEM_CONFIG_CATEGORIES.map((category) => (
            <article key={category.key} className="material-panel-soft rounded-[1.5rem] p-5">
              <span className="oc-badge">{category.key}</span>
              <h3 className="mt-3 text-lg font-semibold text-white">{category.label}</h3>
              <p className="mt-2 text-sm leading-6 material-muted">{category.description}</p>
            </article>
          ))}
        </section>

        <section className="space-y-6">
          {groupedConfigs.map((group) => (
            <div key={group.category.key} className="space-y-4">
              <div className="material-panel-soft rounded-[1.5rem] px-6 py-5">
                <span className="oc-badge">{group.category.key}</span>
                <h3 className="mt-3 text-xl font-semibold text-white">{group.category.label}</h3>
                <p className="mt-2 text-sm material-muted">{group.category.description}</p>
              </div>

              <div className="grid gap-6">
                {group.items.map((config) => (
                  <article key={config.id} className="material-panel rounded-[2rem] p-8">
                    <div className="flex flex-wrap items-center gap-3">
                      <h2 className="text-2xl font-semibold text-white">{config.configKey}</h2>
                      <span className="oc-badge">{config.category}</span>
                    </div>
                    <p className="mt-3 text-sm leading-7 material-muted">{config.description}</p>

                    <form
                      action={`/api/admin/system-configs/${config.id}/update`}
                      method="post"
                      className="mt-6 grid gap-4 lg:grid-cols-2"
                    >
                      <input name="config_key" defaultValue={config.configKey} className="oc-input" />
                      <select name="category" defaultValue={config.category} className="oc-input">
                        {SYSTEM_CONFIG_CATEGORIES.map((c) => (
                          <option key={c.key} value={c.key}>{c.label}</option>
                        ))}
                      </select>
                      <input name="value" defaultValue={config.value} className="oc-input lg:col-span-2" />
                      <textarea name="description" defaultValue={config.description} className="oc-input min-h-28 lg:col-span-2" />
                      <button type="submit" className="oc-btn-action lg:col-span-2">Save config</button>
                    </form>

                    <form action={`/api/admin/system-configs/${config.id}/delete`} method="post" className="mt-3">
                      <button type="submit" className="oc-btn-danger">Delete config</button>
                    </form>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
