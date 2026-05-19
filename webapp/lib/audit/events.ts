import { db } from "@/lib/db";

export type AuditEventType =
  | "login.success"
  | "login.failure"
  | "login.blocked"
  | "login.inactive"
  | "logout"
  | "password_reset.requested"
  | "password_reset.issued"
  | "password_reset.completed"
  | "password_reset.rejected"
  | "user.status_changed"
  | "user.role_changed"
  | "agent_config.created"
  | "agent_config.updated"
  | "agent_config.deleted"
  | "system_config.created"
  | "system_config.updated"
  | "system_config.deleted"
  | "settings.saved"
  | "settings.restart";

export type AuditEvent = {
  type: AuditEventType;
  actor?: string;
  detail: string;
  createdAt: string;
};

export function recordAuditEvent(type: AuditEventType, detail: string, actor?: string) {
  const createdAt = new Date().toISOString();

  db.prepare(
    `
      INSERT INTO audit_events (type, actor, detail, created_at)
      VALUES (?, ?, ?, ?)
    `,
  ).run(type, actor ?? null, detail, createdAt);
}

export function listRecentAuditEvents(limit = 10): AuditEvent[] {
  const rows = db
    .prepare(
      `
        SELECT type, actor, detail, created_at
        FROM audit_events
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
      `,
    )
    .all(limit) as {
    type: AuditEventType;
    actor: string | null;
    detail: string;
    created_at: string;
  }[];

  return rows.map((row) => ({
    type: row.type,
    actor: row.actor ?? undefined,
    detail: row.detail,
    createdAt: row.created_at,
  }));
}
