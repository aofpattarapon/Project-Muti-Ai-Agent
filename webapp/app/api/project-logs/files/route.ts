import { NextRequest, NextResponse } from 'next/server'
import { readdir, readFile } from 'fs/promises'
import path from 'path'

const OUTPUT_BASE = process.env.OUTPUT_BASE_PATH || '/home/socket9companylimited/projects/multi-ai-agent/sdlc/outputs'

export async function GET(req: NextRequest) {
  const project = req.nextUrl.searchParams.get('project')
  const role = req.nextUrl.searchParams.get('role')

  if (!project) {
    return NextResponse.json({ error: 'project required' }, { status: 400 })
  }

  try {
    const baseDir = path.join(OUTPUT_BASE, 'projects', project, role || '')
    const files: Record<string, string> = {}

    const readDirRecursive = async (dir: string, prefix = '') => {
      try {
        const entries = await readdir(dir, { withFileTypes: true })
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name)
          const relPath = prefix ? `${prefix}/${entry.name}` : entry.name
          if (entry.isDirectory()) {
            await readDirRecursive(fullPath, relPath)
          } else {
            try {
              const content = await readFile(fullPath, 'utf-8')
              files[relPath] = content
            } catch {
              files[relPath] = '[binary file]'
            }
          }
        }
      } catch { /* dir doesn't exist — skip silently */ }
    }

    await readDirRecursive(baseDir)

    return NextResponse.json({
      project,
      role: role || 'all',
      files,
      fileCount: Object.keys(files).length,
      exportedAt: new Date().toISOString(),
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
