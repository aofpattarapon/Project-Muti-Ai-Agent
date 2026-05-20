/**
 * POST /api/runtime/paused-tasks/[sdlcTaskId]/resume
 * Operator-initiated resume for a paused SDLC task.
 *
 * Writes a system_config flag: key=runtime.resume_requested.{sdlcTaskId}
 * Python BaseAgent poll loop reads and acts on this flag (Phase 9.3).
 * Does NOT directly mutate sdlc.db — the Python side owns that write.
 *
 * Auth: Admin session (web operator action)
 */
import { NextResponse } from "next/server";
import { upsertResumeRequestFlag } from "@/lib/agents/query";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

type RouteContext = {
  params: Promise<{ sdlcTaskId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const session = await getSession();

  if (!session) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  if (session.role !== "Admin") {
    return NextResponse.json({ success: false, code: "FORBIDDEN" }, { status: 403 });
  }

  const { sdlcTaskId } = await context.params;

  if (!sdlcTaskId) {
    return NextResponse.json({ success: false, code: "BAD_REQUEST" }, { status: 400 });
  }

  upsertResumeRequestFlag(sdlcTaskId, session.username);

  recordAuditEvent(
    "agent.task.resumed.web",
    `Operator ${session.username} requested resume for task ${sdlcTaskId}.`,
    session.username,
  );

  return NextResponse.json({ success: true, sdlcTaskId });
}
