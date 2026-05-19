# 🔗 Integration Guide: Discord Bots ↔ Next.js Web App

ระบบนี้เชื่อม Python Discord Bots กับ Next.js Web App ที่รันอยู่ที่ `http://localhost:3000`

## สถาปัตยกรรมการเชื่อมต่อ

```
Human (Discord)
     │  !new project | !approve | !revise | !reject
     ▼
Discord Bots (Python discord.py) ── x9 bots ─────────────────┐
     │                                                         │
     │  process_task() → LLM (Claude/GPT/Groq/Ollama)         │
     │                                                         │
     │  POST /api/agent-activity/ingest                        │
     │  Bearer: AGENT_SYNC_TOKEN                               │
     ▼                                                         ▼
Next.js Web App (port 3000)                            SQLite (discord bots)
  ├── agent_activity_logs                              (local state machine)
  ├── approval_items
  ├── agent_role_configs
  └── project_hot_cache
```

Events ที่ส่งจาก Bot → Web App:
| Event | เมื่อไหร่ | Status ใน Web |
|-------|---------|-------------|
| `task_started` | Bot เริ่ม LLM call | `in_progress` |
| `task_completed` | Bot ส่ง approval embed | `waiting_approval` |
| `approved` | Human พิมพ์ `!approve` | `approved` |
| `revision_requested` | Human พิมพ์ `!revise` | `rework_requested` |
| `rejected` | Human พิมพ์ `!reject` | `rejected` |
| `error` | Bot เจอ exception | `blocked` |

---

## Step-by-Step Setup

### Step 1: เตรียม Web App

```bash
# เปิด Web App
cd ~/projects/multi-ai-agent-app
pm2 start ecosystem.config.js   # หรือ npm run dev

# ตรวจสอบว่ารันอยู่
curl http://localhost:3000/api/health
```

### Step 2: Seed Database

```bash
cd ~/projects/multi-ai-agent-app

# รัน seed script (จาก Ai-Agent-SDLC folder)
node ~/Ai-Agent-SDLC/scripts/seed_webapp_configs.js
```

Output ที่ได้:
```
✅ Found database: /home/ubuntu/projects/multi-ai-agent-app/data/multi-ai-agent-app.db
🌱 Seeding Multi-AI-Agent SDLC configurations...

📋 Setting up system_configs...
  ✅ reporting.agent_sync_ingest_enabled = true
  ✅ reporting.agent_sync_ingest_token = a1b2c3d4...
  ✅ sdlc.daily_budget_usd = 2.00
  ✅ sdlc.max_revision_rounds = 3

🤖 Setting up agent_role_configs...
  ✅ ceo        → claude-haiku-4-5-20251001
  ✅ pm         → claude-haiku-4-5-20251001
  ...

🔑 AGENT_SYNC_TOKEN=a1b2c3d4e5f6...  ← COPY นี้
```

### Step 3: Copy Token ไปใส่ .env

```bash
cd ~/Ai-Agent-SDLC
cp .env.example .env
nano .env
```

เพิ่ม/แก้ไข:
```env
WEB_APP_URL=http://localhost:3000
AGENT_SYNC_TOKEN=a1b2c3d4e5f6...   # จาก Step 2

# Discord Tokens (9 bots)
CEO_DISCORD_TOKEN=Bot_XXXXX
PM_DISCORD_TOKEN=Bot_XXXXX
# ...

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: สร้าง Discord Server + Channels

ดูคู่มือ: `discord/CHANNEL_SETUP.md`

โครงสร้างที่ต้องสร้าง (30 channels):
```
📁 CONTROL
  #ceo-input       ← Human พิมพ์ !new
  #approvals       ← Human approve/revise/reject
  #project-dashboard

📁 CEO
  #ceo-inbox       ← bot รับงาน
  #ceo-output      ← bot ส่งผล
  #ceo-timelog     ← time tracking

📁 PM
  #pm-inbox / #pm-output / #pm-timelog

... (ทุก role แบบเดียวกัน)
```

### Step 5: อัปเดต Discord Channel IDs

เปิด Developer Mode ใน Discord:
```
Discord Settings → Advanced → Developer Mode: ON
```

Copy Channel IDs แล้วอัปเดต:
```bash
# ทีละ role:
cd ~/projects/multi-ai-agent-app
node ~/Ai-Agent-SDLC/scripts/update_channel_ids.js \
  --role ceo \
  --inbox 1234567890123456789 \
  --output 1234567890123456790 \
  --timelog 1234567890123456791

# หรือ bulk update จาก JSON:
cat > channels.json << 'EOF'
{
  "ceo":      { "inbox": "111", "output": "112", "timelog": "113" },
  "pm":       { "inbox": "211", "output": "212", "timelog": "213" },
  "ba":       { "inbox": "311", "output": "312", "timelog": "313" },
  "sa":       { "inbox": "411", "output": "412", "timelog": "413" },
  "uxui":     { "inbox": "511", "output": "512", "timelog": "513" },
  "frontend": { "inbox": "611", "output": "612", "timelog": "613" },
  "backend":  { "inbox": "711", "output": "712", "timelog": "713" },
  "qa":       { "inbox": "811", "output": "812", "timelog": "813" },
  "devops":   { "inbox": "911", "output": "912", "timelog": "913" }
}
EOF
node ~/Ai-Agent-SDLC/scripts/update_channel_ids.js --from-json channels.json
```

### Step 6: Install Python Dependencies

```bash
cd ~/Ai-Agent-SDLC
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` ที่ต้องการ:
```
discord.py>=2.3.0
anthropic>=0.25.0
openai>=1.20.0
groq>=0.8.0
httpx>=0.27.0        # สำหรับ WebAppBridge
python-dotenv>=1.0.0
```

### Step 7: รัน Discord Bots

**Option A: รันทีละตัว (dev/test)**
```bash
cd ~/Ai-Agent-SDLC
source venv/bin/activate

python -m agents.ceo.agent &
python -m agents.pm.agent &
python -m agents.ba.agent &
# ... ต่อไปทุก role
```

**Option B: PM2 (production)**
```bash
# สร้าง ecosystem.config.js สำหรับ bots
cat > ~/Ai-Agent-SDLC/ecosystem.bots.config.js << 'EOF'
module.exports = {
  apps: [
    { name: 'sdlc-ceo',      script: 'python', args: '-m agents.ceo.agent',      cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-pm',       script: 'python', args: '-m agents.pm.agent',       cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-ba',       script: 'python', args: '-m agents.ba.agent',       cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-sa',       script: 'python', args: '-m agents.sa.agent',       cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-uxui',     script: 'python', args: '-m agents.uxui.agent',     cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-frontend', script: 'python', args: '-m agents.frontend.agent', cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-backend',  script: 'python', args: '-m agents.backend.agent',  cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-qa',       script: 'python', args: '-m agents.qa.agent',       cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
    { name: 'sdlc-devops',   script: 'python', args: '-m agents.devops.agent',   cwd: '/home/ubuntu/Ai-Agent-SDLC', interpreter: 'none' },
  ]
}
EOF

pm2 start ~/Ai-Agent-SDLC/ecosystem.bots.config.js
pm2 save
```

### Step 8: ทดสอบ

```bash
# 1. ตรวจสอบ token ทำงาน
curl -X POST http://localhost:3000/api/agent-activity/ingest \
  -H "Authorization: Bearer YOUR_AGENT_SYNC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "roleKey": "ceo",
    "eventType": "task_started",
    "taskName": "Test Task",
    "status": "in_progress",
    "summary": "Testing integration",
    "channelTarget": "ceo-inbox"
  }'

# ควรได้: {"success": true, "status": "logged"}

# 2. เปิด Discord → #ceo-input → พิมพ์:
!new MyProject | Build a trading bot | Automate crypto trading
```

---

## Troubleshooting

### Token ไม่ทำงาน (401 Unauthorized)
```bash
# ตรวจสอบ token ใน DB
cd ~/projects/multi-ai-agent-app
node -e "
const db = require('better-sqlite3')('data/multi-ai-agent-app.db');
console.log(db.prepare(\"SELECT value FROM system_configs WHERE config_key='reporting.agent_sync_ingest_token'\").get());
"
```
→ ต้องตรงกับ `AGENT_SYNC_TOKEN` ใน `.env` ของ bots

### Bot ไม่ respond
```bash
# ดู logs
pm2 logs sdlc-ceo --lines 50

# ตรวจสอบ token
echo $CEO_DISCORD_TOKEN | head -c 20
```

### Web App ไม่ได้ข้อมูล
```bash
# ตรวจสอบ ingest endpoint
curl -I http://localhost:3000/api/agent-activity/ingest

# ดู PM2 logs ของ Next.js
pm2 logs multi-ai-agent-app --lines 50
```

### ดูสถานะทั้งหมด
```bash
pm2 status    # ดู processes ทั้งหมด
pm2 monit     # real-time monitor
```

---

## File Structure

```
Ai-Agent-SDLC/
├── shared/
│   ├── web_bridge.py       ← NEW: POST → /api/agent-activity/ingest
│   ├── base_agent.py       ← UPDATED: calls web_bridge at every event
│   ├── model_router.py     ← Dynamic model selection
│   ├── llm_client.py       ← Multi-provider LLM client
│   ├── timelog.py          ← Jira-style Discord time logging
│   ├── channel_config.py   ← 3-channel structure per role
│   └── storage.py          ← SQLite state machine
├── agents/
│   ├── ceo/agent.py
│   ├── pm/agent.py
│   ├── ba/agent.py
│   ├── sa/agent.py
│   ├── uxui/agent.py
│   ├── frontend/agent.py
│   ├── backend/agent.py
│   ├── qa/agent.py
│   └── devops/agent.py
├── scripts/
│   ├── seed_webapp_configs.js    ← NEW: seed Next.js DB
│   ├── update_channel_ids.js     ← NEW: update Discord channel IDs
│   └── ubuntu_setup.sh
├── discord/CHANNEL_SETUP.md
├── .env.example                  ← UPDATED: added WEB_APP_URL, AGENT_SYNC_TOKEN
├── INTEGRATION.md                ← THIS FILE
└── requirements.txt
```
