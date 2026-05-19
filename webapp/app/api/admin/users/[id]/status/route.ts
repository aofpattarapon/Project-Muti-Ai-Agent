import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";
import { findUserById, updateUserActiveStatus } from "@/lib/auth/query-users";

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
  const user = findUserById(id);

  if (!user) {
    return NextResponse.redirect(new URL("/users", request.url));
  }

  const formData = await request.formData();
  const nextActiveValue = formData.get("is_active") === "true";

  updateUserActiveStatus(id, nextActiveValue);

  recordAuditEvent(
    "user.status_changed",
    `User ${user.username} status changed to ${nextActiveValue ? "active" : "inactive"}.`,
    session.username,
  );

  return NextResponse.redirect(new URL(`/users/${id}`, request.url));
}
