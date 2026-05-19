import { NextResponse } from "next/server";

import { findSystemConfigById, updateSystemConfig } from "@/lib/agents/query";
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

  const formData = await request.formData();

  updateSystemConfig(Number(id), {
    configKey: String(formData.get("config_key") ?? "").trim(),
    category: String(formData.get("category") ?? "").trim(),
    value: String(formData.get("value") ?? "").trim(),
    description: String(formData.get("description") ?? "").trim(),
  });

  recordAuditEvent(
    "system_config.updated",
    `System config ${config.configKey} updated.`,
    session.username,
  );

  return NextResponse.redirect(new URL("/backoffice", request.url));
}
