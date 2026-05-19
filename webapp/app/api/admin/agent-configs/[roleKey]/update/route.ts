import { NextResponse } from "next/server";

import {
  createAgentActivityLog,
  findAgentRoleConfig,
  updateAgentRoleConfig,
} from "@/lib/agents/query";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

function readSkillTags(formData: FormData) {
  return formData
    .getAll("skill_tags")
    .map((value) => String(value).trim())
    .filter(Boolean);
}

type RouteContext = {
  params: Promise<{
    roleKey: string;
  }>;
};

export async function POST(request: Request, context: RouteContext) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session.role !== "Admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const { roleKey } = await context.params;
  const existing = findAgentRoleConfig(roleKey);

  if (!existing) {
    return NextResponse.redirect(new URL("/agents", request.url));
  }

  const formData = await request.formData();

  updateAgentRoleConfig(roleKey, {
    displayName: String(formData.get("display_name") ?? "").trim(),
    responsibility: String(formData.get("responsibility") ?? "").trim(),
    primaryModel: String(formData.get("primary_model") ?? "").trim(),
    escalationModel: String(formData.get("escalation_model") ?? "").trim(),
    discordBotToken: String(formData.get("discord_bot_token") ?? "").trim(),
    discordChannelIds: String(formData.get("discord_channel_ids") ?? "").trim(),
    skillTags: readSkillTags(formData),
    workingRules: String(formData.get("working_rules") ?? "").trim(),
    claudeDesignAccess: formData.get("claude_design_access") === "true",
    harnessEnabled: formData.get("harness_enabled") === "true",
    hotCacheEnabled: formData.get("hot_cache_enabled") === "true",
    harnessProfile: String(formData.get("harness_profile") ?? "").trim(),
    logicSummary: String(formData.get("logic_summary") ?? "").trim(),
    reportingSummary: String(formData.get("reporting_summary") ?? "").trim(),
    outputMode: String(formData.get("output_mode") ?? "").trim(),
    isActive: formData.get("is_active") === "true",
  });

  recordAuditEvent(
    "agent_config.updated",
    `Agent role config ${roleKey} updated.`,
    session.username,
  );

  createAgentActivityLog({
    roleKey,
    eventType: "config.updated",
    taskName: "Agent control back-office",
    status: "updated",
    summary: `Role config ${existing.displayName} was updated from the project back-office.`,
    artifactRef: `${roleKey}.config`,
    channelTarget: "project-db",
  });

  return NextResponse.redirect(new URL("/agents", request.url));
}
