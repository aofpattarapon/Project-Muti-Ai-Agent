import { afterEach, describe, expect, test } from "vitest";

import { getClientIp } from "@/lib/security/client-ip";

const originalTrustProxyHeaders = process.env.TRUST_PROXY_HEADERS;
const originalNodeEnv = process.env.NODE_ENV;
const originalSessionSecret = process.env.SESSION_SECRET;

describe("client ip", () => {
  afterEach(() => {
    if (originalTrustProxyHeaders === undefined) {
      delete process.env.TRUST_PROXY_HEADERS;
    } else {
      process.env.TRUST_PROXY_HEADERS = originalTrustProxyHeaders;
    }

    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV;
    } else {
      process.env.NODE_ENV = originalNodeEnv;
    }

    if (originalSessionSecret === undefined) {
      delete process.env.SESSION_SECRET;
    } else {
      process.env.SESSION_SECRET = originalSessionSecret;
    }
  });

  test("uses forwarded header when proxy headers are trusted", () => {
    process.env.NODE_ENV = "production";
    process.env.TRUST_PROXY_HEADERS = "true";
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";

    const request = new Request("http://localhost:3000", {
      headers: {
        "x-forwarded-for": "203.0.113.10, 10.0.0.1",
      },
    });

    expect(getClientIp(request)).toBe("203.0.113.10");
  });

  test("ignores proxy headers when not trusted", () => {
    process.env.NODE_ENV = "development";
    process.env.TRUST_PROXY_HEADERS = "false";
    process.env.SESSION_SECRET = "dev-local-session-secret-2026-safe";

    const request = new Request("http://localhost:3000", {
      headers: {
        "x-forwarded-for": "203.0.113.10",
      },
    });

    expect(getClientIp(request)).toBe("direct-client");
  });
});
