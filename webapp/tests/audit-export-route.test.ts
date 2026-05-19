import { beforeEach, describe, expect, test, vi } from "vitest";

import { GET as auditExportGet } from "@/app/api/audit/export/route";

const mockSession = {
  userId: "user-admin",
  username: "admin",
  email: "admin@example.com",
  name: "Admin",
  role: "Admin",
  sessionVersion: 1,
};

const mockSessionCEO = {
  userId: "user-ceo",
  username: "ceo",
  email: "ceo@example.com",
  name: "CEO",
  role: "CEO",
  sessionVersion: 1,
};

const mockSessionUnauthorized = {
  userId: "user-dev",
  username: "dev",
  email: "dev@example.com",
  name: "DEV",
  role: "DEV",
  sessionVersion: 1,
};

vi.mock("@/lib/auth/session");
vi.mock("@/lib/agents/query");

describe("audit export route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns 401 for unauthenticated requests", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValue(null);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(401);
  });

  test("returns 403 for unauthorized roles", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValue(mockSessionUnauthorized);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(403);
  });

  test("exports audit logs as csv for CEO role", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    vi.mocked(getSession).mockResolvedValue(mockSessionCEO);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([
      {
        id: 1,
        roleKey: "PM",
        eventType: "START",
        taskName: "task-123",
        status: "in_progress",
        summary: "Started task execution",
        artifactRef: null,
        channelTarget: null,
        createdAt: "2026-05-15T10:00:00Z",
      },
    ]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/csv");
    expect(response.headers.get("content-disposition")).toContain("attachment");

    const csv = await response.text();
    expect(csv).toContain("timestamp,agent_id,role,event_type,task_id,message,status");
    expect(csv).toContain("2026-05-15T10:00:00Z");
    expect(csv).toContain("PM");
  });

  test("exports audit logs for DevOps role", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    const mockSessionDevOps = { ...mockSessionUnauthorized, role: "DevOps" };

    vi.mocked(getSession).mockResolvedValue(mockSessionDevOps);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(200);
  });

  test("exports audit logs for QA role", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    const mockSessionQA = { ...mockSessionUnauthorized, role: "QA" };

    vi.mocked(getSession).mockResolvedValue(mockSessionQA);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(200);
  });

  test("exports audit logs for Admin role", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    vi.mocked(getSession).mockResolvedValue(mockSession);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(200);
  });

  test("applies filters correctly", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    vi.mocked(getSession).mockResolvedValue(mockSessionCEO);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request(
        "http://localhost:3000/api/audit/export?startDate=2026-05-01&endDate=2026-05-31&agentId=PM&eventType=START&taskId=task-123",
      ),
    );

    expect(response.status).toBe(200);
    expect(vi.mocked(filterAgentActivityLogs)).toHaveBeenCalledWith({
      startDate: "2026-05-01",
      endDate: "2026-05-31",
      agentId: "PM",
      eventType: "START",
      taskId: "task-123",
      limit: 100000,
    });
  });

  test("returns 400 for invalid date range", async () => {
    const { getSession } = await import("@/lib/auth/session");

    vi.mocked(getSession).mockResolvedValue(mockSessionCEO);

    const response = await auditExportGet(
      new Request(
        "http://localhost:3000/api/audit/export?startDate=2026-05-31&endDate=2026-05-01",
      ),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.error).toContain("start_date must not be later than end_date");
  });

  test("handles csv special characters correctly", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    vi.mocked(getSession).mockResolvedValue(mockSessionCEO);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([
      {
        id: 1,
        roleKey: "PM",
        eventType: "ERROR",
        taskName: "task-456",
        status: "failed",
        summary: 'Error: "Unexpected value", please retry',
        artifactRef: null,
        channelTarget: null,
        createdAt: "2026-05-15T10:00:00Z",
      },
    ]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    const response = await auditExportGet(
      new Request("http://localhost:3000/api/audit/export"),
    );

    expect(response.status).toBe(200);
    const csv = await response.text();
    expect(csv).toContain('"Error: ""Unexpected value"", please retry"');
  });

  test("logs export action to audit trail", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { filterAgentActivityLogs, createAgentActivityLog } = await import(
      "@/lib/agents/query"
    );

    vi.mocked(getSession).mockResolvedValue(mockSessionCEO);
    vi.mocked(filterAgentActivityLogs).mockReturnValue([]);
    vi.mocked(createAgentActivityLog).mockReturnValue(true);

    await auditExportGet(new Request("http://localhost:3000/api/audit/export"));

    expect(vi.mocked(createAgentActivityLog)).toHaveBeenCalledWith({
      roleKey: "CEO",
      eventType: "AUDIT_EXPORT",
      taskName: "audit-export",
      status: "SUCCESS",
      summary: "Exported 0 audit records",
    });
  });
});
