import crypto from "node:crypto";

import { findUserByLogin, incrementUserSessionVersion } from "@/lib/auth/users";
import { db } from "@/lib/db";
import { hashPasswordSync } from "@/lib/security/password";

const RESET_TOKEN_TTL_MINUTES = 30;

type ActiveResetTokenRecord = {
  id: string;
  userId: string;
  username: string;
  email: string;
  expiresAt: string;
};

function hashResetToken(token: string) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

export function issuePasswordResetToken(usernameOrEmail: string) {
  const user = findUserByLogin(usernameOrEmail);

  if (!user || !user.isActive) {
    return null;
  }

  const token = `${crypto.randomUUID().replace(/-/g, "")}${crypto.randomBytes(16).toString("hex")}`;
  const tokenHash = hashResetToken(token);
  const createdAt = new Date().toISOString();
  const expiresAt = new Date(Date.now() + RESET_TOKEN_TTL_MINUTES * 60 * 1000).toISOString();

  const issueToken = db.transaction(() => {
    db.prepare(
      `
        UPDATE password_reset_tokens
        SET used_at = ?
        WHERE user_id = ? AND used_at IS NULL
      `,
    ).run(createdAt, user.id);

    db.prepare(
      `
        INSERT INTO password_reset_tokens (id, user_id, token_hash, created_at, expires_at, used_at)
        VALUES (?, ?, ?, ?, ?, NULL)
      `,
    ).run(crypto.randomUUID(), user.id, tokenHash, createdAt, expiresAt);
  });

  issueToken();

  return {
    token,
    username: user.username,
    email: user.email,
    expiresAt,
  };
}

export function findActivePasswordResetToken(token: string): ActiveResetTokenRecord | null {
  const tokenHash = hashResetToken(token);
  const now = new Date().toISOString();

  const record = db
    .prepare(
      `
        SELECT
          password_reset_tokens.id,
          password_reset_tokens.user_id,
          password_reset_tokens.expires_at,
          users.username,
          users.email,
          users.is_active
        FROM password_reset_tokens
        INNER JOIN users ON users.id = password_reset_tokens.user_id
        WHERE password_reset_tokens.token_hash = ?
          AND password_reset_tokens.used_at IS NULL
          AND datetime(password_reset_tokens.expires_at) >= datetime(?)
        LIMIT 1
      `,
    )
    .get(tokenHash, now) as
    | {
        id: string;
        user_id: string;
        expires_at: string;
        username: string;
        email: string;
        is_active: number;
      }
    | undefined;

  if (!record || record.is_active !== 1) {
    return null;
  }

  return {
    id: record.id,
    userId: record.user_id,
    username: record.username,
    email: record.email,
    expiresAt: record.expires_at,
  };
}

export function consumePasswordResetToken(token: string, newPassword: string) {
  const activeToken = findActivePasswordResetToken(token);

  if (!activeToken) {
    return null;
  }

  const usedAt = new Date().toISOString();
  const passwordHash = hashPasswordSync(newPassword);

  const applyReset = db.transaction(() => {
    db.prepare(
      `
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
      `,
    ).run(passwordHash, activeToken.userId);

    incrementUserSessionVersion(activeToken.userId);

    db.prepare(
      `
        UPDATE password_reset_tokens
        SET used_at = ?
        WHERE id = ?
      `,
    ).run(usedAt, activeToken.id);
  });

  applyReset();

  return {
    username: activeToken.username,
    email: activeToken.email,
  };
}

export function deleteExpiredPasswordResetTokens(referenceTime = new Date().toISOString()) {
  const result = db
    .prepare(
      `
        DELETE FROM password_reset_tokens
        WHERE datetime(expires_at) < datetime(?)
      `,
    )
    .run(referenceTime);

  return result.changes;
}

export function deleteUsedPasswordResetTokens() {
  const result = db
    .prepare(
      `
        DELETE FROM password_reset_tokens
        WHERE used_at IS NOT NULL
      `,
    )
    .run();

  return result.changes;
}
