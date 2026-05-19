import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { consumePasswordResetToken } from "@/lib/auth/password-reset";
import {
  PASSWORD_POLICY_MESSAGE,
  validatePasswordPolicy,
} from "@/lib/security/password-policy";

export async function POST(request: Request) {
  const body = (await request.json()) as {
    token?: string;
    password?: string;
    confirm_password?: string;
  };

  const token = body.token?.trim() ?? "";
  const password = body.password ?? "";
  const confirmPassword = body.confirm_password ?? "";

  if (!token || !password || !confirmPassword) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
        message: "Token, password, and confirmation are required.",
      },
      { status: 400 },
    );
  }

  const passwordPolicy = validatePasswordPolicy(password);

  if (!passwordPolicy.valid) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
        message: PASSWORD_POLICY_MESSAGE,
      },
      { status: 400 },
    );
  }

  if (password !== confirmPassword) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
        message: "Password confirmation does not match.",
      },
      { status: 400 },
    );
  }

  const resetResult = consumePasswordResetToken(token, password);

  if (!resetResult) {
    recordAuditEvent(
      "password_reset.rejected",
      "Password reset submission rejected because the token was invalid, expired, or already used.",
    );

    return NextResponse.json(
      {
        success: false,
        code: "INVALID_TOKEN",
        message: "This password reset link is invalid, expired, or already used.",
      },
      { status: 400 },
    );
  }

  recordAuditEvent(
    "password_reset.completed",
    `Password reset completed for ${resetResult.username}.`,
    resetResult.username,
  );

  return NextResponse.json({
    success: true,
    status: "completed",
    message: "Password updated successfully. You can now sign in with the new password.",
    login_url: "/login",
  });
}
