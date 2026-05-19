import { spawnSync } from "node:child_process";

import { NextResponse } from "next/server";

import { getSession } from "@/lib/auth/session";
import { getArtifactPackage } from "@/lib/artifacts/catalog";

export async function GET(request: Request) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("project")?.trim() ?? "";
  const format = searchParams.get("format")?.trim().toLowerCase() ?? "json";

  if (!projectId) {
    return NextResponse.json(
      { success: false, code: "VALIDATION_ERROR", message: "project is required." },
      { status: 400 },
    );
  }

  const artifactPackage = getArtifactPackage(projectId);
  if (!artifactPackage) {
    return NextResponse.json(
      { success: false, code: "NOT_FOUND", message: "Artifact package not found." },
      { status: 404 },
    );
  }

  if (format === "json") {
    return NextResponse.json({
      success: true,
      exported_at: new Date().toISOString(),
      package: artifactPackage,
    });
  }

  const archiveName = `${artifactPackage.projectId}-${artifactPackage.projectName.replace(/\s+/g, "-").toLowerCase()}.tar.gz`;
  const archive = spawnSync("tar", ["-czf", "-", "-C", artifactPackage.packagePath, "."], {
    encoding: null,
  });

  if (archive.status !== 0 || !archive.stdout) {
    return NextResponse.json(
      {
        success: false,
        code: "EXPORT_FAILED",
        message: archive.stderr?.toString() || "Unable to build artifact archive.",
      },
      { status: 500 },
    );
  }

  return new NextResponse(archive.stdout, {
    headers: {
      "Content-Type": "application/gzip",
      "Content-Disposition": `attachment; filename="${archiveName}"`,
    },
  });
}

