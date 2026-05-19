import { NextResponse } from "next/server";

import { listRecentAgentActivityLogs } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

function escapeCsv(value: string | null | undefined) {
  const normalized = value ?? "";
  return `"${normalized.replace(/"/g, '""')}"`;
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
  const logs = listRecentAgentActivityLogs(500);

  if (format === "json") {
    return NextResponse.json({
      success: true,
      exported_at: new Date().toISOString(),
      count: logs.length,
      items: logs,
    });
  }

  const rows = [
    ["role", "event", "task", "status", "summary", "artifact", "target", "when"].join(","),
    ...logs.map((log) =>
      [
        escapeCsv(log.roleKey),
        escapeCsv(log.eventType),
        escapeCsv(log.taskName),
        escapeCsv(log.status),
        escapeCsv(log.summary),
        escapeCsv(log.artifactRef),
        escapeCsv(log.channelTarget),
        escapeCsv(log.createdAt),
      ].join(","),
    ),
  ];

  return new NextResponse(rows.join("\n"), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="project-logs-export.csv"',
    },
  });
}
