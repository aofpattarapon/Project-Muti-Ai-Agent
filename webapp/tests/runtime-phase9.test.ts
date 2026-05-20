/**
 * Phase 9.1 — Runtime recovery status API tests
 *
 * Tests for:
 *   GET  /api/runtime/paused-tasks
 *   POST /api/runtime/paused-tasks/[sdlcTaskId]/resume
 *   GET  /api/runtime/cooldowns
 *   GET  /api/runtime/recovery
 */
import fs from "fs";
import os from "os";
import path from "path";
import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";

import { GET as pausedTasksGet } from "@/app/api/runtime/paused-tasks/route";
import { POST as resumePost } from "@/app/api/runtime/paused-tasks/[sdlcTaskId]/resume/route";
import { GET as cooldownsGet } from "@/app/api/runtime/cooldowns/route";
import { GET as recoveryGet } from "@/app/api/runtime/recovery/route";
import { db } from "@/lib/db";

vi.mock("@/lib/auth/session");

// ─── Shared helpers ───────────────────────────────────────────────────────────

const BEARER = "Bearer phase9-test-token";
const TASK_ID = "sdlc-task-phase9-test";

function authorizedGet(url: string) {
  return new Request(url, { headers: { Authorization: BEARER } });
}

function seedPauseEvent(sdlcTaskId: string, metadata: Record<string, string> = {}) {
  db.prepare(
    `INSERT INTO agent_activity_logs
       (role_key, event_type, task_name, status, summary, created_at, sdlc_task_id, project_id, metadata)
     VALUES ('dev', 'task_paused', 'Phase9 Task', 'paused', 'Rate limited', datetime('now'), ?, 'proj-test', ?)`,
  ).run(sdlcTaskId, JSON.stringify(metadata));
}

// ─── Setup / teardown ─────────────────────────────────────────────────────────

let tmpDir: string;

beforeEach(() => {
  // Enable bearer auth
  db.prepare(
    `UPDATE system_configs SET value = 'true' WHERE config_key = 'reporting.agent_sync_ingest_enabled'`,
  ).run();
  db.prepare(
    `UPDATE system_configs SET value = 'phase9-test-token' WHERE config_key = 'reporting.agent_sync_ingest_token'`,
  ).run();

  // Clean up test rows
  db.prepare(`DELETE FROM agent_activity_logs WHERE task_name = 'Phase9 Task'`).run();
  db.prepare(`DELETE FROM system_configs WHERE config_key LIKE 'runtime.resume_requested.%'`).run();
  db.prepare(`DELETE FROM audit_events WHERE detail LIKE '%phase9%'`).run();

  vi.clearAllMocks();

  // Temp dir for file-based routes
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "phase9-test-"));
  vi.stubEnv("OUTPUT_BASE_PATH", tmpDir);
});

afterAll(() => {
  vi.unstubAllEnvs();
});

// ─── GET /api/runtime/paused-tasks ───────────────────────────────────────────

describe("GET /api/runtime/paused-tasks", () => {
  test("returns 401 without valid token", async () => {
    const res = await pausedTasksGet(new Request("http://localhost/api/runtime/paused-tasks"));
    expect(res.status).toBe(401);
  });

  test("returns empty list when no paused tasks", async () => {
    const res = await pausedTasksGet(authorizedGet("http://localhost/api/runtime/paused-tasks"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { paused: unknown[]; total: number };
    expect(body.total).toBe(0);
    expect(body.paused).toEqual([]);
  });

  test("returns paused task with parsed metadata", async () => {
    seedPauseEvent(TASK_ID, {
      pause_reason: "rate_limited",
      pause_provider: "groq",
      pause_model: "groq/llama-3.3-70b",
      retry_after_at: "2026-05-20T15:00:00",
      resume_policy: "auto",
    });

    const res = await pausedTasksGet(authorizedGet("http://localhost/api/runtime/paused-tasks"));
    expect(res.status).toBe(200);

    const body = (await res.json()) as {
      paused: Array<{
        sdlcTaskId: string;
        pauseReason: string;
        pauseProvider: string;
        pauseModel: string;
        resumePolicy: string;
      }>;
      total: number;
    };

    expect(body.total).toBe(1);
    const task = body.paused[0];
    expect(task.sdlcTaskId).toBe(TASK_ID);
    expect(task.pauseReason).toBe("rate_limited");
    expect(task.pauseProvider).toBe("groq");
    expect(task.pauseModel).toBe("groq/llama-3.3-70b");
    expect(task.resumePolicy).toBe("auto");
  });

  test("returns latest pause event per sdlc_task_id (deduplicates)", async () => {
    // Insert two paused events for the same task
    seedPauseEvent(TASK_ID, { pause_reason: "rate_limited", pause_provider: "groq", pause_model: "" });
    seedPauseEvent(TASK_ID, { pause_reason: "context_limit", pause_provider: "anthropic", pause_model: "" });

    const res = await pausedTasksGet(authorizedGet("http://localhost/api/runtime/paused-tasks"));
    const body = (await res.json()) as { paused: Array<{ pauseReason: string }>; total: number };

    // Only the latest event should appear
    expect(body.total).toBe(1);
    expect(body.paused[0].pauseReason).toBe("context_limit");
  });
});

// ─── POST /api/runtime/paused-tasks/[sdlcTaskId]/resume ──────────────────────

describe("POST /api/runtime/paused-tasks/[sdlcTaskId]/resume", () => {
  test("returns 401 when no session", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValue(null);

    const res = await resumePost(
      new Request(`http://localhost/api/runtime/paused-tasks/${TASK_ID}/resume`, { method: "POST" }),
      { params: Promise.resolve({ sdlcTaskId: TASK_ID }) },
    );
    expect(res.status).toBe(401);
  });

  test("returns 403 for non-Admin session", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValue({
      userId: "u1", username: "ops", email: "ops@test.com", name: "Ops", role: "DevOps", sessionVersion: 1,
    });

    const res = await resumePost(
      new Request(`http://localhost/api/runtime/paused-tasks/${TASK_ID}/resume`, { method: "POST" }),
      { params: Promise.resolve({ sdlcTaskId: TASK_ID }) },
    );
    expect(res.status).toBe(403);
  });

  test("writes system_config flag and audit event for Admin", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValue({
      userId: "u-admin", username: "admin", email: "admin@test.com", name: "Admin", role: "Admin", sessionVersion: 1,
    });

    const res = await resumePost(
      new Request(`http://localhost/api/runtime/paused-tasks/${TASK_ID}/resume`, { method: "POST" }),
      { params: Promise.resolve({ sdlcTaskId: TASK_ID }) },
    );

    expect(res.status).toBe(200);
    const body = (await res.json()) as { success: boolean; sdlcTaskId: string };
    expect(body.success).toBe(true);
    expect(body.sdlcTaskId).toBe(TASK_ID);

    // Verify system_config flag was written
    const flag = db
      .prepare(`SELECT value FROM system_configs WHERE config_key = ?`)
      .get(`runtime.resume_requested.${TASK_ID}`) as { value: string } | undefined;
    expect(flag?.value).toBe("admin");

    // Verify audit event was recorded
    const auditRow = db
      .prepare(`SELECT type, actor FROM audit_events WHERE type = 'agent.task.resumed.web' AND actor = 'admin' ORDER BY id DESC LIMIT 1`)
      .get() as { type: string; actor: string } | undefined;
    expect(auditRow?.type).toBe("agent.task.resumed.web");
    expect(auditRow?.actor).toBe("admin");
  });
});

// ─── GET /api/runtime/cooldowns ──────────────────────────────────────────────

describe("GET /api/runtime/cooldowns", () => {
  test("returns 401 without valid token", async () => {
    const res = await cooldownsGet(new Request("http://localhost/api/runtime/cooldowns"));
    expect(res.status).toBe(401);
  });

  test("returns empty cooldowns when runtime_status.json is missing", async () => {
    const res = await cooldownsGet(authorizedGet("http://localhost/api/runtime/cooldowns"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { cooldowns: unknown[]; workerAlive: boolean };
    expect(body.cooldowns).toEqual([]);
    expect(body.workerAlive).toBe(false);
  });

  test("parses runtime_status.json and returns cooldowns", async () => {
    const recoveryDir = path.join(tmpDir, "recovery");
    fs.mkdirSync(recoveryDir, { recursive: true });
    const recentTick = new Date(Date.now() - 60_000).toISOString(); // 1 min ago
    fs.writeFileSync(
      path.join(recoveryDir, "runtime_status.json"),
      JSON.stringify({
        last_tick: recentTick,
        worker_alive: true,
        paused_count: 2,
        ready_to_resume_count: 1,
        cooldowns: [
          { provider: "groq", model: "llama-3.3-70b", reason: "rate_limited", retry_after_at: "2026-05-20T15:00:00" },
        ],
        last_stats: { requeued: [], deferred: ["task-x"], pruned: 0 },
      }),
    );

    const res = await cooldownsGet(authorizedGet("http://localhost/api/runtime/cooldowns"));
    expect(res.status).toBe(200);

    const body = (await res.json()) as {
      workerAlive: boolean;
      lastTick: string;
      pausedCount: number;
      cooldowns: Array<{ provider: string; model: string }>;
    };

    expect(body.workerAlive).toBe(true);
    expect(body.pausedCount).toBe(2);
    expect(body.cooldowns).toHaveLength(1);
    expect(body.cooldowns[0].provider).toBe("groq");
  });
});

// ─── GET /api/runtime/recovery ───────────────────────────────────────────────

describe("GET /api/runtime/recovery", () => {
  test("returns 401 without valid token", async () => {
    const res = await recoveryGet(new Request("http://localhost/api/runtime/recovery"));
    expect(res.status).toBe(401);
  });

  test("returns empty ticks when tick_history.json is missing", async () => {
    const res = await recoveryGet(authorizedGet("http://localhost/api/runtime/recovery"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { ticks: unknown[]; total: number };
    expect(body.ticks).toEqual([]);
    expect(body.total).toBe(0);
  });

  test("returns ticks newest-first", async () => {
    const recoveryDir = path.join(tmpDir, "recovery");
    fs.mkdirSync(recoveryDir, { recursive: true });
    const history = [
      { timestamp: "2026-05-20T10:00:00", requeued: [], deferred: [], pruned: 0, dry_run: false },
      { timestamp: "2026-05-20T11:00:00", requeued: ["task-a"], deferred: [], pruned: 1, dry_run: false },
      { timestamp: "2026-05-20T12:00:00", requeued: [], deferred: ["task-b"], pruned: 0, dry_run: false },
    ];
    fs.writeFileSync(path.join(recoveryDir, "tick_history.json"), JSON.stringify(history));

    const res = await recoveryGet(authorizedGet("http://localhost/api/runtime/recovery"));
    expect(res.status).toBe(200);

    const body = (await res.json()) as {
      ticks: Array<{ timestamp: string }>;
      total: number;
    };

    expect(body.total).toBe(3);
    expect(body.ticks[0].timestamp).toBe("2026-05-20T12:00:00"); // newest first
    expect(body.ticks[2].timestamp).toBe("2026-05-20T10:00:00"); // oldest last
  });
});
