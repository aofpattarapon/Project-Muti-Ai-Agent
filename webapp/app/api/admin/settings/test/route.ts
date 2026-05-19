import { NextResponse } from "next/server";

import { getSession } from "@/lib/auth/session";

type TestTarget = "anthropic" | "openai" | "groq" | "ollama" | "discord";

async function testAnthropic(apiKey: string) {
  if (!apiKey) return { ok: false, message: "No API key configured" };
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 10,
        messages: [{ role: "user", content: "ping" }],
      }),
      signal: AbortSignal.timeout(10000),
    });
    if (res.status === 200) return { ok: true, message: "API key valid" };
    if (res.status === 401) return { ok: false, message: "API key invalid (401)" };
    const body = await res.json().catch(() => ({}));
    return { ok: false, message: `HTTP ${res.status}: ${body?.error?.message ?? "unknown"}` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Connection failed" };
  }
}

async function testOpenAI(apiKey: string) {
  if (!apiKey) return { ok: false, message: "No API key configured" };
  try {
    const res = await fetch("https://api.openai.com/v1/models", {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(10000),
    });
    if (res.status === 200) return { ok: true, message: "API key valid" };
    if (res.status === 401) return { ok: false, message: "API key invalid (401)" };
    return { ok: false, message: `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Connection failed" };
  }
}

async function testGroq(apiKey: string) {
  if (!apiKey) return { ok: false, message: "No API key configured" };
  try {
    const res = await fetch("https://api.groq.com/openai/v1/models", {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(10000),
    });
    if (res.status === 200) return { ok: true, message: "API key valid" };
    if (res.status === 401) return { ok: false, message: "API key invalid (401)" };
    return { ok: false, message: `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Connection failed" };
  }
}

async function testOllama(ollamaUrl: string) {
  if (!ollamaUrl) return { ok: false, message: "No Ollama URL configured" };
  try {
    const res = await fetch(`${ollamaUrl}/api/tags`, {
      signal: AbortSignal.timeout(8000),
    });
    if (res.status === 200) {
      const data = await res.json();
      const models: string[] = (data.models ?? []).map((m: { name: string }) => m.name);
      return { ok: true, message: `Connected — ${models.length} model(s): ${models.slice(0, 4).join(", ")}` };
    }
    return { ok: false, message: `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Connection failed" };
  }
}

async function testDiscord(token: string, guildId: string) {
  if (!token) return { ok: false, message: "No token configured" };
  try {
    const res = await fetch(`https://discord.com/api/v10/guilds/${guildId}`, {
      headers: { Authorization: `Bot ${token}` },
      signal: AbortSignal.timeout(8000),
    });
    if (res.status === 200) {
      const data = await res.json();
      return { ok: true, message: `Connected to guild: ${data.name}` };
    }
    if (res.status === 401) return { ok: false, message: "Token invalid (401)" };
    return { ok: false, message: `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Connection failed" };
  }
}

export async function POST(request: Request) {
  const session = await getSession();
  if (!session || session.role !== "Admin") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { target: TestTarget; params?: Record<string, string> };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const { target, params = {} } = body;
  let result: { ok: boolean; message: string };

  switch (target) {
    case "anthropic":
      result = await testAnthropic(params.apiKey ?? "");
      break;
    case "openai":
      result = await testOpenAI(params.apiKey ?? "");
      break;
    case "groq":
      result = await testGroq(params.apiKey ?? "");
      break;
    case "ollama":
      result = await testOllama(params.url ?? "");
      break;
    case "discord":
      result = await testDiscord(params.token ?? "", params.guildId ?? "");
      break;
    default:
      return NextResponse.json({ ok: false, error: "Unknown test target" }, { status: 400 });
  }

  return NextResponse.json(result);
}
