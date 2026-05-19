#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# bootstrap_ubuntu.sh
#
# ONE-COMMAND SETUP บน OrbStack Ubuntu
# รัน script นี้บน Ubuntu แล้วมันจะทำทุกอย่างให้เลย:
#
#   1. ค้นหา Ai-Agent-SDLC folder จาก Mac mount
#   2. Copy ไฟล์มาที่ ~/Ai-Agent-SDLC
#   3. ตรวจสอบ multi-ai-agent-app web app
#   4. Seed ฐานข้อมูล + สร้าง AGENT_SYNC_TOKEN
#   5. สร้าง Python venv + install dependencies
#   6. สร้าง .env จาก template
#   7. แสดงขั้นตอนถัดไป
#
# วิธีรัน (บน Ubuntu):
#   bash /mnt/mac/Users/socket9companylimited/Desktop/Muti-Ai-Agent\ for\ claude/Ai-Agent-SDLC/scripts/bootstrap_ubuntu.sh
#
#   หรือสั้นกว่า:
#   bash <(cat "/mnt/mac/Users/socket9companylimited/Desktop/Muti-Ai-Agent for claude/Ai-Agent-SDLC/scripts/bootstrap_ubuntu.sh")
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
info() { echo -e "${CYAN}ℹ️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; }
hdr()  { echo -e "\n${BOLD}${BLUE}══ $* ══${NC}"; }

# ─── Paths ───────────────────────────────────────────────────────────────────
MAC_MOUNT="/mnt/mac"
MAC_SRC="${MAC_MOUNT}/Users/socket9companylimited/Desktop/Muti-Ai-Agent for claude/Ai-Agent-SDLC"
DEST="${HOME}/Ai-Agent-SDLC"
WEBAPP="${HOME}/projects/multi-ai-agent-app"

echo ""
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Multi-AI-Agent SDLC — Ubuntu Bootstrap                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Step 1: Check Mac mount ─────────────────────────────────────────────────
hdr "Step 1: ค้นหา Mac mount"

if [[ -d "${MAC_MOUNT}" ]]; then
    log "Mac mount พบที่: ${MAC_MOUNT}"
else
    err "ไม่พบ Mac mount ที่ /mnt/mac"
    err "OrbStack ควรจะ mount Mac filesystem ให้อัตโนมัติ"
    echo ""
    echo "ลอง manual copy แทน:"
    echo "  scp -r 'mac:/Users/socket9companylimited/Desktop/Muti-Ai-Agent for claude/Ai-Agent-SDLC' ~/Ai-Agent-SDLC"
    exit 1
fi

if [[ -d "${MAC_SRC}" ]]; then
    log "พบ Ai-Agent-SDLC source: ${MAC_SRC}"
else
    err "ไม่พบ source folder: ${MAC_SRC}"
    echo "ตรวจสอบ path ใน Mac"
    # แสดง alternatives
    echo ""
    info "Searching for Ai-Agent-SDLC in /mnt/mac..."
    find /mnt/mac -maxdepth 6 -name "Ai-Agent-SDLC" -type d 2>/dev/null | head -5 || true
    exit 1
fi

# ─── Step 2: Copy files to Ubuntu ────────────────────────────────────────────
hdr "Step 2: Copy ไฟล์มาที่ Ubuntu"

if [[ -d "${DEST}" ]]; then
    warn "พบ ${DEST} แล้ว — จะ sync ไฟล์ใหม่เท่านั้น"
    rsync -av --exclude='.env' --exclude='venv/' --exclude='__pycache__/' \
          --exclude='*.pyc' --exclude='outputs/' --exclude='data/' \
          "${MAC_SRC}/" "${DEST}/" 2>&1 | tail -5
else
    mkdir -p "${DEST}"
    rsync -av --exclude='.env' --exclude='venv/' --exclude='__pycache__/' \
          --exclude='*.pyc' --exclude='outputs/' --exclude='data/' \
          "${MAC_SRC}/" "${DEST}/" 2>&1 | tail -5
fi

# สร้าง directories ที่จำเป็น
mkdir -p "${DEST}/outputs" "${DEST}/data"

log "Files copied to ${DEST}"
echo ""
echo "  Contents:"
ls "${DEST}" | sed 's/^/    /'

# ─── Step 3: Check Web App ───────────────────────────────────────────────────
hdr "Step 3: ตรวจสอบ Web App"

WEBAPP_OK=false

if [[ -d "${WEBAPP}" ]]; then
    log "พบ Web App: ${WEBAPP}"

    # ตรวจสอบ DB
    DB_CANDIDATES=(
        "${WEBAPP}/data/multi-ai-agent-app.db"
        "${WEBAPP}/data/app.db"
        "${WEBAPP}/data/database.db"
    )
    DB_PATH=""
    for c in "${DB_CANDIDATES[@]}"; do
        if [[ -f "$c" ]]; then
            DB_PATH="$c"
            log "พบ Database: ${c}"
            WEBAPP_OK=true
            break
        fi
    done

    if [[ -z "$DB_PATH" ]]; then
        warn "ไม่พบ database file — จะสร้างใหม่เมื่อ seed"
    fi

    # ตรวจสอบว่า running
    if curl -s --max-time 3 http://localhost:3000 > /dev/null 2>&1; then
        log "Web App กำลัง run อยู่ที่ http://localhost:3000"
    else
        warn "Web App ยังไม่ run — จะต้องเปิดเองภายหลัง"
        echo "    cd ${WEBAPP} && pm2 start ecosystem.config.js"
    fi
else
    err "ไม่พบ Web App ที่ ${WEBAPP}"
    warn "ระบบจะยังทำงานได้ แต่ไม่มี Web Dashboard"
    warn "ถ้าต้องการ Web UI ให้ clone project ก่อน"
fi

# ─── Step 4: Install Node.js dependencies ────────────────────────────────────
hdr "Step 4: ตรวจสอบ Node.js"

if ! command -v node &>/dev/null; then
    warn "Node.js ไม่พบ — กำลัง install..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>&1 | tail -3
    sudo apt-get install -y nodejs 2>&1 | tail -3
fi

NODE_VER=$(node --version)
log "Node.js: ${NODE_VER}"

# ─── Step 5: Seed Web App Database ───────────────────────────────────────────
hdr "Step 5: Seed Web App Database"

SEED_SCRIPT="${DEST}/scripts/seed_webapp_configs.js"

if [[ ! -f "${SEED_SCRIPT}" ]]; then
    err "ไม่พบ seed script: ${SEED_SCRIPT}"
    exit 1
fi

if [[ -d "${WEBAPP}" ]]; then
    info "Running seed script..."
    SEED_OUTPUT=$(cd "${WEBAPP}" && node "${SEED_SCRIPT}" 2>&1)
    echo "${SEED_OUTPUT}"

    # Extract token
    SYNC_TOKEN=$(echo "${SEED_OUTPUT}" | grep "AGENT_SYNC_TOKEN=" | tail -1 | cut -d= -f2 | tr -d '[:space:]')
    if [[ -n "${SYNC_TOKEN}" ]]; then
        log "AGENT_SYNC_TOKEN สร้างแล้ว: ${SYNC_TOKEN:0:8}..."
    else
        # ลองดึงจาก DB โดยตรง
        DB_FILE=""
        for c in "${DB_CANDIDATES[@]}"; do
            [[ -f "$c" ]] && DB_FILE="$c" && break
        done
        if [[ -n "$DB_FILE" ]]; then
            SYNC_TOKEN=$(node -e "
                const db = require('better-sqlite3')('${DB_FILE}');
                const row = db.prepare(\"SELECT value FROM system_configs WHERE config_key='reporting.agent_sync_ingest_token'\").get();
                console.log(row ? row.value : '');
            " 2>/dev/null || echo "")
        fi
    fi
else
    warn "ข้าม seed (ไม่พบ Web App)"
    SYNC_TOKEN="REPLACE_WITH_YOUR_TOKEN"
fi

# ─── Step 6: Python Setup ────────────────────────────────────────────────────
hdr "Step 6: Python venv + dependencies"

# ตรวจสอบ Python 3.11+
if ! command -v python3 &>/dev/null; then
    warn "Python3 ไม่พบ — กำลัง install..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv 2>&1 | tail -3
fi

PYTHON_VER=$(python3 --version)
log "Python: ${PYTHON_VER}"

# สร้าง venv
if [[ ! -d "${DEST}/venv" ]]; then
    info "สร้าง virtual environment..."
    python3 -m venv "${DEST}/venv"
    log "venv สร้างแล้ว"
else
    log "venv มีอยู่แล้ว"
fi

# Install dependencies
info "Installing Python packages..."
source "${DEST}/venv/bin/activate"

pip install --quiet --upgrade pip 2>&1 | tail -1

if [[ -f "${DEST}/requirements.txt" ]]; then
    pip install --quiet -r "${DEST}/requirements.txt" 2>&1 | tail -3
    log "Python packages installed"
else
    warn "ไม่พบ requirements.txt"
    pip install --quiet discord.py anthropic openai groq httpx python-dotenv 2>&1 | tail -3
fi

deactivate

# ─── Step 7: Create .env ──────────────────────────────────────────────────────
hdr "Step 7: สร้าง .env"

ENV_FILE="${DEST}/.env"

if [[ -f "${ENV_FILE}" ]]; then
    warn ".env มีอยู่แล้ว — ไม่เขียนทับ"
    info "ตรวจสอบว่ามี AGENT_SYNC_TOKEN:"
    grep "AGENT_SYNC_TOKEN" "${ENV_FILE}" || echo "    (ยังไม่มี — ต้องเพิ่มเอง)"
else
    info "สร้าง .env จาก template..."
    cp "${DEST}/.env.example" "${ENV_FILE}"

    # ใส่ค่าเริ่มต้น
    sed -i "s|WEB_APP_URL=.*|WEB_APP_URL=http://localhost:3000|" "${ENV_FILE}"

    if [[ -n "${SYNC_TOKEN:-}" && "${SYNC_TOKEN}" != "REPLACE_WITH_YOUR_TOKEN" ]]; then
        sed -i "s|AGENT_SYNC_TOKEN=.*|AGENT_SYNC_TOKEN=${SYNC_TOKEN}|" "${ENV_FILE}"
        log "AGENT_SYNC_TOKEN ใส่ใน .env แล้ว"
    else
        warn "ต้องใส่ AGENT_SYNC_TOKEN เอง"
    fi

    # Database path
    sed -i "s|DB_PATH=.*|DB_PATH=${DEST}/data/sdlc.db|" "${ENV_FILE}"
    sed -i "s|OUTPUT_BASE_PATH=.*|OUTPUT_BASE_PATH=${DEST}/outputs|" "${ENV_FILE}"

    log ".env สร้างแล้ว: ${ENV_FILE}"
fi

# ─── Step 8: Create PM2 ecosystem for bots ───────────────────────────────────
hdr "Step 8: สร้าง PM2 config"

PM2_CONFIG="${DEST}/ecosystem.bots.config.js"

if [[ ! -f "${PM2_CONFIG}" ]]; then
cat > "${PM2_CONFIG}" << EOFPM2
module.exports = {
  apps: [
    { name: 'sdlc-ceo',      script: '${DEST}/venv/bin/python', args: '-m agents.ceo.agent',      cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-pm',       script: '${DEST}/venv/bin/python', args: '-m agents.pm.agent',       cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-ba',       script: '${DEST}/venv/bin/python', args: '-m agents.ba.agent',       cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-sa',       script: '${DEST}/venv/bin/python', args: '-m agents.sa.agent',       cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-uxui',     script: '${DEST}/venv/bin/python', args: '-m agents.uxui.agent',     cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-frontend', script: '${DEST}/venv/bin/python', args: '-m agents.frontend.agent', cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-backend',  script: '${DEST}/venv/bin/python', args: '-m agents.backend.agent',  cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-qa',       script: '${DEST}/venv/bin/python', args: '-m agents.qa.agent',       cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
    { name: 'sdlc-devops',   script: '${DEST}/venv/bin/python', args: '-m agents.devops.agent',   cwd: '${DEST}', interpreter: 'none', env_file: '${DEST}/.env' },
  ]
}
EOFPM2
    log "PM2 config สร้างแล้ว: ${PM2_CONFIG}"
else
    warn "PM2 config มีอยู่แล้ว"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Bootstrap เสร็จแล้ว! ✅                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BOLD}📁 Files:${NC}        ${DEST}"
echo -e "${BOLD}🐍 Python venv:${NC}  ${DEST}/venv"
echo -e "${BOLD}⚙️  Config:${NC}       ${ENV_FILE}"
echo ""

if [[ -n "${SYNC_TOKEN:-}" && "${SYNC_TOKEN}" != "REPLACE_WITH_YOUR_TOKEN" ]]; then
    echo -e "${BOLD}🔑 AGENT_SYNC_TOKEN:${NC} ${SYNC_TOKEN:0:8}...${SYNC_TOKEN: -4}"
fi

echo ""
echo -e "${BOLD}${YELLOW}📋 ขั้นตอนถัดไป:${NC}"
echo ""
echo -e "  ${BOLD}1. ใส่ Discord Bot Tokens ใน .env:${NC}"
echo "     nano ${ENV_FILE}"
echo "     # CEO_DISCORD_TOKEN=Bot_xxx"
echo "     # PM_DISCORD_TOKEN=Bot_xxx"
echo "     # ... (ทุก 9 bots)"
echo "     # ANTHROPIC_API_KEY=sk-ant-..."
echo ""
echo -e "  ${BOLD}2. (ถ้ายังไม่ได้) ทำ Discord Channel Setup:${NC}"
echo "     cat ${DEST}/discord/CHANNEL_SETUP.md"
echo ""
echo -e "  ${BOLD}3. อัปเดต Discord Channel IDs:${NC}"
echo "     cd ${WEBAPP:-'~/projects/multi-ai-agent-app'}"
echo "     node ${DEST}/scripts/update_channel_ids.js"
echo ""
echo -e "  ${BOLD}4. เปิด Web App:${NC}"
echo "     cd ${WEBAPP:-'~/projects/multi-ai-agent-app'} && pm2 start ecosystem.config.js"
echo ""
echo -e "  ${BOLD}5. เปิด Discord Bots:${NC}"
echo "     pm2 start ${PM2_CONFIG}"
echo "     pm2 save && pm2 logs"
echo ""
echo -e "  ${BOLD}6. ทดสอบ:${NC}"
echo "     # ใน Discord → #ceo-input:"
echo "     # !new MyApp | Build a simple todo app | CRUD operations"
echo ""
echo -e "${BOLD}${CYAN}Quick test (หลังใส่ token แล้ว):${NC}"
echo "  curl -X POST http://localhost:3000/api/agent-activity/ingest \\"
echo "    -H 'Authorization: Bearer \${AGENT_SYNC_TOKEN}' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"roleKey\":\"ceo\",\"eventType\":\"task_started\",\"taskName\":\"Test\",\"status\":\"in_progress\",\"summary\":\"ok\",\"channelTarget\":\"ceo-inbox\"}'"
echo ""
