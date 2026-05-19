# 📋 Discord Channel Setup Guide

สร้าง Channels และ Categories ทั้งหมดสำหรับ Multi-AI-Agent SDLC

---

## โครงสร้าง Channels ที่ต้องสร้าง

### 🎮 CONTROL (ห้องควบคุมกลาง)
| Channel | หน้าที่ |
|---------|--------|
| `#ceo-input` | 👤 Human พิมพ์ Requirement ที่นี่ |
| `#approvals` | ✅ Human Approve / Revise / Reject ทุก Step |
| `#project-dashboard` | 📊 Project Status Overview |

---

### 👑 CEO
| Channel | หน้าที่ |
|---------|--------|
| `#ceo-inbox` | 📥 CEO รับ Task Assignment |
| `#ceo-output` | 📤 CEO ส่ง Project Brief, Epics |
| `#ceo-timelog` | ⏱️ CEO Time Log (Jira-style) |

**Bot Token:** `CEO_DISCORD_TOKEN`

---

### 📊 PM — Project Manager
| Channel | หน้าที่ |
|---------|--------|
| `#pm-inbox` | 📥 PM รับ Project Brief จาก CEO |
| `#pm-output` | 📤 PM ส่ง Project Plan, Timeline, Risk Register |
| `#pm-timelog` | ⏱️ PM Time Log |

**Bot Token:** `PM_DISCORD_TOKEN`

---

### 📝 BA — Business Analyst
| Channel | หน้าที่ |
|---------|--------|
| `#ba-inbox` | 📥 BA รับ Project Plan จาก PM |
| `#ba-output` | 📤 BA ส่ง BRD, Use Cases, User Stories, Data Dictionary |
| `#ba-timelog` | ⏱️ BA Time Log |

**Bot Token:** `BA_DISCORD_TOKEN`

---

### 🏛️ SA — System Architect
| Channel | หน้าที่ |
|---------|--------|
| `#sa-inbox` | 📥 SA รับ Requirements จาก BA |
| `#sa-output` | 📤 SA ส่ง Architecture, DB Design, API Spec (Swagger YAML) |
| `#sa-timelog` | ⏱️ SA Time Log |

**Bot Token:** `SA_DISCORD_TOKEN`

---

### 🎨 UXUI — UX/UI Designer
| Channel | หน้าที่ |
|---------|--------|
| `#uxui-inbox` | 📥 UXUI รับ Architecture + User Stories |
| `#uxui-output` | 📤 UXUI ส่ง Wireframe Spec, Design System, User Flow |
| `#uxui-timelog` | ⏱️ UXUI Time Log |

**Bot Token:** `UXUI_DISCORD_TOKEN`

---

### 💻 FRONTEND-DEV — Next.js Developer
| Channel | หน้าที่ |
|---------|--------|
| `#frontend-inbox` | 📥 Frontend รับ Design + API Spec |
| `#frontend-output` | 📤 Frontend ส่ง Next.js Code (MVC), run instructions |
| `#frontend-timelog` | ⏱️ Frontend Dev Time Log |

**Bot Token:** `FRONTEND_DISCORD_TOKEN`

---

### ⚙️ BACKEND-DEV — FastAPI Developer
| Channel | หน้าที่ |
|---------|--------|
| `#backend-inbox` | 📥 Backend รับ API Spec + DB Design |
| `#backend-output` | 📤 Backend ส่ง FastAPI Code + **Swagger URL** |
| `#backend-timelog` | ⏱️ Backend Dev Time Log |

**Bot Token:** `BACKEND_DISCORD_TOKEN`

---

### 🧪 QA — Quality Assurance
| Channel | หน้าที่ |
|---------|--------|
| `#qa-inbox` | 📥 QA รับ Code จาก Frontend + Backend |
| `#qa-output` | 📤 QA ส่ง Test Plan, Test Results, Bug Report |
| `#qa-timelog` | ⏱️ QA Time Log |

**Bot Token:** `QA_DISCORD_TOKEN`

---

### 🔧 DEVOPS — DevOps Engineer
| Channel | หน้าที่ |
|---------|--------|
| `#devops-inbox` | 📥 DevOps รับ Tested Code + QA Report |
| `#devops-output` | 📤 DevOps ส่ง Dockerfile, docker-compose, CI/CD, Deploy URL |
| `#devops-timelog` | ⏱️ DevOps Time Log |

**Bot Token:** `DEVOPS_DISCORD_TOKEN`

---

## วิธีสร้าง Channels ใน Discord (Step by Step)

### Step 1: สร้าง Server
```
Discord → + → Create My Own → "SDLC Multi-Agent System"
```

### Step 2: สร้าง Category และ Channels

สำหรับแต่ละ Category ด้านบน:
```
1. Right-click ใน Server → Add Category
2. ตั้งชื่อ Category (เช่น "🎮 CONTROL")
3. Right-click Category → Create Channel
4. ตั้งชื่อ Channel (lowercase, เช่น "ceo-input")
5. ตั้ง Topic ตามตาราง
6. ทำซ้ำ
```

### Step 3: ตั้ง Channel Permissions

**#approvals** (สำคัญมาก):
- Bots ทุกตัว: อ่านได้ ✅ เขียนได้ ✅
- Human: อ่านได้ ✅ เขียนได้ ✅ (สำหรับ approve)

**#{role}-timelog**:
- Bot ของ role นั้น: เขียนได้ ✅
- Human + Bot อื่น: อ่านได้เท่านั้น ✅

### Step 4: เปิด Developer Mode + Copy IDs
```
Discord Settings → Advanced → Developer Mode: ON
Right-click Server → Copy Server ID → DISCORD_GUILD_ID
Right-click #approvals → Copy ID → DISCORD_APPROVAL_CHANNEL_ID
```

---

## Time Log Format (ใน #{role}-timelog)

เมื่อ Agent เริ่มทำงาน:
```
⏱️ 📊 PM — เริ่มทำงาน
📋 Project: `A1B2C3D4` Trading Bot AI
🔖 Task Type: 🔨 Processing
🔄 Revision #: 0
🕐 Start: 09:00:00 UTC
📝 Description: Trading Bot AI — PM phase
```

เมื่อ Agent ทำงานเสร็จ:
```
✅ 📊 PM — งานเสร็จ
📋 Project: `A1B2C3D4` Trading Bot AI
🕐 เริ่ม: 09:00:00
🕑 เสร็จ: 09:02:35
⏱️ ใช้เวลา: 2m 35s
🤖 Model: 💰 claude-haiku-4-5
💰 Cost: $0.00045
📄 Output (4 files):
  • `project_plan.md`
  • `timeline.md`
  • `risk_register.md`
  • `raci_matrix.md`
```

---

## Discord Commands สรุป

| Command | ที่ไหน | ผล |
|---------|--------|-----|
| `!new [name] \| [desc] \| [goal]` | #ceo-input | เริ่ม project |
| `!approve` (reply) | #approvals | ส่งต่อ role ถัดไป |
| `!revise [comment]` (reply) | #approvals | แก้ไข |
| `!reject [reason]` (reply) | #approvals | หยุด |
| `!cost` | ทุก channel | ดู spending วันนี้ |
| `!model [prompt]` | ทุก channel | preview model routing |
| `!status` | ทุก channel | active projects |
| `!timelog [project_id]` | ทุก channel | ดู time summary |
