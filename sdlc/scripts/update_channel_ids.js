#!/usr/bin/env node
/**
 * update_channel_ids.js
 *
 * อัปเดต Discord Channel IDs ใน agent_role_configs หลังจากสร้าง Discord channels แล้ว
 *
 * วิธีใช้:
 *   cd ~/projects/multi-ai-agent/webapp
 *
 *   # อัปเดตทีละ role:
 *   node /path/to/scripts/update_channel_ids.js \
 *     --role ceo \
 *     --inbox 1234567890 \
 *     --output 1234567891 \
 *     --timelog 1234567892
 *
 *   # อัปเดตทุก role พร้อมกัน (จาก JSON file):
 *   node /path/to/scripts/update_channel_ids.js --from-json channels.json
 *
 * channels.json format:
 * {
 *   "ceo":      { "inbox": "...", "output": "...", "timelog": "..." },
 *   "pm":       { "inbox": "...", "output": "...", "timelog": "..." },
 *   ...
 * }
 *
 * วิธีหา Channel ID:
 *   Discord Settings → Advanced → Developer Mode: ON
 *   Right-click channel → Copy Channel ID
 */

const path = require('path');
const fs = require('fs');

let Database;
try {
  Database = require('better-sqlite3');
} catch (e) {
  console.error('❌ better-sqlite3 not found. Run: npm install better-sqlite3');
  process.exit(1);
}

function findDatabase() {
  const candidates = [
    path.join(process.cwd(), 'data', 'multi-ai-agent-app.db'),
    path.join(process.cwd(), 'data', 'app.db'),
    path.join(process.cwd(), 'data', 'database.db'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error('Database not found. Run seed_webapp_configs.js first.');
}

function parseArgs() {
  const args = process.argv.slice(2);
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      result[args[i].slice(2)] = args[i + 1];
      i++;
    }
  }
  return result;
}

function main() {
  const args = parseArgs();
  const db = new Database(findDatabase());
  db.pragma('journal_mode = WAL');

  const updateStmt = db.prepare(`
    UPDATE agent_role_configs
    SET discord_channel_ids = @channel_ids, updated_at = datetime('now')
    WHERE role_key = @role_key
  `);

  if (args['from-json']) {
    // Bulk update from JSON file
    const jsonPath = path.resolve(args['from-json']);
    if (!fs.existsSync(jsonPath)) {
      console.error(`❌ File not found: ${jsonPath}`);
      process.exit(1);
    }
    const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    console.log(`\n📋 Updating channel IDs from ${jsonPath}...\n`);

    for (const [roleKey, ids] of Object.entries(data)) {
      const result = updateStmt.run({
        role_key: roleKey,
        channel_ids: JSON.stringify(ids),
      });
      if (result.changes > 0) {
        console.log(`  ✅ ${roleKey.padEnd(10)} inbox=${ids.inbox?.slice(-6)} output=${ids.output?.slice(-6)} timelog=${ids.timelog?.slice(-6)}`);
      } else {
        console.log(`  ⚠️  ${roleKey} — role not found in DB (run seed first)`);
      }
    }
  } else if (args.role) {
    // Single role update
    const { role, inbox, output, timelog } = args;
    if (!inbox || !output || !timelog) {
      console.error('Usage: --role <role> --inbox <id> --output <id> --timelog <id>');
      process.exit(1);
    }
    const result = updateStmt.run({
      role_key: role,
      channel_ids: JSON.stringify({ inbox, output, timelog }),
    });
    if (result.changes > 0) {
      console.log(`\n✅ Updated ${role}: inbox=${inbox} output=${output} timelog=${timelog}\n`);
    } else {
      console.error(`❌ Role "${role}" not found. Run seed_webapp_configs.js first.`);
    }
  } else {
    // Show current state
    const roles = db.prepare('SELECT role_key, discord_channel_ids FROM agent_role_configs ORDER BY role_key').all();
    console.log('\n📋 Current Discord Channel IDs:\n');
    for (const row of roles) {
      const ids = JSON.parse(row.discord_channel_ids || '{}');
      const hasIds = ids.inbox && ids.inbox !== '000000000000000000';
      console.log(`  ${hasIds ? '✅' : '⚠️ '} ${row.role_key.padEnd(10)} inbox=${ids.inbox || 'NOT SET'}`);
    }
    console.log('\nTo update, use:');
    console.log('  node update_channel_ids.js --role ceo --inbox <id> --output <id> --timelog <id>');
    console.log('  node update_channel_ids.js --from-json channels.json\n');
  }

  db.close();
}

main();
