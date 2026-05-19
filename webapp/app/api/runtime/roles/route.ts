import { NextResponse } from "next/server";

import { findSystemConfigByKey, listAgentRoleConfigs } from "@/lib/agents/query";

function readSyncToken(request: Request) {
  const authHeader = request.headers.get("authorization");

  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice("Bearer ".length).trim();
  }

  return request.headers.get("x-agent-sync-token")?.trim() ?? "";
}

function isRuntimeAuthorized(receivedToken: string) {
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");

  if (syncEnabled?.value !== "true" || !expectedToken?.value) {
    return false;
  }

  return !!receivedToken && receivedToken === expectedToken.value;
}

function parseChannelIds(value: string) {
  return value
    .split(/[\n,]+/)
    .map((channelId) => channelId.trim())
    .filter((channelId) => channelId.length > 0);
}

export async function GET(request: Request) {
  const receivedToken = readSyncToken(request);

  if (!isRuntimeAuthorized(receivedToken)) {
    return NextResponse.json(
      {
        success: false,
        code: "UNAUTHORIZED",
      },
      { status: 401 },
    );
  }

  const roles = listAgentRoleConfigs()
    .filter((role) => role.isActive)
    .map((role) => ({
      role_key: role.roleKey,
      display_name: role.displayName,
      responsibility: role.responsibility,
      primary_model: role.primaryModel,
      escalation_model: role.escalationModel,
      channel_ids: parseChannelIds(role.discordChannelIds),
      skill_tags: role.skillTags,
      working_rules: role.workingRules,
      claude_design_access: role.claudeDesignAccess,
      harness_enabled: role.harnessEnabled,
      hot_cache_enabled: role.hotCacheEnabled,
      harness_profile: role.harnessProfile,
      logic_summary: role.logicSummary,
      reporting_summary: role.reportingSummary,
      output_mode: role.outputMode,
      updated_at: role.updatedAt,
    }));

  return NextResponse.json({
    success: true,
    count: roles.length,
    roles,
  });
}
