import { beforeEach, describe, expect, test, vi } from "vitest";

import { GET as exportProjectLogsGet } from "@/app/api/project-logs/export/route";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(async () => ({
    userId: "user-admin",
    username: "admin",
    email: "admin@example.com",
    name: "Admin",
    role: "Admin",
    sessionVersion: 1,
  })),
}));

describe("project logs export route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("exports project logs as csv for admins", async () => {
    const response = await exportProjectLogsGet(
      new Request("http://localhost:3000/api/project-logs/export?format=csv"),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/csv");

    const csv = await response.text();
    expect(csv).toContain("role,event,task,status,summary,artifact,target,when");
  });
});
