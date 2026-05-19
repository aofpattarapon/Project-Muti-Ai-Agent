import { NextResponse } from "next/server";

import { deleteSystemConfig, findSystemConfigById } from "@/lib/agents/query";
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
  const config = findSystemConfigById(Number(id));

  if (!config) {
    return NextResponse.redirect(new URL("/backoffice", request.url));
  }

  deleteSystemConfig(Number(id));

  recordAuditEvent(
    "system_config.deleted",
    `System config ${config.configKey} deleted.`,
    session.username,
  );

  return NextResponse.redirect(new URL("/backoffice", request.url));
}
