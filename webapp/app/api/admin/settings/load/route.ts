import { NextResponse } from "next/server";

import { loadAllSettings } from "@/lib/config/env-manager";
import { getSession } from "@/lib/auth/session";

export async function GET(request: Request) {
  const session = await getSession();

  if (!session || session.role !== "Admin") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const settings = loadAllSettings();
    return NextResponse.json({ ok: true, settings });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
