import { beforeEach, describe, expect, test } from "vitest";

import {
  findUserByLogin,
  getUserSessionVersion,
  incrementUserSessionVersion,
  isSessionVersionCurrent,
} from "@/lib/auth/users";
import { db } from "@/lib/db";

describe("session version", () => {
  beforeEach(() => {
    db.prepare("UPDATE users SET session_version = 1").run();
  });

  test("tracks the current session version for a user", () => {
    const admin = findUserByLogin("admin");

    expect(admin).toBeTruthy();
    expect(getUserSessionVersion(admin!.id)).toBe(1);
    expect(isSessionVersionCurrent(admin!.id, admin!.sessionVersion)).toBe(true);
  });

  test("invalidates older session versions after increment", () => {
    const admin = findUserByLogin("admin");

    expect(admin).toBeTruthy();

    incrementUserSessionVersion(admin!.id);

    expect(getUserSessionVersion(admin!.id)).toBe(2);
    expect(isSessionVersionCurrent(admin!.id, admin!.sessionVersion)).toBe(false);
    expect(isSessionVersionCurrent(admin!.id, 2)).toBe(true);
  });
});
