import { redirect } from "next/navigation";

import { listAgentRoleConfigs } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

const MODEL_OPTIONS = [
  "anthropic/claude-haiku-4-5",
  "anthropic/claude-sonnet-4-5",
  "anthropic/claude-opus-4-7",
  "openai-codex/gpt-5.5",
];

const HARNESS_PROFILE_OPTIONS = [
  "orchestrator-lite",
  "planning-harness",
  "requirements-harness",
  "architecture-harness",
  "design-harness",
  "execution-harness",
  "validation-harness",
  "release-harness",
  "custom-harness",
];

const OUTPUT_MODE_OPTIONS = ["discord-and-project", "project-only", "discord-only"];

const SKILL_OPTIONS = [
  "orchestration", "approval-gates", "dynamic-routing", "planning", "scope-control",
  "dependency-mapping", "requirements", "acceptance-criteria", "edge-cases",
  "architecture", "api-design", "security-review", "ux-flows", "ui-states",
  "claude-design", "implementation", "testing", "codex-execution", "validation",
  "defect-triage", "quality-gate", "deploy", "runtime", "rollback", "custom",
];

function SkillMultiSelect({ selected = [] }: { selected?: string[] }) {
  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.09)] bg-[rgba(255,255,255,0.03)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm material-muted">Select one or more skills for this role.</p>
        <span className="oc-badge">{selected.length} selected</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {SKILL_OPTIONS.map((skill) => (
          <label
            key={skill}
            className="flex items-center gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] px-3 py-2.5 text-sm text-slate-300 transition hover:border-[rgba(255,255,255,0.12)] cursor-pointer"
          >
            <input
              type="checkbox"
              name="skill_tags"
              value={skill}
              defaultChecked={selected.includes(skill)}
              className="accent-[#4f8cff]"
            />
            <span>{skill}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

export default async function AgentsPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const configs = listAgentRoleConfigs();

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
            Agent Control
          </p>
          <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
            Multi-agent role control
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
            Configure routing models, Discord wiring, skill packs, Claude design access,
            harness policy, hot cache participation, and reporting rules for each SDLC role.
          </p>
        </section>

        <section className="material-panel rounded-[2rem] p-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            New role config
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Add agent role</h2>

          <form action="/api/admin/agent-configs/create" method="post" className="mt-6 grid gap-4 lg:grid-cols-2">
            <input name="role_key" placeholder="role_key" className="oc-input" />
            <input name="display_name" placeholder="Display name" className="oc-input" />
            <select name="primary_model" defaultValue="anthropic/claude-haiku-4-5" className="oc-input">
              {MODEL_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <select name="escalation_model" defaultValue="anthropic/claude-sonnet-4-5" className="oc-input">
              {MODEL_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <input name="discord_bot_token" placeholder="Discord token (optional)" className="oc-input" />
            <input name="discord_channel_ids" placeholder="channel-a,channel-b,report-output" className="oc-input" />
            <select name="harness_profile" defaultValue="planning-harness" className="oc-input">
              {HARNESS_PROFILE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <select name="output_mode" defaultValue="discord-and-project" className="oc-input">
              {OUTPUT_MODE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <textarea name="responsibility" placeholder="Responsibility" className="oc-input min-h-28 lg:col-span-2" />
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Skill config</p>
              <SkillMultiSelect />
            </div>
            <textarea name="working_rules" placeholder="Working rules / agent contract" className="oc-input min-h-32" />
            <textarea name="logic_summary" placeholder="Logic summary" className="oc-input min-h-28" />
            <textarea name="reporting_summary" placeholder="Reporting summary" className="oc-input min-h-28" />
            <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" name="claude_design_access" value="true" className="accent-[#4f8cff]" /> Claude design access
            </label>
            <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" name="harness_enabled" value="true" defaultChecked className="accent-[#4f8cff]" /> Harness enabled
            </label>
            <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" name="hot_cache_enabled" value="true" defaultChecked className="accent-[#4f8cff]" /> Hot cache enabled
            </label>
            <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" name="is_active" value="true" defaultChecked className="accent-[#4f8cff]" /> Active
            </label>
            <button type="submit" className="oc-btn-action lg:col-span-2">Create role config</button>
          </form>
        </section>

        <section className="grid gap-6">
          {configs.map((config) => (
            <article key={config.roleKey} className="material-panel rounded-[2rem] p-8">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-2xl font-semibold text-white">{config.displayName}</h2>
                    <span className="oc-badge">{config.roleKey}</span>
                    <span className={`oc-badge ${config.isActive ? "ok-text" : "bad-text"}`}
                      style={config.isActive
                        ? { background: "rgba(36,224,138,0.1)", borderColor: "rgba(36,224,138,0.25)" }
                        : { background: "rgba(255,92,92,0.1)", borderColor: "rgba(255,92,92,0.25)" }
                      }
                    >
                      {config.isActive ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">{config.responsibility}</p>
                </div>
                <div className="grid gap-2 text-sm text-slate-400 shrink-0">
                  <p><span className="font-medium text-slate-200">Primary:</span> {config.primaryModel}</p>
                  <p><span className="font-medium text-slate-200">Escalation:</span> {config.escalationModel}</p>
                  <p><span className="font-medium text-slate-200">Discord:</span> {config.discordChannelIds || "Not configured"}</p>
                  <p><span className="font-medium text-slate-200">Skills:</span> {config.skillTags.join(", ") || "None"}</p>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                {[
                  { label: "Logic summary",    value: config.logicSummary },
                  { label: "Reporting summary", value: config.reportingSummary },
                  { label: "Working rules",     value: config.workingRules },
                ].map(({ label, value }) => (
                  <div key={label} className="material-panel-soft rounded-[1.5rem] p-5">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
                    <p className="mt-3 text-sm leading-7 text-slate-300">{value}</p>
                  </div>
                ))}
              </div>

              <form action={`/api/admin/agent-configs/${config.roleKey}/update`} method="post" className="mt-6 grid gap-4 lg:grid-cols-2">
                <input name="display_name" defaultValue={config.displayName} className="oc-input" />
                <textarea name="responsibility" defaultValue={config.responsibility} className="oc-input min-h-28" />
                <select name="primary_model" defaultValue={config.primaryModel} className="oc-input">
                  {MODEL_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                <select name="escalation_model" defaultValue={config.escalationModel} className="oc-input">
                  {MODEL_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                <input name="discord_bot_token" defaultValue={config.discordBotToken} placeholder="Discord token" className="oc-input" />
                <input name="discord_channel_ids" defaultValue={config.discordChannelIds} placeholder="Channel ids" className="oc-input" />
                <select name="harness_profile" defaultValue={config.harnessProfile} className="oc-input">
                  {HARNESS_PROFILE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                <select name="output_mode" defaultValue={config.outputMode} className="oc-input">
                  {OUTPUT_MODE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                <div>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Skill config</p>
                  <SkillMultiSelect selected={config.skillTags} />
                </div>
                <textarea name="working_rules" defaultValue={config.workingRules} className="oc-input min-h-32" />
                <textarea name="logic_summary" defaultValue={config.logicSummary} className="oc-input min-h-28" />
                <textarea name="reporting_summary" defaultValue={config.reportingSummary} className="oc-input min-h-28" />
                <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" name="claude_design_access" value="true" defaultChecked={config.claudeDesignAccess} className="accent-[#4f8cff]" /> Claude design access
                </label>
                <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" name="harness_enabled" value="true" defaultChecked={config.harnessEnabled} className="accent-[#4f8cff]" /> Harness enabled
                </label>
                <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" name="hot_cache_enabled" value="true" defaultChecked={config.hotCacheEnabled} className="accent-[#4f8cff]" /> Hot cache enabled
                </label>
                <label className="flex items-center gap-3 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" name="is_active" value="true" defaultChecked={config.isActive} className="accent-[#4f8cff]" /> Active
                </label>
                <div className="flex flex-wrap gap-3 lg:col-span-2">
                  <button type="submit" className="oc-btn-action">Save role config</button>
                </div>
              </form>

              <form action={`/api/admin/agent-configs/${config.roleKey}/delete`} method="post" className="mt-3">
                <button type="submit" className="oc-btn-danger">Delete role config</button>
              </form>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
