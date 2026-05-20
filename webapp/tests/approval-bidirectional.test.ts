/**
 * Hotfix tests — bi-directional SDLC approvals
 *
 * Tests:
 *  - Approval item stores discord_message_id from the approve channel (not output)
 *  - Discord !approve ingest updates matching approval_item by sdlc_task_id
 *  - Web approval decision is returned by decisions endpoint
 *  - Contract-failed tasks (status="blocked") do NOT create approval_items
 *  - Source_runtime field is set to "discord" on ingest-created items
 */

import { beforeEach, describe, expect, test } from "vitest";

import { POST as ingestPost } from "@/app/api/agent-activity/ingest/route";
import { GET as decisionsGet } from "@/app/api/runtime/decisions/route";
import { db } from "@/lib/db";

const TOKEN = "pilot-sync-token";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${TOKEN}`,
  };
}

function makeIngestRequest(body: Record<string, unknown>) {
  return new Request("http://localhost/api/agent-activity/ingest", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  db.prepare("DELETE FROM approval_items WHERE task_name LIKE 'BidirTest%'").run();
  db.prepare("DELETE FROM agent_activity_logs WHERE task_name LIKE 'BidirTest%'").run();
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

// ─── Approval item stores approve-channel message id ─────────────────────────

describe("approval item stores approve-channel discord_message_id", () => {
  test("ingest with discord_message_id from approve channel stores it on approval_item", async () => {
    const APPROVE_CHANNEL_MSG_ID = "777888999000";

    await ingestPost(
      makeIngestRequest({
        role_key: "pm",
        event_type: "task_completed",
        task_name: "BidirTest:ApproveCard",
        status: "waiting_approval",
        summary: "PM charter ready for review",
        sdlc_task_id: "P10-PROJECT-PM01",
        project_id: "P10",
        discord_message_id: APPROVE_CHANNEL_MSG_ID,
      }),
    );

    const row = db
      .prepare("SELECT * FROM approval_items WHERE task_name='BidirTest:ApproveCard' LIMIT 1")
      .get() as Record<string, unknown> | undefined;

    expect(row).toBeTruthy();
    expect(row!.discord_message_id).toBe(APPROVE_CHANNEL_MSG_ID);
    expect(row!.sdlc_task_id).toBe("P10-PROJECT-PM01");
    expect(row!.status).toBe("waiting_approval");
    expect(row!.source_runtime).toBe("discord");
  });
});

// ─── Discord !approve syncs back to approval_item ────────────────────────────

describe("discord !approve syncs to web approval_item by sdlc_task_id", () => {
  test("approved event updates matching approval_item status", async () => {
    // Step 1: task_completed creates the approval_item
    await ingestPost(
      makeIngestRequest({
        role_key: "ba",
        event_type: "task_completed",
        task_name: "BidirTest:DiscordApprove",
        status: "waiting_approval",
        summary: "BRD ready",
        sdlc_task_id: "P11-E001-BA01",
        project_id: "P11",
        discord_message_id: "AAA111BBB222",
      }),
    );

    const beforeRow = db
      .prepare(
        "SELECT id, status FROM approval_items WHERE task_name='BidirTest:DiscordApprove' LIMIT 1",
      )
      .get() as Record<string, unknown>;
    expect(beforeRow.status).toBe("waiting_approval");

    // Step 2: Discord !approve triggers approved ingest event
    await ingestPost(
      makeIngestRequest({
        role_key: "ba",
        event_type: "approved",
        task_name: "BidirTest:DiscordApprove",
        status: "approved",
        summary: "Approved by TestUser#1234",
        sdlc_task_id: "P11-E001-BA01",
        project_id: "P11",
      }),
    );

    const afterRow = db
      .prepare(
        "SELECT status, processed_by_runtime_at FROM approval_items WHERE task_name='BidirTest:DiscordApprove' LIMIT 1",
      )
      .get() as Record<string, unknown>;

    expect(afterRow.status).toBe("approved");
    // Discord-side approval marks it processed immediately
    expect(afterRow.processed_by_runtime_at).not.toBeNull();
  });

  test("revision_requested event updates approval_item to rework_requested", async () => {
    await ingestPost(
      makeIngestRequest({
        role_key: "sa",
        event_type: "task_completed",
        task_name: "BidirTest:Revise",
        status: "waiting_approval",
        summary: "System purpose ready",
        sdlc_task_id: "P12-E001-SA01",
        project_id: "P12",
      }),
    );

    await ingestPost(
      makeIngestRequest({
        role_key: "sa",
        event_type: "revision_requested",
        task_name: "BidirTest:Revise",
        status: "rework_requested",
        summary: "Please add more detail to scope definition",
        sdlc_task_id: "P12-E001-SA01",
        project_id: "P12",
      }),
    );

    const row = db
      .prepare(
        "SELECT status FROM approval_items WHERE task_name='BidirTest:Revise' LIMIT 1",
      )
      .get() as Record<string, unknown>;

    expect(row.status).toBe("rework_requested");
  });
});

// ─── Web approval decisions appear in decisions endpoint ─────────────────────

describe("web decisions endpoint returns decided (non-waiting) approval items", () => {
  test("item decided via web UI appears in decisions endpoint for bot to pick up", async () => {
    // Step 1: Bot posts task_completed → creates waiting_approval item
    await ingestPost(
      makeIngestRequest({
        role_key: "uxui",
        event_type: "task_completed",
        task_name: "BidirTest:WebDecision",
        status: "waiting_approval",
        summary: "User flow diagram complete",
        sdlc_task_id: "P13-E001-UX01",
        project_id: "P13",
        discord_message_id: "DISCORD_APPROVE_MSG_777",
      }),
    );

    // Step 2: Web UI approves — directly update the DB (simulates the /approvals/{id}/decision endpoint)
    const itemRow = db
      .prepare(
        "SELECT id FROM approval_items WHERE task_name='BidirTest:WebDecision' LIMIT 1",
      )
      .get() as { id: number };
    expect(itemRow).toBeTruthy();

    db.prepare(
      "UPDATE approval_items SET status='approved', approver='web-operator', updated_at=? WHERE id=?",
    ).run(new Date().toISOString(), itemRow.id);

    // Step 3: Bot polls decisions endpoint — should see the approved item
    const resp = await decisionsGet(
      new Request("http://localhost/api/runtime/decisions", {
        headers: { Authorization: `Bearer ${TOKEN}` },
      }),
    );
    expect(resp.status).toBe(200);

    const data = (await resp.json()) as {
      items: Array<{
        task_name: string;
        status: string;
        sdlc_task_id: string;
        discord_message_id: string;
      }>;
    };

    const item = data.items.find((i) => i.task_name === "BidirTest:WebDecision");
    expect(item).toBeTruthy();
    expect(item!.status).toBe("approved");
    expect(item!.sdlc_task_id).toBe("P13-E001-UX01");
    // discord_message_id is preserved so bot can reply to the correct approve-channel message
    expect(item!.discord_message_id).toBe("DISCORD_APPROVE_MSG_777");
  });
});

// ─── Contract-failed tasks must not create approval_items ────────────────────

describe("contract-failed tasks (status=blocked) do not create approval_items", () => {
  test("ingest with status=blocked creates activity log but no approval_item", async () => {
    await ingestPost(
      makeIngestRequest({
        role_key: "pm",
        event_type: "task_completed",
        task_name: "BidirTest:ContractFailed",
        status: "blocked",
        summary: "[contract-failed] Missing section: Constraints",
        sdlc_task_id: "P14-PROJECT-PM01",
        project_id: "P14",
      }),
    );

    // Activity log must exist
    const logRow = db
      .prepare(
        "SELECT COUNT(*) as count FROM agent_activity_logs WHERE task_name='BidirTest:ContractFailed'",
      )
      .get() as { count: number };
    expect(logRow.count).toBeGreaterThan(0);

    // No approval_item should be created for "blocked" status
    const approvalRow = db
      .prepare(
        "SELECT COUNT(*) as count FROM approval_items WHERE task_name='BidirTest:ContractFailed'",
      )
      .get() as { count: number };
    expect(approvalRow.count).toBe(0);
  });

  test("validation-failed tasks (status=blocked) are not shown in decisions endpoint", async () => {
    await ingestPost(
      makeIngestRequest({
        role_key: "dev",
        event_type: "task_completed",
        task_name: "BidirTest:ValidationFailed",
        status: "blocked",
        summary: "Validation failed: missing required section",
        sdlc_task_id: "P15-E001-DE01",
        project_id: "P15",
      }),
    );

    const resp = await decisionsGet(
      new Request("http://localhost/api/runtime/decisions", {
        headers: { Authorization: `Bearer ${TOKEN}` },
      }),
    );
    const data = (await resp.json()) as { items: Array<{ task_name: string }> };
    const names = data.items.map((i) => i.task_name);
    expect(names).not.toContain("BidirTest:ValidationFailed");
  });
});
