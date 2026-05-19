import { NextResponse } from "next/server";

import {
  createAgentActivityLog,
  createApprovalItem,
  findApprovalItemBySdlcTaskId,
  findLatestPendingApprovalItem,
  findSystemConfigByKey,
  markApprovalItemProcessed,
  updateApprovalDecision,
  upsertProjectHotCache,
} from "@/lib/agents/query";

function readSyncToken(request: Request) {
  const authHeader = request.headers.get("authorization");

  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice("Bearer ".length).trim();
  }

  return request.headers.get("x-agent-sync-token")?.trim() ?? "";
}

export async function POST(request: Request) {
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");

  if (syncEnabled?.value !== "true" || !expectedToken?.value) {
    return NextResponse.json(
      {
        success: false,
        code: "SYNC_DISABLED",
      },
      { status: 403 },
    );
  }

  const receivedToken = readSyncToken(request);

  if (!receivedToken || receivedToken !== expectedToken.value) {
    return NextResponse.json(
      {
        success: false,
        code: "UNAUTHORIZED",
      },
      { status: 401 },
    );
  }

  const body = (await request.json()) as {
    role_key?: string;
    event_type?: string;
    task_name?: string;
    status?: string;
    summary?: string;
    artifact_ref?: string;
    channel_target?: string;
    hot_cache_title?: string;
    hot_cache_summary?: string;
    hot_cache_scope?: string;
    hot_cache_status?: string;
    hot_cache_key?: string;
    // Identity fields for exact Discord/SDLC task mapping
    sdlc_task_id?: string;
    project_id?: string;
    role_task_id?: string;
    discord_message_id?: string;
  };

  const roleKey = body.role_key?.trim().toLowerCase() ?? "";
  const eventType = body.event_type?.trim() ?? "";
  const taskName = body.task_name?.trim() ?? "";
  const status = body.status?.trim() ?? "";
  const summary = body.summary?.trim() ?? "";

  if (!roleKey || !eventType || !taskName || !status || !summary) {
    return NextResponse.json(
      {
        success: false,
        code: "VALIDATION_ERROR",
      },
      { status: 400 },
    );
  }

  const created = createAgentActivityLog({
    roleKey,
    eventType,
    taskName,
    status,
    summary,
    artifactRef: body.artifact_ref?.trim(),
    channelTarget: body.channel_target?.trim() ?? "project-sync",
  });

  if (created && status === "waiting_approval") {
    createApprovalItem({
      roleKey,
      taskName,
      summary,
      artifactRef: body.artifact_ref?.trim(),
      outputSummary: summary,
      requestedBy: roleKey,
      channelTarget: body.channel_target?.trim() ?? "project-sync",
      projectId: body.project_id?.trim() ?? "",
      sdlcTaskId: body.sdlc_task_id?.trim() ?? "",
      roleTaskId: body.role_task_id?.trim() ?? "",
      discordMessageId: body.discord_message_id?.trim() ?? "",
      sourceRuntime: "discord",
    });
  }

  // Sync Discord decisions back to webapp approval_items
  const DECISION_EVENT_MAP: Record<string, "approved" | "rejected" | "rework_requested"> = {
    approved: "approved",
    rejected: "rejected",
    revision_requested: "rework_requested",
  };
  const decisionStatus = DECISION_EVENT_MAP[eventType];
  if (created && decisionStatus) {
    // Prefer exact lookup by sdlc_task_id; fall back to role+name for legacy items
    const sdlcTaskId = body.sdlc_task_id?.trim() ?? "";
    const item = sdlcTaskId
      ? (findApprovalItemBySdlcTaskId(sdlcTaskId) ?? findLatestPendingApprovalItem(roleKey, taskName))
      : findLatestPendingApprovalItem(roleKey, taskName);
    if (item) {
      updateApprovalDecision({
        id: item.id,
        status: decisionStatus,
        approver: "discord",
        decisionNote: summary,
      });
      // Mark as processed so the bot poll loop skips it on restart
      markApprovalItemProcessed(item.id, decisionStatus);
    }
  }

  const hotCacheEnabled = findSystemConfigByKey("project.hot_cache_enabled");
  const hotCacheSummary = body.hot_cache_summary?.trim();

  if (created && hotCacheEnabled?.value === "true" && hotCacheSummary) {
    upsertProjectHotCache({
      cacheKey: body.hot_cache_key?.trim() || "current_project",
      title: body.hot_cache_title?.trim() || taskName,
      summary: hotCacheSummary,
      scope: body.hot_cache_scope?.trim() || "global",
      status: body.hot_cache_status?.trim() || status,
      sourceRole: roleKey,
      artifactRef: body.artifact_ref?.trim(),
    });
  }

  return NextResponse.json({
    success: created,
    status: created ? "logged" : "ignored",
  });
}
