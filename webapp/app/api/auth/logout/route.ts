import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { clearSession, getSession } from "@/lib/auth/session";

export async function POST() {
  const session = await getSession();

  if (session) {
    recordAuditEvent("logout", "User signed out.", session.username);
  }

  await clearSession();

  return NextResponse.json({
    success: true,
    session_status: "ended",
  });
}
