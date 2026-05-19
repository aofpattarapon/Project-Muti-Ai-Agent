#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".env.local" ]; then
  echo "Missing .env.local"
  exit 1
fi

echo "Installing dependencies if needed..."
npm install

echo "Running quality checks..."
npm run lint
npm run test

echo "Building application..."
npm run build

echo "Starting application on 0.0.0.0:3000..."
HOST=0.0.0.0 PORT=3000 npm run start
