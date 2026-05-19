import { describe, expect, test } from "vitest";

import { seedUsers } from "@/data/seed-users";
import { findUserByLogin } from "@/lib/auth/users";
import { canViewAdminControls, roleSections } from "@/lib/rbac/permissions";

describe("seed users", () => {
  test("has three pilot users", () => {
    expect(seedUsers).toHaveLength(3);
  });

  test("includes Admin, Operator, and Viewer roles", () => {
    expect(seedUsers.map((user) => user.role)).toEqual([
      "Admin",
      "Operator",
      "Viewer",
    ]);
  });
});

describe("findUserByLogin", () => {
  test("finds admin by username", () => {
    const user = findUserByLogin("admin");
    expect(user?.role).toBe("Admin");
  });

  test("finds operator by email", () => {
    const user = findUserByLogin("operator@example.com");
    expect(user?.role).toBe("Operator");
  });

  test("returns undefined for unknown user", () => {
    const user = findUserByLogin("unknown@example.com");
    expect(user).toBeUndefined();
  });
});

describe("rbac permissions", () => {
  test("admin can view admin controls", () => {
    expect(canViewAdminControls("Admin")).toBe(true);
  });

  test("operator cannot view admin controls", () => {
    expect(canViewAdminControls("Operator")).toBe(false);
  });

  test("viewer has read-only style sections configured", () => {
    expect(roleSections.Viewer).toEqual(["Overview", "Read-only summary"]);
  });
});
