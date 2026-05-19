/**
 * GET /api/runtime/tasks
 * Returns current SDLC task states derived from the latest activity log entry per task.
 *
 * Query params:
 *   project_id — filter by project (optional)
 *   role_key   — filter by role (optional)
 *   limit      — max results (default 100)
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey, listTaskStates } from "@/lib/agents/query";

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
  const projectId = url.searchParams.get("project_id") ?? "";
  const roleKey = url.searchParams.get("role_key") ?? "";
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "100", 10), 500);

  const tasks = listTaskStates({
    projectId: projectId || undefined,
    roleKey: roleKey || undefined,
    limit,
  });

  return NextResponse.json({ success: true, count: tasks.length, tasks });
}
