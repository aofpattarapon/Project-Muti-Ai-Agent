import fs from "node:fs";
import path from "node:path";

import Database from "better-sqlite3";

import { seedInitialBackofficeData, seedInitialUsers } from "@/lib/db/seed";
import {
  createCoreSchema,
  ensureAgentRoleConfigExpansionColumns,
  ensureApprovalItemIdentityColumns,
  ensureUserMfaColumns,
  ensureUserSessionVersionColumn,
  ensureUserStatusColumn,
  migrateLegacyPasswordColumn,
} from "@/lib/db/schema";

const dataDir = path.join(process.cwd(), "data");
const dbPath = path.join(dataDir, "multi-ai-agent-app.db");

function ensureDataDirectory() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
}

function openDatabase() {
  ensureDataDirectory();
  return new Database(dbPath);
}

function initializeDatabase(db: Database.Database) {
  createCoreSchema(db);
  migrateLegacyPasswordColumn(db);
  ensureUserStatusColumn(db);
  ensureUserSessionVersionColumn(db);
  ensureUserMfaColumns(db);
  ensureAgentRoleConfigExpansionColumns(db);
  ensureApprovalItemIdentityColumns(db);
  seedInitialUsers(db);
  seedInitialBackofficeData(db);
}

const db = openDatabase();

initializeDatabase(db);

export { db, initializeDatabase };
