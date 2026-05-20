/**
 * GET /api/runtime/cooldowns
 * Returns active provider cooldowns and recovery worker health from
 * outputs/recovery/runtime_status.json (written by recovery_worker on each tick).
 *
 * Returns empty cooldowns array (not an error) when the file is missing or unreadable.
 *
 * Auth: Bearer token (reporting.agent_sync_ingest_token)
 */
import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { findSystemConfigByKey } from "@/lib/agents/query";

interface CooldownEntry {
  provider: string;
  model: string;
  reason: string;
  retry_after_at: string;
}

interface RuntimeStatus {
  last_tick: string | null;
  worker_alive: boolean;
  paused_count: number;
  ready_to_resume_count: number;
  cooldowns: CooldownEntry[];
  last_stats: {
    requeued: string[];
    deferred: string[];
    pruned: number;
  } | null;
}

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  return syncEnabled?.value === "true" && !!expectedToken?.value && token === expectedToken.value;
}

function readRuntimeStatus(): RuntimeStatus {
  const outputBase = process.env.OUTPUT_BASE_PATH ?? "/app/outputs";
  const statusFile = path.join(outputBase, "recovery", "runtime_status.json");

  try {
    if (!fs.existsSync(statusFile)) {
      return { last_tick: null, worker_alive: false, paused_count: 0, ready_to_resume_count: 0, cooldowns: [], last_stats: null };
    }
    const raw = fs.readFileSync(statusFile, "utf-8");
    return JSON.parse(raw) as RuntimeStatus;
  } catch {
    return { last_tick: null, worker_alive: false, paused_count: 0, ready_to_resume_count: 0, cooldowns: [], last_stats: null };
  }
}

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const status = readRuntimeStatus();

  // Determine if worker is alive: last_tick < 10 minutes ago
  let workerAlive = false;
  if (status.last_tick) {
    const ageMs = Date.now() - new Date(status.last_tick).getTime();
    workerAlive = ageMs < 10 * 60 * 1000;
  }

  return NextResponse.json({
    workerAlive,
    lastTick: status.last_tick,
    pausedCount: status.paused_count,
    readyToResumeCount: status.ready_to_resume_count,
    cooldowns: status.cooldowns ?? [],
    lastStats: status.last_stats ?? null,
  });
}
