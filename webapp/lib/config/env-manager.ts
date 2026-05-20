import fs from "node:fs";
import path from "node:path";

const SDLC_ROOT = path.dirname(
  process.env.OUTPUT_BASE_PATH ?? "/home/off_poff_p/projects/multi-ai-agent/sdlc/outputs",
);
export const SDLC_ENV_PATH = path.join(SDLC_ROOT, ".env");

const WEB_ENV_PATH = path.join(process.cwd(), ".env.local");

type EnvMap = Record<string, string>;

function parseEnvFile(filePath: string): EnvMap {
  const result: EnvMap = {};
  if (!fs.existsSync(filePath)) return result;
  for (const line of fs.readFileSync(filePath, "utf-8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    result[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1);
  }
  return result;
}

function patchEnvFile(filePath: string, updates: EnvMap): void {
  const raw = fs.existsSync(filePath) ? fs.readFileSync(filePath, "utf-8") : "";
  const remaining = new Set(Object.keys(updates));

  const patched = raw.split("\n").map((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) return line;
    const eq = trimmed.indexOf("=");
    if (eq === -1) return line;
    const key = trimmed.slice(0, eq).trim();
    if (key in updates) {
      remaining.delete(key);
      return `${key}=${updates[key]}`;
    }
    return line;
  });

  for (const key of remaining) {
    patched.push(`${key}=${updates[key]}`);
  }

  fs.writeFileSync(filePath, patched.join("\n"), "utf-8");
}

export function readSdlcEnv(): EnvMap {
  return parseEnvFile(SDLC_ENV_PATH);
}

export function writeSdlcEnv(updates: EnvMap): void {
  patchEnvFile(SDLC_ENV_PATH, updates);
}

export function readWebEnv(): EnvMap {
  return parseEnvFile(WEB_ENV_PATH);
}

export function writeWebEnv(updates: EnvMap): void {
  patchEnvFile(WEB_ENV_PATH, updates);
}

export type SettingsSnapshot = {
  discord: {
    CEO_DISCORD_TOKEN: string;
    PM_DISCORD_TOKEN: string;
    BA_DISCORD_TOKEN: string;
    SA_DISCORD_TOKEN: string;
    UXUI_DISCORD_TOKEN: string;
    FRONTEND_DISCORD_TOKEN: string;
    BACKEND_DISCORD_TOKEN: string;
    QA_DISCORD_TOKEN: string;
    DEVOPS_DISCORD_TOKEN: string;
    DISCORD_GUILD_ID: string;
    DISCORD_APPROVAL_CHANNEL_ID: string;
  };
  llm: {
    ANTHROPIC_API_KEY: string;
    OPENAI_API_KEY: string;
    GROQ_API_KEY: string;
    OLLAMA_URL: string;
    OLLAMA_MODEL_CODE: string;
    DAILY_BUDGET_USD: string;
    COMPLEXITY_FREE_THRESHOLD: string;
    COMPLEXITY_CHEAP_THRESHOLD: string;
  };
  pipeline: {
    LOG_LEVEL: string;
    MAX_REVISION_ROUNDS: string;
    DEFAULT_BU_TYPE: string;
    WEB_APP_URL: string;
    AGENT_SYNC_TOKEN: string;
    DB_PATH: string;
    OUTPUT_BASE_PATH: string;
  };
  trading: {
    OANDA_API_KEY: string;
    OANDA_ACCOUNT_ID: string;
    TRADING_MODE: string;
    TRADING_RISK_PERCENT: string;
    TRADING_ENVIRONMENT: string;
  };
  obsidian: {
    OBSIDIAN_VAULT_PATH: string;
    OBSIDIAN_API_URL: string;
    OBSIDIAN_API_KEY: string;
  };
  webapp: {
    SESSION_SECRET: string;
    TRUST_PROXY_HEADERS: string;
    RESET_EMAIL_DELIVERY_MODE: string;
  };
};

const DISCORD_KEYS = [
  "CEO_DISCORD_TOKEN", "PM_DISCORD_TOKEN", "BA_DISCORD_TOKEN", "SA_DISCORD_TOKEN",
  "UXUI_DISCORD_TOKEN", "FRONTEND_DISCORD_TOKEN", "BACKEND_DISCORD_TOKEN",
  "QA_DISCORD_TOKEN", "DEVOPS_DISCORD_TOKEN", "DISCORD_GUILD_ID", "DISCORD_APPROVAL_CHANNEL_ID",
];
const LLM_KEYS = [
  "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "OLLAMA_URL",
  "OLLAMA_MODEL_CODE", "DAILY_BUDGET_USD", "COMPLEXITY_FREE_THRESHOLD", "COMPLEXITY_CHEAP_THRESHOLD",
];
const PIPELINE_KEYS = [
  "LOG_LEVEL", "MAX_REVISION_ROUNDS", "DEFAULT_BU_TYPE", "WEB_APP_URL",
  "AGENT_SYNC_TOKEN", "DB_PATH", "OUTPUT_BASE_PATH",
];
const TRADING_KEYS = [
  "OANDA_API_KEY", "OANDA_ACCOUNT_ID", "TRADING_MODE", "TRADING_RISK_PERCENT", "TRADING_ENVIRONMENT",
];
const OBSIDIAN_KEYS = ["OBSIDIAN_VAULT_PATH", "OBSIDIAN_API_URL", "OBSIDIAN_API_KEY"];
const WEBAPP_KEYS = ["SESSION_SECRET", "TRUST_PROXY_HEADERS", "RESET_EMAIL_DELIVERY_MODE"];

export function loadAllSettings(): SettingsSnapshot {
  const sdlc = readSdlcEnv();
  const web = readWebEnv();

  function pick(map: EnvMap, keys: string[]): Record<string, string> {
    return Object.fromEntries(keys.map((k) => [k, map[k] ?? ""]));
  }

  return {
    discord: pick(sdlc, DISCORD_KEYS) as SettingsSnapshot["discord"],
    llm: pick(sdlc, LLM_KEYS) as SettingsSnapshot["llm"],
    pipeline: pick(sdlc, PIPELINE_KEYS) as SettingsSnapshot["pipeline"],
    trading: pick(sdlc, TRADING_KEYS) as SettingsSnapshot["trading"],
    obsidian: pick(sdlc, OBSIDIAN_KEYS) as SettingsSnapshot["obsidian"],
    webapp: pick(web, WEBAPP_KEYS) as SettingsSnapshot["webapp"],
  };
}

export type SettingsGroup = keyof SettingsSnapshot;

export function saveGroupSettings(group: SettingsGroup, values: Record<string, string>): void {
  if (group === "webapp") {
    writeWebEnv(values);
  } else {
    writeSdlcEnv(values);
  }
}
