import { describe, expect, test } from "vitest";

import {
  createAgentActivityLog,
  createAgentRoleConfig,
  createSystemConfig,
  deleteAgentRoleConfig,
  deleteSystemConfig,
  findAgentRoleConfig,
  findProjectHotCache,
  findSystemConfigById,
  listAgentRoleConfigs,
  listProjectHotCache,
  listRecentAgentActivityLogs,
  listSystemConfigs,
  upsertProjectHotCache,
  updateAgentRoleConfig,
  updateSystemConfig,
} from "@/lib/agents/query";

describe("agent back-office queries", () => {
  test("lists seeded agent role configs", () => {
    const configs = listAgentRoleConfigs();

    expect(configs.some((config) => config.roleKey === "ceo")).toBe(true);
    expect(configs.some((config) => config.roleKey === "uxui")).toBe(true);
    expect(configs.some((config) => config.claudeDesignAccess)).toBe(true);
  });

  test("creates, updates, and deletes a custom agent role config", () => {
    const roleKey = "research";

    deleteAgentRoleConfig(roleKey);

    expect(
      createAgentRoleConfig({
        roleKey,
        displayName: "Research",
        responsibility: "Research and synthesize inputs.",
        primaryModel: "anthropic/claude-haiku-4-5",
        escalationModel: "anthropic/claude-sonnet-4-5",
        discordBotToken: "discord-token",
        discordChannelIds: "research-room,report-output",
        skillTags: ["requirements", "custom"],
        workingRules: "Reuse the active project hot cache when the task is part of the same project.",
        claudeDesignAccess: true,
        harnessEnabled: true,
        hotCacheEnabled: true,
        harnessProfile: "research-harness",
        logicSummary: "Collect data and summarize.",
        reportingSummary: "Report findings and references.",
        outputMode: "discord-and-project",
        isActive: true,
      }),
    ).toBe(true);

    expect(findAgentRoleConfig(roleKey)?.displayName).toBe("Research");

    expect(
      updateAgentRoleConfig(roleKey, {
        displayName: "Research Ops",
        responsibility: "Research and synthesize inputs.",
        primaryModel: "anthropic/claude-haiku-4-5",
        escalationModel: "anthropic/claude-sonnet-4-5",
        discordBotToken: "",
        discordChannelIds: "research-room",
        skillTags: ["custom"],
        workingRules: "Ask before resetting the hot cache.",
        claudeDesignAccess: false,
        harnessEnabled: true,
        hotCacheEnabled: false,
        harnessProfile: "research-harness",
        logicSummary: "Collect data and summarize.",
        reportingSummary: "Report findings and references.",
        outputMode: "project-only",
        isActive: false,
      }),
    ).toBe(true);

    const updated = findAgentRoleConfig(roleKey);
    expect(updated?.displayName).toBe("Research Ops");
    expect(updated?.claudeDesignAccess).toBe(false);
    expect(updated?.skillTags).toEqual(["custom"]);
    expect(updated?.outputMode).toBe("project-only");
    expect(updated?.hotCacheEnabled).toBe(false);
    expect(updated?.isActive).toBe(false);

    expect(deleteAgentRoleConfig(roleKey)).toBe(true);
    expect(findAgentRoleConfig(roleKey)).toBeNull();
  });

  test("stores project-visible agent activity logs", () => {
    expect(
      createAgentActivityLog({
        roleKey: "ceo",
        eventType: "pilot.test",
        taskName: "Audit Export CSV",
        status: "waiting_approval",
        summary: "Pilot reached implementation gate and stopped.",
        artifactRef: "pilot.audit-export",
        channelTarget: "project-db",
      }),
    ).toBe(true);

    const logs = listRecentAgentActivityLogs(5);
    expect(logs.some((log) => log.eventType === "pilot.test")).toBe(true);
  });

  test("creates, updates, and deletes a system config", () => {
    const existing = listSystemConfigs().find((item) => item.configKey === "tmp.test.config");

    if (existing) {
      deleteSystemConfig(existing.id);
    }

    createSystemConfig({
      configKey: "tmp.test.config",
      category: "test",
      value: "on",
      description: "Temporary test config",
    });

    const config = listSystemConfigs().find((item) => item.configKey === "tmp.test.config");
    expect(config).toBeTruthy();

    expect(
      updateSystemConfig(config!.id, {
        configKey: "tmp.test.config",
        category: "test",
        value: "off",
        description: "Updated temporary test config",
      }),
    ).toBe(true);

    expect(findSystemConfigById(config!.id)?.value).toBe("off");
    expect(deleteSystemConfig(config!.id)).toBe(true);
    expect(findSystemConfigById(config!.id)).toBeNull();
  });

  test("updates project hot cache for the active project", () => {
    expect(
      upsertProjectHotCache({
        cacheKey: "current_project",
        title: "Audit export pilot",
        summary: "The active project is the audit export flow with approval before implementation.",
        scope: "global",
        status: "active",
        sourceRole: "ceo",
        artifactRef: "ceo.route.package",
      }),
    ).toBe(true);

    expect(findProjectHotCache("current_project")?.title).toBe("Audit export pilot");
    expect(listProjectHotCache().length).toBeGreaterThan(0);
  });
});
