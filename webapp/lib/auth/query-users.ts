import { db } from "@/lib/db";

export const USER_ROLES = ["Admin", "Operator", "Viewer"] as const;
export type UserRole = (typeof USER_ROLES)[number];

export type UserRecord = {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  name: string;
  isActive: boolean;
  mfaEnabled: boolean;
  mfaEnrolledAt: string | null;
};

export function isUserRole(value: string): value is UserRole {
  return USER_ROLES.includes(value as UserRole);
}

export function listUsers(): UserRecord[] {
  const rows = db
    .prepare(
      `
        SELECT id, username, email, role, name, is_active, mfa_enabled, mfa_enrolled_at
        FROM users
        ORDER BY name ASC, username ASC
      `,
    )
    .all() as {
    id: string;
    username: string;
    email: string;
    role: UserRole;
    name: string;
    is_active: number;
    mfa_enabled: number;
    mfa_enrolled_at: string | null;
  }[];

  return rows.map((user) => ({
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
    name: user.name,
    isActive: user.is_active === 1,
    mfaEnabled: user.mfa_enabled === 1,
    mfaEnrolledAt: user.mfa_enrolled_at,
  }));
}

export function findUserById(id: string): UserRecord | null {
  const user = db
    .prepare(
      `
        SELECT id, username, email, role, name, is_active, mfa_enabled, mfa_enrolled_at
        FROM users
        WHERE id = ?
        LIMIT 1
      `,
    )
    .get(id) as
    | {
        id: string;
        username: string;
        email: string;
        role: UserRole;
        name: string;
        is_active: number;
        mfa_enabled: number;
        mfa_enrolled_at: string | null;
      }
    | undefined;

  if (!user) {
    return null;
  }

  return {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role,
    name: user.name,
    isActive: user.is_active === 1,
    mfaEnabled: user.mfa_enabled === 1,
    mfaEnrolledAt: user.mfa_enrolled_at,
  };
}

export function updateUserActiveStatus(id: string, isActive: boolean) {
  const result = db
    .prepare(
      `
        UPDATE users
        SET is_active = ?
        WHERE id = ?
      `,
    )
    .run(isActive ? 1 : 0, id);

  return result.changes > 0;
}

export function updateUserRole(id: string, role: UserRole) {
  const result = db
    .prepare(
      `
        UPDATE users
        SET role = ?
        WHERE id = ?
      `,
    )
    .run(role, id);

  return result.changes > 0;
}
