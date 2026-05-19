import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { getSessionMock } = vi.hoisted(() => ({
  getSessionMock: vi.fn(),
}));

vi.mock("@/lib/auth/session", () => ({
  getSession: getSessionMock,
}));

import { POST as updateUserRolePost } from "@/app/api/admin/users/[id]/role/route";
import { listRecentAuditEvents } from "@/lib/audit/query";
import { db } from "@/lib/db";
import { findUserById, listUsers } from "@/lib/auth/query-users";

describe("admin user role route", () => {
  beforeEach(() => {
    db.prepare("DELETE FROM audit_events").run();
    db.prepare("UPDATE users SET role = 'Operator' WHERE username = 'operator'").run();

    getSessionMock.mockResolvedValue({
      userId: "user-admin",
      username: "admin",
      email: "admin@example.com",
      name: "Avery Admin",
      role: "Admin",
    });
  });

  afterEach(() => {
    db.prepare("UPDATE users SET role = 'Operator' WHERE username = 'operator'").run();
    vi.clearAllMocks();
  });

  test("updates a user role and records an audit event", async () => {
    const operator = listUsers().find((user) => user.username === "operator");

    expect(operator).toBeTruthy();

    const formData = new FormData();
    formData.set("role", "Viewer");

    const response = await updateUserRolePost(
      new Request("http://localhost:3000/api/admin/users/role", {
        method: "POST",
        body: formData,
      }),
      {
        params: Promise.resolve({
          id: operator!.id,
        }),
      },
    );

    expect(response.status).toBe(307);
    expect(findUserById(operator!.id)?.role).toBe("Viewer");

    const events = listRecentAuditEvents({ type: "user.role_changed", limit: 10 });
    expect(events.length).toBe(1);
    expect(events[0]?.actor).toBe("admin");
  });

  test("rejects invalid role submission without changing role", async () => {
    const operator = listUsers().find((user) => user.username === "operator");

    expect(operator).toBeTruthy();

    const formData = new FormData();
    formData.set("role", "SuperAdmin");

    const response = await updateUserRolePost(
      new Request("http://localhost:3000/api/admin/users/role", {
        method: "POST",
        body: formData,
      }),
      {
        params: Promise.resolve({
          id: operator!.id,
        }),
      },
    );

    expect(response.status).toBe(307);
    expect(findUserById(operator!.id)?.role).toBe("Operator");

    const events = listRecentAuditEvents({ type: "user.role_changed", limit: 10 });
    expect(events.length).toBe(0);
  });
});
