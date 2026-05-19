import { beforeEach, describe, expect, test } from "vitest";

import {
  clearLoginRateLimitState,
  getLoginRateLimitKey,
  isLoginBlocked,
  recordLoginFailure,
  recordLoginSuccess,
} from "@/lib/security/login-rate-limit";

describe("login rate limit", () => {
  beforeEach(() => {
    clearLoginRateLimitState();
  });

  test("blocks after repeated failures", () => {
    const key = getLoginRateLimitKey("admin", "127.0.0.1");

    for (let index = 0; index < 5; index += 1) {
      recordLoginFailure(key);
    }

    const state = isLoginBlocked(key);

    expect(state.blocked).toBe(true);
    expect(state.retryAfterSeconds).toBeGreaterThan(0);
  });

  test("success clears failure state", () => {
    const key = getLoginRateLimitKey("admin", "127.0.0.1");

    recordLoginFailure(key);
    recordLoginSuccess(key);

    const state = isLoginBlocked(key);

    expect(state.blocked).toBe(false);
  });
});
