/**
 * GET /api/runtime/paused-tasks
 * Returns the latest pause event per sdlc_task_id from agent_activity_logs.
 * Pause metadata (reason, provider, model, retry_after_at, resume_policy) is
 * stored in the metadata JSON column by base_agent._pause_task_for_quota().
 *
 * Auth: Bearer token (reporting.agent_sync_ingest_token)
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey, listPausedTaskEvents } from "@/lib/agents/query";

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  return syncEnabled?.value === "true" && !!expectedToken?.value && token === expectedToken.value;
}

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const url = new URL(request.url);
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "100", 10), 500);

  const paused = listPausedTaskEvents(limit);

  return NextResponse.json({ paused, total: paused.length });
}
