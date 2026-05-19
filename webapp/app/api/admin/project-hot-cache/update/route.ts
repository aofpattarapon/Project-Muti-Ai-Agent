import { NextResponse } from "next/server";

import { upsertProjectHotCache } from "@/lib/agents/query";
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
  const cacheKey = String(formData.get("cache_key") ?? "").trim();

  if (!cacheKey) {
    return NextResponse.redirect(new URL("/project-memory", request.url));
  }

  upsertProjectHotCache({
    cacheKey,
    title: String(formData.get("title") ?? "").trim(),
    summary: String(formData.get("summary") ?? "").trim(),
    scope: String(formData.get("scope") ?? "").trim() || "global",
    status: String(formData.get("status") ?? "").trim() || "active",
    sourceRole: String(formData.get("source_role") ?? "").trim() || session.username,
    artifactRef: String(formData.get("artifact_ref") ?? "").trim(),
  });

  recordAuditEvent(
    "system_config.updated",
    `Project hot cache ${cacheKey} updated.`,
    session.username,
  );

  return NextResponse.redirect(new URL("/project-memory", request.url));
}
