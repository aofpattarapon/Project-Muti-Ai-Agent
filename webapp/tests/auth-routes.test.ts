import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  createSession: vi.fn(async () => {}),
  getSession: vi.fn(async () => ({
    userId: "user-admin",
    username: "admin",
    email: "admin@example.com",
    name: "Avery Admin",
    role: "Admin",
  })),
  clearSession: vi.fn(async () => {}),
}));

import { POST as loginPost } from "@/app/api/auth/login/route";
import { POST as logoutPost } from "@/app/api/auth/logout/route";
import { db } from "@/lib/db";
import { clearLoginRateLimitState } from "@/lib/security/login-rate-limit";

const originalSessionSecret = process.env.SESSION_SECRET;
const originalNodeEnv = process.env.NODE_ENV;
const originalTrustProxyHeaders = process.env.TRUST_PROXY_HEADERS;

describe("auth routes", () => {
  beforeEach(() => {
    clearLoginRateLimitState();
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";
    process.env.NODE_ENV = "test";
    process.env.TRUST_PROXY_HEADERS = "true";
    db.prepare("UPDATE users SET is_active = 1").run();
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

    if (originalTrustProxyHeaders === undefined) {
      delete process.env.TRUST_PROXY_HEADERS;
    } else {
      process.env.TRUST_PROXY_HEADERS = originalTrustProxyHeaders;
    }

    db.prepare("UPDATE users SET is_active = 1").run();
  });

  test("login returns validation error when username_or_email is missing", async () => {
    const response = await loginPost(
      new Request("http://localhost:3000/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password: "anything" }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "VALIDATION_ERROR",
    });
  });

  test("login returns invalid credentials for unknown user", async () => {
    const response = await loginPost(
      new Request("http://localhost:3000/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username_or_email: "missing@example.com",
          password: "bad-password",
        }),
        headers: { "Content-Type": "application/json", "x-forwarded-for": "127.0.0.1" },
      }),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "INVALID_CREDENTIALS",
    });
  });

  test("login rejects inactive users", async () => {
    db.prepare("UPDATE users SET is_active = 0 WHERE username = 'admin'").run();

    const response = await loginPost(
      new Request("http://localhost:3000/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username_or_email: "admin",
          password: "Admin123!",
        }),
        headers: { "Content-Type": "application/json", "x-forwarded-for": "127.0.0.1" },
      }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      code: "ACCOUNT_INACTIVE",
    });
  });

  test("login succeeds for valid seeded admin user", async () => {
    const response = await loginPost(
      new Request("http://localhost:3000/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username_or_email: "admin",
          password: "Admin123!",
        }),
        headers: { "Content-Type": "application/json", "x-forwarded-for": "127.0.0.1" },
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      role: "Admin",
      dashboard_route: "/dashboard",
    });
  });

  test("login is rate limited after repeated failures", async () => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await loginPost(
        new Request("http://localhost:3000/api/auth/login", {
          method: "POST",
          body: JSON.stringify({
            username_or_email: "admin",
            password: "wrong-password",
          }),
          headers: { "Content-Type": "application/json", "x-forwarded-for": "127.0.0.1" },
        }),
      );
    }

    const blockedResponse = await loginPost(
      new Request("http://localhost:3000/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username_or_email: "admin",
          password: "wrong-password",
        }),
        headers: { "Content-Type": "application/json", "x-forwarded-for": "127.0.0.1" },
      }),
    );

    expect(blockedResponse.status).toBe(429);
    expect(blockedResponse.headers.get("Retry-After")).toBeTruthy();
    await expect(blockedResponse.json()).resolves.toMatchObject({
      success: false,
      code: "RATE_LIMITED",
    });
  });

  test("logout returns success response", async () => {
    const response = await logoutPost(
      new Request("http://localhost:3000/api/auth/logout", {
        method: "POST",
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
    });
  });
});
