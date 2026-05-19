import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { POST as passwordResetConfirmPost } from "@/app/api/auth/password-reset/confirm/route";
import { POST as passwordResetRequestPost } from "@/app/api/auth/password-reset/request/route";
import {
  deleteExpiredPasswordResetTokens,
  deleteUsedPasswordResetTokens,
} from "@/lib/auth/password-reset";
import { listRecentAuditEvents } from "@/lib/audit/query";
import { getUserSessionVersion } from "@/lib/auth/users";
import { db } from "@/lib/db";
import { clearEmailSink, listEmailSinkEntries } from "@/lib/notifications/email";
import { hashPasswordSync, verifyPassword } from "@/lib/security/password";
import { PASSWORD_POLICY_MESSAGE } from "@/lib/security/password-policy";

const originalSessionSecret = process.env.SESSION_SECRET;
const originalNodeEnv = process.env.NODE_ENV;
const originalResetEmailDeliveryMode = process.env.RESET_EMAIL_DELIVERY_MODE;

describe("password reset routes", () => {
  beforeEach(() => {
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";
    process.env.NODE_ENV = "test";
    process.env.RESET_EMAIL_DELIVERY_MODE = "sink";

    db.prepare("DELETE FROM audit_events").run();
    db.prepare("DELETE FROM password_reset_tokens").run();
    db.prepare("UPDATE users SET is_active = 1 WHERE username = 'admin'").run();
    db.prepare("UPDATE users SET password_hash = ? WHERE username = 'admin'").run(
      hashPasswordSync("Admin123!"),
    );
    db.prepare("UPDATE users SET session_version = 1 WHERE username = 'admin'").run();
    clearEmailSink();
  });

  afterEach(() => {
    if (originalSessionSecret === undefined) {
      delete process.env.SESSION_SECRET;
    } else {
      process.env.SESSION_SECRET = originalSessionSecret;
    }

    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV;
    } else {
      process.env.NODE_ENV = originalNodeEnv;
    }

    if (originalResetEmailDeliveryMode === undefined) {
      delete process.env.RESET_EMAIL_DELIVERY_MODE;
    } else {
      process.env.RESET_EMAIL_DELIVERY_MODE = originalResetEmailDeliveryMode;
    }
  });

  test("returns validation error when username_or_email is missing", async () => {
    const response = await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({}),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "VALIDATION_ERROR",
    });
  });

  test("issues a reset token for a known active user and writes to email sink", async () => {
    const response = await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(200);

    const payload = (await response.json()) as {
      success: boolean;
      reset_url?: string;
    };

    expect(payload.success).toBe(true);
    expect(payload.reset_url).toBeUndefined();

    const tokenCount = db
      .prepare("SELECT COUNT(*) as count FROM password_reset_tokens")
      .get() as { count: number };

    expect(tokenCount.count).toBe(1);

    const sinkEntries = listEmailSinkEntries();
    expect(sinkEntries.length).toBe(1);
    expect(sinkEntries[0]?.to).toBe("admin@example.com");
    expect(sinkEntries[0]?.resetUrl).toContain("/reset-password/");

    const events = listRecentAuditEvents({ limit: 10 });
    expect(events.some((event) => event.type === "password_reset.requested")).toBe(true);
    expect(events.some((event) => event.type === "password_reset.issued")).toBe(true);
  });

  test("returns neutral success for unknown user without creating token", async () => {
    const response = await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "nobody@example.com" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(200);

    const payload = (await response.json()) as {
      success: boolean;
      reset_url?: string;
    };

    expect(payload.success).toBe(true);
    expect(payload.reset_url).toBeUndefined();

    const tokenCount = db
      .prepare("SELECT COUNT(*) as count FROM password_reset_tokens")
      .get() as { count: number };

    expect(tokenCount.count).toBe(0);
    expect(listEmailSinkEntries()).toHaveLength(0);
  });

  test("rejects weak password submission", async () => {
    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    const sinkEntries = listEmailSinkEntries();
    const token = sinkEntries[0]?.resetUrl.split("/reset-password/")[1];

    expect(token).toBeTruthy();

    const response = await passwordResetConfirmPost(
      new Request("http://localhost:3000/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({
          token,
          password: "weakpass",
          confirm_password: "weakpass",
        }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "VALIDATION_ERROR",
      message: PASSWORD_POLICY_MESSAGE,
    });
  });

  test("completes reset for a valid token, updates password, and bumps session version", async () => {
    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    const admin = db
      .prepare("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
      .get() as { id: string };

    expect(getUserSessionVersion(admin.id)).toBe(1);

    const sinkEntries = listEmailSinkEntries();
    const token = sinkEntries[0]?.resetUrl.split("/reset-password/")[1];

    expect(token).toBeTruthy();

    const response = await passwordResetConfirmPost(
      new Request("http://localhost:3000/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({
          token,
          password: "NewAdmin123!",
          confirm_password: "NewAdmin123!",
        }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      status: "completed",
    });

    const updatedAdmin = db
      .prepare("SELECT password_hash FROM users WHERE username = 'admin' LIMIT 1")
      .get() as { password_hash: string };

    await expect(verifyPassword("NewAdmin123!", updatedAdmin.password_hash)).resolves.toBe(true);

    const usedCount = db
      .prepare("SELECT COUNT(*) as count FROM password_reset_tokens WHERE used_at IS NOT NULL")
      .get() as { count: number };

    expect(usedCount.count).toBe(1);
    expect(getUserSessionVersion(admin.id)).toBe(2);

    const events = listRecentAuditEvents({ type: "password_reset.completed", limit: 10 });
    expect(events.length).toBe(1);
    expect(events[0]?.actor).toBe("admin");
  });

  test("deletes used reset tokens without touching active ones", async () => {
    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    const sinkEntries = listEmailSinkEntries();
    const token = sinkEntries[0]?.resetUrl.split("/reset-password/")[1];

    await passwordResetConfirmPost(
      new Request("http://localhost:3000/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({
          token,
          password: "NewAdmin123!",
          confirm_password: "NewAdmin123!",
        }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    db.prepare("UPDATE users SET password_hash = ? WHERE username = 'admin'").run(
      hashPasswordSync("Admin123!"),
    );

    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    const deletedCount = deleteUsedPasswordResetTokens();

    const remaining = db
      .prepare("SELECT COUNT(*) as count FROM password_reset_tokens")
      .get() as { count: number };

    expect(deletedCount).toBe(1);
    expect(remaining.count).toBe(1);
  });

  test("deletes expired reset tokens without touching valid active ones", async () => {
    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    db.prepare(
      `
        UPDATE password_reset_tokens
        SET expires_at = '2000-01-01T00:00:00.000Z'
      `,
    ).run();

    db.prepare("UPDATE users SET password_hash = ? WHERE username = 'admin'").run(
      hashPasswordSync("Admin123!"),
    );

    await passwordResetRequestPost(
      new Request("http://localhost:3000/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ username_or_email: "admin" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    const deletedCount = deleteExpiredPasswordResetTokens("2026-01-01T00:00:00.000Z");

    const remaining = db
      .prepare("SELECT COUNT(*) as count FROM password_reset_tokens")
      .get() as { count: number };

    expect(deletedCount).toBe(1);
    expect(remaining.count).toBe(1);
  });

  test("rejects invalid token submission", async () => {
    const response = await passwordResetConfirmPost(
      new Request("http://localhost:3000/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({
          token: "invalid-token",
          password: "NewAdmin123!",
          confirm_password: "NewAdmin123!",
        }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "INVALID_TOKEN",
    });

    const events = listRecentAuditEvents({ type: "password_reset.rejected", limit: 10 });
    expect(events.length).toBe(1);
  });
});
