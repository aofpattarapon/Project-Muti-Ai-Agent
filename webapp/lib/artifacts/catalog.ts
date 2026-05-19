import fs from "node:fs";
import path from "node:path";

import Database from "better-sqlite3";

export type ArtifactFileRecord = {
  roleKey: string;
  category: string;
  relativePath: string;
  fileName: string;
  absolutePath: string;
  extension: string;
  sizeBytes: number;
  updatedAt: string;
};

export type ArtifactPackageRecord = {
  projectId: string;
  projectName: string;
  projectStatus: string;
  currentRole: string;
  createdAt: string | null;
  packagePath: string;
  updatedAt: string;
  roles: string[];
  fileCount: number;
  files: ArtifactFileRecord[];
};

const ROLE_CATEGORY_MAP: Record<string, string> = {
  ceo: "requirements",
  pm: "plan",
  ba: "brd",
  sa: "architecture",
  uxui: "design",
  dev: "code",
  qa: "tests",
  devops: "devops",
};

function getSdlcRoot() {
  return process.env.SDLC_ROOT_PATH ?? path.resolve(process.cwd(), "../sdlc");
}

function getProjectsRoot() {
  return process.env.SDLC_OUTPUT_PROJECTS_PATH ?? path.join(getSdlcRoot(), "outputs", "projects");
}

function getSdlcDbPath() {
  return process.env.SDLC_DB_PATH ?? path.join(getSdlcRoot(), "data", "sdlc.db");
}

function openSdlcDb() {
  const dbPath = getSdlcDbPath();
  if (!fs.existsSync(dbPath)) {
    return null;
  }

  return new Database(dbPath, { readonly: true });
}

function listFilesRecursively(baseDir: string, currentDir: string, roleKey: string): ArtifactFileRecord[] {
  const entries = fs.readdirSync(currentDir, { withFileTypes: true });
  const files: ArtifactFileRecord[] = [];

  for (const entry of entries) {
    const absolutePath = path.join(currentDir, entry.name);

    if (entry.isDirectory()) {
      files.push(...listFilesRecursively(baseDir, absolutePath, roleKey));
      continue;
    }

    const stats = fs.statSync(absolutePath);
    const relativePath = path.relative(baseDir, absolutePath);
    const extension = path.extname(entry.name).replace(/^\./, "").toLowerCase();

    files.push({
      roleKey,
      category: ROLE_CATEGORY_MAP[roleKey] ?? roleKey,
      relativePath,
      fileName: entry.name,
      absolutePath,
      extension,
      sizeBytes: stats.size,
      updatedAt: stats.mtime.toISOString(),
    });
  }

  return files;
}

function loadProjectMetadata(projectId: string) {
  const db = openSdlcDb();
  if (!db) {
    return null;
  }

  try {
    const row = db
      .prepare(
        `
          SELECT id, name, status, current_role, created_at
          FROM projects
          WHERE id = ?
          LIMIT 1
        `,
      )
      .get(projectId) as
      | {
          id: string;
          name: string;
          status: string;
          current_role: string;
          created_at: string;
        }
      | undefined;

    return row ?? null;
  } finally {
    db.close();
  }
}

function buildPackageRecord(projectId: string): ArtifactPackageRecord | null {
  const projectPath = path.join(getProjectsRoot(), projectId);
  if (!fs.existsSync(projectPath)) {
    return null;
  }

  const roleDirs = fs
    .readdirSync(projectPath, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();

  const files = roleDirs.flatMap((roleKey) =>
    listFilesRecursively(projectPath, path.join(projectPath, roleKey), roleKey),
  );

  const metadata = loadProjectMetadata(projectId);
  const dirStats = fs.statSync(projectPath);

  return {
    projectId,
    projectName: metadata?.name ?? projectId,
    projectStatus: metadata?.status ?? "unknown",
    currentRole: metadata?.current_role ?? "unknown",
    createdAt: metadata?.created_at ?? null,
    packagePath: projectPath,
    updatedAt: dirStats.mtime.toISOString(),
    roles: roleDirs,
    fileCount: files.length,
    files: files.sort((a, b) => a.relativePath.localeCompare(b.relativePath)),
  };
}

export function listArtifactPackages(): ArtifactPackageRecord[] {
  const projectsRoot = getProjectsRoot();
  if (!fs.existsSync(projectsRoot)) {
    return [];
  }

  return fs
    .readdirSync(projectsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => buildPackageRecord(entry.name))
    .filter((entry): entry is ArtifactPackageRecord => entry !== null)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getArtifactPackage(projectId: string) {
  return buildPackageRecord(projectId);
}

export function findArtifactFile(projectId: string, relativePath: string) {
  const pkg = getArtifactPackage(projectId);
  if (!pkg) {
    return null;
  }

  const normalized = relativePath.replace(/^\/+/, "");
  return pkg.files.find((file) => file.relativePath === normalized) ?? null;
}

