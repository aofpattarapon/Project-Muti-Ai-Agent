import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { readFile, rm } from 'fs/promises'
import { existsSync } from 'fs'
import path from 'path'
import os from 'os'
import { promisify } from 'util'

const execAsync = promisify(exec)
const OUTPUT_BASE = process.env.OUTPUT_BASE_PATH || '/home/off_poff_p/projects/multi-ai-agent/sdlc/outputs'

/**
 * GET /api/project-logs/files/download-zip?project=PROJ123&role=sa
 *
 * Downloads all output files for a project (and optionally a specific role)
 * as a .tar.gz archive.
 *
 * Query params:
 *   project  (required) — project ID
 *   role     (optional) — limit to a specific role; omit for all roles
 */
export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get('project')
  const role    = req.nextUrl.searchParams.get('role') ?? ''

  if (!project) {
    return NextResponse.json({ error: 'project is required' }, { status: 400 })
  }

  // Validate project/role are safe identifiers (no path traversal)
  if (!/^[A-Za-z0-9_\-]+$/.test(project)) {
    return NextResponse.json({ error: 'invalid project id' }, { status: 400 })
  }
  if (role && !/^[A-Za-z0-9_\-]+$/.test(role)) {
    return NextResponse.json({ error: 'invalid role' }, { status: 400 })
  }

  const resolvedBase = path.resolve(OUTPUT_BASE)
  const projectDir   = path.resolve(path.join(resolvedBase, 'projects', project, role))

  // Ensure we're still inside OUTPUT_BASE
  if (!projectDir.startsWith(resolvedBase)) {
    return NextResponse.json({ error: 'invalid path' }, { status: 400 })
  }

  if (!existsSync(projectDir)) {
    return NextResponse.json({ error: 'no output files found' }, { status: 404 })
  }

  const archiveName = role ? `${project}_${role}.tar.gz` : `${project}_all.tar.gz`
  const tmpPath = path.join(os.tmpdir(), `sdlc-${Date.now()}-${archiveName}`)

  try {
    // Create tar.gz of the project output directory
    await execAsync(`tar czf "${tmpPath}" -C "${projectDir}" .`)

    const content = await readFile(tmpPath)

    return new NextResponse(content, {
      status: 200,
      headers: {
        'Content-Type': 'application/gzip',
        'Content-Disposition': `attachment; filename="${archiveName}"`,
        'Cache-Control': 'no-store',
      },
    })
  } catch (err) {
    console.error('[download-zip] error:', err)
    return NextResponse.json({ error: 'failed to create archive' }, { status: 500 })
  } finally {
    // Clean up temp file
    rm(tmpPath, { force: true }).catch(() => {})
  }
}
