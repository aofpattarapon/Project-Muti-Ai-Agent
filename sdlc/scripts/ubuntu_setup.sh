#!/bin/bash
# ============================================================
# Multi-AI-Agent SDLC — Ubuntu Setup Script (OrbStack)
# รัน script นี้ใน OrbStack Ubuntu Terminal
# ใช้เวลา: ~10-15 นาที
# ============================================================

set -e  # หยุดทันทีถ้ามี error

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
step() { echo -e "\n${BOLD}${CYAN}══ $1 ══${NC}"; }
fail() { echo -e "${RED}[✗] $1${NC}"; exit 1; }

echo ""
echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Multi-AI-Agent SDLC — Ubuntu Setup (OrbStack)    ║"
echo "║   Ubuntu 24.04 | Python 3.11 | Ollama | Docker     ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── ตรวจสอบ OS ──────────────────────────────────────────────────
if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    fail "Script นี้ต้องรันบน Ubuntu เท่านั้น"
fi
log "Ubuntu detected: $(lsb_release -d | cut -f2)"

# ─── STEP 1: Update System ───────────────────────────────────────
step "STEP 1: Update & Upgrade System"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
    curl wget git vim nano unzip \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg lsb-release \
    htop tree jq
log "System packages installed"

# ─── STEP 2: Python 3.11 ─────────────────────────────────────────
step "STEP 2: Install Python 3.11"
if ! python3.11 --version &>/dev/null 2>&1; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
fi
sudo apt-get install -y -qq python3-pip python3-venv
log "Python $(python3.11 --version) installed"

# Set python3.11 as default python3 (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 || true

# ─── STEP 3: Ollama (Local LLM) ──────────────────────────────────
step "STEP 3: Install Ollama (Local LLM — Free)"
if ! command -v ollama &>/dev/null; then
    info "Downloading and installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    log "Ollama installed"
else
    log "Ollama already installed: $(ollama --version)"
fi

# Start Ollama service
info "Starting Ollama service..."
sudo systemctl enable ollama 2>/dev/null || true
sudo systemctl start ollama 2>/dev/null || (ollama serve &>/dev/null & sleep 3)

# Wait for Ollama to be ready
sleep 3
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    log "Ollama is running at http://localhost:11434"
else
    warn "Ollama might not be running — start manually: ollama serve &"
fi

# Pull models
step "STEP 3b: Pull Ollama Models"
echo ""
echo "Models ที่แนะนำ:"
echo "  1. hermes3      (~4.7GB) — DEV/DEVOPS Agent (ฟรี)"
echo "  2. qwen2.5-coder:7b (~4.7GB) — Code generation ดีมาก"
echo ""
read -p "Pull hermes3 ตอนนี้เลย? (y/n): " PULL_HERMES
if [[ "$PULL_HERMES" == "y" ]]; then
    info "Pulling hermes3... (~4.7GB, อาจใช้เวลาสักครู่)"
    ollama pull hermes3
    log "hermes3 ready"
fi

read -p "Pull qwen2.5-coder:7b ด้วย? (y/n): " PULL_CODER
if [[ "$PULL_CODER" == "y" ]]; then
    info "Pulling qwen2.5-coder:7b..."
    ollama pull qwen2.5-coder:7b
    log "qwen2.5-coder ready"
fi

# ─── STEP 4: Docker ──────────────────────────────────────────────
step "STEP 4: Install Docker CE"
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    # Add Docker GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repo
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Add current user to docker group
    sudo usermod -aG docker "$USER"
    log "Docker installed — please re-login or run: newgrp docker"
else
    log "Docker already installed: $(docker --version)"
fi

# ─── STEP 5: Setup Project ───────────────────────────────────────
step "STEP 5: Setup Project"

PROJECT_DIR="$HOME/sdlc-agents"

# Clone or create project directory
if [ -d "$PROJECT_DIR" ]; then
    warn "Directory $PROJECT_DIR already exists"
else
    mkdir -p "$PROJECT_DIR"
    log "Created $PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# สร้าง folder structure
mkdir -p {shared,agents/{ceo,pm,ba,sa,uxui,dev,qa,devops},docs,scripts,data,outputs/projects,logs}
log "Folder structure created"

# ─── STEP 6: Python Virtual Environment ─────────────────────────
step "STEP 6: Python Virtual Environment"
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3.11 -m venv "$PROJECT_DIR/venv"
    log "Virtual environment created"
fi

source "$PROJECT_DIR/venv/bin/activate"

# Upgrade pip
pip install --upgrade pip -q

log "Python venv activated: $(which python)"

# ─── STEP 7: Install Python Dependencies ─────────────────────────
step "STEP 7: Install Python Dependencies"

cat > "$PROJECT_DIR/requirements.txt" << 'REQUIREMENTS'
# Discord
discord.py>=2.3.2

# HTTP Client
httpx>=0.27.0
aiohttp>=3.9.0

# LLM
anthropic>=0.28.0
openai>=1.35.0
groq>=0.9.0

# Database
aiosqlite>=0.20.0

# Utilities
python-dotenv>=1.0.0
pydantic>=2.7.0
tiktoken>=0.7.0

# Testing (QA Agent)
pytest>=8.0.0
pytest-cov>=5.0.0
pytest-asyncio>=0.23.0
requests>=2.32.0

# Code Quality (DEV Agent)
black>=24.0.0
flake8>=7.0.0

# Logging
rich>=13.7.0

# Cost Tracking
REQUIREMENTS

pip install -r requirements.txt -q
log "Python packages installed"

# ─── STEP 8: Environment File ────────────────────────────────────
step "STEP 8: Setup .env File"

if [ ! -f "$PROJECT_DIR/.env" ]; then
    cat > "$PROJECT_DIR/.env" << 'ENV_TEMPLATE'
# ══════════════════════════════════════════════
# Multi-AI-Agent SDLC — Environment Variables
# ══════════════════════════════════════════════

# ─── Discord Bot Tokens ─────────────────────
CEO_DISCORD_TOKEN=
PM_DISCORD_TOKEN=
BA_DISCORD_TOKEN=
SA_DISCORD_TOKEN=
UXUI_DISCORD_TOKEN=
DEV_DISCORD_TOKEN=
QA_DISCORD_TOKEN=
DEVOPS_DISCORD_TOKEN=

# ─── Discord Server ─────────────────────────
DISCORD_GUILD_ID=
DISCORD_APPROVAL_CHANNEL_ID=

# ─── LLM API Keys ───────────────────────────
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GROQ_API_KEY=

# ─── Ollama (Local Free) ────────────────────
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL_CODE=hermes3
OLLAMA_MODEL_DEVOPS=hermes3

# ─── Dynamic Model Router ───────────────────
# ค่าใช้จ่ายต่อวัน (USD) ก่อน fallback ไป free
DAILY_BUDGET_USD=1.00
# Complexity threshold (0-100)
# < 40  → Free (Ollama/Groq)
# 40-70 → Cheap (Claude Haiku / GPT-4o-mini)
# > 70  → Smart (Claude Sonnet)
COMPLEXITY_FREE_THRESHOLD=40
COMPLEXITY_CHEAP_THRESHOLD=70

# ─── Storage ────────────────────────────────
DB_PATH=/home/ubuntu/sdlc-agents/data/sdlc.db
OUTPUT_BASE_PATH=/home/ubuntu/sdlc-agents/outputs
LOG_LEVEL=INFO
ENV_TEMPLATE
    log ".env file created at $PROJECT_DIR/.env"
    warn "⚠️  กรุณาเปิด .env และใส่ API Keys + Discord Tokens"
else
    warn ".env already exists, skipping"
fi

# ─── STEP 9: Create systemd services ─────────────────────────────
step "STEP 9: Create Start/Stop Scripts"

cat > "$PROJECT_DIR/scripts/start.sh" << 'STARTSCRIPT'
#!/bin/bash
PROJECT_DIR="$HOME/sdlc-agents"
source "$PROJECT_DIR/venv/bin/activate"
cd "$PROJECT_DIR"

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

echo "🚀 Starting SDLC Agents..."
# Start all agents in background with logging
ROLES=(ceo pm ba sa uxui dev qa devops)
for role in "${ROLES[@]}"; do
    LOG="$PROJECT_DIR/logs/${role}.log"
    python -m "agents.${role}.agent" > "$LOG" 2>&1 &
    echo "  ✅ ${role^^} Agent started (PID: $!)"
    sleep 0.5
done

echo ""
echo "✅ All 8 agents running!"
echo "Logs: $PROJECT_DIR/logs/"
echo "Stop: $PROJECT_DIR/scripts/stop.sh"
STARTSCRIPT

cat > "$PROJECT_DIR/scripts/stop.sh" << 'STOPSCRIPT'
#!/bin/bash
echo "🛑 Stopping SDLC Agents..."
pkill -f "python -m agents" 2>/dev/null && echo "✅ Agents stopped" || echo "No agents running"
STOPSCRIPT

cat > "$PROJECT_DIR/scripts/logs.sh" << 'LOGSCRIPT'
#!/bin/bash
# ดู logs ทุก agent พร้อมกัน
tail -f ~/sdlc-agents/logs/*.log
LOGSCRIPT

chmod +x "$PROJECT_DIR/scripts/"*.sh
log "Scripts created"

# ─── STEP 10: Summary ────────────────────────────────────────────
step "SETUP COMPLETE!"

echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════╗"
echo -e "║  ✅  Setup เสร็จสมบูรณ์!                        ║"
echo -e "╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}📁 Project Location:${NC} $PROJECT_DIR"
echo ""
echo -e "${BOLD}ขั้นตอนถัดไป:${NC}"
echo -e "${YELLOW}1.${NC} ใส่ API Keys ใน .env:"
echo -e "   ${CYAN}nano $PROJECT_DIR/.env${NC}"
echo ""
echo -e "${YELLOW}2.${NC} สร้าง Discord Bots 8 ตัว (ดู DISCORD_SETUP.md)"
echo -e "   ใส่ Discord Tokens ใน .env"
echo ""
echo -e "${YELLOW}3.${NC} Copy code files จาก Mac → OrbStack:"
echo -e "   ${CYAN}# บน Mac Terminal:${NC}"
echo -e "   ${CYAN}scp -r ~/Desktop/Muti-Ai-Agent\\ for\\ claude/Ai-Agent-SDLC/* ubuntu@<orbstack-ip>:~/sdlc-agents/${NC}"
echo ""
echo -e "${YELLOW}4.${NC} Start agents:"
echo -e "   ${CYAN}cd ~/sdlc-agents && source venv/bin/activate${NC}"
echo -e "   ${CYAN}./scripts/start.sh${NC}"
echo ""
echo -e "${YELLOW}5.${NC} ทดสอบ — พิมพ์ใน Discord #ceo-input:"
echo -e "   ${CYAN}!new Test Project | ทดสอบระบบ | verify workflow${NC}"
echo ""

# Save setup info
cat > "$PROJECT_DIR/SETUP_INFO.txt" << INFO
Setup completed: $(date)
Python: $(python3.11 --version)
Ollama: $(ollama --version 2>/dev/null || echo "installed")
Project: $PROJECT_DIR
Venv: $PROJECT_DIR/venv
INFO

log "Setup info saved to SETUP_INFO.txt"
