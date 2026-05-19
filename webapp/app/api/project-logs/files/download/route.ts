import { NextRequest, NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import path from 'path'

const OUTPUT_BASE = process.env.OUTPUT_BASE_PATH || '/home/socket9companylimited/projects/multi-ai-agent/sdlc/outputs'

export async function GET(req: NextRequest) {
  const project  = req.nextUrl.searchParams.get('project')
  const role     = req.nextUrl.searchParams.get('role')
  const filename = req.nextUrl.searchParams.get('file')

  if (!project || !filename) {
    return NextResponse.json({ error: 'project and file are required' }, { status: 400 })
  }

  // Sanitize: prevent path traversal
  const safeFilename = path.normalize(filename).replace(/^(\.\.[/\\])+/, '')
  const filePath = path.join(OUTPUT_BASE, 'projects', project, role || '', safeFilename)

  // Ensure resolved path is still within OUTPUT_BASE
  const resolvedBase = path.resolve(OUTPUT_BASE)
  const resolvedFile = path.resolve(filePath)
  if (!resolvedFile.startsWith(resolvedBase)) {
    return NextResponse.json({ error: 'invalid path' }, { status: 400 })
  }

  try {
    const content = await readFile(resolvedFile)
    const ext = path.extname(safeFilename).toLowerCase()
    const contentType =
      ext === '.json' ? 'application/json' :
      ext === '.yaml' || ext === '.yml' ? 'application/yaml' :
      ext === '.md'  ? 'text/markdown' :
      ext === '.sql' ? 'text/plain' :
      ext === '.py'  ? 'text/plain' :
      ext === '.ts' || ext === '.js' ? 'text/plain' :
      'application/octet-stream'

    return new NextResponse(content, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${path.basename(safeFilename)}"`,
        'Cache-Control': 'no-store',
      },
    })
  } catch {
    return NextResponse.json({ error: 'file not found' }, { status: 404 })
  }
}
