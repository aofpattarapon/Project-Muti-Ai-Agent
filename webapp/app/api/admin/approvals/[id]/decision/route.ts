import { NextResponse } from "next/server";

import { createAgentActivityLog, updateApprovalDecision } from "@/lib/agents/query";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

type RouteContext = {
  params: Promise<{
    id: string;
  }>;
};

export async function POST(request: Request, context: RouteContext) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session.role !== "Admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const { id } = await context.params;
  const formData = await request.formData();
  const decision = String(formData.get("decision") ?? "").trim() as
    | "approved"
    | "rejected"
    | "rework_requested";
  const roleKey = String(formData.get("role_key") ?? "").trim();
  const taskName = String(formData.get("task_name") ?? "").trim();
  const note = String(formData.get("decision_note") ?? "").trim();

  if (!id || !decision || !roleKey || !taskName) {
    return NextResponse.redirect(new URL("/approvals", request.url));
  }

  const updated = updateApprovalDecision({
    id: Number(id),
    status: decision,
    approver: session.username,
    decisionNote: note,
  });

  if (updated) {
    recordAuditEvent(
      "system_config.updated",
      `Approval item ${id} marked ${decision}.`,
      session.username,
    );

    createAgentActivityLog({
      roleKey,
      eventType: "approval.decision",
      taskName,
      status: decision,
      summary:
        note || `${session.username} marked this approval item as ${decision}.`,
      artifactRef: `approval.${id}`,
      channelTarget: "project-approval",
    });
  }

  return NextResponse.redirect(new URL("/approvals", request.url));
}
