import { cookies } from "next/headers";

import { getUserSessionVersion } from "@/lib/auth/users";
import type { AuthSession } from "@/lib/auth/types";
import { getRuntimeConfig } from "@/lib/config/runtime";
import { signSessionValue, verifySignedSessionValue } from "@/lib/security/session-signing";

const SESSION_COOKIE = "maa_session";
const SESSION_MAX_AGE = 60 * 60 * 8;

function encodeSession(session: AuthSession) {
  return signSessionValue(JSON.stringify(session));
}

function decodeSession(value: string): AuthSession | null {
  const verifiedValue = verifySignedSessionValue(value);

  if (!verifiedValue) {
    return null;
  }

  try {
    return JSON.parse(verifiedValue) as AuthSession;
  } catch {
    return null;
  }
}

export async function createSession(session: AuthSession) {
  const cookieStore = await cookies();
  const { nodeEnv } = getRuntimeConfig();

  cookieStore.set(SESSION_COOKIE, encodeSession(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: nodeEnv === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
}

export async function clearSession() {
  const cookieStore = await cookies();
  const { nodeEnv } = getRuntimeConfig();

  cookieStore.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: nodeEnv === "production",
    path: "/",
    maxAge: 0,
  });
}

export async function getSession() {
  const cookieStore = await cookies();
  const value = cookieStore.get(SESSION_COOKIE)?.value;

  if (!value) {
    return null;
  }

  const session = decodeSession(value);

  if (!session) {
    return null;
  }

  const currentSessionVersion = getUserSessionVersion(session.userId);

  if (currentSessionVersion === null) {
    return null;
  }

  if (currentSessionVersion !== session.sessionVersion) {
    return null;
  }

  return session;
}

export { SESSION_COOKIE };
