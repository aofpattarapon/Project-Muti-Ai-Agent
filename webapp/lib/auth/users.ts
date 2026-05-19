import { db } from "@/lib/db";
import type { UserRole } from "@/lib/auth/types";

export type AuthUser = {
  id: string;
  username: string;
  email: string;
  password_hash: string;
  role: UserRole;
  name: string;
  isActive: boolean;
  sessionVersion: number;
};

export function findUserByLogin(usernameOrEmail: string): AuthUser | undefined {
  const login = usernameOrEmail.trim().toLowerCase();

  const user = db
    .prepare(
      `
        SELECT id, username, email, password_hash, role, name, is_active, session_version
        FROM users
        WHERE LOWER(username) = ? OR LOWER(email) = ?
        LIMIT 1
      `,
    )
    .get(login, login) as
    | {
        id: string;
        username: string;
        email: string;
        password_hash: string;
        role: UserRole;
        name: string;
        is_active: number;
        session_version: number;
      }
    | undefined;

  if (!user) {
    return undefined;
  }

  return {
    id: user.id,
    username: user.username,
    email: user.email,
    password_hash: user.password_hash,
    role: user.role,
    name: user.name,
    isActive: user.is_active === 1,
    sessionVersion: user.session_version,
  };
}

export function getUserSessionVersion(userId: string): number | null {
  const row = db
    .prepare(
      `
        SELECT session_version
        FROM users
        WHERE id = ?
        LIMIT 1
      `,
    )
    .get(userId) as { session_version: number } | undefined;

  return row?.session_version ?? null;
}

export function isSessionVersionCurrent(userId: string, sessionVersion: number) {
  return getUserSessionVersion(userId) === sessionVersion;
}

export function incrementUserSessionVersion(userId: string) {
  const result = db
    .prepare(
      `
        UPDATE users
        SET session_version = session_version + 1
        WHERE id = ?
      `,
    )
    .run(userId);

  return result.changes > 0;
}
