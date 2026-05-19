import { NextResponse } from "next/server";

import {
  createAgentActivityLog,
  deleteAgentRoleConfig,
  findAgentRoleConfig,
} from "@/lib/agents/query";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

type RouteContext = {
  params: Promise<{
    roleKey: string;
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

  const { roleKey } = await context.params;
  const existing = findAgentRoleConfig(roleKey);

  if (!existing) {
    return NextResponse.redirect(new URL("/agents", request.url));
  }

  deleteAgentRoleConfig(roleKey);

  recordAuditEvent(
    "agent_config.deleted",
    `Agent role config ${roleKey} deleted.`,
    session.username,
  );

  createAgentActivityLog({
    roleKey,
    eventType: "config.deleted",
    taskName: "Agent control back-office",
    status: "deleted",
    summary: `Role config ${existing.displayName} was deleted from the project back-office.`,
    artifactRef: `${roleKey}.config`,
    channelTarget: "project-db",
  });

  return NextResponse.redirect(new URL("/agents", request.url));
}
