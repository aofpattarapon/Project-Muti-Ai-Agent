import { NextResponse } from "next/server";

import { createSystemConfig } from "@/lib/agents/query";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

export async function POST(request: Request) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session.role !== "Admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const formData = await request.formData();
  const configKey = String(formData.get("config_key") ?? "").trim();

  if (!configKey) {
    return NextResponse.redirect(new URL("/backoffice", request.url));
  }

  const created = createSystemConfig({
    configKey,
    category: String(formData.get("category") ?? "").trim(),
    value: String(formData.get("value") ?? "").trim(),
    description: String(formData.get("description") ?? "").trim(),
  });

  if (created) {
    recordAuditEvent(
      "system_config.created",
      `System config ${configKey} created.`,
      session.username,
    );
  }

  return NextResponse.redirect(new URL("/backoffice", request.url));
}
