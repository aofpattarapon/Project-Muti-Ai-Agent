import { NextResponse } from "next/server";

import {
  createAgentActivityLog,
  findApprovalItemById,
  findSystemConfigByKey,
  updateApprovalDecision,
} from "@/lib/agents/query";

type RouteContext = {
  params: Promise<{
    id: string;
  }>;
};

function readSyncToken(request: Request) {
  const authHeader = request.headers.get("authorization");

  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice("Bearer ".length).trim();
  }

  return request.headers.get("x-agent-sync-token")?.trim() ?? "";
}

function isRuntimeAuthorized(request: Request) {
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  const runtimeApprovalEnabled = findSystemConfigByKey("sync.runtime_approval_queue_enabled");

  if (
    syncEnabled?.value !== "true" ||
    runtimeApprovalEnabled?.value !== "true" ||
    !expectedToken?.value
  ) {
    return false;
  }

  const receivedToken = readSyncToken(request);
  return !!receivedToken && receivedToken === expectedToken.value;
}

export async function POST(request: Request, context: RouteContext) {
  if (!isRuntimeAuthorized(request)) {
    return NextResponse.json(
      {
        success: false,
        code: "UNAUTHORIZED",
      },
      { status: 401 },
    );
  }

  const { id } = await context.params;
  const approvalItem = findApprovalItemById(Number(id));

  if (!approvalItem) {
    return NextResponse.json(
      {
        success: false,
        code: "NOT_FOUND",
      },
      { status: 404 },
    );
  }

  const body = (await request.json()) as {
    decision?: "approved" | "rejected" | "rework_requested";
    decision_note?: string;
    approver?: string;
    source?: string;
  };

  const decision = body.decision?.trim() as "approved" | "rejected" | "rework_requested" | undefined;
  const decisionNote = body.decision_note?.trim() ?? "";
  const approver = body.approver?.trim() || "discord-runtime";
  const source = body.source?.trim() || "discord";

  if (!decision) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
      },
      { status: 400 },
    );
  }

  const updated = updateApprovalDecision({
    id: approvalItem.id,
    status: decision,
    approver,
    decisionNote,
  });

  if (updated) {
    createAgentActivityLog({
      roleKey: approvalItem.roleKey,
      eventType: source === "discord" ? "approval.discord_decision" : "approval.runtime_decision",
      taskName: approvalItem.taskName,
      status: decision,
      summary:
        decisionNote || `${approver} marked this approval item as ${decision} via ${source}.`,
      artifactRef: `approval.${approvalItem.id}`,
      channelTarget: approvalItem.channelTarget ?? "project-approval",
    });
  }

  return NextResponse.json({
    success: updated,
    status: updated ? decision : "ignored",
    approval_id: approvalItem.id,
  });
}
