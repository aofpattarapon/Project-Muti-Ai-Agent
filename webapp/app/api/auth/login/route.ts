import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { createSession } from "@/lib/auth/session";
import { findUserByLogin } from "@/lib/auth/users";
import { getClientIp } from "@/lib/security/client-ip";
import {
  getLoginRateLimitKey,
  isLoginBlocked,
  recordLoginFailure,
  recordLoginSuccess,
} from "@/lib/security/login-rate-limit";
import { verifyPassword } from "@/lib/security/password";

export async function POST(request: Request) {
  const body = (await request.json()) as {
    username_or_email?: string;
    password?: string;
  };

  const usernameOrEmail = body.username_or_email?.trim() ?? "";
  const password = body.password?.trim() ?? "";

  if (!usernameOrEmail || !password) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
        message: !usernameOrEmail
          ? "Username or email is required."
          : "Password is required.",
      },
      { status: 400 },
    );
  }

  const rateLimitKey = getLoginRateLimitKey(usernameOrEmail, getClientIp(request));
  const blockState = isLoginBlocked(rateLimitKey);

  if (blockState.blocked) {
    recordAuditEvent(
      "login.blocked",
      `Rate-limited login attempt for ${usernameOrEmail.toLowerCase()}`,
    );

    return NextResponse.json(
      {
        success: false,
        code: "RATE_LIMITED",
        message: "Too many failed login attempts. Please try again later.",
        retry_after_seconds: blockState.retryAfterSeconds,
      },
      {
        status: 429,
        headers: {
          "Retry-After": String(blockState.retryAfterSeconds),
        },
      },
    );
  }

  const user = findUserByLogin(usernameOrEmail);

  if (user && !user.isActive) {
    recordAuditEvent(
      "login.inactive",
      `Inactive account login attempt for ${usernameOrEmail.toLowerCase()}`,
      user.username,
    );

    return NextResponse.json(
      {
        success: false,
        code: "ACCOUNT_INACTIVE",
        message: "This account is inactive. Please contact an administrator.",
      },
      { status: 403 },
    );
  }

  if (!user || !(await verifyPassword(password, user.password_hash))) {
    recordLoginFailure(rateLimitKey);

    recordAuditEvent(
      "login.failure",
      `Invalid login attempt for ${usernameOrEmail.toLowerCase()}`,
    );

    return NextResponse.json(
      {
        success: false,
        code: "INVALID_CREDENTIALS",
        message: "Invalid username, email, or password.",
      },
      { status: 401 },
    );
  }

  recordLoginSuccess(rateLimitKey);

  await createSession({
    userId: user.id,
    username: user.username,
    email: user.email,
    name: user.name,
    role: user.role,
    sessionVersion: user.sessionVersion,
  });

  recordAuditEvent("login.success", "User signed in successfully.", user.username);

  return NextResponse.json({
    success: true,
    role: user.role,
    dashboard_route: "/dashboard",
  });
}
