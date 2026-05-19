/**
 * GET /api/runtime/tasks/[sdlc_task_id]/artifacts
 * Lists all registered artifacts for an SDLC task.
 * Artifact types: output_file, deployment_report, devops_execution_result,
 *   release_notes, qa_execution_result, workspace_manifest, workspace_diff, etc.
 */
import { NextResponse } from "next/server";
import { findSystemConfigByKey, listTaskArtifacts } from "@/lib/agents/query";

type RouteContext = { params: Promise<{ sdlc_task_id: string }> };

function isAuthorized(request: Request): boolean {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const syncEnabled = findSystemConfigByKey("reporting.agent_sync_ingest_enabled");
  const expectedToken = findSystemConfigByKey("reporting.agent_sync_ingest_token");
  return syncEnabled?.value === "true" && !!expectedToken?.value && token === expectedToken.value;
}

export async function GET(request: Request, context: RouteContext) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ success: false, code: "UNAUTHORIZED" }, { status: 401 });
  }

  const { sdlc_task_id } = await context.params;
  if (!sdlc_task_id?.trim()) {
    return NextResponse.json({ success: false, code: "BAD_REQUEST" }, { status: 400 });
  }

  const artifacts = listTaskArtifacts(sdlc_task_id.trim());
  return NextResponse.json({ success: true, sdlc_task_id, count: artifacts.length, artifacts });
}
