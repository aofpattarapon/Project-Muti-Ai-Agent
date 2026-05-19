/**
 * Phase 5.1: Approval Identity — webapp tests
 *
 * Tests:
 *  - approval_items stores sdlc_task_id / project_id / discord_message_id
 *  - runtime decisions endpoint returns unprocessed decisions only
 *  - processed decisions are excluded from polling results
 *  - bot restart (since_id=0) does not re-surface already-processed items
 *  - duplicate task names across projects do not collide (sdlc_task_id is authoritative)
 *  - discord ingest updates matching approval item by sdlc_task_id
 *  - mark-processed endpoint sets processed_by_runtime_at
 */

import { beforeEach, describe, expect, test } from "vitest";

import { POST as ingestPost } from "@/app/api/agent-activity/ingest/route";
import { GET as decisionsGet } from "@/app/api/runtime/decisions/route";
import { POST as markProcessedPost } from "@/app/api/runtime/decisions/[id]/processed/route";
import { db } from "@/lib/db";

const TOKEN = "pilot-sync-token";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${TOKEN}`,
  };
}

function makeRequest(url: string, body: Record<string, unknown>, method = "POST") {
  return new Request(url, {
    method,
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
}

function makeGetRequest(url: string) {
  return new Request(url, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
}

beforeEach(() => {
  db.prepare("DELETE FROM approval_items WHERE task_name LIKE 'Phase51%'").run();
  db.prepare("DELETE FROM agent_activity_logs WHERE task_name LIKE 'Phase51%'").run();
  db.prepare(
    "UPDATE system_configs SET value='true' WHERE config_key='reporting.agent_sync_ingest_enabled'",
  ).run();
  db.prepare(
    `UPDATE system_configs SET value='${TOKEN}' WHERE config_key='reporting.agent_sync_ingest_token'`,
  ).run();
  db.prepare(
    "UPDATE system_configs SET value='true' WHERE config_key='sync.runtime_approval_queue_enabled'",
  ).run();
});

// ─── Approval item stores identity fields ────────────────────────────────────

describe("approval item identity fields", () => {
  test("ingest stores sdlc_task_id on approval_item", async () => {
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "task_completed",
        task_name: "Phase51:IdentityTask",
        status: "waiting_approval",
        summary: "Backend API ready for review",
        sdlc_task_id: "p1-E001-T003",
        project_id: "p1",
        discord_message_id: "111222333444",
      }),
    );

    const row = db
      .prepare("SELECT * FROM approval_items WHERE task_name='Phase51:IdentityTask' LIMIT 1")
      .get() as Record<string, unknown> | undefined;

    expect(row).toBeTruthy();
    expect(row!.sdlc_task_id).toBe("p1-E001-T003");
    expect(row!.project_id).toBe("p1");
    expect(row!.discord_message_id).toBe("111222333444");
    expect(row!.source_runtime).toBe("discord");
    expect(row!.processed_by_runtime_at).toBeNull();
    expect(row!.runtime_processed_status).toBeNull();
  });

  test("ingest without identity fields defaults to empty strings", async () => {
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "task_completed",
        task_name: "Phase51:NoIdentity",
        status: "waiting_approval",
        summary: "Task done",
      }),
    );

    const row = db
      .prepare("SELECT * FROM approval_items WHERE task_name='Phase51:NoIdentity' LIMIT 1")
      .get() as Record<string, unknown> | undefined;

    expect(row).toBeTruthy();
    expect(row!.sdlc_task_id).toBe("");
    expect(row!.project_id).toBe("");
    expect(row!.processed_by_runtime_at).toBeNull();
  });
});

// ─── Runtime decisions endpoint — unprocessed filter ─────────────────────────

describe("runtime decisions: unprocessed filter", () => {
  test("returns only unprocessed decisions", async () => {
    // Create two approved items — one processed, one not
    const now = new Date().toISOString();
    db.prepare(`
      INSERT INTO approval_items
        (role_key, task_name, status, summary, requested_by, created_at, updated_at,
         sdlc_task_id, project_id, processed_by_runtime_at)
      VALUES ('dev','Phase51:Unprocessed','approved','done','dev',?,?,?,'',NULL)
    `).run(now, now, "p1-E001-T010");

    db.prepare(`
      INSERT INTO approval_items
        (role_key, task_name, status, summary, requested_by, created_at, updated_at,
         sdlc_task_id, project_id, processed_by_runtime_at)
      VALUES ('dev','Phase51:AlreadyProcessed','approved','done','dev',?,?,?,'',?)
    `).run(now, now, "p1-E001-T011", now);

    const resp = await decisionsGet(makeGetRequest("http://localhost/api/runtime/decisions"));
    expect(resp.status).toBe(200);
    const data = (await resp.json()) as { items: Array<{ task_name: string }> };

    const names = data.items.map((i) => i.task_name);
    expect(names).toContain("Phase51:Unprocessed");
    expect(names).not.toContain("Phase51:AlreadyProcessed");
  });

  test("includes identity fields in response", async () => {
    const now = new Date().toISOString();
    db.prepare(`
      INSERT INTO approval_items
        (role_key, task_name, status, summary, requested_by, created_at, updated_at,
         sdlc_task_id, project_id, discord_message_id, processed_by_runtime_at)
      VALUES ('dev','Phase51:WithIdentity','approved','done','dev',?,?,?,?,'999888',NULL)
    `).run(now, now, "p-id-xyz", "p99");

    const resp = await decisionsGet(makeGetRequest("http://localhost/api/runtime/decisions"));
    const data = (await resp.json()) as { items: Array<Record<string, unknown>> };
    const item = data.items.find((i) => i.task_name === "Phase51:WithIdentity");

    expect(item).toBeTruthy();
    expect(item!.sdlc_task_id).toBe("p-id-xyz");
    expect(item!.project_id).toBe("p99");
    expect(item!.discord_message_id).toBe("999888");
  });

  test("bot restart (since_id=0) does not re-surface processed items", async () => {
    const now = new Date().toISOString();
    db.prepare(`
      INSERT INTO approval_items
        (role_key, task_name, status, summary, requested_by, created_at, updated_at,
         sdlc_task_id, processed_by_runtime_at)
      VALUES ('dev','Phase51:RestartSafe','approved','done','dev',?,?,'p-restart',?)
    `).run(now, now, now);

    // Simulate bot restart: since_id=0 (no memory of last_id)
    const resp = await decisionsGet(
      makeGetRequest("http://localhost/api/runtime/decisions?since_id=0"),
    );
    const data = (await resp.json()) as { items: Array<{ task_name: string }> };
    const names = data.items.map((i) => i.task_name);
    expect(names).not.toContain("Phase51:RestartSafe");
  });
});

// ─── Mark-processed endpoint ─────────────────────────────────────────────────

describe("mark-processed endpoint", () => {
  test("sets processed_by_runtime_at on the approval item", async () => {
    const now = new Date().toISOString();
    const info = db.prepare(`
      INSERT INTO approval_items
        (role_key, task_name, status, summary, requested_by, created_at, updated_at,
         sdlc_task_id, processed_by_runtime_at)
      VALUES ('dev','Phase51:MarkMe','approved','done','dev',?,?,'t-mark',NULL)
    `).run(now, now) as { lastInsertRowid: number };

    const resp = await markProcessedPost(
      makeRequest(`http://localhost/api/runtime/decisions/${info.lastInsertRowid}/processed`, {
        status: "approved",
      }),
      { params: Promise.resolve({ id: String(info.lastInsertRowid) }) },
    );

    expect(resp.status).toBe(200);
    const body = (await resp.json()) as Record<string, unknown>;
    expect(body.success).toBe(true);
    expect(body.approval_id).toBe(info.lastInsertRowid);

    const row = db
      .prepare("SELECT processed_by_runtime_at, runtime_processed_status FROM approval_items WHERE id=?")
      .get(info.lastInsertRowid) as Record<string, unknown>;

    expect(row.processed_by_runtime_at).not.toBeNull();
    expect(row.runtime_processed_status).toBe("approved");
  });

  test("returns 404 for non-existent item", async () => {
    const resp = await markProcessedPost(
      makeRequest("http://localhost/api/runtime/decisions/999999/processed", {
        status: "approved",
      }),
      { params: Promise.resolve({ id: "999999" }) },
    );
    expect(resp.status).toBe(404);
  });

  test("returns 401 without token", async () => {
    const resp = await markProcessedPost(
      new Request("http://localhost/api/runtime/decisions/1/processed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "approved" }),
      }),
      { params: Promise.resolve({ id: "1" }) },
    );
    expect(resp.status).toBe(401);
  });
});

// ─── Discord ingest decision sync-back by sdlc_task_id ───────────────────────

describe("discord decision sync-back by sdlc_task_id", () => {
  test("uses sdlc_task_id to find matching approval item for sync-back", async () => {
    // Step 1: create approval item with sdlc_task_id
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "task_completed",
        task_name: "Phase51:SyncByIdTask",
        status: "waiting_approval",
        summary: "waiting for review",
        sdlc_task_id: "proj-sync-T007",
        project_id: "proj-sync",
      }),
    );

    const beforeRow = db
      .prepare("SELECT id, status FROM approval_items WHERE task_name='Phase51:SyncByIdTask' LIMIT 1")
      .get() as Record<string, unknown>;
    expect(beforeRow.status).toBe("waiting_approval");

    // Step 2: Discord approves — sends approved event with sdlc_task_id
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "approved",
        task_name: "Phase51:SyncByIdTask",
        status: "approved",
        summary: "Approved via Discord !approve",
        sdlc_task_id: "proj-sync-T007",
      }),
    );

    const afterRow = db
      .prepare("SELECT status, approver, processed_by_runtime_at FROM approval_items WHERE id=?")
      .get(beforeRow.id) as Record<string, unknown>;

    expect(afterRow.status).toBe("approved");
    expect(afterRow.approver).toBe("discord");
    // item should be marked processed after discord sync
    expect(afterRow.processed_by_runtime_at).not.toBeNull();
  });

  test("duplicate task names across projects do not collide", async () => {
    // Two tasks with same title in different projects
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "task_completed",
        task_name: "Phase51:SharedName",
        status: "waiting_approval",
        summary: "Project A task",
        sdlc_task_id: "projA-E001-T001",
        project_id: "projA",
      }),
    );
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "task_completed",
        task_name: "Phase51:SharedName",
        status: "waiting_approval",
        summary: "Project B task",
        sdlc_task_id: "projB-E001-T001",
        project_id: "projB",
      }),
    );

    // Discord approves only projB's task
    await ingestPost(
      makeRequest("http://localhost/api/agent-activity/ingest", {
        role_key: "dev",
        event_type: "approved",
        task_name: "Phase51:SharedName",
        status: "approved",
        summary: "Project B approved",
        sdlc_task_id: "projB-E001-T001",
      }),
    );

    const projARow = db
      .prepare("SELECT status FROM approval_items WHERE sdlc_task_id='projA-E001-T001' LIMIT 1")
      .get() as Record<string, unknown> | undefined;
    const projBRow = db
      .prepare("SELECT status FROM approval_items WHERE sdlc_task_id='projB-E001-T001' LIMIT 1")
      .get() as Record<string, unknown> | undefined;

    expect(projARow?.status).toBe("waiting_approval"); // projA untouched
    expect(projBRow?.status).toBe("approved"); // projB correctly approved
  });
});
