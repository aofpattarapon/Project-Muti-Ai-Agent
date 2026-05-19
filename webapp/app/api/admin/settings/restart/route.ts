import { execSync } from "node:child_process";
import { NextResponse } from "next/server";

import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

export async function POST(request: Request) {
  const session = await getSession();
  if (!session || session.role !== "Admin") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { target?: string } = {};
  try {
    body = await request.json();
  } catch {
    // default: restart all bots
  }

  const target = body.target ?? "all";
  const validTargets = ["all", "sdlc-ceo", "sdlc-pm", "sdlc-ba", "sdlc-sa", "sdlc-uxui", "sdlc-dev", "sdlc-qa", "sdlc-devops", "sdlc-cron"];

  if (!validTargets.includes(target)) {
    return NextResponse.json({ ok: false, error: "Invalid target" }, { status: 400 });
  }

  try {
    const cmd = target === "all"
      ? "pm2 restart sdlc-ceo sdlc-pm sdlc-ba sdlc-sa sdlc-uxui sdlc-dev sdlc-qa sdlc-devops sdlc-cron 2>&1"
      : `pm2 restart ${target} 2>&1`;

    const output = execSync(cmd, { timeout: 30000 }).toString().trim();

    recordAuditEvent(
      "settings.restart",
      `PM2 restart [${target}] by ${session.username}.`,
      session.username,
    );

    return NextResponse.json({ ok: true, target, output: output.slice(0, 500) });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
