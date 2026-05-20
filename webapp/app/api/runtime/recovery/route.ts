/**
 * GET /api/runtime/recovery
 * Returns recovery worker tick history from
 * outputs/recovery/tick_history.json (written by recovery_worker on each tick).
 *
 * Returns empty history array (not an error) when the file is missing or unreadable.
 * Results are returned newest-first.
 *
 * Auth: Bearer token (reporting.agent_sync_ingest_token)
 */
import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { findSystemConfigByKey } from "@/lib/agents/query";

interface TickEntry {
  timestamp: string;
  requeued: string[];
  deferred: string[];
  pruned: number;
  dry_run: boolean;
}

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  return syncEnabled?.value === "true" && !!expectedToken?.value && token === expectedToken.value;
}

function readTickHistory(): TickEntry[] {
  const outputBase = process.env.OUTPUT_BASE_PATH ?? "/app/outputs";
  const histFile = path.join(outputBase, "recovery", "tick_history.json");

  try {
    if (!fs.existsSync(histFile)) return [];
    const raw = fs.readFileSync(histFile, "utf-8");
    return JSON.parse(raw) as TickEntry[];
  } catch {
    return [];
  }
}

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const url = new URL(request.url);
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "50", 10), 200);

  const history = readTickHistory();
  const ticks = history.slice().reverse().slice(0, limit); // newest first

  return NextResponse.json({ ticks, total: history.length });
}
