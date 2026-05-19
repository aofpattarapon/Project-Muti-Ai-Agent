import { NextResponse } from "next/server";

import { listApprovalItems, listRecentAgentActivityLogs } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

function escapeCsv(value: string | null | undefined) {
  const normalized = value ?? "";
  return `"${normalized.replace(/"/g, '""')}"`;
}

function buildTaskRows() {
  const logs = listRecentAgentActivityLogs(500);
  const pendingApprovals = listApprovalItems("waiting_approval");
  const taskMap = new Map<
    string,
    {
      taskName: string;
      currentRole: string;
      status: string;
      summary: string;
      artifactRef: string | null;
      channelTarget: string | null;
      waitingApproval: boolean;
      updatedAt: string;
    }
  >();

  for (const log of logs) {
    if (taskMap.has(log.taskName)) {
      continue;
    }

    taskMap.set(log.taskName, {
      taskName: log.taskName,
      currentRole: log.roleKey,
      status: log.status,
      summary: log.summary,
      artifactRef: log.artifactRef,
      channelTarget: log.channelTarget,
      waitingApproval: pendingApprovals.some((item) => item.taskName === log.taskName),
      updatedAt: log.createdAt,
    });
  }

  return Array.from(taskMap.values()).sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );
}

export async function GET(request: Request) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (session.role !== "Admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const { searchParams } = new URL(request.url);
  const format = searchParams.get("format")?.trim().toLowerCase() ?? "csv";
  const tasks = buildTaskRows();

  if (format === "json") {
    return NextResponse.json({
      success: true,
      exported_at: new Date().toISOString(),
      count: tasks.length,
      items: tasks,
    });
  }

  const rows = [
    ["task", "current_role", "status", "summary", "artifact", "target", "waiting_approval", "updated_at"].join(","),
    ...tasks.map((task) =>
      [
        escapeCsv(task.taskName),
        escapeCsv(task.currentRole),
        escapeCsv(task.status),
        escapeCsv(task.summary),
        escapeCsv(task.artifactRef),
        escapeCsv(task.channelTarget),
        escapeCsv(String(task.waitingApproval)),
        escapeCsv(task.updatedAt),
      ].join(","),
    ),
  ];

  return new NextResponse(rows.join("\n"), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="workboard-export.csv"',
    },
  });
}
