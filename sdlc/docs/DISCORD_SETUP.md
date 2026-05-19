# 🤖 Discord Bot Setup Guide

วิธีสร้าง Discord Bot 8 ตัว (1 ตัวต่อ 1 Role)

---

## ขั้นตอนที่ 1: สร้าง Discord Application + Bot

ต้องทำซ้ำ **8 ครั้ง** สำหรับแต่ละ Role: CEO, PM, BA, SA, UXUI, DEV, QA, DEVOPS

### 1.1 ไปที่ Discord Developer Portal
```
https://discord.com/developers/applications
```

### 1.2 สร้าง Application ใหม่
- คลิก **"New Application"**
- ชื่อ: `SDLC-CEO` (หรือ PM, BA, SA, ...)
- คลิก **"Create"**

### 1.3 สร้าง Bot
- ไปที่ **Bot** ใน left menu
- คลิก **"Add Bot"**
- ตั้งชื่อ Bot: `[CEO] SDLC Agent`
- Upload Avatar ตาม role (optional)

### 1.4 เปิด Permissions (สำคัญ!)
ใน Bot settings เปิด:
- ✅ **Message Content Intent**
- ✅ **Server Members Intent**
- ✅ **Presence Intent**

### 1.5 Copy Bot Token
- คลิก **"Reset Token"**
- Copy token ใส่ `.env`
```
CEO_DISCORD_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 1.6 Invite Bot เข้า Server
ไปที่ **OAuth2 → URL Generator**:
- Scopes: ✅ `bot`
- Bot Permissions:
  - ✅ Send Messages
  - ✅ Read Messages/View Channels
  - ✅ Read Message History
  - ✅ Add Reactions
  - ✅ Embed Links
  - ✅ Attach Files
  - ✅ Mention Everyone

Copy URL → เปิดใน browser → เลือก Server → Authorize

---

## ขั้นตอนที่ 2: Setup Discord Server

### 2.1 สร้าง Server ใหม่ (แนะนำ)
- ชื่อ: `SDLC Multi-Agent`

### 2.2 สร้าง Channel Categories และ Channels

```
📁 CONTROL
  #ceo-input          ← พิมพ์ Requirement ที่นี่
  #approvals          ← Human Approval ทุก Step ⚠️ สำคัญมาก

📁 AGENTS
  #ceo-agent
  #pm-agent
  #ba-agent
  #sa-agent
  #uxui-agent
  #dev-agent
  #qa-agent
  #devops-agent

📁 LOGS
  #system-logs
  #error-logs
```

### 2.3 Copy Channel IDs
- เปิด Discord Settings → Advanced → **Developer Mode: ON**
- Right-click channel → **Copy ID**
- ใส่ใน `.env`:
```
DISCORD_APPROVAL_CHANNEL_ID=1234567890123456789
DISCORD_GUILD_ID=9876543210987654321
```

### 2.4 ตั้ง Bot Permissions ใน แต่ละ Channel
- แต่ละ Bot ควรมีสิทธิ์อ่าน/เขียนเฉพาะ channel ของตัวเอง
- #approvals: ทุก Bot อ่านได้ แต่เฉพาะ Human เท่านั้นที่ approve ได้

---

## ขั้นตอนที่ 3: ทดสอบ

### Test CEO Bot
```bash
# Start เฉพาะ CEO ก่อน
docker-compose up ceo-agent -d

# ดู logs
docker-compose logs -f ceo-agent
```

พิมพ์ใน `#ceo-input`:
```
!new Trading Bot Test | ระบบทดสอบ | ทดสอบ workflow
```

ถ้าเห็น Bot ตอบกลับ = สำเร็จ ✅

---

## ตารางสรุป Bot Tokens

| Role | Token Variable | Channel |
|------|---------------|---------|
| CEO | CEO_DISCORD_TOKEN | #ceo-agent |
| PM | PM_DISCORD_TOKEN | #pm-agent |
| BA | BA_DISCORD_TOKEN | #ba-agent |
| SA | SA_DISCORD_TOKEN | #sa-agent |
| UXUI | UXUI_DISCORD_TOKEN | #uxui-agent |
| DEV | DEV_DISCORD_TOKEN | #dev-agent |
| QA | QA_DISCORD_TOKEN | #qa-agent |
| DEVOPS | DEVOPS_DISCORD_TOKEN | #devops-agent |
