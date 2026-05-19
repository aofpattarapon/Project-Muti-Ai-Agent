import { NextResponse } from "next/server";

import {
  findSystemConfigByKey,
  listApprovalItems,
  listRecentAgentActivityLogs,
} from "@/lib/agents/query";

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
  const runtimeApprovalEnabled = findSystemConfigByKey("sync.runtime_approval_queue_enabled");

  if (
    syncEnabled?.value !== "true" ||
    runtimeApprovalEnabled?.value !== "true" ||
    !expectedToken?.value
  ) {
    return false;
  }

  return !!receivedToken && receivedToken === expectedToken.value;
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

  const items = listApprovalItems("waiting_approval").map((item) => ({
    ...item,
    recent_logs: listRecentAgentActivityLogs(50)
      .filter((log) => log.taskName === item.taskName)
      .slice(0, 6),
  }));

  return NextResponse.json({
    success: true,
    count: items.length,
    items,
  });
}
