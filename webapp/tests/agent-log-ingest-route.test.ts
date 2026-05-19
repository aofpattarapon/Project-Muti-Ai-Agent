import { beforeEach, describe, expect, test } from "vitest";

import { POST as ingestAgentLogPost } from "@/app/api/agent-activity/ingest/route";
import { db } from "@/lib/db";

describe("agent log ingest route", () => {
  beforeEach(() => {
    db.prepare("DELETE FROM agent_activity_logs WHERE event_type = 'sync.test'").run();
    db.prepare("DELETE FROM approval_items WHERE task_name = 'Pilot'").run();
    db.prepare(
      "UPDATE system_configs SET value = 'true' WHERE config_key = 'reporting.agent_sync_ingest_enabled'",
    ).run();
    db.prepare(
      "UPDATE system_configs SET value = 'pilot-sync-token' WHERE config_key = 'reporting.agent_sync_ingest_token'",
    ).run();
  });

  test("rejects unauthorized sync token", async () => {
    const response = await ingestAgentLogPost(
      new Request("http://localhost:3000/api/agent-activity/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer wrong-token",
        },
        body: JSON.stringify({
          role_key: "ceo",
          event_type: "sync.test",
          task_name: "Pilot",
          status: "started",
          summary: "Testing sync endpoint.",
        }),
      }),
    );

    expect(response.status).toBe(401);
  });

  test("stores synced agent log in the project database", async () => {
    const response = await ingestAgentLogPost(
      new Request("http://localhost:3000/api/agent-activity/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer pilot-sync-token",
        },
        body: JSON.stringify({
          role_key: "ceo",
          event_type: "sync.test",
          task_name: "Pilot",
          status: "waiting_approval",
          summary: "CEO routed work and paused at approval gate.",
          artifact_ref: "ceo.route.package",
          channel_target: "project-sync",
          hot_cache_title: "Pilot",
          hot_cache_summary: "Pilot project is active and paused for approval.",
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      success: true,
      status: "logged",
    });

    const row = db
      .prepare(
        `
          SELECT COUNT(*) as count
          FROM agent_activity_logs
          WHERE event_type = 'sync.test' AND role_key = 'ceo'
        `,
      )
      .get() as { count: number };

    expect(row.count).toBe(1);

    const approvalRow = db
      .prepare(
        `
          SELECT COUNT(*) as count
          FROM approval_items
          WHERE task_name = 'Pilot' AND status = 'waiting_approval'
        `,
      )
      .get() as { count: number };

    expect(approvalRow.count).toBe(1);

    const cacheRow = db
      .prepare(
        `
          SELECT summary
          FROM project_hot_cache
          WHERE cache_key = 'current_project'
          LIMIT 1
        `,
      )
      .get() as { summary: string };

    expect(cacheRow.summary).toBe("Pilot project is active and paused for approval.");
  });
});
