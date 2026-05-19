#!/bin/bash
# ─────────────────────────────────────────────────────────
# Start all SDLC agents via PM2 (local dev, no Docker)
# Usage: ./scripts/start_pm2.sh [--no-cron]
# ─────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "🚀 Starting Multi-AI-Agent SDLC via PM2..."
echo ""

# Check PM2
if ! command -v pm2 &>/dev/null; then
  echo "❌ PM2 not found. Install: npm install -g pm2"
  exit 1
fi

# Check .env
if [ ! -f .env ]; then
  echo "❌ .env not found"
  exit 1
fi

# Check venv
if [ ! -f venv/bin/python ]; then
  echo "❌ venv not found. Run: python3 -m venv venv && pip install -r requirements.txt"
  exit 1
fi

# Stop existing processes
pm2 delete ecosystem.bots.config.js 2>/dev/null || true
sleep 1

# Start all bots
if [[ "$1" == "--no-cron" ]]; then
  # Start all except cron
  pm2 start ecosystem.bots.config.js --only "sdlc-ceo,sdlc-pm,sdlc-ba,sdlc-sa,sdlc-uxui,sdlc-dev,sdlc-qa,sdlc-devops"
else
  pm2 start ecosystem.bots.config.js
fi

sleep 3

echo ""
echo "📊 Status:"
pm2 list

echo ""
echo "✅ All agents started!"
echo ""
echo "Useful commands:"
echo "  pm2 logs sdlc-ceo          # watch CEO bot log"
echo "  pm2 logs --lines 50        # all logs"
echo "  pm2 monit                  # live dashboard"
echo "  pm2 restart sdlc-ba        # restart one agent"
echo "  pm2 delete all             # stop everything"
echo ""
echo "Web dashboard: http://localhost:3001"
echo "Cron dashboard: http://localhost:3001/cron"
