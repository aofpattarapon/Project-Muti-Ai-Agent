# Multi-AI-Agent SDLC System

ระบบ Multi-AI-Agent สำหรับ Software Development Lifecycle อัตโนมัติ — แต่ละ Role เป็น Discord Bot ที่มี AI ของตัวเอง ส่งงานต่อกันแบบ Chain พร้อม Human-in-the-Loop Approval ทุก Step

---

## Architecture Overview

```
Human Input (Discord #ceo-input)
        │
   ┌────▼────┐
   │   CEO   │ วิเคราะห์ requirement → แตก Epic → มอบหมายงาน
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │   PM    │ Project Plan, Timeline, Risk Register
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │   BA    │ BRD, User Stories, Acceptance Criteria
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │   SA    │ System Architecture, SRS, DB Schema, API Spec
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │  UXUI   │ Wireframe Spec, Component List, Design System
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │   DEV   │ Source Code, Unit Tests, Code Docs
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │   QA    │ Test Plan, Test Cases, Bug Reports
   └────┬────┘
        │ Human Approve ✅
   ┌────▼────┐
   │ DEVOPS  │ Dockerfile, CI/CD Pipeline, Deployment Guide
   └─────────┘
```

ทุก Agent โพสต์ผลงานใน Discord → รอ Human Approve → ส่งต่อ Agent ถัดไป  
ระหว่างรอ Human สามารถสั่ง `!revise [comment]` เพื่อให้ Agent แก้งานได้

---

## Quick Start

### Prerequisites

```bash
# Mac — ติดตั้ง Ollama (Local LLM)
brew install ollama
OLLAMA_HOST=0.0.0.0 ollama serve   # เปิดให้ OrbStack เข้าถึงได้

# Pull models ที่ต้องการ
ollama pull hermes3:3b
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:7b

# ติดตั้ง Node + PM2
npm install -g pm2
```

### Setup

```bash
git clone <repo>
cd Ai-Agent-SDLC

# สร้าง virtual environment
python3 -m venv venv
pip install -r requirements.txt

# คัดลอก .env แล้วใส่ API Keys
cp .env.example .env
```

### Environment Variables (.env)

```env
# Discord Bot Tokens — ต้องมีครบทุก Role
DISCORD_BOT_TOKEN_CEO=...
DISCORD_BOT_TOKEN_PM=...
DISCORD_BOT_TOKEN_BA=...
DISCORD_BOT_TOKEN_SA=...
DISCORD_BOT_TOKEN_UXUI=...
DISCORD_BOT_TOKEN_DEV=...
DISCORD_BOT_TOKEN_QA=...
DISCORD_BOT_TOKEN_DEVOPS=...

# Discord Server
DISCORD_GUILD_ID=...
DISCORD_APPROVALS_CHANNEL_ID=...

# AI API Keys (ใช้ fallback chain — ไม่มีก็ยังทำงานได้)
ANTHROPIC_API_KEY=...       # Claude API (paid tier)
GROQ_API_KEY=...            # Groq (free tier — เร็วมาก)

# Ollama (Local — ฟรี 100%)
OLLAMA_URL=http://host.docker.internal:11434   # OrbStack → Mac

# Web App Sync
WEB_APP_URL=http://localhost:3001
AGENT_SYNC_TOKEN=...

# Database & Output
DB_PATH=data/sdlc.db
OUTPUT_DIR=outputs/projects
```

### Start Agents

```bash
# วิธีที่ 1: PM2 (แนะนำ — local dev)
./scripts/start_pm2.sh

# วิธีที่ 2: PM2 ไม่รวม cron
./scripts/start_pm2.sh --no-cron

# ดู logs
pm2 logs sdlc-ceo          # log ของ CEO bot
pm2 logs --lines 50        # log ทั้งหมด
pm2 monit                  # live dashboard
pm2 restart sdlc-ba        # restart หนึ่ง agent
pm2 delete all             # stop ทั้งหมด
```

### เริ่มใช้งาน

พิมพ์ใน Discord channel `#ceo-input`:

```
/project start
Project: HealthTrack Mobile App
Description: แอปติดตามสุขภาพสำหรับผู้สูงอายุ รองรับ iOS/Android
             ฟีเจอร์: บันทึกยา, วัดความดัน, แจ้งเตือน, รายงาน
```

---

## Agents — ทำอะไร / Input / Output

### CEO Agent
**หน้าที่**: วิเคราะห์ Requirement → แตก Epic/Feature → มอบหมายงานทุก Role

| | รายละเอียด |
|---|---|
| Input | ข้อความ Requirement จาก User (Discord DM หรือ #ceo-input) |
| Output | Project Brief, Epic List, Role Assignment Matrix |
| Output path | `outputs/projects/{id}/requirements/` |
| Discord | `#ceo-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/qwen3:8b |

**Discord Commands:**
```
/project start    — เริ่ม project ใหม่ (ใน #ceo-input)
/project status   — ดู status project ปัจจุบัน
```

---

### PM Agent (Project Manager)
**หน้าที่**: วางแผน Project → สร้าง Timeline → ระบุ Risk

| | รายละเอียด |
|---|---|
| Input | Project Brief จาก CEO |
| Output | Project Plan (.md), Gantt Timeline, Risk Register, RACI Matrix |
| Output path | `outputs/projects/{id}/plan/` |
| Discord | `#pm-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/qwen3:8b |

**Discord Output Fields:**
- Epics: จำนวน Epic ทั้งหมด
- Sprints: จำนวน Sprint / Duration
- Timeline: ระยะเวลา project รวม
- Risks: จำนวน Risk item ที่ระบุ

---

### BA Agent (Business Analyst)
**หน้าที่**: เขียน BRD → สร้าง User Stories → กำหนด Acceptance Criteria

| | รายละเอียด |
|---|---|
| Input | Project Plan จาก PM |
| Output | BRD.md, User Stories (.md), Use Case Diagram (text), AC Checklist |
| Output path | `outputs/projects/{id}/brd/` |
| Discord | `#ba-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/hermes3:3b |

**Discord Output Fields:**
- User Stories: จำนวน US ทั้งหมด
- Actors: Stakeholders ที่เกี่ยวข้อง
- Modules: หัวข้อ Functional Area หลัก

---

### SA Agent (System Architect)
**หน้าที่**: ออกแบบ System Architecture → เขียน SRS → กำหนด Tech Stack → DB Schema → API Spec

| | รายละเอียด |
|---|---|
| Input | BRD + User Stories จาก BA |
| Output | Architecture.md, SRS.md, DB-Schema.sql, openapi.yaml |
| Output path | `outputs/projects/{id}/architecture/` |
| Discord | `#sa-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/deepseek-r1:7b |

**Discord Output Fields:**
- Frontend: React / Next.js / Vue (detect จาก output)
- Backend: FastAPI / Django / Express
- Database: PostgreSQL / MongoDB / MySQL
- Infra: Docker / K8s / Cloud

---

### UXUI Agent
**หน้าที่**: ออกแบบ Wireframe → Component Library → User Flow → Design System

| | รายละเอียด |
|---|---|
| Input | SRS + Architecture จาก SA |
| Output | Wireframe-Spec.md, Components.md, UserFlow.md, DesignSystem.md |
| Output path | `outputs/projects/{id}/design/` |
| Discord | `#uxui-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/qwen3:8b |

**Discord Output Fields:**
- Screens: จำนวน Screen / Page ที่ออกแบบ
- Components: จำนวน UI Component
- User Flows: จำนวน Flow

---

### DEV Agent (Developer)
**หน้าที่**: เขียน Source Code → Unit Tests → Code Documentation

| | รายละเอียด |
|---|---|
| Input | Architecture + Wireframe จาก SA + UXUI |
| Output | Source files (.py/.ts/.js), unit tests, README-code.md |
| Output path | `outputs/projects/{id}/code/` |
| Discord | `#dev-timelog` — progress; `#approvals` — รอ Approve |
| Model | ollama/qwen2.5-coder:7b → groq/qwen3-32b → claude-sonnet-4-6 |

**Discord Output Fields:**
- Files: จำนวนไฟล์ที่สร้าง
- Lines: จำนวน lines of code (ประมาณ)
- Test Coverage: % coverage จาก unit tests

---

### QA Agent (Quality Assurance)
**หน้าที่**: เขียน Test Plan → Test Cases → รัน Tests → รายงาน Bug

| | รายละเอียด |
|---|---|
| Input | Source Code จาก DEV |
| Output | TestPlan.md, TestCases.md, TestResults.md, BugReport.md |
| Output path | `outputs/projects/{id}/tests/` |
| Discord | `#qa-timelog` — progress; `#approvals` — รอ Approve |
| Model | claude-sonnet-4-6 → groq/qwen3-32b → ollama/hermes3:3b |

**Discord Output Fields:**
- Test Cases: จำนวน test cases ทั้งหมด
- Passed / Failed / Skipped: สรุปผล
- Bugs Found: จำนวน bug ที่พบ

---

### DevOps Agent
**หน้าที่**: เขียน Dockerfile → docker-compose → CI/CD Pipeline → Deployment Guide

| | รายละเอียด |
|---|---|
| Input | Source Code + Architecture จาก DEV + SA |
| Output | Dockerfile, docker-compose.yml, .github/workflows/*.yml, deploy.sh |
| Output path | `outputs/projects/{id}/devops/` |
| Discord | `#devops-timelog` — progress; `#approvals` — รอ Approve |
| Model | ollama/qwen2.5-coder:7b → groq/qwen3-32b → claude-sonnet-4-6 |

**Discord Output Fields:**
- Services: containers ที่ระบุ (nginx, postgres, redis, ...)
- CI/CD Steps: จำนวน pipeline steps
- Environments: dev / staging / prod

---

## Discord Channel Structure

| Channel | ใช้งาน |
|---------|--------|
| `#ceo-input` | รับ project requirement จาก User |
| `#approvals` | Human Approve / Revise / Reject ทุก role |
| `#ceo-timelog` | Time log ของ CEO Agent |
| `#pm-timelog` | Time log ของ PM Agent |
| `#ba-timelog` | Time log ของ BA Agent |
| `#sa-timelog` | Time log ของ SA Agent |
| `#uxui-timelog` | Time log ของ UXUI Agent |
| `#dev-timelog` | Time log ของ DEV Agent |
| `#qa-timelog` | Time log ของ QA Agent |
| `#devops-timelog` | Time log ของ DevOps Agent |
| `#pipeline-events` | Hermes Cron events, fallback alerts |

---

## Human Approval Commands

ใช้ใน `#approvals` channel หลังจาก Agent โพสต์งาน:

```
!approve                    — อนุมัติ ส่งงานต่อ agent ถัดไป
!revise ต้องเพิ่ม auth flow   — ส่งกลับให้แก้ไข (พร้อม comment)
!reject เหตุผล               — ยกเลิก project หรือ task นั้น
```

Approval embed จะแสดง:
- Project name + ID
- Key Deliverables (3 รายการแรก)
- Model ที่ใช้ + tier (Free/Paid)
- ลิงก์ดู Output ใน Web App

---

## Model Routing & Fallback Chain

ระบบจะเลือก model ที่ดีที่สุดสำหรับแต่ละ role โดยอัตโนมัติ และ fallback เมื่อ quota หมด/error:

```
claude-sonnet-4-6 (paid)
       │ billing error / 401
       ▼
groq/qwen3-32b (free API)
       │ quota / timeout
       ▼
ollama/deepseek-r1:7b หรือ qwen2.5-coder:7b (local, ฟรี 100%)
       │ service down
       ▼
ollama/hermes3:3b (local fallback สุดท้าย)
```

Model Score Matrix (1–10 per role):

| Model | CEO | PM | BA | SA | UXUI | DEV | QA | DevOps |
|-------|-----|----|----|-----|------|-----|----|--------|
| claude-sonnet-4-6 | 10 | 10 | 10 | 10 | 10 | 9 | 10 | 9 |
| groq/qwen3-32b | 8 | 8 | 8 | 8 | 7 | 8 | 8 | 8 |
| qwen2.5-coder:7b | 5 | 5 | 5 | 7 | 5 | **9** | 7 | **9** |
| deepseek-r1:7b | 7 | 7 | 7 | **9** | 6 | 7 | 7 | 7 |
| qwen3:8b | 7 | 7 | 7 | 7 | 8 | 7 | 7 | 7 |
| hermes3:3b | 6 | 6 | 6 | 5 | 6 | 6 | 6 | 6 |

Upgrade path (หลัง pull 14b models):
```bash
ollama pull qwen2.5-coder:14b   # DEV + DevOps tier
ollama pull deepseek-r1:14b     # SA tier
ollama pull qwen3:14b           # General tier
# แล้วอัพเดท model_ids ใน shared/model_router.py
```

---

## DNA Bootstrap (ครั้งแรก)

DNA Bootstrap สร้าง Compressed System Prompt สำหรับแต่ละ role โดยใช้ Claude paid model ครั้งเดียว แล้ว cache ไว้ เพื่อให้ free model ได้รับ context คุณภาพสูงทุกครั้ง

```bash
# Bootstrap DNA ทุก 8 roles (ทำครั้งแรกก่อน start agents)
python3 scripts/pre_test_bootstrap.py
```

ผล:
- Role DNA cached ใน `data/dna_cache/`
- Free models ทำงานได้ดีขึ้นมาก เพราะได้รับ context ที่ดี
- Skip roles ที่ cached แล้วอัตโนมัติ

---

## Hermes Cron Jobs

Cron daemon (`agents/hermes_cron.py`) รัน background tasks อัตโนมัติ:

| Job | Schedule | หน้าที่ |
|-----|----------|---------|
| Weekly Pattern Review | ทุกวันจันทร์ 9:00 | วิเคราะห์ pattern จาก log สัปดาห์ที่ผ่านมา |
| DNA Refresh | ทุกวันอาทิตย์ 2:00 | Refresh DNA cache ทุก role |
| Cost Report | ทุกวัน 23:00 | สรุปค่าใช้จ่าย API รายวัน |
| Stale Task Alert | ทุก 2 ชั่วโมง | แจ้ง task ที่ค้างเกิน 24h |

```bash
# ดู cron job ที่รันอยู่
pm2 logs sdlc-cron

# Web dashboard
http://localhost:3001/cron
```

---

## Time Log System

ทุก Agent บันทึก time log แบบ Jira-style:

**Start embed** (โพสต์เมื่อ Agent เริ่มทำงาน):
- Project ID + Name
- Task Type: Processing / Revision / Review / Research / Deploy
- เวลาเริ่ม (Thai timezone UTC+7)
- Task # สำหรับ project นี้ (นับสะสม)

**Finish embed** (โพสต์เมื่อ Agent จบงาน):
- Duration (เช่น `3m 42s`)
- เวลาเริ่ม–เสร็จ (Thai timezone)
- Model ที่ใช้ + tier indicator (🆓 Free / 💰 Cheap / 🧠 Smart)
- Cost: USD + THB (×35)
- Output files ที่สร้าง (สูงสุด 8 ไฟล์)

---

## Monitoring

```bash
# Terminal pipeline monitor (อัพเดทแบบ realtime)
python3 scripts/watch_pipeline.py

# กรอง project เฉพาะ
python3 scripts/watch_pipeline.py --project PROJ-001

# ดู log ของ agent เฉพาะ
pm2 logs sdlc-ba

# Web app dashboard
http://localhost:3001

# ดูสถานะ Ollama
python3 scripts/test_ollama.py
```

---

## File Structure

```
Ai-Agent-SDLC/
├── agents/
│   ├── ceo/
│   │   ├── agent.py         — CEO Discord bot
│   │   └── prompts.py       — CEO system prompt + task builder
│   ├── pm/ ba/ sa/ uxui/    — (same structure per role)
│   ├── dev/ qa/ devops/
│   └── hermes_cron.py       — Background cron daemon
│
├── shared/
│   ├── base_agent.py        — Base Discord bot class (approval embeds, handoff)
│   ├── model_router.py      — Model selection + fallback chain + cost tracker
│   ├── timelog.py           — Jira-style time logging + Discord embeds
│   ├── web_bridge.py        — Sync lifecycle events to Next.js web app
│   ├── dna_bootstrap.py     — Compress + cache role DNA prompts
│   └── db.py                — SQLite ORM (projects, role_tasks, time_logs)
│
├── scripts/
│   ├── start_pm2.sh         — Start all bots via PM2
│   ├── pre_test_bootstrap.py — Bootstrap DNA for all roles
│   ├── watch_pipeline.py    — Terminal realtime monitor
│   ├── test_ollama.py       — Test Ollama connectivity + models
│   └── discord_live_test.py — Autonomous full-loop Discord test
│
├── outputs/
│   └── projects/
│       └── {project_id}/
│           ├── requirements/ — CEO output
│           ├── plan/         — PM output
│           ├── brd/          — BA output
│           ├── architecture/ — SA output
│           ├── design/       — UXUI output
│           ├── code/         — DEV output
│           ├── tests/        — QA output
│           └── devops/       — DevOps output
│
├── data/
│   ├── sdlc.db              — SQLite database
│   └── dna_cache/           — Cached role DNA prompts
│
├── ecosystem.bots.config.js — PM2 process config (9 processes)
├── requirements.txt
└── .env
```

---

## Web App Integration

Next.js web app (port 3001) sync realtime กับ agent pipeline:

| Event | Discord Trigger | Web Status |
|-------|----------------|-----------|
| `task_started` | Agent เริ่มทำงาน | `in_progress` |
| `task_completed` | Agent จบ รอ Approve | `waiting_approval` |
| `approved` | `!approve` | `approved` |
| `revision_requested` | `!revise ...` | `rework_requested` |
| `rejected` | `!reject ...` | `rejected` |
| `error` | Agent error | `blocked` |

Export API:
```
GET /api/project-logs/files?project={PROJECT_ID}&role={ROLE}
```
ส่งคืน JSON ที่มีชื่อไฟล์ + เนื้อหา สำหรับ download จาก web

---

## Troubleshooting

**Ollama ไม่ตอบสนองจาก OrbStack:**
```bash
# Mac — เปิด Ollama ให้ฟังทุก interface
OLLAMA_HOST=0.0.0.0 ollama serve

# ตรวจสอบ .env
OLLAMA_URL=http://host.docker.internal:11434

# ทดสอบ
python3 scripts/test_ollama.py
```

**Agent ไม่ตอบสนองใน Discord:**
```bash
pm2 logs sdlc-{role}   # ดู error log
pm2 restart sdlc-{role}
```

**DNA cache เสีย:**
```bash
rm -rf data/dna_cache/
python3 scripts/pre_test_bootstrap.py
```

**ค่าใช้จ่ายเกิน quota:**
ระบบ fallback chain ทำงานอัตโนมัติ — ไม่ต้องทำอะไร  
ตรวจสอบ fallback events ใน `#pipeline-events`

**Project ค้างไม่ส่งต่อ:**
```bash
# ดูสถานะ project ใน DB
sqlite3 data/sdlc.db "SELECT id, current_role, status FROM projects ORDER BY created_at DESC LIMIT 10;"
```

---

## Document Contracts

แต่ละ Agent มี Document Output Contract ใน `docs/contracts/`:

| Role | Contract File |
|------|--------------|
| CEO | CEO_OPERATING_MODEL.md |
| PM | PM_DOCUMENT_OUTPUT_CONTRACT.md |
| BA | BA_DOCUMENT_OUTPUT_CONTRACT.md |
| SA | SA_DOCUMENT_OUTPUT_CONTRACT.md |
| UXUI | UX_UI_DOCUMENT_OUTPUT_CONTRACT.md |
| DEV | DEV_DOCUMENT_OUTPUT_CONTRACT.md |
| QA | QA_DOCUMENT_OUTPUT_CONTRACT.md |
| DevOps | DEVOPS_OPERATING_MODEL.md |

Contract ระบุ: Role Mission, Required Inputs, Output Documents, Definition of Done, Agent Instruction Snippet
