import { afterEach, describe, expect, test } from "vitest";

import { getRuntimeConfig } from "@/lib/config/runtime";

const originalSessionSecret = process.env.SESSION_SECRET;
const originalNodeEnv = process.env.NODE_ENV;
const originalTrustProxyHeaders = process.env.TRUST_PROXY_HEADERS;
const originalResetEmailDeliveryMode = process.env.RESET_EMAIL_DELIVERY_MODE;

describe("runtime config", () => {
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

    if (originalResetEmailDeliveryMode === undefined) {
      delete process.env.RESET_EMAIL_DELIVERY_MODE;
    } else {
      process.env.RESET_EMAIL_DELIVERY_MODE = originalResetEmailDeliveryMode;
    }
  });

  test("reads valid session secret", () => {
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";
    process.env.NODE_ENV = "development";

    expect(getRuntimeConfig()).toMatchObject({
      sessionSecret: "dev-local-session-secret-2026-safe",
      nodeEnv: "development",
      trustProxyHeaders: false,
      resetEmailDeliveryMode: "sink",
    });
  });

  test("enables trusted proxy headers by default in production", () => {
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";
    process.env.NODE_ENV = "production";
    delete process.env.TRUST_PROXY_HEADERS;
    delete process.env.RESET_EMAIL_DELIVERY_MODE;

    expect(getRuntimeConfig()).toMatchObject({
      nodeEnv: "production",
      trustProxyHeaders: true,
      resetEmailDeliveryMode: "disabled",
    });
  });

  test("accepts explicit reset delivery mode override", () => {
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";
    process.env.NODE_ENV = "production";
    process.env.RESET_EMAIL_DELIVERY_MODE = "sink";

    expect(getRuntimeConfig()).toMatchObject({
      resetEmailDeliveryMode: "sink",
    });
  });

  test("throws when session secret is missing", () => {
    delete process.env.SESSION_SECRET;

    expect(() => getRuntimeConfig()).toThrow(
      "Missing required environment variable: SESSION_SECRET",
    );
  });

  test("throws when session secret uses unsafe default", () => {
    process.env.SESSION_SECRET = "dev-session-secret-change-me";

    expect(() => getRuntimeConfig()).toThrow(
      "Unsafe SESSION_SECRET detected. Replace the default development secret before running this app.",
    );
  });

  test("throws when session secret is too short", () => {
    process.env.SESSION_SECRET = "short-secret";

    expect(() => getRuntimeConfig()).toThrow(
      "SESSION_SECRET must be at least 16 characters long.",
    );
  });
});
