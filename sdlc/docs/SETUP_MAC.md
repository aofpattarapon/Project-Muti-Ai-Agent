# 🍎 Mac Setup Guide - Multi-AI-Agent SDLC

วิธีติดตั้งและรันระบบบน Mac ตั้งแต่ต้น

---

## คำถาม: ใช้ Docker หรือ WSL บน Mac?

> **WSL (Windows Subsystem for Linux) = ใช้ไม่ได้บน Mac** ❌
> WSL มีเฉพาะบน Windows เท่านั้น

### ตัวเลือกบน Mac:

| Option | ความยาก | ฟรี | แนะนำ |
|--------|---------|-----|-------|
| **Docker Desktop** | ง่าย | ✅ | ⭐⭐⭐ **แนะนำ** |
| **Lima** (Linux VM) | ปานกลาง | ✅ | ⭐⭐ |
| **Multipass** (Ubuntu VM) | ง่าย | ✅ | ⭐⭐ |
| UTM | ปานกลาง | ✅ | ⭐ |

**คำแนะนำ: ใช้ Docker Desktop** - ง่ายที่สุด, ฟรี, รองรับ Mac M1/M2/M3

---

## Step 1: ติดตั้ง Homebrew (ถ้ายังไม่มี)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## Step 2: ติดตั้ง Docker Desktop

### วิธี 1: ผ่าน Homebrew (แนะนำ)
```bash
brew install --cask docker
```

### วิธี 2: Download โดยตรง
```
https://docs.docker.com/desktop/install/mac-install/
```
- เลือก **Mac with Apple chip** (M1/M2/M3) หรือ **Intel chip**

### ตรวจสอบ
```bash
docker --version
# Docker version 26.x.x
docker-compose --version
# Docker Compose version v2.x.x
```

---

## Step 3: ติดตั้ง Ollama (Local LLM - ฟรี 100%)

```bash
# ติดตั้ง Ollama
brew install ollama

# Start Ollama server
ollama serve &

# Pull models
ollama pull hermes3         # Primary สำหรับ DEV/DEVOPS (~4.7GB)
ollama pull codellama:13b   # Optional: ดีกว่าสำหรับ coding (~7.4GB)

# ทดสอบ
ollama run hermes3 "Hello, what can you do?"
```

**Resource Requirements:**
- hermes3: RAM 8GB+, Storage 5GB
- codellama:13b: RAM 16GB+, Storage 8GB
- ถ้า RAM น้อย: ใช้ `hermes3:7b` หรือ `phi3:mini`

---

## Step 4: Clone/Setup Project

```bash
# ไปที่ folder ที่ต้องการ
cd ~/Desktop/Muti-Ai-Agent\ for\ claude/

# ติดตั้ง Python dependencies (สำหรับ local dev)
python3 -m venv venv
source venv/bin/activate
pip install -r Ai-Agent-SDLC/requirements.txt
```

---

## Step 5: Setup API Keys และ Discord

```bash
cd Ai-Agent-SDLC
cp .env.example .env
```

แก้ไข `.env`:
```bash
# ใช้ TextEdit หรือ VS Code
open -a TextEdit .env
# หรือ
code .env
```

**API Keys ที่ต้องการ (อย่างน้อย 1 อัน):**

### Option A: Claude API (แนะนำสำหรับ reasoning)
```
สมัคร: https://console.anthropic.com
Free tier: ~$5 credits
ANTHROPIC_API_KEY=sk-ant-...
```

### Option B: Groq API (ฟรี ไม่ต้องใส่บัตร)
```
สมัคร: https://console.groq.com
ฟรีสมบูรณ์: rate limited แต่ใช้ได้
GROQ_API_KEY=gsk_...
```

### Option C: Together AI (Free $25 credits)
```
สมัคร: https://api.together.xyz
TOGETHER_API_KEY=...
```

---

## Step 6: Build และ Start

```bash
# Build Docker images
docker-compose build

# Start ทั้งหมด
./scripts/start_all.sh

# หรือ manual
docker-compose up -d

# ดู logs
docker-compose logs -f
```

---

## Step 7: ทดสอบระบบ

1. เปิด Discord
2. ไปที่ channel `#ceo-input`
3. พิมพ์:
```
!new My Test Project | ทดสอบระบบ Multi-Agent | ทดสอบ workflow ทั้งหมด
```
4. รอดู CEO Bot ตอบกลับ
5. ไปดูที่ `#approvals` channel
6. พิมพ์ `!approve` เพื่อส่งต่อ PM

---

## Troubleshooting

### Problem: Docker ไม่ Start
```bash
# รัน Docker Desktop ก่อน
open -a Docker
sleep 10
docker ps
```

### Problem: Ollama ไม่ตอบสนอง
```bash
# Restart Ollama
pkill ollama
ollama serve &
curl http://localhost:11434/api/tags
```

### Problem: Bot ไม่ Online ใน Discord
```bash
# ตรวจสอบ Token ใน .env
docker-compose logs ceo-agent | grep "ERROR\|token"
```

### Problem: Out of Memory (M1 Mac ≤8GB RAM)
```bash
# ใช้ Model ขนาดเล็กกว่า
# แก้ใน .env:
DEV_MODEL=phi3:mini
DEVOPS_MODEL=phi3:mini
```

---

## Useful Commands

```bash
# ดูสถานะ agents ทั้งหมด
docker-compose ps

# Restart agent เดียว
docker-compose restart ceo-agent

# ดู logs real-time
docker-compose logs -f dev-agent

# เข้าไปใน container
docker exec -it sdlc-ceo bash

# Stop ทุกอย่าง
./scripts/stop_all.sh
```
