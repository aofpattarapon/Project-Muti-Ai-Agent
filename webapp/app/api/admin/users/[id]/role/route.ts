import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";
import { findUserById, isUserRole, updateUserRole } from "@/lib/auth/query-users";

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
  const nextRoleValue = String(formData.get("role") ?? "");

  if (!isUserRole(nextRoleValue)) {
    return NextResponse.redirect(new URL(`/users/${id}`, request.url));
  }

  if (nextRoleValue !== user.role) {
    updateUserRole(id, nextRoleValue);

    recordAuditEvent(
      "user.role_changed",
      `User ${user.username} role changed from ${user.role} to ${nextRoleValue}.`,
      session.username,
    );
  }

  return NextResponse.redirect(new URL(`/users/${id}`, request.url));
}
