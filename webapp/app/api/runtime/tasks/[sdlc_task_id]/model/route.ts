/**
 * GET /api/runtime/tasks/[sdlc_task_id]/model
 * Returns model observability data for an SDLC task from the latest activity log.
 * Fields: preferred_model, routed_model, actual_model, fallback_used,
 *         estimated_cost_usd, duration_seconds, error_info.
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey, findLatestTaskLog } from "@/lib/agents/query";

type RouteContext = { params: Promise<{ sdlc_task_id: string }> };

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  return syncEnabled?.value === "true" && !!expectedToken?.value && token === expectedToken.value;
}

export async function GET(request: Request, context: RouteContext) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const { sdlc_task_id } = await context.params;
  if (!sdlc_task_id?.trim()) {
    return NextResponse.json({ success: false, code: "BAD_REQUEST" }, { status: 400 });
  }

  const log = findLatestTaskLog(sdlc_task_id.trim());
  if (!log) {
    return NextResponse.json({ success: false, code: "NOT_FOUND" }, { status: 404 });
  }

  let meta: Record<string, unknown> = {};
  try {
    meta = JSON.parse(log.metadata) as Record<string, unknown>;
  } catch {
    // metadata not parseable — return empty model info
  }

  return NextResponse.json({
    success: true,
    sdlc_task_id,
    task_name: log.taskName,
    role_key: log.roleKey,
    last_status: log.status,
    last_event_type: log.eventType,
    last_updated: log.createdAt,
    model: {
      preferred_model: (meta.preferred_model as string) ?? "",
      routed_model: (meta.routed_model as string) ?? "",
      actual_model: (meta.model_id as string) ?? "",
      fallback_used: !!(meta.fallback_used),
      estimated_cost_usd: (meta.cost_usd as number) ?? 0,
      duration_seconds: (meta.duration_seconds as number) ?? 0,
      error_info: (meta.error_info as string) ?? "",
    },
  });
}
