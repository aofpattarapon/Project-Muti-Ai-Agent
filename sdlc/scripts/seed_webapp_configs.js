#!/usr/bin/env node
/**
 * seed_webapp_configs.js
 *
 * Seed ข้อมูลใน Next.js SQLite Database สำหรับ Multi-AI-Agent SDLC System
 *
 * ทำอะไร:
 *   1. สร้าง/อัปเดต system_configs → reporting.agent_sync_ingest_token
 *   2. สร้าง/อัปเดต agent_role_configs สำหรับทุก 9 roles
 *
 * วิธีใช้:
 *   cd ~/projects/multi-ai-agent/webapp
 *   node ~/projects/multi-ai-agent/sdlc/scripts/seed_webapp_configs.js
 *
 *   หรือถ้าอยู่ใน folder เดียวกัน:
 *   node scripts/seed_webapp_configs.js
 *
 * ต้องการ .env ใน webapp ที่มี:
 *   (ใช้ค่า default ถ้าไม่มี)
 */

const path = require('path');
const crypto = require('crypto');
const fs = require('fs');

// ─── ค้นหา Database ─────────────────────────────────────────────────────────

function findDatabase() {
  const candidates = [
    path.join(process.cwd(), 'data', 'multi-ai-agent-app.db'),
    path.join(process.cwd(), 'data', 'app.db'),
    path.join(process.cwd(), 'data', 'database.db'),
    path.join(process.cwd(), 'data', 'sdlc.db'),
    path.join(__dirname, '..', 'data', 'multi-ai-agent-app.db'),
  ];

  // ลองอ่าน DATABASE_URL จาก .env
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const match = envContent.match(/DATABASE_URL\s*=\s*(.+)/);
    if (match) {
      const dbUrl = match[1].trim().replace(/^file:/, '');
      if (!dbUrl.startsWith('postgresql') && !dbUrl.startsWith('postgres')) {
        candidates.unshift(path.resolve(process.cwd(), dbUrl));
      }
    }
  }

  for (const c of candidates) {
    if (fs.existsSync(c)) {
      console.log(`✅ Found database: ${c}`);
      return c;
    }
  }

  // สร้าง data dir ถ้าไม่มี แล้ว return default path
  const defaultPath = path.join(process.cwd(), 'data', 'multi-ai-agent-app.db');
  fs.mkdirSync(path.dirname(defaultPath), { recursive: true });
  console.log(`⚠️  Database not found — will create: ${defaultPath}`);
  return defaultPath;
}

// ─── Load better-sqlite3 ────────────────────────────────────────────────────

let Database;
try {
  Database = require('better-sqlite3');
} catch (e) {
  console.error('❌ better-sqlite3 not found. Run: npm install better-sqlite3');
  process.exit(1);
}

// ─── Config ─────────────────────────────────────────────────────────────────

// Generate secure token ถ้ายังไม่มี
const SYNC_TOKEN = process.env.AGENT_SYNC_TOKEN || crypto.randomBytes(32).toString('hex');

// Discord channel IDs (จะอัปเดตทีหลังด้วยค่าจริง)
const PLACEHOLDER_CHANNEL_IDS = {
  inbox:   '000000000000000000',
  output:  '000000000000000000',
  timelog: '000000000000000000',
  approvals: '000000000000000000',
};

const ROLE_CONFIGS = [
  {
    roleKey: 'ceo',
    displayName: 'CEO Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['requirement_analysis', 'project_brief', 'epic_breakdown'],
    workingRules: 'รับ requirement จาก Human → สร้าง Project Brief + Epics → ส่งต่อ PM',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'pm',
    displayName: 'PM Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['project_planning', 'timeline', 'risk_management', 'raci'],
    workingRules: 'รับ Project Brief → สร้าง Project Plan, Timeline, Risk Register, RACI Matrix',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'ba',
    displayName: 'BA Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['brd', 'use_cases', 'user_stories', 'data_dictionary'],
    workingRules: 'รับ Project Plan → สร้าง BRD, Use Cases, User Stories, Data Dictionary',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'sa',
    displayName: 'SA Agent',
    primaryModel: 'claude-sonnet-4-6',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['system_architecture', 'database_design', 'api_spec', 'openapi'],
    workingRules: 'รับ Requirements → สร้าง Architecture Diagram, DB Schema, OpenAPI Spec (Swagger YAML)',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'uxui',
    displayName: 'UXUI Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['wireframe', 'design_system', 'user_flow', 'component_spec'],
    workingRules: 'รับ Architecture + User Stories → สร้าง Wireframe Spec, Design System, User Flow Diagram',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'frontend',
    displayName: 'Frontend Dev Agent',
    primaryModel: 'claude-sonnet-4-6',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['nextjs', 'typescript', 'mvc', 'react', 'tailwind'],
    workingRules: 'รับ Design + API Spec → เขียน Next.js 14 + TypeScript MVC code ครบ project structure',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'backend',
    displayName: 'Backend Dev Agent',
    primaryModel: 'claude-sonnet-4-6',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['fastapi', 'sqlalchemy', 'postgresql', 'swagger', 'alembic'],
    workingRules: 'รับ API Spec + DB Design → เขียน FastAPI + SQLAlchemy code พร้อม Swagger /docs',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'qa',
    displayName: 'QA Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['test_plan', 'pytest', 'bug_report', 'test_cases'],
    workingRules: 'รับ Code จาก Frontend + Backend → สร้าง Test Plan, pytest tests, Bug Report',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
  {
    roleKey: 'devops',
    displayName: 'DevOps Agent',
    primaryModel: 'claude-haiku-4-5-20251001',
    escalationModel: 'claude-sonnet-4-6',
    skillTags: ['docker', 'docker_compose', 'github_actions', 'cicd', 'deployment'],
    workingRules: 'รับ Tested Code → สร้าง Dockerfile, docker-compose, GitHub Actions CI/CD pipeline',
    discordChannelIds: {
      inbox: PLACEHOLDER_CHANNEL_IDS.inbox,
      output: PLACEHOLDER_CHANNEL_IDS.output,
      timelog: PLACEHOLDER_CHANNEL_IDS.timelog,
    },
  },
];

// ─── Main ────────────────────────────────────────────────────────────────────

function main() {
  const dbPath = findDatabase();
  const db = new Database(dbPath);

  // Enable WAL mode for better concurrency
  db.pragma('journal_mode = WAL');

  console.log('\n🌱 Seeding Multi-AI-Agent SDLC configurations...\n');

  // ─── 1. system_configs ──────────────────────────────────────────────────────
  console.log('📋 Setting up system_configs...');

  const configsToSet = [
    {
      id: 'reporting-ingest-enabled',
      config_key: 'reporting.agent_sync_ingest_enabled',
      category: 'reporting',
      value: 'true',
      description: 'Enable agent activity ingest endpoint',
    },
    {
      id: 'reporting-ingest-token',
      config_key: 'reporting.agent_sync_ingest_token',
      category: 'reporting',
      value: SYNC_TOKEN,
      description: 'Bearer token for /api/agent-activity/ingest',
    },
    {
      id: 'sdlc-daily-budget',
      config_key: 'sdlc.daily_budget_usd',
      category: 'sdlc',
      value: '2.00',
      description: 'Daily LLM budget in USD before forcing free models',
    },
    {
      id: 'sdlc-max-revisions',
      config_key: 'sdlc.max_revision_rounds',
      category: 'sdlc',
      value: '3',
      description: 'Maximum revision rounds per agent phase',
    },
  ];

  // Check if system_configs table exists
  const tableExists = db.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='system_configs'"
  ).get();

  if (!tableExists) {
    console.log('  ⚠️  system_configs table not found — creating it...');
    db.exec(`
      CREATE TABLE IF NOT EXISTS system_configs (
        id TEXT PRIMARY KEY,
        config_key TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        value TEXT,
        description TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      )
    `);
  }

  const upsertConfig = db.prepare(`
    INSERT INTO system_configs (id, config_key, category, value, description, updated_at)
    VALUES (@id, @config_key, @category, @value, @description, datetime('now'))
    ON CONFLICT(config_key) DO UPDATE SET
      value = excluded.value,
      updated_at = datetime('now')
  `);

  for (const cfg of configsToSet) {
    upsertConfig.run(cfg);
    const display = cfg.config_key === 'reporting.agent_sync_ingest_token'
      ? cfg.value.slice(0, 8) + '...'
      : cfg.value;
    console.log(`  ✅ ${cfg.config_key} = ${display}`);
  }

  // ─── 2. agent_role_configs ──────────────────────────────────────────────────
  console.log('\n🤖 Setting up agent_role_configs...');

  const roleTableExists = db.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_role_configs'"
  ).get();

  if (!roleTableExists) {
    console.log('  ⚠️  agent_role_configs table not found — creating it...');
    db.exec(`
      CREATE TABLE IF NOT EXISTS agent_role_configs (
        role_key TEXT PRIMARY KEY,
        display_name TEXT,
        primary_model TEXT,
        escalation_model TEXT,
        discord_bot_token TEXT,
        discord_channel_ids TEXT,
        skill_tags TEXT,
        working_rules TEXT,
        is_active INTEGER DEFAULT 1,
        harness_enabled INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      )
    `);
  }

  const upsertRole = db.prepare(`
    INSERT INTO agent_role_configs (
      role_key, display_name, primary_model, escalation_model,
      discord_channel_ids, skill_tags, working_rules,
      is_active, harness_enabled, updated_at
    )
    VALUES (
      @role_key, @display_name, @primary_model, @escalation_model,
      @discord_channel_ids, @skill_tags, @working_rules,
      1, 0, datetime('now')
    )
    ON CONFLICT(role_key) DO UPDATE SET
      display_name       = excluded.display_name,
      primary_model      = excluded.primary_model,
      escalation_model   = excluded.escalation_model,
      discord_channel_ids = excluded.discord_channel_ids,
      skill_tags         = excluded.skill_tags,
      working_rules      = excluded.working_rules,
      updated_at         = datetime('now')
  `);

  for (const role of ROLE_CONFIGS) {
    upsertRole.run({
      role_key: role.roleKey,
      display_name: role.displayName,
      primary_model: role.primaryModel,
      escalation_model: role.escalationModel,
      discord_channel_ids: JSON.stringify(role.discordChannelIds),
      skill_tags: JSON.stringify(role.skillTags),
      working_rules: role.workingRules,
    });
    console.log(`  ✅ ${role.roleKey.padEnd(10)} → ${role.primaryModel}`);
  }

  // ─── 3. Verify ─────────────────────────────────────────────────────────────
  console.log('\n🔍 Verifying...');

  const tokenRow = db.prepare(
    "SELECT value FROM system_configs WHERE config_key = 'reporting.agent_sync_ingest_token'"
  ).get();
  const roleCount = db.prepare('SELECT COUNT(*) as count FROM agent_role_configs').get();

  console.log(`  Token set:   ${tokenRow ? '✅ yes' : '❌ NO'}`);
  console.log(`  Agent roles: ${roleCount.count} / ${ROLE_CONFIGS.length}`);

  db.close();

  // ─── 4. Print next steps ────────────────────────────────────────────────────
  console.log('\n' + '═'.repeat(60));
  console.log('✅ Seed complete!\n');
  console.log('📋 Next Steps:\n');
  console.log('1. Add to your Discord Bot Python .env:');
  console.log(`   WEB_APP_URL=http://localhost:3000`);
  console.log(`   AGENT_SYNC_TOKEN=${SYNC_TOKEN}\n`);
  console.log('2. Make sure the web app is running:');
  console.log('   cd ~/projects/multi-ai-agent/webapp && pm2 start ecosystem.config.js\n');
  console.log('3. Update Discord channel IDs in agent_role_configs:');
  console.log('   node scripts/update_channel_ids.js\n');
  console.log('4. Start Discord bots:');
  console.log('   cd ~/projects/multi-ai-agent/sdlc && python -m agents.ceo.agent\n');
  console.log('═'.repeat(60));
  console.log(`\n🔑 AGENT_SYNC_TOKEN=${SYNC_TOKEN}`);
  console.log('   (Save this to your .env files)\n');
}

main();
