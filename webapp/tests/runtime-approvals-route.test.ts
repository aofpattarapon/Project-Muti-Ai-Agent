import { beforeEach, describe, expect, test } from "vitest";

import { POST as ingestAgentLogPost } from "@/app/api/agent-activity/ingest/route";
import { POST as runtimeApprovalDecisionPost } from "@/app/api/runtime/approvals/[id]/decision/route";
import { GET as runtimePendingApprovalsGet } from "@/app/api/runtime/approvals/pending/route";
import { db } from "@/lib/db";

describe("runtime approvals routes", () => {
  beforeEach(async () => {
    db.prepare("DELETE FROM approval_items WHERE task_name = 'Runtime Pilot'").run();
    db.prepare("DELETE FROM agent_activity_logs WHERE task_name = 'Runtime Pilot'").run();
    db.prepare(
      "UPDATE system_configs SET value = 'true' WHERE config_key = 'reporting.agent_sync_ingest_enabled'",
    ).run();
    db.prepare(
      "UPDATE system_configs SET value = 'pilot-sync-token' WHERE config_key = 'reporting.agent_sync_ingest_token'",
    ).run();

    await ingestAgentLogPost(
      new Request("http://localhost:3000/api/agent-activity/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer pilot-sync-token",
        },
        body: JSON.stringify({
          role_key: "ceo",
          event_type: "runtime.seed",
          task_name: "Runtime Pilot",
          status: "waiting_approval",
          summary: "Seeded approval item for runtime testing.",
          artifact_ref: "runtime.seed.package",
          channel_target: "ceo-room",
        }),
      }),
    );
  });

  test("lists pending approvals for authorized runtime clients", async () => {
    const response = await runtimePendingApprovalsGet(
      new Request("http://localhost:3000/api/runtime/approvals/pending", {
        headers: {
          Authorization: "Bearer pilot-sync-token",
        },
      }),
    );

    expect(response.status).toBe(200);

    const payload = (await response.json()) as {
      success: boolean;
      count: number;
      items: Array<{ taskName: string; recent_logs: unknown[] }>;
    };

    expect(payload.success).toBe(true);
    expect(payload.count).toBeGreaterThanOrEqual(1);
    const runtimePilot = payload.items.find((item) => item.taskName === "Runtime Pilot");

    expect(runtimePilot).toBeTruthy();
    expect(runtimePilot?.recent_logs.length).toBeGreaterThan(0);
  });

  test("records runtime approval decisions", async () => {
    const approval = db
      .prepare(
        `
          SELECT id
          FROM approval_items
          WHERE task_name = 'Runtime Pilot'
          ORDER BY id DESC
          LIMIT 1
        `,
      )
      .get() as { id: number };

    const response = await runtimeApprovalDecisionPost(
      new Request(`http://localhost:3000/api/runtime/approvals/${approval.id}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer pilot-sync-token",
        },
        body: JSON.stringify({
          decision: "rework_requested",
          decision_note: "Please tighten the acceptance criteria before implementation.",
          approver: "discord-owner",
          source: "discord",
        }),
      }),
      {
        params: Promise.resolve({
          id: String(approval.id),
        }),
      },
    );

    expect(response.status).toBe(200);

    const updatedApproval = db
      .prepare(
        `
          SELECT status, approver, decision_note
          FROM approval_items
          WHERE id = ?
          LIMIT 1
        `,
      )
      .get(approval.id) as {
      status: string;
      approver: string;
      decision_note: string;
    };

    expect(updatedApproval.status).toBe("rework_requested");
    expect(updatedApproval.approver).toBe("discord-owner");
    expect(updatedApproval.decision_note).toContain("acceptance criteria");

    const logRow = db
      .prepare(
        `
          SELECT COUNT(*) as count
          FROM agent_activity_logs
          WHERE task_name = 'Runtime Pilot'
            AND event_type = 'approval.discord_decision'
            AND status = 'rework_requested'
        `,
      )
      .get() as { count: number };

    expect(logRow.count).toBe(1);
  });
});
