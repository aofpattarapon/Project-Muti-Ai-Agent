"use client";

import { useState, useCallback } from "react";
import type { SettingsSnapshot } from "@/lib/config/env-manager";

type Tab = "discord" | "llm" | "pipeline" | "trading" | "obsidian" | "webapp";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "discord",  label: "Discord / Bots",  icon: "🤖" },
  { id: "llm",      label: "LLM Providers",   icon: "🧠" },
  { id: "pipeline", label: "Pipeline",         icon: "⚙️" },
  { id: "trading",  label: "Trading Bot",      icon: "📈" },
  { id: "obsidian", label: "Obsidian",         icon: "🗂️" },
  { id: "webapp",   label: "Web App / System", icon: "🌐" },
];

type SaveState = "idle" | "saving" | "ok" | "error";
type TestState = "idle" | "testing" | "ok" | "error";

function StatusBadge({ state, message }: { state: SaveState | TestState; message?: string }) {
  if (state === "idle") return null;
  const cls = state === "ok" ? "oc-badge-ok" : state === "error" ? "oc-badge-bad" : "oc-badge-warn";
  const label = state === "saving" || state === "testing" ? "..." : (message ?? (state === "ok" ? "Saved" : "Error"));
  return <span className={`oc-badge ${cls} ml-2 text-xs`}>{label}</span>;
}

function FieldRow({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

type TestButtonProps = { label: string; onTest: () => void; testState: TestState; testMsg?: string };
function TestButton({ label, onTest, testState, testMsg }: TestButtonProps) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onTest}
        disabled={testState === "testing"}
        className="oc-btn-ghost text-xs px-3 py-1.5"
      >
        {testState === "testing" ? "Testing…" : `Test ${label}`}
      </button>
      {testState !== "idle" && (
        <span className={`text-xs font-medium ${testState === "ok" ? "text-emerald-400" : testState === "error" ? "text-red-400" : "text-slate-400"}`}>
          {testMsg}
        </span>
      )}
    </div>
  );
}

async function callTest(target: string, params: Record<string, string>) {
  const res = await fetch("/api/admin/settings/test", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ target, params }),
  });
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

async function callSave(group: string, values: Record<string, string>) {
  const res = await fetch("/api/admin/settings/save", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ group, values }),
  });
  return res.json() as Promise<{ ok: boolean; error?: string }>;
}

// ─── Discord Tab ──────────────────────────────────────────────────────────────

function DiscordTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["discord"];
  onChange: (k: keyof SettingsSnapshot["discord"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  const [discordTest, setDiscordTest] = useState<TestState>("idle");
  const [discordMsg, setDiscordMsg] = useState("");

  const tokens: [keyof SettingsSnapshot["discord"], string][] = [
    ["CEO_DISCORD_TOKEN", "CEO Bot"],
    ["PM_DISCORD_TOKEN", "PM Bot"],
    ["BA_DISCORD_TOKEN", "BA Bot"],
    ["SA_DISCORD_TOKEN", "SA Bot"],
    ["UXUI_DISCORD_TOKEN", "UX/UI Bot"],
    ["FRONTEND_DISCORD_TOKEN", "Frontend Bot"],
    ["BACKEND_DISCORD_TOKEN", "Backend Bot"],
    ["QA_DISCORD_TOKEN", "QA Bot"],
    ["DEVOPS_DISCORD_TOKEN", "DevOps Bot"],
  ];

  async function handleTestDiscord() {
    setDiscordTest("testing");
    setDiscordMsg("Connecting...");
    const r = await callTest("discord", { token: data.CEO_DISCORD_TOKEN, guildId: data.DISCORD_GUILD_ID });
    setDiscordTest(r.ok ? "ok" : "error");
    setDiscordMsg(r.message);
  }

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">Bot Tokens</h3>
        <p className="text-xs text-slate-500 mb-4">Stored in SDLC .env — requires bot restart to take effect.</p>
        <div className="grid gap-4 lg:grid-cols-2">
          {tokens.map(([key, label]) => (
            <FieldRow key={key} label={label}>
              <input
                type="password"
                value={data[key]}
                onChange={(e) => onChange(key, e.target.value)}
                placeholder="Discord bot token"
                className="oc-input font-mono text-xs"
                autoComplete="off"
              />
            </FieldRow>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Server IDs</h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldRow label="Guild ID" hint="Discord server (guild) ID">
            <input
              type="text"
              value={data.DISCORD_GUILD_ID}
              onChange={(e) => onChange("DISCORD_GUILD_ID", e.target.value)}
              className="oc-input font-mono"
            />
          </FieldRow>
          <FieldRow label="Approval Channel ID" hint="Channel where approval messages are posted">
            <input
              type="text"
              value={data.DISCORD_APPROVAL_CHANNEL_ID}
              onChange={(e) => onChange("DISCORD_APPROVAL_CHANNEL_ID", e.target.value)}
              className="oc-input font-mono"
            />
          </FieldRow>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save Discord Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
        <TestButton label="Discord" onTest={handleTestDiscord} testState={discordTest} testMsg={discordMsg} />
      </div>
    </div>
  );
}

// ─── LLM Tab ─────────────────────────────────────────────────────────────────

function LlmTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["llm"];
  onChange: (k: keyof SettingsSnapshot["llm"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  const [anthTest, setAnthTest] = useState<TestState>("idle");
  const [anthMsg, setAnthMsg] = useState("");
  const [openaiTest, setOpenaiTest] = useState<TestState>("idle");
  const [openaiMsg, setOpenaiMsg] = useState("");
  const [groqTest, setGroqTest] = useState<TestState>("idle");
  const [groqMsg, setGroqMsg] = useState("");
  const [ollamaTest, setOllamaTest] = useState<TestState>("idle");
  const [ollamaMsg, setOllamaMsg] = useState("");

  const OLLAMA_MODELS = ["hermes3:3b", "qwen3:8b", "qwen2.5-coder:7b", "deepseek-r1:7b", "hermes3:latest", "llama3.2:3b"];

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">API Keys</h3>
        <div className="grid gap-6">
          <FieldRow label="Anthropic API Key">
            <input type="password" value={data.ANTHROPIC_API_KEY} onChange={(e) => onChange("ANTHROPIC_API_KEY", e.target.value)} placeholder="sk-ant-..." className="oc-input font-mono text-xs" autoComplete="off" />
            <TestButton label="Anthropic" onTest={async () => { setAnthTest("testing"); setAnthMsg("Connecting..."); const r = await callTest("anthropic", { apiKey: data.ANTHROPIC_API_KEY }); setAnthTest(r.ok ? "ok" : "error"); setAnthMsg(r.message); }} testState={anthTest} testMsg={anthMsg} />
          </FieldRow>

          <FieldRow label="OpenAI API Key">
            <input type="password" value={data.OPENAI_API_KEY} onChange={(e) => onChange("OPENAI_API_KEY", e.target.value)} placeholder="sk-..." className="oc-input font-mono text-xs" autoComplete="off" />
            <TestButton label="OpenAI" onTest={async () => { setOpenaiTest("testing"); setOpenaiMsg("Connecting..."); const r = await callTest("openai", { apiKey: data.OPENAI_API_KEY }); setOpenaiTest(r.ok ? "ok" : "error"); setOpenaiMsg(r.message); }} testState={openaiTest} testMsg={openaiMsg} />
          </FieldRow>

          <FieldRow label="Groq API Key">
            <input type="password" value={data.GROQ_API_KEY} onChange={(e) => onChange("GROQ_API_KEY", e.target.value)} placeholder="gsk_..." className="oc-input font-mono text-xs" autoComplete="off" />
            <TestButton label="Groq" onTest={async () => { setGroqTest("testing"); setGroqMsg("Connecting..."); const r = await callTest("groq", { apiKey: data.GROQ_API_KEY }); setGroqTest(r.ok ? "ok" : "error"); setGroqMsg(r.message); }} testState={groqTest} testMsg={groqMsg} />
          </FieldRow>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Ollama (Local LLM)</h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldRow label="Ollama URL" hint="host.docker.internal:11434 for OrbStack Mac host">
            <input type="text" value={data.OLLAMA_URL} onChange={(e) => onChange("OLLAMA_URL", e.target.value)} className="oc-input font-mono text-xs" />
            <TestButton label="Ollama" onTest={async () => { setOllamaTest("testing"); setOllamaMsg("Connecting..."); const r = await callTest("ollama", { url: data.OLLAMA_URL }); setOllamaTest(r.ok ? "ok" : "error"); setOllamaMsg(r.message); }} testState={ollamaTest} testMsg={ollamaMsg} />
          </FieldRow>

          <FieldRow label="Default Model" hint="Model used for Hermes cron and cheap tasks">
            <select value={data.OLLAMA_MODEL_CODE} onChange={(e) => onChange("OLLAMA_MODEL_CODE", e.target.value)} className="oc-input">
              {OLLAMA_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              {!OLLAMA_MODELS.includes(data.OLLAMA_MODEL_CODE) && data.OLLAMA_MODEL_CODE && (
                <option value={data.OLLAMA_MODEL_CODE}>{data.OLLAMA_MODEL_CODE}</option>
              )}
            </select>
          </FieldRow>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Dynamic Model Router</h3>
        <div className="grid gap-4 lg:grid-cols-3">
          <FieldRow label="Daily Budget (USD)" hint="Max spend per day across all LLM calls">
            <input type="number" step="0.01" min="0" value={data.DAILY_BUDGET_USD} onChange={(e) => onChange("DAILY_BUDGET_USD", e.target.value)} className="oc-input" />
          </FieldRow>
          <FieldRow label="Free Threshold" hint="Complexity score ≤ this → use free/cheap model (Ollama)">
            <input type="number" min="0" max="100" value={data.COMPLEXITY_FREE_THRESHOLD} onChange={(e) => onChange("COMPLEXITY_FREE_THRESHOLD", e.target.value)} className="oc-input" />
          </FieldRow>
          <FieldRow label="Cheap Threshold" hint="Complexity score ≤ this → use Groq/cheap; above → use Anthropic/OpenAI">
            <input type="number" min="0" max="100" value={data.COMPLEXITY_CHEAP_THRESHOLD} onChange={(e) => onChange("COMPLEXITY_CHEAP_THRESHOLD", e.target.value)} className="oc-input" />
          </FieldRow>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save LLM Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
      </div>
    </div>
  );
}

// ─── Pipeline Tab ─────────────────────────────────────────────────────────────

function PipelineTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["pipeline"];
  onChange: (k: keyof SettingsSnapshot["pipeline"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">General</h3>
        <div className="grid gap-4 lg:grid-cols-3">
          <FieldRow label="Log Level">
            <select value={data.LOG_LEVEL} onChange={(e) => onChange("LOG_LEVEL", e.target.value)} className="oc-input">
              {["DEBUG", "INFO", "WARNING", "ERROR"].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FieldRow>
          <FieldRow label="Max Revision Rounds" hint="Number of times an agent can revise its work">
            <input type="number" min="1" max="10" value={data.MAX_REVISION_ROUNDS} onChange={(e) => onChange("MAX_REVISION_ROUNDS", e.target.value)} className="oc-input" />
          </FieldRow>
          <FieldRow label="Default BU Type">
            <select value={data.DEFAULT_BU_TYPE} onChange={(e) => onChange("DEFAULT_BU_TYPE", e.target.value)} className="oc-input">
              {["internal", "external", "client", "poc"].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </FieldRow>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Web App Bridge</h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldRow label="Web App URL" hint="URL the SDLC agents POST updates to">
            <input type="text" value={data.WEB_APP_URL} onChange={(e) => onChange("WEB_APP_URL", e.target.value)} className="oc-input font-mono" />
          </FieldRow>
          <FieldRow label="Agent Sync Token" hint="Bearer token checked on /api/agent-activity/ingest">
            <input type="password" value={data.AGENT_SYNC_TOKEN} onChange={(e) => onChange("AGENT_SYNC_TOKEN", e.target.value)} className="oc-input font-mono text-xs" autoComplete="off" />
          </FieldRow>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">File Paths</h3>
        <div className="grid gap-4">
          <FieldRow label="SDLC Database Path" hint="SQLite DB for project/task state">
            <input type="text" value={data.DB_PATH} onChange={(e) => onChange("DB_PATH", e.target.value)} className="oc-input font-mono text-xs" />
          </FieldRow>
          <FieldRow label="Output Base Path" hint="Root directory for all agent-generated files">
            <input type="text" value={data.OUTPUT_BASE_PATH} onChange={(e) => onChange("OUTPUT_BASE_PATH", e.target.value)} className="oc-input font-mono text-xs" />
          </FieldRow>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save Pipeline Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
      </div>
    </div>
  );
}

// ─── Trading Tab ─────────────────────────────────────────────────────────────

function TradingTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["trading"];
  onChange: (k: keyof SettingsSnapshot["trading"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  return (
    <div className="space-y-8">
      <div className="material-panel-soft rounded-2xl p-4">
        <p className="text-xs text-amber-400 font-medium">OANDA credentials are required to run the Gold Bot. Leave blank to disable trading.</p>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">OANDA Credentials</h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldRow label="OANDA API Key">
            <input type="password" value={data.OANDA_API_KEY} onChange={(e) => onChange("OANDA_API_KEY", e.target.value)} placeholder="Access token from OANDA" className="oc-input font-mono text-xs" autoComplete="off" />
          </FieldRow>
          <FieldRow label="OANDA Account ID">
            <input type="text" value={data.OANDA_ACCOUNT_ID} onChange={(e) => onChange("OANDA_ACCOUNT_ID", e.target.value)} placeholder="001-..." className="oc-input font-mono" />
          </FieldRow>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Trading Configuration</h3>
        <div className="grid gap-4 lg:grid-cols-3">
          <FieldRow label="Trade Mode">
            <select value={data.TRADING_MODE} onChange={(e) => onChange("TRADING_MODE", e.target.value)} className="oc-input">
              <option value="">Select mode</option>
              <option value="disabled">Disabled (no trades)</option>
              <option value="paper">Paper (simulate)</option>
              <option value="live">Live (real money)</option>
            </select>
          </FieldRow>
          <FieldRow label="Environment">
            <select value={data.TRADING_ENVIRONMENT} onChange={(e) => onChange("TRADING_ENVIRONMENT", e.target.value)} className="oc-input">
              <option value="">Select env</option>
              <option value="practice">Practice (fxTrade Practice)</option>
              <option value="live">Live (fxTrade)</option>
            </select>
          </FieldRow>
          <FieldRow label="Risk Per Trade (%)" hint="Max account % risked per trade">
            <input type="number" step="0.1" min="0.1" max="5" value={data.TRADING_RISK_PERCENT} onChange={(e) => onChange("TRADING_RISK_PERCENT", e.target.value)} placeholder="1.0" className="oc-input" />
          </FieldRow>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save Trading Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
      </div>
    </div>
  );
}

// ─── Obsidian Tab ─────────────────────────────────────────────────────────────

function ObsidianTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["obsidian"];
  onChange: (k: keyof SettingsSnapshot["obsidian"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  return (
    <div className="space-y-8">
      <div className="grid gap-4">
        <FieldRow label="Vault Path" hint="Absolute path to your Obsidian vault directory (Mac Desktop path)">
          <input type="text" value={data.OBSIDIAN_VAULT_PATH} onChange={(e) => onChange("OBSIDIAN_VAULT_PATH", e.target.value)} placeholder="/Users/username/Documents/obsidian-vault" className="oc-input font-mono text-xs" />
        </FieldRow>
        <FieldRow label="Obsidian Local REST API URL" hint="Requires the 'Local REST API' plugin in Obsidian">
          <input type="text" value={data.OBSIDIAN_API_URL} onChange={(e) => onChange("OBSIDIAN_API_URL", e.target.value)} placeholder="http://localhost:27123" className="oc-input font-mono" />
        </FieldRow>
        <FieldRow label="Obsidian API Key" hint="From Obsidian → Settings → Local REST API → API Key">
          <input type="password" value={data.OBSIDIAN_API_KEY} onChange={(e) => onChange("OBSIDIAN_API_KEY", e.target.value)} placeholder="Obsidian API key" className="oc-input font-mono text-xs" autoComplete="off" />
        </FieldRow>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save Obsidian Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
      </div>
    </div>
  );
}

// ─── Web App Tab ──────────────────────────────────────────────────────────────

function WebappTab({ data, onChange, onSave, saveState, saveMsg }: {
  data: SettingsSnapshot["webapp"];
  onChange: (k: keyof SettingsSnapshot["webapp"], v: string) => void;
  onSave: () => void;
  saveState: SaveState;
  saveMsg?: string;
}) {
  return (
    <div className="space-y-8">
      <div className="material-panel-soft rounded-2xl p-4">
        <p className="text-xs text-amber-400 font-medium">Changes to SESSION_SECRET will invalidate all active sessions. The web app must be restarted to pick up new env vars.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <FieldRow label="Session Secret" hint="Min 16 chars. Changing this logs out all users.">
          <input type="password" value={data.SESSION_SECRET} onChange={(e) => onChange("SESSION_SECRET", e.target.value)} className="oc-input font-mono text-xs" autoComplete="off" />
        </FieldRow>
        <FieldRow label="Reset Email Delivery Mode" hint="'sink' logs the reset link to console instead of sending email">
          <select value={data.RESET_EMAIL_DELIVERY_MODE} onChange={(e) => onChange("RESET_EMAIL_DELIVERY_MODE", e.target.value)} className="oc-input">
            <option value="sink">Sink (dev — log to console)</option>
            <option value="disabled">Disabled</option>
          </select>
        </FieldRow>
        <FieldRow label="Trust Proxy Headers" hint="Set true only behind a trusted reverse proxy (Nginx/Caddy)">
          <select value={data.TRUST_PROXY_HEADERS} onChange={(e) => onChange("TRUST_PROXY_HEADERS", e.target.value)} className="oc-input">
            <option value="false">false (direct)</option>
            <option value="true">true (behind proxy)</option>
          </select>
        </FieldRow>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/8">
        <button type="button" onClick={onSave} disabled={saveState === "saving"} className="oc-btn-action">
          {saveState === "saving" ? "Saving…" : "Save Web App Settings"}
        </button>
        <StatusBadge state={saveState} message={saveMsg} />
        <span className="text-xs text-slate-500">Restart Next.js server after saving</span>
      </div>
    </div>
  );
}

// ─── Restart Panel ────────────────────────────────────────────────────────────

function RestartPanel() {
  const [restartState, setRestartState] = useState<"idle" | "restarting" | "ok" | "error">("idle");
  const [restartMsg, setRestartMsg] = useState("");

  const BOT_PROCESSES = [
    "sdlc-ceo", "sdlc-pm", "sdlc-ba", "sdlc-sa",
    "sdlc-uxui", "sdlc-dev", "sdlc-qa", "sdlc-devops", "sdlc-cron",
  ];

  async function doRestart(target: string) {
    setRestartState("restarting");
    setRestartMsg(`Restarting ${target}…`);
    try {
      const res = await fetch("/api/admin/settings/restart", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ target }),
      });
      const data = await res.json();
      setRestartState(data.ok ? "ok" : "error");
      setRestartMsg(data.ok ? `Restarted ${target}` : (data.error ?? "Failed"));
    } catch (err) {
      setRestartState("error");
      setRestartMsg(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div className="material-panel-soft rounded-2xl p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-white">PM2 Process Control</h3>
        <p className="text-xs text-slate-500 mt-1">Restart bots after saving tokens or changing pipeline config.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => doRestart("all")}
          disabled={restartState === "restarting"}
          className="oc-btn-action text-xs px-4 py-2"
        >
          {restartState === "restarting" ? "Restarting…" : "Restart All Bots"}
        </button>
        {BOT_PROCESSES.map((proc) => (
          <button
            key={proc}
            type="button"
            onClick={() => doRestart(proc)}
            disabled={restartState === "restarting"}
            className="oc-btn-ghost text-xs px-3 py-1.5"
          >
            {proc.replace("sdlc-", "")}
          </button>
        ))}
      </div>
      {restartState !== "idle" && (
        <p className={`text-xs font-medium ${restartState === "ok" ? "text-emerald-400" : restartState === "error" ? "text-red-400" : "text-slate-400"}`}>
          {restartMsg}
        </p>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function SettingsClient({ initialSettings }: { initialSettings: SettingsSnapshot }) {
  const [activeTab, setActiveTab] = useState<Tab>("discord");
  const [settings, setSettings] = useState<SettingsSnapshot>(initialSettings);
  const [saveStates, setSaveStates] = useState<Record<Tab, SaveState>>({
    discord: "idle", llm: "idle", pipeline: "idle",
    trading: "idle", obsidian: "idle", webapp: "idle",
  });
  const [saveMsgs, setSaveMsgs] = useState<Record<Tab, string>>({
    discord: "", llm: "", pipeline: "", trading: "", obsidian: "", webapp: "",
  });

  function setGroupField<G extends keyof SettingsSnapshot>(
    group: G,
    key: keyof SettingsSnapshot[G],
    value: string,
  ) {
    setSettings((prev) => ({
      ...prev,
      [group]: { ...prev[group], [key]: value },
    }));
  }

  const handleSave = useCallback(async (group: Tab) => {
    setSaveStates((s) => ({ ...s, [group]: "saving" }));
    const r = await callSave(group, settings[group] as Record<string, string>);
    setSaveStates((s) => ({ ...s, [group]: r.ok ? "ok" : "error" }));
    setSaveMsgs((s) => ({ ...s, [group]: r.ok ? "Saved successfully" : (r.error ?? "Save failed") }));
    if (r.ok) setTimeout(() => setSaveStates((s) => ({ ...s, [group]: "idle" })), 3000);
  }, [settings]);

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">

        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">System</p>
              <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">Settings</h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 material-muted">
                Configure Discord bots, LLM providers, pipeline parameters, integrations, and security.
                All changes write directly to <span className="font-mono text-xs text-slate-300">.env</span> files.
              </p>
            </div>
          </div>
        </section>

        <div className="flex gap-6 lg:gap-8">
          <aside className="hidden lg:flex flex-col gap-1 w-52 shrink-0 pt-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2.5 rounded-2xl px-3.5 py-2.5 text-sm font-medium text-left transition ${
                  activeTab === tab.id
                    ? "bg-[linear-gradient(135deg,#4f8cff_0%,#6aa0ff_100%)] text-white shadow-[0_8px_24px_-8px_rgba(79,140,255,0.6)]"
                    : "text-slate-400 hover:bg-white/6 hover:text-white"
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
            <div className="mt-4">
              <RestartPanel />
            </div>
          </aside>

          <div className="lg:hidden flex gap-2 overflow-x-auto pb-1">
            {TABS.map((tab) => (
              <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)}
                className={`shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition ${activeTab === tab.id ? "bg-[#4f8cff] text-white" : "text-slate-400 bg-white/5"}`}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 min-w-0">
            <div className="material-panel rounded-[2rem] p-8">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 mb-1">
                {TABS.find((t) => t.id === activeTab)?.icon} Config group
              </p>
              <h2 className="text-2xl font-semibold text-white mb-6">
                {TABS.find((t) => t.id === activeTab)?.label}
              </h2>

              {activeTab === "discord" && (
                <DiscordTab
                  data={settings.discord}
                  onChange={(k, v) => setGroupField("discord", k, v)}
                  onSave={() => handleSave("discord")}
                  saveState={saveStates.discord}
                  saveMsg={saveMsgs.discord}
                />
              )}
              {activeTab === "llm" && (
                <LlmTab
                  data={settings.llm}
                  onChange={(k, v) => setGroupField("llm", k, v)}
                  onSave={() => handleSave("llm")}
                  saveState={saveStates.llm}
                  saveMsg={saveMsgs.llm}
                />
              )}
              {activeTab === "pipeline" && (
                <PipelineTab
                  data={settings.pipeline}
                  onChange={(k, v) => setGroupField("pipeline", k, v)}
                  onSave={() => handleSave("pipeline")}
                  saveState={saveStates.pipeline}
                  saveMsg={saveMsgs.pipeline}
                />
              )}
              {activeTab === "trading" && (
                <TradingTab
                  data={settings.trading}
                  onChange={(k, v) => setGroupField("trading", k, v)}
                  onSave={() => handleSave("trading")}
                  saveState={saveStates.trading}
                  saveMsg={saveMsgs.trading}
                />
              )}
              {activeTab === "obsidian" && (
                <ObsidianTab
                  data={settings.obsidian}
                  onChange={(k, v) => setGroupField("obsidian", k, v)}
                  onSave={() => handleSave("obsidian")}
                  saveState={saveStates.obsidian}
                  saveMsg={saveMsgs.obsidian}
                />
              )}
              {activeTab === "webapp" && (
                <WebappTab
                  data={settings.webapp}
                  onChange={(k, v) => setGroupField("webapp", k, v)}
                  onSave={() => handleSave("webapp")}
                  saveState={saveStates.webapp}
                  saveMsg={saveMsgs.webapp}
                />
              )}
            </div>

            <div className="lg:hidden mt-6">
              <RestartPanel />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
