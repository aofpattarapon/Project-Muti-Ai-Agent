import type Database from "better-sqlite3";

import { agentRoleConfigSeeds, systemConfigSeeds } from "@/data/agent-backoffice-seed";
import { seedUsers } from "@/data/seed-users";
import { hashPasswordSync } from "@/lib/security/password";

export function seedInitialUsers(db: Database.Database) {
  const insertSeedUser = db.prepare(`
    INSERT OR IGNORE INTO users (
      id, username, email, password_hash, role, name, is_active, session_version, mfa_enabled, mfa_enrolled_at
    )
    VALUES (
      @id, @username, @email, @password_hash, @role, @name, @is_active, @session_version, @mfa_enabled, @mfa_enrolled_at
    )
  `);

  for (const user of seedUsers) {
    insertSeedUser.run({
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
}

export function seedInitialBackofficeData(db: Database.Database) {
  const now = new Date().toISOString();

  const insertRoleConfig = db.prepare(`
    INSERT OR IGNORE INTO agent_role_configs (
      role_key, display_name, responsibility, primary_model, escalation_model,
      discord_bot_token, discord_channel_ids, skill_tags, working_rules,
      claude_design_access, harness_enabled, hot_cache_enabled, harness_profile, logic_summary,
      reporting_summary, output_mode, is_active, updated_at
    )
    VALUES (
      @role_key, @display_name, @responsibility, @primary_model, @escalation_model,
      @discord_bot_token, @discord_channel_ids, @skill_tags, @working_rules,
      @claude_design_access, @harness_enabled, @hot_cache_enabled, @harness_profile, @logic_summary,
      @reporting_summary, @output_mode, @is_active, @updated_at
    )
  `);

  for (const config of agentRoleConfigSeeds) {
    insertRoleConfig.run({
      role_key: config.roleKey,
      display_name: config.displayName,
      responsibility: config.responsibility,
      primary_model: config.primaryModel,
      escalation_model: config.escalationModel,
      discord_bot_token: config.discordBotToken,
      discord_channel_ids: config.discordChannelIds,
      skill_tags: JSON.stringify(config.skillTags),
      working_rules: config.workingRules,
      claude_design_access: config.claudeDesignAccess ? 1 : 0,
      harness_enabled: config.harnessEnabled ? 1 : 0,
      hot_cache_enabled: config.hotCacheEnabled ? 1 : 0,
      harness_profile: config.harnessProfile,
      logic_summary: config.logicSummary,
      reporting_summary: config.reportingSummary,
      output_mode: config.outputMode,
      is_active: config.isActive ? 1 : 0,
      updated_at: now,
    });
  }

  const insertSystemConfig = db.prepare(`
    INSERT OR IGNORE INTO system_configs (
      config_key, category, value, description, updated_at
    )
    VALUES (
      @config_key, @category, @value, @description, @updated_at
    )
  `);
  const refreshSystemConfigMetadata = db.prepare(`
    UPDATE system_configs
    SET category = @category, description = @description
    WHERE config_key = @config_key
  `);

  for (const config of systemConfigSeeds) {
    insertSystemConfig.run({
      config_key: config.configKey,
      category: config.category,
      value: config.value,
      description: config.description,
      updated_at: now,
    });
    refreshSystemConfigMetadata.run({
      config_key: config.configKey,
      category: config.category,
      description: config.description,
    });
  }

  const existingLogs = db
    .prepare("SELECT COUNT(*) as count FROM agent_activity_logs")
    .get() as { count: number };

  db.prepare(
    `
      INSERT OR IGNORE INTO project_hot_cache (
        cache_key, title, summary, scope, status, source_role, artifact_ref, updated_at
      )
      VALUES (
        'current_project',
        'Current active project context',
        'No active project has been pinned into hot cache yet.',
        'global',
        'idle',
        'system',
        'project.hot-cache',
        ?
      )
    `,
  ).run(now);

  if (existingLogs.count > 0) {
    return;
  }

  const insertLog = db.prepare(`
    INSERT INTO agent_activity_logs (
      role_key, event_type, task_name, status, summary, artifact_ref, channel_target, created_at
    )
    VALUES (
      @role_key, @event_type, @task_name, @status, @summary, @artifact_ref, @channel_target, @created_at
    )
  `);

  for (const config of agentRoleConfigSeeds) {
    insertLog.run({
      role_key: config.roleKey,
      event_type: "logic.registered",
      task_name: "Initial multi-agent operating model",
      status: "ready",
      summary: `${config.displayName} logic and reporting profile registered in the project back-office.`,
      artifact_ref: `${config.roleKey}.logic-profile`,
      channel_target: "project-db",
      created_at: now,
    });
  }
}
