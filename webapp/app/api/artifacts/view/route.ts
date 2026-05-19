import fs from "node:fs";

import { NextResponse } from "next/server";

import { getSession } from "@/lib/auth/session";
import { findArtifactFile } from "@/lib/artifacts/catalog";

const TEXT_EXTENSIONS = new Set([
  "md",
  "txt",
  "json",
  "yaml",
  "yml",
  "sql",
  "py",
  "ts",
  "tsx",
  "js",
  "jsx",
  "html",
  "css",
  "sh",
  "mmd",
]);

export async function GET(request: Request) {
  const session = await getSession();

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("project")?.trim() ?? "";
  const relativePath = searchParams.get("file")?.trim() ?? "";

  if (!projectId || !relativePath) {
    return NextResponse.json(
      { success: false, code: "VALIDATION_ERROR", message: "project and file are required." },
      { status: 400 },
    );
  }

  const artifact = findArtifactFile(projectId, relativePath);
  if (!artifact || !fs.existsSync(artifact.absolutePath)) {
    return NextResponse.json(
      { success: false, code: "NOT_FOUND", message: "Artifact file not found." },
      { status: 404 },
    );
  }

  const buffer = fs.readFileSync(artifact.absolutePath);
  const contentType = TEXT_EXTENSIONS.has(artifact.extension)
    ? "text/plain; charset=utf-8"
    : "application/octet-stream";

  return new NextResponse(buffer, {
    headers: {
      "Content-Type": contentType,
      "X-Artifact-Project": projectId,
      "X-Artifact-Path": artifact.relativePath,
    },
  });
}

