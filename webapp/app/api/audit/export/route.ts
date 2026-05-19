import { NextResponse } from "next/server";

import { filterAgentActivityLogs, createAgentActivityLog } from "@/lib/agents/query";
import { getSession } from "@/lib/auth/session";

const AUTHORIZED_ROLES = ["Admin", "CEO", "DevOps", "QA"];
const EXPORT_TIMEOUT_MS = 60000;
const MAX_ROWS = 100000;

function escapeCsv(value: string | null | undefined) {
  const normalized = value ?? "";
  const hasSpecialChars =
    normalized.includes(",") ||
    normalized.includes('"') ||
    normalized.includes("\n") ||
    normalized.includes("\r");
  const hasFormulaChars =
    /^[=+\-@\t]/.test(normalized);

  if (hasSpecialChars || hasFormulaChars) {
    const escaped = normalized.replace(/"/g, '""');
    const prefixed = hasFormulaChars ? `'${escaped}` : escaped;
    return `"${prefixed}"`;
  }

  return normalized;
}

export async function GET(request: Request) {
  const session = await getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!AUTHORIZED_ROLES.includes(session.role)) {
    return NextResponse.json(
      { error: "Access denied. Only Admin, CEO, DevOps, and QA can export audit logs." },
      { status: 403 },
    );
  }

  const { searchParams } = new URL(request.url);
  const startDate = searchParams.get("startDate")?.trim();
  const endDate = searchParams.get("endDate")?.trim();
  const agentId = searchParams.get("agentId")?.trim();
  const eventType = searchParams.get("eventType")?.trim();
  const taskId = searchParams.get("taskId")?.trim();

  if (startDate && endDate) {
    const start = new Date(startDate).getTime();
    const end = new Date(endDate).getTime();
    if (start > end) {
      return NextResponse.json(
        { error: "start_date must not be later than end_date" },
        { status: 400 },
      );
    }
  }

  try {
    const timeoutPromise = new Promise<NextResponse>((resolve) => {
      setTimeout(() => {
        resolve(
          NextResponse.json(
            { error: "Export took too long. Try with a smaller date range." },
            { status: 504 },
          ),
        );
      }, EXPORT_TIMEOUT_MS);
    });

    const exportPromise = Promise.resolve().then(() => {
      const logs = filterAgentActivityLogs({
        startDate,
        endDate,
        agentId,
        eventType,
        taskId,
        limit: MAX_ROWS,
      });

      if (logs.length === MAX_ROWS) {
        return NextResponse.json(
          { error: "Too many results. Please narrow your filters to fewer than 100,000 rows." },
          { status: 400 },
        );
      }

      const csvRows = [
        "timestamp,agent_id,role,event_type,task_id,message,status",
        ...logs.map((log) =>
          [
            escapeCsv(log.createdAt),
            escapeCsv(log.roleKey),
            escapeCsv(log.roleKey),
            escapeCsv(log.eventType),
            escapeCsv(log.taskName),
            escapeCsv(log.summary),
            escapeCsv(log.status),
          ].join(","),
        ),
      ];

      const filename = `audit-export-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.csv`;

      createAgentActivityLog({
        roleKey: session.role,
        eventType: "AUDIT_EXPORT",
        taskName: "audit-export",
        status: "SUCCESS",
        summary: `Exported ${logs.length} audit records`,
      });

      return new NextResponse(csvRows.join("\n"), {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": `attachment; filename="${filename}"`,
          "X-Content-Type-Options": "nosniff",
        },
      });
    });

    return Promise.race([timeoutPromise, exportPromise]);
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to export audit logs" },
      { status: 500 },
    );
  }
}
