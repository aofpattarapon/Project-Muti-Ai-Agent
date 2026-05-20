import { db } from "@/lib/db";

export type AgentRoleConfigRecord = {
  roleKey: string;
  displayName: string;
  responsibility: string;
  primaryModel: string;
  escalationModel: string;
  discordBotToken: string;
  discordChannelIds: string;
  skillTags: string[];
  workingRules: string;
  claudeDesignAccess: boolean;
  harnessEnabled: boolean;
  hotCacheEnabled: boolean;
  harnessProfile: string;
  logicSummary: string;
  reportingSummary: string;
  outputMode: string;
  isActive: boolean;
  updatedAt: string;
};

export type AgentActivityLogRecord = {
  id: number;
  roleKey: string;
  eventType: string;
  taskName: string;
  status: string;
  summary: string;
  artifactRef: string | null;
  channelTarget: string | null;
  createdAt: string;
  sdlcTaskId: string;
  projectId: string;
  metadata: string;
};

export type TaskArtifactRecord = {
  id: number;
  sdlcTaskId: string;
  projectId: string;
  roleKey: string;
  artifactType: string;
  artifactPath: string;
  artifactRef: string;
  createdAt: string;
  updatedAt: string;
};

export type SystemConfigRecord = {
  id: number;
  configKey: string;
  category: string;
  value: string;
  description: string;
  updatedAt: string;
};

export type ProjectHotCacheRecord = {
  cacheKey: string;
  title: string;
  summary: string;
  scope: string;
  status: string;
  sourceRole: string;
  artifactRef: string | null;
  updatedAt: string;
};

export type ApprovalItemRecord = {
  id: number;
  roleKey: string;
  taskName: string;
  status: string;
  summary: string;
  artifactRef: string | null;
  outputSummary: string | null;
  requestedBy: string;
  approver: string | null;
  decisionNote: string | null;
  channelTarget: string | null;
  createdAt: string;
  updatedAt: string;
  // Identity fields for exact Discord/SDLC task mapping
  projectId: string;
  sdlcTaskId: string;
  roleTaskId: string;
  discordMessageId: string;
  sourceRuntime: string;
  processedByRuntimeAt: string | null;
  runtimeProcessedStatus: string | null;
};

function safeParseSkillTags(value: string) {
  try {
    const parsed = JSON.parse(value) as unknown;

    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === "string");
    }
  } catch {}

  return [];
}

function mapAgentRoleConfig(
  row:
    | {
        role_key: string;
        display_name: string;
        responsibility: string;
        primary_model: string;
        escalation_model: string;
        discord_bot_token: string;
        discord_channel_ids: string;
        skill_tags: string;
        working_rules: string;
        claude_design_access: number;
        harness_enabled: number;
        hot_cache_enabled: number;
        harness_profile: string;
        logic_summary: string;
        reporting_summary: string;
        output_mode: string;
        is_active: number;
        updated_at: string;
      }
    | undefined,
): AgentRoleConfigRecord | null {
  if (!row) {
    return null;
  }

  return {
    roleKey: row.role_key,
    displayName: row.display_name,
    responsibility: row.responsibility,
    primaryModel: row.primary_model,
    escalationModel: row.escalation_model,
    discordBotToken: row.discord_bot_token,
    discordChannelIds: row.discord_channel_ids,
    skillTags: safeParseSkillTags(row.skill_tags),
    workingRules: row.working_rules,
    claudeDesignAccess: row.claude_design_access === 1,
    harnessEnabled: row.harness_enabled === 1,
    hotCacheEnabled: row.hot_cache_enabled === 1,
    harnessProfile: row.harness_profile,
    logicSummary: row.logic_summary,
    reportingSummary: row.reporting_summary,
    outputMode: row.output_mode,
    isActive: row.is_active === 1,
    updatedAt: row.updated_at,
  };
}

function mapAgentActivityLog(
  row:
    | {
        id: number;
        role_key: string;
        event_type: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        channel_target: string | null;
        created_at: string;
        sdlc_task_id?: string;
        project_id?: string;
        metadata?: string;
      }
    | undefined,
): AgentActivityLogRecord | null {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    roleKey: row.role_key,
    eventType: row.event_type,
    taskName: row.task_name,
    status: row.status,
    summary: row.summary,
    artifactRef: row.artifact_ref,
    channelTarget: row.channel_target,
    createdAt: row.created_at,
    sdlcTaskId: row.sdlc_task_id ?? "",
    projectId: row.project_id ?? "",
    metadata: row.metadata ?? "{}",
  };
}

function mapSystemConfig(
  row:
    | {
        id: number;
        config_key: string;
        category: string;
        value: string;
        description: string;
        updated_at: string;
      }
    | undefined,
): SystemConfigRecord | null {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    configKey: row.config_key,
    category: row.category,
    value: row.value,
    description: row.description,
    updatedAt: row.updated_at,
  };
}

function mapProjectHotCache(
  row:
    | {
        cache_key: string;
        title: string;
        summary: string;
        scope: string;
        status: string;
        source_role: string;
        artifact_ref: string | null;
        updated_at: string;
      }
    | undefined,
): ProjectHotCacheRecord | null {
  if (!row) {
    return null;
  }

  return {
    cacheKey: row.cache_key,
    title: row.title,
    summary: row.summary,
    scope: row.scope,
    status: row.status,
    sourceRole: row.source_role,
    artifactRef: row.artifact_ref,
    updatedAt: row.updated_at,
  };
}

function mapApprovalItem(
  row:
    | {
        id: number;
        role_key: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        output_summary: string | null;
        requested_by: string;
        approver: string | null;
        decision_note: string | null;
        channel_target: string | null;
        created_at: string;
        updated_at: string;
        project_id?: string;
        sdlc_task_id?: string;
        role_task_id?: string;
        discord_message_id?: string;
        source_runtime?: string;
        processed_by_runtime_at?: string | null;
        runtime_processed_status?: string | null;
      }
    | undefined,
): ApprovalItemRecord | null {
  if (!row) {
    return null;
  }

  return {
    id: row.id,
    roleKey: row.role_key,
    taskName: row.task_name,
    status: row.status,
    summary: row.summary,
    artifactRef: row.artifact_ref,
    outputSummary: row.output_summary,
    requestedBy: row.requested_by,
    approver: row.approver,
    decisionNote: row.decision_note,
    channelTarget: row.channel_target,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    projectId: row.project_id ?? "",
    sdlcTaskId: row.sdlc_task_id ?? "",
    roleTaskId: row.role_task_id ?? "",
    discordMessageId: row.discord_message_id ?? "",
    sourceRuntime: row.source_runtime ?? "discord",
    processedByRuntimeAt: row.processed_by_runtime_at ?? null,
    runtimeProcessedStatus: row.runtime_processed_status ?? null,
  };
}

export function listAgentRoleConfigs(): AgentRoleConfigRecord[] {
  const rows = db
    .prepare(
      `
        SELECT role_key, display_name, responsibility, primary_model, escalation_model,
               discord_bot_token, discord_channel_ids, skill_tags, working_rules,
               claude_design_access, harness_enabled, hot_cache_enabled, harness_profile,
               logic_summary, reporting_summary, output_mode, is_active, updated_at
        FROM agent_role_configs
        ORDER BY display_name ASC, role_key ASC
      `,
    )
    .all() as Array<{
    role_key: string;
    display_name: string;
    responsibility: string;
    primary_model: string;
    escalation_model: string;
    discord_bot_token: string;
    discord_channel_ids: string;
    skill_tags: string;
    working_rules: string;
    claude_design_access: number;
    harness_enabled: number;
    hot_cache_enabled: number;
    harness_profile: string;
    logic_summary: string;
    reporting_summary: string;
    output_mode: string;
    is_active: number;
    updated_at: string;
  }>;

  return rows
    .map((row) => mapAgentRoleConfig(row))
    .filter((row): row is AgentRoleConfigRecord => row !== null);
}

export function findAgentRoleConfig(roleKey: string): AgentRoleConfigRecord | null {
  const row = db
    .prepare(
      `
        SELECT role_key, display_name, responsibility, primary_model, escalation_model,
               discord_bot_token, discord_channel_ids, skill_tags, working_rules,
               claude_design_access, harness_enabled, hot_cache_enabled, harness_profile,
               logic_summary, reporting_summary, output_mode, is_active, updated_at
        FROM agent_role_configs
        WHERE role_key = ?
        LIMIT 1
      `,
    )
    .get(roleKey) as
    | {
        role_key: string;
        display_name: string;
        responsibility: string;
        primary_model: string;
        escalation_model: string;
        discord_bot_token: string;
        discord_channel_ids: string;
        skill_tags: string;
        working_rules: string;
        claude_design_access: number;
        harness_enabled: number;
        hot_cache_enabled: number;
        harness_profile: string;
        logic_summary: string;
        reporting_summary: string;
        output_mode: string;
        is_active: number;
        updated_at: string;
      }
    | undefined;

  return mapAgentRoleConfig(row);
}

export function createAgentRoleConfig(input: {
  roleKey: string;
  displayName: string;
  responsibility: string;
  primaryModel: string;
  escalationModel: string;
  discordBotToken: string;
  discordChannelIds: string;
  skillTags: string[];
  workingRules: string;
  claudeDesignAccess: boolean;
  harnessEnabled: boolean;
  hotCacheEnabled: boolean;
  harnessProfile: string;
  logicSummary: string;
  reportingSummary: string;
  outputMode: string;
  isActive: boolean;
}) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        INSERT INTO agent_role_configs (
          role_key, display_name, responsibility, primary_model, escalation_model,
          discord_bot_token, discord_channel_ids, skill_tags, working_rules,
          claude_design_access, harness_enabled, hot_cache_enabled, harness_profile,
          logic_summary, reporting_summary, output_mode, is_active, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
    .run(
      input.roleKey,
      input.displayName,
      input.responsibility,
      input.primaryModel,
      input.escalationModel,
      input.discordBotToken,
      input.discordChannelIds,
      JSON.stringify(input.skillTags),
      input.workingRules,
      input.claudeDesignAccess ? 1 : 0,
      input.harnessEnabled ? 1 : 0,
      input.hotCacheEnabled ? 1 : 0,
      input.harnessProfile,
      input.logicSummary,
      input.reportingSummary,
      input.outputMode,
      input.isActive ? 1 : 0,
      now,
    );

  return result.changes > 0;
}

export function updateAgentRoleConfig(
  roleKey: string,
  input: {
    displayName: string;
    responsibility: string;
    primaryModel: string;
    escalationModel: string;
    discordBotToken: string;
    discordChannelIds: string;
    skillTags: string[];
    workingRules: string;
    claudeDesignAccess: boolean;
    harnessEnabled: boolean;
    hotCacheEnabled: boolean;
    harnessProfile: string;
    logicSummary: string;
    reportingSummary: string;
    outputMode: string;
    isActive: boolean;
  },
) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        UPDATE agent_role_configs
        SET display_name = ?,
            responsibility = ?,
            primary_model = ?,
            escalation_model = ?,
            discord_bot_token = ?,
            discord_channel_ids = ?,
            skill_tags = ?,
            working_rules = ?,
            claude_design_access = ?,
            harness_enabled = ?,
            hot_cache_enabled = ?,
            harness_profile = ?,
            logic_summary = ?,
            reporting_summary = ?,
            output_mode = ?,
            is_active = ?,
            updated_at = ?
        WHERE role_key = ?
      `,
    )
    .run(
      input.displayName,
      input.responsibility,
      input.primaryModel,
      input.escalationModel,
      input.discordBotToken,
      input.discordChannelIds,
      JSON.stringify(input.skillTags),
      input.workingRules,
      input.claudeDesignAccess ? 1 : 0,
      input.harnessEnabled ? 1 : 0,
      input.hotCacheEnabled ? 1 : 0,
      input.harnessProfile,
      input.logicSummary,
      input.reportingSummary,
      input.outputMode,
      input.isActive ? 1 : 0,
      now,
      roleKey,
    );

  return result.changes > 0;
}

export function deleteAgentRoleConfig(roleKey: string) {
  const result = db
    .prepare(
      `
        DELETE FROM agent_role_configs
        WHERE role_key = ?
      `,
    )
    .run(roleKey);

  return result.changes > 0;
}

export function listRecentAgentActivityLogs(limit = 25): AgentActivityLogRecord[] {
  const rows = db
    .prepare(
      `
        SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target, created_at
        FROM agent_activity_logs
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
      `,
    )
    .all(limit) as Array<{
    id: number;
    role_key: string;
    event_type: string;
    task_name: string;
    status: string;
    summary: string;
    artifact_ref: string | null;
    channel_target: string | null;
    created_at: string;
  }>;

  return rows
    .map((row) => mapAgentActivityLog(row))
    .filter((row): row is AgentActivityLogRecord => row !== null);
}

export function createAgentActivityLog(input: {
  roleKey: string;
  eventType: string;
  taskName: string;
  status: string;
  summary: string;
  artifactRef?: string;
  channelTarget?: string;
  sdlcTaskId?: string;
  projectId?: string;
  metadata?: string;
}) {
  const createdAt = new Date().toISOString();

  const result = db
    .prepare(
      `
        INSERT INTO agent_activity_logs (
          role_key, event_type, task_name, status, summary, artifact_ref, channel_target, created_at,
          sdlc_task_id, project_id, metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
    .run(
      input.roleKey,
      input.eventType,
      input.taskName,
      input.status,
      input.summary,
      input.artifactRef ?? null,
      input.channelTarget ?? null,
      createdAt,
      input.sdlcTaskId ?? "",
      input.projectId ?? "",
      input.metadata ?? "{}",
    );

  return result.changes > 0;
}

export function countAgentActivityLogs() {
  const row = db
    .prepare(
      `
        SELECT COUNT(*) as count
        FROM agent_activity_logs
      `,
    )
    .get() as { count: number };

  return row.count;
}

export function countAgentActivityLogsByStatus() {
  return db
    .prepare(
      `
        SELECT status, COUNT(*) as count
        FROM agent_activity_logs
        GROUP BY status
        ORDER BY count DESC, status ASC
      `,
    )
    .all() as Array<{ status: string; count: number }>;
}

export function filterAgentActivityLogs(filters: {
  startDate?: string;
  endDate?: string;
  agentId?: string;
  eventType?: string;
  taskId?: string;
  limit?: number;
}): AgentActivityLogRecord[] {
  const limit = filters.limit ?? 100000;
  let query = `
    SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target, created_at
    FROM agent_activity_logs
    WHERE 1=1
  `;
  const params: Array<string | number> = [];

  if (filters.startDate) {
    query += ` AND datetime(created_at) >= datetime(?)`;
    params.push(filters.startDate);
  }

  if (filters.endDate) {
    query += ` AND datetime(created_at) <= datetime(?)`;
    params.push(filters.endDate);
  }

  if (filters.agentId) {
    query += ` AND role_key = ?`;
    params.push(filters.agentId);
  }

  if (filters.eventType) {
    query += ` AND event_type = ?`;
    params.push(filters.eventType);
  }

  if (filters.taskId) {
    query += ` AND task_name = ?`;
    params.push(filters.taskId);
  }

  query += ` ORDER BY datetime(created_at) DESC, id DESC LIMIT ?`;
  params.push(limit);

  const rows = db.prepare(query).all(...params) as Array<{
    id: number;
    role_key: string;
    event_type: string;
    task_name: string;
    status: string;
    summary: string;
    artifact_ref: string | null;
    channel_target: string | null;
    created_at: string;
  }>;

  return rows
    .map((row) => mapAgentActivityLog(row))
    .filter((row): row is AgentActivityLogRecord => row !== null);
}

export function listApprovalItems(status?: string): ApprovalItemRecord[] {
  const rows = (
    status
      ? db
          .prepare(
            `
              SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
                     requested_by, approver, decision_note, channel_target, created_at, updated_at
              FROM approval_items
              WHERE status = ?
              ORDER BY datetime(updated_at) DESC, id DESC
            `,
          )
          .all(status)
      : db
          .prepare(
            `
              SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
                     requested_by, approver, decision_note, channel_target, created_at, updated_at
              FROM approval_items
              ORDER BY datetime(updated_at) DESC, id DESC
            `,
          )
          .all()
  ) as Array<{
    id: number;
    role_key: string;
    task_name: string;
    status: string;
    summary: string;
    artifact_ref: string | null;
    output_summary: string | null;
    requested_by: string;
    approver: string | null;
    decision_note: string | null;
    channel_target: string | null;
    created_at: string;
    updated_at: string;
  }>;

  return rows
    .map((row) => mapApprovalItem(row))
    .filter((row): row is ApprovalItemRecord => row !== null);
}

export function countPendingApprovalItems() {
  const row = db
    .prepare(
      `
        SELECT COUNT(*) as count
        FROM approval_items
        WHERE status = 'waiting_approval'
      `,
    )
    .get() as { count: number };

  return row.count;
}

export function findApprovalItemById(id: number): ApprovalItemRecord | null {
  const row = db
    .prepare(
      `
        SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
               requested_by, approver, decision_note, channel_target, created_at, updated_at,
               project_id, sdlc_task_id, role_task_id, discord_message_id, source_runtime,
               processed_by_runtime_at, runtime_processed_status
        FROM approval_items
        WHERE id = ?
        LIMIT 1
      `,
    )
    .get(id) as
    | {
        id: number;
        role_key: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        output_summary: string | null;
        requested_by: string;
        approver: string | null;
        decision_note: string | null;
        channel_target: string | null;
        created_at: string;
        updated_at: string;
        project_id: string;
        sdlc_task_id: string;
        role_task_id: string;
        discord_message_id: string;
        source_runtime: string;
        processed_by_runtime_at: string | null;
        runtime_processed_status: string | null;
      }
    | undefined;

  return mapApprovalItem(row);
}

export function createApprovalItem(input: {
  roleKey: string;
  taskName: string;
  summary: string;
  artifactRef?: string;
  outputSummary?: string;
  requestedBy: string;
  channelTarget?: string;
  projectId?: string;
  sdlcTaskId?: string;
  roleTaskId?: string;
  discordMessageId?: string;
  sourceRuntime?: string;
}) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        INSERT INTO approval_items (
          role_key, task_name, status, summary, artifact_ref, output_summary,
          requested_by, approver, decision_note, channel_target, created_at, updated_at,
          project_id, sdlc_task_id, role_task_id, discord_message_id, source_runtime
        )
        VALUES (?, ?, 'waiting_approval', ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
    .run(
      input.roleKey,
      input.taskName,
      input.summary,
      input.artifactRef ?? null,
      input.outputSummary ?? null,
      input.requestedBy,
      input.channelTarget ?? null,
      now,
      now,
      input.projectId ?? "",
      input.sdlcTaskId ?? "",
      input.roleTaskId ?? "",
      input.discordMessageId ?? "",
      input.sourceRuntime ?? "discord",
    );

  return result.lastInsertRowid;
}

export function findLatestPendingApprovalItem(
  roleKey: string,
  taskName: string,
): ApprovalItemRecord | null {
  const row = db
    .prepare(
      `
        SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
               requested_by, approver, decision_note, channel_target, created_at, updated_at,
               project_id, sdlc_task_id, role_task_id, discord_message_id, source_runtime,
               processed_by_runtime_at, runtime_processed_status
        FROM approval_items
        WHERE role_key = ? AND task_name = ? AND status = 'waiting_approval'
        ORDER BY id DESC
        LIMIT 1
      `,
    )
    .get(roleKey, taskName) as
    | {
        id: number;
        role_key: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        output_summary: string | null;
        requested_by: string;
        approver: string | null;
        decision_note: string | null;
        channel_target: string | null;
        created_at: string;
        updated_at: string;
        project_id: string;
        sdlc_task_id: string;
        role_task_id: string;
        discord_message_id: string;
        source_runtime: string;
        processed_by_runtime_at: string | null;
        runtime_processed_status: string | null;
      }
    | undefined;
  return row ? mapApprovalItem(row) : null;
}

export function findApprovalItemBySdlcTaskId(sdlcTaskId: string): ApprovalItemRecord | null {
  if (!sdlcTaskId) return null;
  const row = db
    .prepare(
      `
        SELECT id, role_key, task_name, status, summary, artifact_ref, output_summary,
               requested_by, approver, decision_note, channel_target, created_at, updated_at,
               project_id, sdlc_task_id, role_task_id, discord_message_id, source_runtime,
               processed_by_runtime_at, runtime_processed_status
        FROM approval_items
        WHERE sdlc_task_id = ? AND status = 'waiting_approval'
        ORDER BY id DESC
        LIMIT 1
      `,
    )
    .get(sdlcTaskId) as
    | {
        id: number;
        role_key: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        output_summary: string | null;
        requested_by: string;
        approver: string | null;
        decision_note: string | null;
        channel_target: string | null;
        created_at: string;
        updated_at: string;
        project_id: string;
        sdlc_task_id: string;
        role_task_id: string;
        discord_message_id: string;
        source_runtime: string;
        processed_by_runtime_at: string | null;
        runtime_processed_status: string | null;
      }
    | undefined;
  return row ? mapApprovalItem(row) : null;
}

export function markApprovalItemProcessed(id: number, runtimeStatus: string): boolean {
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `
        UPDATE approval_items
        SET processed_by_runtime_at = ?, runtime_processed_status = ?, updated_at = ?
        WHERE id = ?
      `,
    )
    .run(now, runtimeStatus, now, id);
  return result.changes > 0;
}

export function updateApprovalDecision(input: {
  id: number;
  status: "approved" | "rejected" | "rework_requested";
  approver: string;
  decisionNote: string;
}) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        UPDATE approval_items
        SET status = ?, approver = ?, decision_note = ?, updated_at = ?
        WHERE id = ?
      `,
    )
    .run(input.status, input.approver, input.decisionNote, now, input.id);

  return result.changes > 0;
}

export function listSystemConfigs(): SystemConfigRecord[] {
  const rows = db
    .prepare(
      `
        SELECT id, config_key, category, value, description, updated_at
        FROM system_configs
        ORDER BY category ASC, config_key ASC
      `,
    )
    .all() as Array<{
    id: number;
    config_key: string;
    category: string;
    value: string;
    description: string;
    updated_at: string;
  }>;

  return rows
    .map((row) => mapSystemConfig(row))
    .filter((row): row is SystemConfigRecord => row !== null);
}

export function findSystemConfigById(id: number): SystemConfigRecord | null {
  const row = db
    .prepare(
      `
        SELECT id, config_key, category, value, description, updated_at
        FROM system_configs
        WHERE id = ?
        LIMIT 1
      `,
    )
    .get(id) as
    | {
        id: number;
        config_key: string;
        category: string;
        value: string;
        description: string;
        updated_at: string;
      }
    | undefined;

  return mapSystemConfig(row);
}

export function findSystemConfigByKey(configKey: string): SystemConfigRecord | null {
  const row = db
    .prepare(
      `
        SELECT id, config_key, category, value, description, updated_at
        FROM system_configs
        WHERE config_key = ?
        LIMIT 1
      `,
    )
    .get(configKey) as
    | {
        id: number;
        config_key: string;
        category: string;
        value: string;
        description: string;
        updated_at: string;
      }
    | undefined;

  return mapSystemConfig(row);
}

export function createSystemConfig(input: {
  configKey: string;
  category: string;
  value: string;
  description: string;
}) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        INSERT INTO system_configs (config_key, category, value, description, updated_at)
        VALUES (?, ?, ?, ?, ?)
      `,
    )
    .run(input.configKey, input.category, input.value, input.description, now);

  return result.changes > 0;
}

export function updateSystemConfig(
  id: number,
  input: {
    configKey: string;
    category: string;
    value: string;
    description: string;
  },
) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        UPDATE system_configs
        SET config_key = ?, category = ?, value = ?, description = ?, updated_at = ?
        WHERE id = ?
      `,
    )
    .run(input.configKey, input.category, input.value, input.description, now, id);

  return result.changes > 0;
}

export function deleteSystemConfig(id: number) {
  const result = db
    .prepare(
      `
        DELETE FROM system_configs
        WHERE id = ?
      `,
    )
    .run(id);

  return result.changes > 0;
}

export function listProjectHotCache(): ProjectHotCacheRecord[] {
  const rows = db
    .prepare(
      `
        SELECT cache_key, title, summary, scope, status, source_role, artifact_ref, updated_at
        FROM project_hot_cache
        ORDER BY datetime(updated_at) DESC, cache_key ASC
      `,
    )
    .all() as Array<{
    cache_key: string;
    title: string;
    summary: string;
    scope: string;
    status: string;
    source_role: string;
    artifact_ref: string | null;
    updated_at: string;
  }>;

  return rows
    .map((row) => mapProjectHotCache(row))
    .filter((row): row is ProjectHotCacheRecord => row !== null);
}

export function findProjectHotCache(cacheKey: string): ProjectHotCacheRecord | null {
  const row = db
    .prepare(
      `
        SELECT cache_key, title, summary, scope, status, source_role, artifact_ref, updated_at
        FROM project_hot_cache
        WHERE cache_key = ?
        LIMIT 1
      `,
    )
    .get(cacheKey) as
    | {
        cache_key: string;
        title: string;
        summary: string;
        scope: string;
        status: string;
        source_role: string;
        artifact_ref: string | null;
        updated_at: string;
      }
    | undefined;

  return mapProjectHotCache(row);
}

export function upsertProjectHotCache(input: {
  cacheKey: string;
  title: string;
  summary: string;
  scope: string;
  status: string;
  sourceRole: string;
  artifactRef?: string;
}) {
  const now = new Date().toISOString();

  const result = db
    .prepare(
      `
        INSERT INTO project_hot_cache (
          cache_key, title, summary, scope, status, source_role, artifact_ref, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
          title = excluded.title,
          summary = excluded.summary,
          scope = excluded.scope,
          status = excluded.status,
          source_role = excluded.source_role,
          artifact_ref = excluded.artifact_ref,
          updated_at = excluded.updated_at
      `,
    )
    .run(
      input.cacheKey,
      input.title,
      input.summary,
      input.scope,
      input.status,
      input.sourceRole,
      input.artifactRef ?? null,
      now,
    );

  return result.changes > 0;
}

// ─── Task Artifacts ───────────────────────────────────────────────────────────

function mapTaskArtifact(row: {
  id: number;
  sdlc_task_id: string;
  project_id: string;
  role_key: string;
  artifact_type: string;
  artifact_path: string;
  artifact_ref: string;
  created_at: string;
  updated_at: string;
}): TaskArtifactRecord {
  return {
    id: row.id,
    sdlcTaskId: row.sdlc_task_id,
    projectId: row.project_id,
    roleKey: row.role_key,
    artifactType: row.artifact_type,
    artifactPath: row.artifact_path,
    artifactRef: row.artifact_ref,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export function upsertTaskArtifact(input: {
  sdlcTaskId: string;
  projectId?: string;
  roleKey?: string;
  artifactType: string;
  artifactPath?: string;
  artifactRef?: string;
}): boolean {
  const now = new Date().toISOString();
  const result = db
    .prepare(
      `INSERT INTO task_artifacts
         (sdlc_task_id, project_id, role_key, artifact_type, artifact_path, artifact_ref, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(sdlc_task_id, artifact_type) DO UPDATE SET
         artifact_path = excluded.artifact_path,
         artifact_ref  = excluded.artifact_ref,
         role_key      = excluded.role_key,
         project_id    = excluded.project_id,
         updated_at    = excluded.updated_at`,
    )
    .run(
      input.sdlcTaskId,
      input.projectId ?? "",
      input.roleKey ?? "",
      input.artifactType,
      input.artifactPath ?? "",
      input.artifactRef ?? "",
      now,
      now,
    );
  return result.changes > 0;
}

export function listTaskArtifacts(sdlcTaskId: string): TaskArtifactRecord[] {
  const rows = db
    .prepare(
      `SELECT id, sdlc_task_id, project_id, role_key, artifact_type, artifact_path, artifact_ref,
              created_at, updated_at
       FROM task_artifacts
       WHERE sdlc_task_id = ?
       ORDER BY artifact_type ASC`,
    )
    .all(sdlcTaskId) as Array<{
    id: number;
    sdlc_task_id: string;
    project_id: string;
    role_key: string;
    artifact_type: string;
    artifact_path: string;
    artifact_ref: string;
    created_at: string;
    updated_at: string;
  }>;
  return rows.map(mapTaskArtifact);
}

export function listProjectArtifacts(projectId: string): TaskArtifactRecord[] {
  const rows = db
    .prepare(
      `SELECT id, sdlc_task_id, project_id, role_key, artifact_type, artifact_path, artifact_ref,
              created_at, updated_at
       FROM task_artifacts
       WHERE project_id = ?
       ORDER BY sdlc_task_id ASC, artifact_type ASC`,
    )
    .all(projectId) as Array<{
    id: number;
    sdlc_task_id: string;
    project_id: string;
    role_key: string;
    artifact_type: string;
    artifact_path: string;
    artifact_ref: string;
    created_at: string;
    updated_at: string;
  }>;
  return rows.map(mapTaskArtifact);
}

// ─── Task Model Observability ─────────────────────────────────────────────────

export function findLatestTaskLog(sdlcTaskId: string): AgentActivityLogRecord | null {
  const row = db
    .prepare(
      `SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target,
              created_at, sdlc_task_id, project_id, metadata
       FROM agent_activity_logs
       WHERE sdlc_task_id = ?
       ORDER BY id DESC LIMIT 1`,
    )
    .get(sdlcTaskId) as
    | {
        id: number;
        role_key: string;
        event_type: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        channel_target: string | null;
        created_at: string;
        sdlc_task_id: string;
        project_id: string;
        metadata: string;
      }
    | undefined;
  return mapAgentActivityLog(row);
}

export function findLatestTaskCompletionLog(sdlcTaskId: string): AgentActivityLogRecord | null {
  const row = db
    .prepare(
      `SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target,
              created_at, sdlc_task_id, project_id, metadata
       FROM agent_activity_logs
       WHERE sdlc_task_id = ? AND event_type = 'task_completed'
       ORDER BY id DESC LIMIT 1`,
    )
    .get(sdlcTaskId) as
    | {
        id: number;
        role_key: string;
        event_type: string;
        task_name: string;
        status: string;
        summary: string;
        artifact_ref: string | null;
        channel_target: string | null;
        created_at: string;
        sdlc_task_id: string;
        project_id: string;
        metadata: string;
      }
    | undefined;
  return mapAgentActivityLog(row);
}

export function listTaskStates(opts: {
  projectId?: string;
  roleKey?: string;
  limit?: number;
}): Array<{
  sdlcTaskId: string;
  projectId: string;
  roleKey: string;
  taskName: string;
  lastStatus: string;
  lastEventType: string;
  lastLogId: number;
  updatedAt: string;
}> {
  const limit = opts.limit ?? 100;
  let query: string;
  let params: unknown[];

  if (opts.projectId && opts.roleKey) {
    query = `
      SELECT sdlc_task_id, project_id, role_key, task_name,
             status as last_status, event_type as last_event_type,
             id as last_log_id, created_at as updated_at
      FROM agent_activity_logs
      WHERE sdlc_task_id != ''
        AND project_id = ?
        AND role_key = ?
        AND id IN (
          SELECT MAX(id) FROM agent_activity_logs
          WHERE sdlc_task_id != '' AND project_id = ? AND role_key = ?
          GROUP BY sdlc_task_id
        )
      ORDER BY id DESC LIMIT ?`;
    params = [opts.projectId, opts.roleKey, opts.projectId, opts.roleKey, limit];
  } else if (opts.projectId) {
    query = `
      SELECT sdlc_task_id, project_id, role_key, task_name,
             status as last_status, event_type as last_event_type,
             id as last_log_id, created_at as updated_at
      FROM agent_activity_logs
      WHERE sdlc_task_id != '' AND project_id = ?
        AND id IN (
          SELECT MAX(id) FROM agent_activity_logs
          WHERE sdlc_task_id != '' AND project_id = ?
          GROUP BY sdlc_task_id
        )
      ORDER BY id DESC LIMIT ?`;
    params = [opts.projectId, opts.projectId, limit];
  } else {
    query = `
      SELECT sdlc_task_id, project_id, role_key, task_name,
             status as last_status, event_type as last_event_type,
             id as last_log_id, created_at as updated_at
      FROM agent_activity_logs
      WHERE sdlc_task_id != ''
        AND id IN (
          SELECT MAX(id) FROM agent_activity_logs
          WHERE sdlc_task_id != ''
          GROUP BY sdlc_task_id
        )
      ORDER BY id DESC LIMIT ?`;
    params = [limit];
  }

  const rows = db.prepare(query).all(...params) as Array<{
    sdlc_task_id: string;
    project_id: string;
    role_key: string;
    task_name: string;
    last_status: string;
    last_event_type: string;
    last_log_id: number;
    updated_at: string;
  }>;

  return rows.map((r) => ({
    sdlcTaskId: r.sdlc_task_id,
    projectId: r.project_id,
    roleKey: r.role_key,
    taskName: r.task_name,
    lastStatus: r.last_status,
    lastEventType: r.last_event_type,
    lastLogId: r.last_log_id,
    updatedAt: r.updated_at,
  }));
}

// ─── Phase 9.1: Paused Task Events ───────────────────────────────────────────

export type PausedTaskEvent = {
  sdlcTaskId: string;
  taskName: string;
  roleKey: string;
  projectId: string;
  pauseReason: string;
  pauseProvider: string;
  pauseModel: string;
  retryAfterAt: string;
  resumePolicy: string;
  pausedAt: string;
};

export function listPausedTaskEvents(limit = 100): PausedTaskEvent[] {
  // Find only tasks where the most recent event overall is 'paused'.
  // This excludes tasks that were paused but later resumed/completed (their latest
  // event will have a different status, so the correlated MAX(id) won't match).
  const rows = db
    .prepare(
      `SELECT id, role_key, task_name, sdlc_task_id, project_id, metadata, created_at
       FROM agent_activity_logs a
       WHERE sdlc_task_id != ''
         AND status = 'paused'
         AND id = (SELECT MAX(id) FROM agent_activity_logs WHERE sdlc_task_id = a.sdlc_task_id)
       ORDER BY id DESC LIMIT ?`,
    )
    .all(limit) as Array<{
    id: number;
    role_key: string;
    task_name: string;
    sdlc_task_id: string;
    project_id: string;
    metadata: string;
    created_at: string;
  }>;

  return rows.map((row) => {
    let meta: Record<string, string> = {};
    try {
      meta = JSON.parse(row.metadata ?? "{}") as Record<string, string>;
    } catch {}
    return {
      sdlcTaskId: row.sdlc_task_id,
      taskName: row.task_name,
      roleKey: row.role_key,
      projectId: row.project_id ?? "",
      pauseReason: meta["pause_reason"] ?? "",
      pauseProvider: meta["pause_provider"] ?? "",
      pauseModel: meta["pause_model"] ?? "",
      retryAfterAt: meta["retry_after_at"] ?? "",
      resumePolicy: meta["resume_policy"] ?? "auto",
      pausedAt: row.created_at,
    };
  });
}

// Writes system_config flag key=runtime.resume_requested.{sdlcTaskId} so Python can poll it.
// Python consumer: BaseAgent poll loop (Phase 9.3). Flag is cleared by Python after acting on it.
export function upsertResumeRequestFlag(sdlcTaskId: string, operatorUser: string): void {
  const key = `runtime.resume_requested.${sdlcTaskId}`;
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO system_configs (config_key, category, value, description, updated_at)
     VALUES (?, 'runtime', ?, 'Operator-requested resume via web', ?)
     ON CONFLICT(config_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
  ).run(key, operatorUser, now);
}

export function listBlockedEvents(opts: { roleKey?: string; limit?: number }): AgentActivityLogRecord[] {
  const limit = opts.limit ?? 50;
  type ActivityLogRow = {
    id: number; role_key: string; event_type: string; task_name: string; status: string;
    summary: string; artifact_ref: string | null; channel_target: string | null;
    created_at: string; sdlc_task_id: string; project_id: string; metadata: string;
  };
  const rows = opts.roleKey
    ? (db
        .prepare(
          `SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target,
                  created_at, sdlc_task_id, project_id, metadata
           FROM agent_activity_logs
           WHERE event_type = 'devops_blocked' AND role_key = ?
           ORDER BY id DESC LIMIT ?`,
        )
        .all(opts.roleKey, limit) as ActivityLogRow[])
    : (db
        .prepare(
          `SELECT id, role_key, event_type, task_name, status, summary, artifact_ref, channel_target,
                  created_at, sdlc_task_id, project_id, metadata
           FROM agent_activity_logs
           WHERE event_type = 'devops_blocked'
           ORDER BY id DESC LIMIT ?`,
        )
        .all(limit) as ActivityLogRow[]);
  return rows.map((r) => mapAgentActivityLog(r)).filter((r): r is AgentActivityLogRecord => r !== null);
}
