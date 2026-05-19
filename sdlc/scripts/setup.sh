#!/bin/bash
# ============================================================
# Multi-AI-Agent SDLC System - Initial Setup Script (Mac)
# ============================================================

set -e
echo "🚀 Setting up Multi-AI-Agent SDLC System..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✅ $1 found${NC}"
        return 0
    else
        echo -e "${RED}❌ $1 not found${NC}"
        return 1
    fi
}

# ─── 1. Check Prerequisites ───────────────────────────────────────
echo "📋 Checking prerequisites..."
echo ""

MISSING=0

if ! check_command "docker"; then
    echo "   Install: https://docs.docker.com/desktop/mac/install/"
    MISSING=1
fi

if ! check_command "docker-compose"; then
    echo "   Docker Compose comes with Docker Desktop"
fi

if ! check_command "ollama"; then
    echo -e "${YELLOW}⚠️  Ollama not found (needed for DEV/DEVOPS agents)${NC}"
    echo "   Install: brew install ollama"
    echo "   หรือ: https://ollama.com/download"
fi

if ! check_command "python3"; then
    echo "   Install: brew install python3"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "${RED}❌ กรุณาติดตั้ง prerequisites ก่อน แล้วรัน script ใหม่${NC}"
    exit 1
fi

echo ""

# ─── 2. Setup Ollama Models ───────────────────────────────────────
if command -v ollama &> /dev/null; then
    echo "🤖 Setting up Ollama Local Models..."
    echo ""

    # Start Ollama server ถ้ายังไม่รัน
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Starting Ollama server..."
        ollama serve &
        sleep 3
    fi

    echo "Pulling hermes3 (Primary - for DEV/DEVOPS)..."
    ollama pull hermes3 || echo "hermes3 pull failed, will try later"

    echo ""
    echo -e "${YELLOW}Optional: Pull more models? (y/n)${NC}"
    read -r PULL_MORE

    if [[ "$PULL_MORE" == "y" ]]; then
        echo "Pulling codellama:13b (Better for code)..."
        ollama pull codellama:13b
        echo "Pulling llama3.1:8b (General purpose)..."
        ollama pull llama3.1:8b
    fi
fi

# ─── 3. Create .env file ──────────────────────────────────────────
echo ""
echo "⚙️  Setting up environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env from .env.example${NC}"
    echo -e "${YELLOW}⚠️  กรุณาแก้ไข .env ใส่ API Keys และ Discord Bot Tokens${NC}"
else
    echo -e "${YELLOW}⚠️  .env already exists, skipping${NC}"
fi

# ─── 4. Create output directories ────────────────────────────────
echo ""
echo "📁 Creating directories..."
mkdir -p data outputs/projects
echo -e "${GREEN}✅ Directories created${NC}"

# ─── 5. Build Docker images ───────────────────────────────────────
echo ""
echo "🐳 Building Docker images..."
docker-compose build --parallel
echo -e "${GREEN}✅ Docker images built${NC}"

# ─── 6. Setup Discord Server Template ────────────────────────────
echo ""
echo "📋 Discord Server Setup Guide:"
echo ""
echo "กรุณาสร้าง Channels ต่อไปนี้ใน Discord Server:"
echo ""
echo "📂 SDLC Channels:"
echo "  #ceo-input        ← พิมพ์ Requirement ที่นี่"
echo "  #approvals        ← Human Approval ทุก Step"
echo "  #ceo-agent"
echo "  #pm-agent"
echo "  #ba-agent"
echo "  #sa-agent"
echo "  #uxui-agent"
echo "  #dev-agent"
echo "  #qa-agent"
echo "  #devops-agent"
echo ""
echo "📋 Step ต่อไป:"
echo "  1. แก้ไข .env ใส่ Discord Bot Tokens (ดู docs/DISCORD_SETUP.md)"
echo "  2. ใส่ API Keys (อย่างน้อย ANTHROPIC_API_KEY หรือ GROQ_API_KEY)"
echo "  3. รัน: ./scripts/start_all.sh"
echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
