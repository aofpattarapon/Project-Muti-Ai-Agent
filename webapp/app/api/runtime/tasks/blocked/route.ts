/**
 * GET /api/runtime/tasks/blocked
 * Returns devops_blocked events from agent_activity_logs for infra/tool visibility.
 * These are log-only events — they never create approval_items.
 *
 * Query params:
 *   role_key — filter by role (optional, default: all blocked events)
 *   limit    — max results (default 50)
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey, listBlockedEvents } from "@/lib/agents/query";

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
  const roleKey = url.searchParams.get("role_key") ?? "";
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "50", 10), 200);

  const events = listBlockedEvents({ roleKey: roleKey || undefined, limit });

  return NextResponse.json({ success: true, count: events.length, events });
}
