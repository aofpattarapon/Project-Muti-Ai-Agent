/**
 * GET /api/runtime/decisions
 * Returns approval items decided via web UI (status != waiting_approval)
 * in the last 60 minutes, for the bot to pick up and execute in Discord.
 *
 * Query params:
 *   role_key  - filter by role (optional)
 *   since_id  - only items with id > since_id (for incremental polling)
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey } from "@/lib/agents/query";
import { db } from "@/lib/db";

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  const runtimeEnabled = findSystemConfigByKey("sync.runtime_approval_queue_enabled");
  return (
    syncEnabled?.value === "true" &&
    runtimeEnabled?.value === "true" &&
    !!expectedToken?.value &&
    token === expectedToken.value
  );
}

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const url = new URL(request.url);
  const roleKey = url.searchParams.get("role_key") ?? "";
  const sinceId = parseInt(url.searchParams.get("since_id") ?? "0", 10);
  const sinceMs = Date.now() - 60 * 60 * 1000; // last 60 min
  const sinceIso = new Date(sinceMs).toISOString();

  const query = roleKey
    ? `SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
              requested_by, approver, decision_note, channel_target, created_at, updated_at
       FROM approval_items
       WHERE status != 'waiting_approval'
         AND role_key = ?
         AND id > ?
         AND datetime(updated_at) >= datetime(?)
       ORDER BY id ASC LIMIT 20`
    : `SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
              requested_by, approver, decision_note, channel_target, created_at, updated_at
       FROM approval_items
       WHERE status != 'waiting_approval'
         AND id > ?
         AND datetime(updated_at) >= datetime(?)
       ORDER BY id ASC LIMIT 50`;

  const rows = roleKey
    ? (db.prepare(query).all(roleKey, sinceId, sinceIso) as any[])
    : (db.prepare(query).all(sinceId, sinceIso) as any[]);

  return NextResponse.json({
    success: true,
    count: rows.length,
    items: rows,
  });
}
