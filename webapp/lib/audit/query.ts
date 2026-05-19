import { db } from "@/lib/db";

export type AuditEventRecord = {
  id: number;
  type: string;
  actor: string | null;
  detail: string;
  created_at: string;
};

export type AuditEventFilters = {
  type?: string;
  actor?: string;
  limit?: number;
  offset?: number;
};

function buildFilterParts(filters: AuditEventFilters) {
  const clauses: string[] = [];
  const values: Array<string | number> = [];

  if (filters.type && filters.type !== "all") {
    clauses.push("type = ?");
    values.push(filters.type);
  }

  if (filters.actor?.trim()) {
    clauses.push("LOWER(COALESCE(actor, '')) LIKE ?");
    values.push(`%${filters.actor.trim().toLowerCase()}%`);
  }

  return {
    whereClause: clauses.length > 0 ? `WHERE ${clauses.join(" AND ")}` : "",
    values,
  };
}

export function listRecentAuditEvents(filters: AuditEventFilters = {}): AuditEventRecord[] {
  const { whereClause, values } = buildFilterParts(filters);
  const limit = filters.limit ?? 25;
  const offset = filters.offset ?? 0;

  return db
    .prepare(
      `
        SELECT id, type, actor, detail, created_at
        FROM audit_events
        ${whereClause}
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ? OFFSET ?
      `,
    )
    .all(...values, limit, offset) as AuditEventRecord[];
}

export function countAuditEvents(filters: AuditEventFilters = {}): number {
  const { whereClause, values } = buildFilterParts(filters);

  const row = db
    .prepare(
      `
        SELECT COUNT(*) as count
        FROM audit_events
        ${whereClause}
      `,
    )
    .get(...values) as { count: number };

  return row.count;
}
