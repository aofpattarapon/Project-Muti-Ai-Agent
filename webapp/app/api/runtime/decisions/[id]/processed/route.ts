/**
 * POST /api/runtime/decisions/:id/processed
 * Bot calls this after successfully executing a web decision in Discord,
 * so the item is excluded from future poll results even after bot restart.
 */
import { NextResponse } from "next/server";
import { findApprovalItemById, findSystemConfigByKey, markApprovalItemProcessed } from "@/lib/agents/query";

type RouteContext = {
  params: Promise<{ id: string }>;
};

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

export async function POST(request: Request, context: RouteContext) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const { id } = await context.params;
  const approvalItem = findApprovalItemById(Number(id));

  if (!approvalItem) {
    return NextResponse.json({ success: false, code: "NOT_FOUND" }, { status: 404 });
  }

  const body = (await request.json()) as { status?: string };
  const runtimeStatus = body.status?.trim() || approvalItem.status;

  const marked = markApprovalItemProcessed(approvalItem.id, runtimeStatus);

  return NextResponse.json({
    success: marked,
    approval_id: approvalItem.id,
    runtime_processed_status: runtimeStatus,
  });
}
