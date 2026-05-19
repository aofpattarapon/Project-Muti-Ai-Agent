import { describe, expect, test } from "vitest";

import { db } from "@/lib/db";
import {
  findUserById,
  isUserRole,
  listUsers,
  updateUserActiveStatus,
  updateUserRole,
} from "@/lib/auth/query-users";

describe("query users", () => {
  test("returns users without password data", () => {
    const users = listUsers();

    expect(users.length).toBeGreaterThanOrEqual(3);
    expect(users.some((user) => user.username === "admin")).toBe(true);
    expect(users.every((user) => "role" in user)).toBe(true);
    expect(users.every((user) => "isActive" in user)).toBe(true);
    expect(users.every((user) => "mfaEnabled" in user)).toBe(true);
    expect(users.every((user) => "mfaEnrolledAt" in user)).toBe(true);
    expect(users.every((user) => !("password" in user))).toBe(true);
    expect(users.every((user) => !("password_hash" in user))).toBe(true);
  });

  test("finds a user by id", () => {
    const users = listUsers();
    const admin = users.find((user) => user.username === "admin");

    expect(admin).toBeTruthy();

    const found = findUserById(admin!.id);

    expect(found).toMatchObject({
      username: "admin",
      role: "Admin",
      mfaEnabled: false,
    });
  });

  test("returns null for unknown id", () => {
    expect(findUserById("missing-user-id")).toBeNull();
  });

  test("updates user active status", () => {
    const admin = listUsers().find((user) => user.username === "admin");

    expect(admin).toBeTruthy();

    updateUserActiveStatus(admin!.id, false);
    expect(findUserById(admin!.id)?.isActive).toBe(false);

    updateUserActiveStatus(admin!.id, true);
    expect(findUserById(admin!.id)?.isActive).toBe(true);
  });

  test("updates user role", () => {
    const operator = listUsers().find((user) => user.username === "operator");

    expect(operator).toBeTruthy();

    updateUserRole(operator!.id, "Viewer");
    expect(findUserById(operator!.id)?.role).toBe("Viewer");

    updateUserRole(operator!.id, "Operator");
    expect(findUserById(operator!.id)?.role).toBe("Operator");
  });

  test("validates allowed roles", () => {
    expect(isUserRole("Admin")).toBe(true);
    expect(isUserRole("Operator")).toBe(true);
    expect(isUserRole("Viewer")).toBe(true);
    expect(isUserRole("SuperAdmin")).toBe(false);
  });

  test("defaults MFA readiness fields for seeded users", () => {
    const admin = listUsers().find((user) => user.username === "admin");

    expect(admin).toBeTruthy();
    expect(admin?.mfaEnabled).toBe(false);
    expect(admin?.mfaEnrolledAt).toBeNull();
  });

  test("restores seeded user state for later tests", () => {
    db.prepare("UPDATE users SET is_active = 1 WHERE username = 'admin'").run();
    db.prepare("UPDATE users SET role = 'Operator' WHERE username = 'operator'").run();

    const admin = listUsers().find((user) => user.username === "admin");
    const operator = listUsers().find((user) => user.username === "operator");

    expect(admin?.isActive).toBe(true);
    expect(operator?.role).toBe("Operator");
  });
});
