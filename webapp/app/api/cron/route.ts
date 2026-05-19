import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

interface JobEntry {
  job: string;
  status: "ok" | "warn" | "error";
  summary: string;
  timestamp: string;
}

interface CronStatus {
  running: boolean;
  lastUpdated: string | null;
  jobs: JobEntry[];
  summary: {
    total: number;
    ok: number;
    warn: number;
    error: number;
    lastRun: string | null;
  };
}

function readJobHistory(): JobEntry[] {
  const outputBase = process.env.OUTPUT_BASE_PATH ?? "/app/outputs";
  const histFile = path.join(outputBase, "cron", "job_history.json");

  try {
    if (!fs.existsSync(histFile)) return [];
    const raw = fs.readFileSync(histFile, "utf-8");
    return JSON.parse(raw) as JobEntry[];
  } catch {
    return [];
  }
}

export async function GET(): Promise<NextResponse<CronStatus>> {
  const history = readJobHistory();
  const recent = history.slice(-100).reverse(); // newest first, max 100

  const ok    = recent.filter((j) => j.status === "ok").length;
  const warn  = recent.filter((j) => j.status === "warn").length;
  const error = recent.filter((j) => j.status === "error").length;
  const lastRun = recent[0]?.timestamp ?? null;

  // Detect if hermes_cron is "running" by checking if last entry is < 2h old
  let running = false;
  if (lastRun) {
    const ageMs = Date.now() - new Date(lastRun).getTime();
    running = ageMs < 2 * 60 * 60 * 1000; // 2 hours
  }

  return NextResponse.json({
    running,
    lastUpdated: lastRun,
    jobs: recent.slice(0, 50),
    summary: {
      total: recent.length,
      ok,
      warn,
      error,
      lastRun,
    },
  });
}
