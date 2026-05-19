# 🚀 MASTER SETUP GUIDE — 0 → Running

> **เริ่มจาก OrbStack Ubuntu ใหม่ → Bot ทุกตัว Online ใน Discord**
> ทำตามลำดับ copy-paste ได้เลย

---

## ✅ สิ่งที่ต้องมีก่อน

| สิ่ง | ตรวจสอบ | ลิงก์ |
|-----|--------|-------|
| OrbStack + Ubuntu 24.04 | เปิด OrbStack เห็น Ubuntu | [orbstack.dev](https://orbstack.dev) |
| Anthropic API Key | `sk-ant-...` | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI API Key | `sk-...` | [platform.openai.com](https://platform.openai.com) |
| Groq API Key (ฟรี) | `gsk_...` | [console.groq.com](https://console.groq.com) |
| Discord Account | มี Server ที่เป็น Admin | [discord.com](https://discord.com) |

---

## PHASE 1 — ติดตั้ง Ubuntu (OrbStack Terminal)

### เปิด Terminal ใน OrbStack Ubuntu
```
OrbStack → Ubuntu → Open Terminal
หรือ SSH: ssh ubuntu@orb
```

### 1.1 รัน Setup Script
```bash
# Download + รัน setup script ทีเดียว
curl -fsSL https://raw.githubusercontent.com/your-repo/main/scripts/ubuntu_setup.sh | bash

# หรือถ้า copy มาจาก Mac แล้ว:
chmod +x ~/sdlc-agents/scripts/ubuntu_setup.sh
bash ~/sdlc-agents/scripts/ubuntu_setup.sh
```

Script จะติดตั้ง: Python 3.11, Ollama, Docker, Project structure

### 1.2 ตรวจสอบ Ollama
```bash
# ดู models ที่ pull แล้ว
ollama list

# ทดสอบ hermes3
ollama run hermes3 "สวัสดี บอกฉันว่าคุณทำอะไรได้บ้าง"

# ดู API
curl http://localhost:11434/api/tags | python3 -m json.tool
```

---

## PHASE 2 — Copy Project Files จาก Mac

### วิธี 1: scp (แนะนำ)
```bash
# บน Mac Terminal
PROJECT="~/Desktop/Muti-Ai-Agent for claude/Ai-Agent-SDLC"
scp -r "$PROJECT"/* ubuntu@orb:~/sdlc-agents/

# ตรวจสอบ
ssh ubuntu@orb "ls ~/sdlc-agents/"
```

### วิธี 2: OrbStack Shared Files
```
OrbStack → Files → drag & drop ไปที่ Ubuntu home
```

### วิธี 3: Git (ถ้ามี repo)
```bash
cd ~/sdlc-agents
git init
git remote add origin https://github.com/yourname/sdlc-agents.git
git pull origin main
```

---

## PHASE 3 — ตั้งค่า Environment Variables

```bash
cd ~/sdlc-agents
nano .env
```

ใส่ค่าทั้งหมดนี้:
```env
# ── API Keys ──────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx   # สมัครฟรีที่ console.groq.com

# ── Discord (ใส่หลังทำ Phase 4) ──────────────────
CEO_DISCORD_TOKEN=
PM_DISCORD_TOKEN=
BA_DISCORD_TOKEN=
SA_DISCORD_TOKEN=
UXUI_DISCORD_TOKEN=
DEV_DISCORD_TOKEN=
QA_DISCORD_TOKEN=
DEVOPS_DISCORD_TOKEN=

DISCORD_GUILD_ID=
DISCORD_APPROVAL_CHANNEL_ID=

# ── Ollama (Local Free) ───────────────────────────
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL_CODE=hermes3

# ── Dynamic Model Router ──────────────────────────
DAILY_BUDGET_USD=1.00        # หยุดใช้ paid model ถ้าเกินนี้/วัน
COMPLEXITY_FREE_THRESHOLD=40  # < 40  → ฟรี (Ollama/Groq)
COMPLEXITY_CHEAP_THRESHOLD=70 # 40-70 → Haiku/GPT-4o-mini
                               # > 70  → Sonnet (งาน complex)

# ── Storage ───────────────────────────────────────
DB_PATH=/home/ubuntu/sdlc-agents/data/sdlc.db
OUTPUT_BASE_PATH=/home/ubuntu/sdlc-agents/outputs
LOG_LEVEL=INFO
```

บันทึก: `Ctrl+O → Enter → Ctrl+X`

---

## PHASE 4 — สร้าง Discord Bots (ทำครั้งเดียว)

### 4.1 สร้าง Discord Server
```
Discord → + (Add Server) → Create My Own → "SDLC Multi-Agent"
```

### 4.2 สร้าง Channels
```
สร้าง Text Channels ต่อไปนี้:
📁 CONTROL
  #ceo-input        ← Human พิมพ์ requirement ที่นี่
  #approvals        ← Human approve/revise/reject ที่นี่ ⚠️

📁 AGENTS  
  #ceo-agent
  #pm-agent
  #ba-agent
  #sa-agent
  #uxui-agent
  #dev-agent
  #qa-agent
  #devops-agent
```

### 4.3 สร้าง Bot Application (ทำซ้ำ 8 ครั้ง)

ไปที่: https://discord.com/developers/applications

สำหรับแต่ละ Role (CEO, PM, BA, SA, UXUI, DEV, QA, DEVOPS):

```
1. New Application → ชื่อ: "SDLC-CEO" (หรือ PM, BA, ...)
2. Bot → Add Bot → ตั้งชื่อ: "[CEO] SDLC Agent"
3. เปิด: Message Content Intent ✅
         Server Members Intent   ✅
         Presence Intent         ✅
4. Reset Token → Copy Token → ใส่ใน .env (CEO_DISCORD_TOKEN=...)
5. OAuth2 → URL Generator:
   - Scopes: bot ✅
   - Permissions: Send Messages, Read Messages, Read History,
                  Add Reactions, Embed Links, Attach Files ✅
6. Copy URL → เปิดใน Browser → เลือก Server → Authorize
```

### 4.4 Copy Channel + Server IDs

```
Discord Settings → Advanced → Developer Mode: ON ✅

Right-click Server name → Copy Server ID → DISCORD_GUILD_ID=...
Right-click #approvals → Copy ID → DISCORD_APPROVAL_CHANNEL_ID=...
```

ใส่ใน `.env` แล้วบันทึก

---

## PHASE 5 — Install Python Packages

```bash
cd ~/sdlc-agents
source venv/bin/activate   # activate virtual env
pip install -r requirements.txt
```

---

## PHASE 6 — ทดสอบ Model Router

```bash
cd ~/sdlc-agents
source venv/bin/activate

python3 - << 'EOF'
from shared.model_router import get_router, ModelTier

router = get_router()

# ทดสอบ routing
test_cases = [
    ("สรุปสั้นๆ ว่า project นี้ทำอะไร", "ceo"),
    ("ออกแบบ system architecture สำหรับ distributed microservices", "sa"),
    ("เขียน unit tests สำหรับ trading bot", "dev"),
    ("สร้าง Dockerfile และ docker-compose", "devops"),
]

print("\n=== Dynamic Model Router Test ===\n")
for prompt, role in test_cases:
    cfg, key, score = router.route(prompt, role)
    tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(cfg.tier, "?")
    print(f"Role: {role:8} | Score: {score:3}/100 | {tier_emoji} {key}")

print("\n✅ Router working!")
EOF
```

ผลลัพธ์ที่ควรเห็น:
```
=== Dynamic Model Router Test ===

Role: ceo      | Score:  25/100 | 🆓 groq/llama-3.3-70b
Role: sa       | Score:  75/100 | 🧠 anthropic/claude-sonnet
Role: dev      | Score:  60/100 | 💰 openai/gpt-4o-mini
Role: devops   | Score:  55/100 | 🆓 ollama/hermes3
```

---

## PHASE 7 — Start Agents!

```bash
cd ~/sdlc-agents
source venv/bin/activate
./scripts/start.sh
```

ดู logs:
```bash
tail -f logs/ceo.log
tail -f logs/dev.log

# ดูทุก agent พร้อมกัน
tail -f logs/*.log
```

---

## PHASE 8 — ทดสอบ End-to-End

### 8.1 ทดสอบ Bot Online
เปิด Discord → เห็น Bot ทุกตัวสีเขียว (online) ✅

### 8.2 ทดสอบ CEO รับงาน
พิมพ์ใน `#ceo-input`:
```
!new Test Project | ทดสอบระบบ multi-agent ครั้งแรก | verify workflow ทั้งหมด
```

สิ่งที่ควรเห็น:
1. CEO Bot ตอบ พร้อมบอก model ที่ใช้ (เช่น `groq/llama-3.3-70b 🆓`)
2. CEO ส่ง output ไปที่ `#approvals`
3. ไปที่ `#approvals` → reply ด้วย `!approve`
4. PM Bot เริ่มทำงาน...

### 8.3 ดู Cost
พิมพ์ในช่อง agent ใดก็ได้:
```
!cost
```

---

## 🔧 Commands สรุป

| Command | ที่ไหน | ผล |
|---------|--------|-----|
| `!new [ชื่อ] \| [desc] \| [goal]` | #ceo-input | เริ่ม project |
| `!approve` | #approvals (reply) | ส่งต่อ role ถัดไป |
| `!revise [comment]` | #approvals (reply) | แก้ไข |
| `!reject [reason]` | #approvals (reply) | หยุด |
| `!cost` | ทุก channel | ดู spending วันนี้ |
| `!model [prompt]` | ทุก channel | preview routing |
| `!status` | ทุก channel | active projects |

---

## 💰 Dynamic Model Router — ทำงานยังไง

```
คำนวณ Complexity Score (0-100):
  + ความยาว prompt          (+10 ถ้า > 200 คำ)
  + Complex keywords         (+5 ต่อ keyword)
  + Role baseline            (SA=+20, DEV=+15, CEO=0)
  - Simple keywords          (-5 ต่อ keyword)
  - Revision (แก้งานเดิม)   (-15)
  - ยาว = เกิน DAILY_BUDGET  (→ force FREE)

Score → Tier:
  < 40  🆓 FREE   → Ollama hermes3 / Groq Llama3  ($0)
  40-70 💰 CHEAP  → Claude Haiku / GPT-4o-mini    (~$0.001/call)
  > 70  🧠 SMART  → Claude Sonnet / GPT-4o        (~$0.01/call)

Budget Guard:
  ถ้า spend วันนี้ ≥ DAILY_BUDGET_USD → force FREE ทันที
```

---

## 🆘 Troubleshooting

### Bot ไม่ Online
```bash
# ตรวจสอบ token
grep "DISCORD_TOKEN" ~/.env | head -3

# ดู error log
cat logs/ceo.log | grep -i error
```

### Ollama ไม่ตอบ
```bash
curl http://localhost:11434/api/tags
# ถ้า error:
ollama serve &
sleep 3
ollama list
```

### เกิน Budget แล้ว Fallback ไม่ทำงาน
```bash
# ดู spend วันนี้
python3 -c "
from shared.model_router import CostTracker
t = CostTracker()
print(t.today_summary())
"
```

### Python import error
```bash
cd ~/sdlc-agents
source venv/bin/activate
export PYTHONPATH="$HOME/sdlc-agents:$PYTHONPATH"
```
