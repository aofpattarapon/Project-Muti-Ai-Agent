import { beforeEach, describe, expect, test } from "vitest";

import { GET as runtimeRolesGet } from "@/app/api/runtime/roles/route";
import { db } from "@/lib/db";

describe("runtime role map route", () => {
  beforeEach(() => {
    db.prepare(
      "UPDATE system_configs SET value = 'true' WHERE config_key = 'reporting.agent_sync_ingest_enabled'",
    ).run();
    db.prepare(
      "UPDATE system_configs SET value = 'pilot-sync-token' WHERE config_key = 'reporting.agent_sync_ingest_token'",
    ).run();
    db.prepare(
      "UPDATE agent_role_configs SET discord_channel_ids = '150000000000000001,150000000000000002' WHERE role_key = 'ceo'",
    ).run();
  });

  test("returns active runtime role mappings for authorized clients", async () => {
    const response = await runtimeRolesGet(
      new Request("http://localhost:3000/api/runtime/roles", {
        headers: {
          Authorization: "Bearer pilot-sync-token",
        },
      }),
    );

    expect(response.status).toBe(200);

    const payload = (await response.json()) as {
      success: boolean;
      count: number;
      roles: Array<{
        role_key: string;
        channel_ids: string[];
        harness_enabled: boolean;
      }>;
    };

    expect(payload.success).toBe(true);
    expect(payload.count).toBeGreaterThanOrEqual(8);

    const ceo = payload.roles.find((role) => role.role_key === "ceo");

    expect(ceo).toBeTruthy();
    expect(ceo?.channel_ids).toEqual([
      "150000000000000001",
      "150000000000000002",
    ]);
    expect(typeof ceo?.harness_enabled).toBe("boolean");
  });
});
