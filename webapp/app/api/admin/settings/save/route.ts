import { NextResponse } from "next/server";

import { saveGroupSettings, type SettingsGroup } from "@/lib/config/env-manager";
import { recordAuditEvent } from "@/lib/audit/events";
import { getSession } from "@/lib/auth/session";

const VALID_GROUPS: SettingsGroup[] = ["discord", "llm", "pipeline", "trading", "obsidian", "webapp"];

export async function POST(request: Request) {
  const session = await getSession();

  if (!session || session.role !== "Admin") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { group: string; values: Record<string, string> };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const group = body.group as SettingsGroup;
  if (!VALID_GROUPS.includes(group)) {
    return NextResponse.json({ ok: false, error: "Unknown settings group" }, { status: 400 });
  }

  const values = body.values ?? {};

  try {
    saveGroupSettings(group, values);
    recordAuditEvent(
      "settings.saved",
      `Settings group [${group}] updated by ${session.username}.`,
      session.username,
    );
    return NextResponse.json({ ok: true, group, saved: Object.keys(values).length });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
