import type Database from "better-sqlite3";

import { hashPasswordSync } from "@/lib/security/password";

export function createCoreSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT NOT NULL UNIQUE,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      name TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1,
      session_version INTEGER NOT NULL DEFAULT 1,
      mfa_enabled INTEGER NOT NULL DEFAULT 0,
      mfa_enrolled_at TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      type TEXT NOT NULL,
      actor TEXT,
      detail TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS password_reset_tokens (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      used_at TEXT,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS agent_role_configs (
      role_key TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      responsibility TEXT NOT NULL,
      primary_model TEXT NOT NULL,
      escalation_model TEXT NOT NULL,
      discord_bot_token TEXT NOT NULL DEFAULT '',
      discord_channel_ids TEXT NOT NULL DEFAULT '',
      skill_tags TEXT NOT NULL DEFAULT '[]',
      working_rules TEXT NOT NULL DEFAULT '',
      claude_design_access INTEGER NOT NULL DEFAULT 0,
      harness_enabled INTEGER NOT NULL DEFAULT 1,
      hot_cache_enabled INTEGER NOT NULL DEFAULT 1,
      harness_profile TEXT NOT NULL,
      logic_summary TEXT NOT NULL,
      reporting_summary TEXT NOT NULL,
      output_mode TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_activity_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      role_key TEXT NOT NULL,
      event_type TEXT NOT NULL,
      task_name TEXT NOT NULL,
      status TEXT NOT NULL,
      summary TEXT NOT NULL,
      artifact_ref TEXT,
      channel_target TEXT,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS system_configs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      config_key TEXT NOT NULL UNIQUE,
      category TEXT NOT NULL,
      value TEXT NOT NULL,
      description TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS project_hot_cache (
      cache_key TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      summary TEXT NOT NULL,
      scope TEXT NOT NULL,
      status TEXT NOT NULL,
      source_role TEXT NOT NULL,
      artifact_ref TEXT,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS approval_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      role_key TEXT NOT NULL,
      task_name TEXT NOT NULL,
      status TEXT NOT NULL,
      summary TEXT NOT NULL,
      artifact_ref TEXT,
      output_summary TEXT,
      requested_by TEXT NOT NULL,
      approver TEXT,
      decision_note TEXT,
      channel_target TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
    ON password_reset_tokens(user_id);

    CREATE INDEX IF NOT EXISTS idx_agent_activity_logs_role_key
    ON agent_activity_logs(role_key);

    CREATE INDEX IF NOT EXISTS idx_agent_activity_logs_created_at
    ON agent_activity_logs(created_at);

    CREATE INDEX IF NOT EXISTS idx_project_hot_cache_updated_at
    ON project_hot_cache(updated_at);

    CREATE INDEX IF NOT EXISTS idx_approval_items_status
    ON approval_items(status);

    CREATE INDEX IF NOT EXISTS idx_approval_items_updated_at
    ON approval_items(updated_at);

    CREATE TABLE IF NOT EXISTS task_artifacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sdlc_task_id TEXT NOT NULL,
      project_id TEXT NOT NULL DEFAULT '',
      role_key TEXT NOT NULL DEFAULT '',
      artifact_type TEXT NOT NULL,
      artifact_path TEXT NOT NULL DEFAULT '',
      artifact_ref TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(sdlc_task_id, artifact_type)
    );

    CREATE INDEX IF NOT EXISTS idx_task_artifacts_sdlc_task_id
    ON task_artifacts(sdlc_task_id);

    CREATE INDEX IF NOT EXISTS idx_task_artifacts_project_id
    ON task_artifacts(project_id);
  `);
}

export function migrateLegacyPasswordColumn(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(users)").all() as { name: string }[];
  const hasPasswordColumn = columns.some((column) => column.name === "password");
  const hasPasswordHashColumn = columns.some((column) => column.name === "password_hash");

  if (!hasPasswordColumn || hasPasswordHashColumn) {
    return;
  }

  db.exec(`
    ALTER TABLE users RENAME TO users_old;

    CREATE TABLE users (
      id TEXT PRIMARY KEY,
      username TEXT NOT NULL UNIQUE,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      name TEXT NOT NULL,
      is_active INTEGER NOT NULL DEFAULT 1,
      session_version INTEGER NOT NULL DEFAULT 1,
      mfa_enabled INTEGER NOT NULL DEFAULT 0,
      mfa_enrolled_at TEXT
    );
  `);

  const legacyUsers = db.prepare(
    "SELECT id, username, email, password, role, name FROM users_old",
  ).all() as {
    id: string;
    username: string;
    email: string;
    password: string;
    role: string;
    name: string;
  }[];

  const insertUser = db.prepare(`
    INSERT OR IGNORE INTO users (
      id, username, email, password_hash, role, name, is_active, session_version, mfa_enabled, mfa_enrolled_at
    )
    VALUES (
      @id, @username, @email, @password_hash, @role, @name, @is_active, @session_version, @mfa_enabled, @mfa_enrolled_at
    )
  `);

  for (const user of legacyUsers) {
    insertUser.run({
      id: user.id,
      username: user.username,
      email: user.email,
      password_hash: hashPasswordSync(user.password),
      role: user.role,
      name: user.name,
      is_active: 1,
      session_version: 1,
      mfa_enabled: 0,
      mfa_enrolled_at: null,
    });
  }

  db.exec("DROP TABLE users_old");
}

export function ensureUserStatusColumn(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(users)").all() as { name: string }[];
  const hasIsActiveColumn = columns.some((column) => column.name === "is_active");

  if (hasIsActiveColumn) {
    return;
  }

  try {
    db.exec(`
      ALTER TABLE users
      ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
    `);
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.toLowerCase().includes("duplicate column name")
    ) {
      return;
    }

    throw error;
  }
}

export function ensureUserSessionVersionColumn(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(users)").all() as { name: string }[];
  const hasSessionVersionColumn = columns.some((column) => column.name === "session_version");

  if (hasSessionVersionColumn) {
    return;
  }

  try {
    db.exec(`
      ALTER TABLE users
      ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1
    `);
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.toLowerCase().includes("duplicate column name")
    ) {
      return;
    }

    throw error;
  }
}

export function ensureUserMfaColumns(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(users)").all() as { name: string }[];
  const hasMfaEnabledColumn = columns.some((column) => column.name === "mfa_enabled");
  const hasMfaEnrolledAtColumn = columns.some((column) => column.name === "mfa_enrolled_at");

  if (!hasMfaEnabledColumn) {
    try {
      db.exec(`
        ALTER TABLE users
        ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0
      `);
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.toLowerCase().includes("duplicate column name")
      ) {
        throw error;
      }
    }
  }

  if (!hasMfaEnrolledAtColumn) {
    try {
      db.exec(`
        ALTER TABLE users
        ADD COLUMN mfa_enrolled_at TEXT
      `);
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.toLowerCase().includes("duplicate column name")
      ) {
        throw error;
      }
    }
  }
}

export function ensureApprovalItemIdentityColumns(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(approval_items)").all() as { name: string }[];
  const additions = [
    { name: "project_id", sql: "ALTER TABLE approval_items ADD COLUMN project_id TEXT NOT NULL DEFAULT ''" },
    { name: "sdlc_task_id", sql: "ALTER TABLE approval_items ADD COLUMN sdlc_task_id TEXT NOT NULL DEFAULT ''" },
    { name: "role_task_id", sql: "ALTER TABLE approval_items ADD COLUMN role_task_id TEXT NOT NULL DEFAULT ''" },
    { name: "discord_message_id", sql: "ALTER TABLE approval_items ADD COLUMN discord_message_id TEXT NOT NULL DEFAULT ''" },
    { name: "source_runtime", sql: "ALTER TABLE approval_items ADD COLUMN source_runtime TEXT NOT NULL DEFAULT 'discord'" },
    { name: "processed_by_runtime_at", sql: "ALTER TABLE approval_items ADD COLUMN processed_by_runtime_at TEXT" },
    { name: "runtime_processed_status", sql: "ALTER TABLE approval_items ADD COLUMN runtime_processed_status TEXT" },
  ];

  for (const addition of additions) {
    if (columns.some((c) => c.name === addition.name)) continue;
    try {
      db.exec(addition.sql);
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.toLowerCase().includes("duplicate column name")
      ) {
        throw error;
      }
    }
  }
}

export function ensureAgentRoleConfigExpansionColumns(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(agent_role_configs)").all() as { name: string }[];
  const additions = [
    { name: "discord_bot_token", sql: "ALTER TABLE agent_role_configs ADD COLUMN discord_bot_token TEXT NOT NULL DEFAULT ''" },
    { name: "discord_channel_ids", sql: "ALTER TABLE agent_role_configs ADD COLUMN discord_channel_ids TEXT NOT NULL DEFAULT ''" },
    { name: "skill_tags", sql: "ALTER TABLE agent_role_configs ADD COLUMN skill_tags TEXT NOT NULL DEFAULT '[]'" },
    { name: "working_rules", sql: "ALTER TABLE agent_role_configs ADD COLUMN working_rules TEXT NOT NULL DEFAULT ''" },
    { name: "hot_cache_enabled", sql: "ALTER TABLE agent_role_configs ADD COLUMN hot_cache_enabled INTEGER NOT NULL DEFAULT 1" },
  ];

  for (const addition of additions) {
    const hasColumn = columns.some((column) => column.name === addition.name);

    if (hasColumn) {
      continue;
    }

    try {
      db.exec(addition.sql);
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.toLowerCase().includes("duplicate column name")
      ) {
        throw error;
      }
    }
  }
}

export function ensureAgentActivityLogColumns(db: Database.Database) {
  const columns = db.prepare("PRAGMA table_info(agent_activity_logs)").all() as { name: string }[];
  const additions = [
    { name: "sdlc_task_id", sql: "ALTER TABLE agent_activity_logs ADD COLUMN sdlc_task_id TEXT NOT NULL DEFAULT ''" },
    { name: "project_id",   sql: "ALTER TABLE agent_activity_logs ADD COLUMN project_id TEXT NOT NULL DEFAULT ''" },
    { name: "metadata",     sql: "ALTER TABLE agent_activity_logs ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'" },
  ];
  for (const addition of additions) {
    if (columns.some((c) => c.name === addition.name)) continue;
    try {
      db.exec(addition.sql);
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.toLowerCase().includes("duplicate column name")
      ) {
        throw error;
      }
    }
  }
}
