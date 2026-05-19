import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { issuePasswordResetToken } from "@/lib/auth/password-reset";
import { findUserByLogin } from "@/lib/auth/users";
import { sendPasswordResetEmail } from "@/lib/notifications/email";

const NEUTRAL_MESSAGE =
  "If an active account matches that username or email, reset instructions have been prepared for delivery.";

export async function POST(request: Request) {
  const body = (await request.json()) as {
    username_or_email?: string;
  };

  const usernameOrEmail = body.username_or_email?.trim() ?? "";

  if (!usernameOrEmail) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
        message: "Username or email is required.",
      },
      { status: 400 },
    );
  }

  const matchedUser = findUserByLogin(usernameOrEmail);

  recordAuditEvent(
    "password_reset.requested",
    "Password reset request submitted.",
    matchedUser?.username,
  );

  const issuedToken = issuePasswordResetToken(usernameOrEmail);

  if (issuedToken) {
    const resetUrl = new URL(`/reset-password/${issuedToken.token}`, request.url).toString();

    sendPasswordResetEmail({
      to: issuedToken.email,
      username: issuedToken.username,
      resetUrl,
      expiresAt: issuedToken.expiresAt,
    });

    recordAuditEvent(
      "password_reset.issued",
      `Password reset token issued for ${issuedToken.username}.`,
      issuedToken.username,
    );
  }

  return NextResponse.json({
    success: true,
    status: "accepted",
    message: NEUTRAL_MESSAGE,
  });
}
