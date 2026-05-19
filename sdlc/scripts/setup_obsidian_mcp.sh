#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Obsidian MCP Setup (Option 3)
# Sets up obsidian-mcp for Claude Code to access the vault directly.
#
# Usage:
#   chmod +x scripts/setup_obsidian_mcp.sh
#   ./scripts/setup_obsidian_mcp.sh /path/to/your/obsidian/vault
# ──────────────────────────────────────────────────────────────

set -euo pipefail

VAULT_PATH="${1:-${OBSIDIAN_VAULT_PATH:-}}"

if [[ -z "$VAULT_PATH" ]]; then
  echo "❌  Usage: $0 /path/to/obsidian/vault"
  echo "   Or set OBSIDIAN_VAULT_PATH in .env"
  exit 1
fi

if [[ ! -d "$VAULT_PATH" ]]; then
  echo "❌  Vault path does not exist: $VAULT_PATH"
  echo "   Create the directory first or install Obsidian and create a vault."
  exit 1
fi

echo "🔧 Setting up Obsidian MCP for vault: $VAULT_PATH"

# ── 1. Install obsidian-mcp globally (if not already) ──────────────
if ! command -v npx &>/dev/null; then
  echo "❌  npx not found — install Node.js 18+ first"
  exit 1
fi

echo "📦 Installing obsidian-mcp..."
npm install -g obsidian-mcp 2>/dev/null || true

# ── 2. Write Claude Code MCP config ────────────────────────────────
CLAUDE_MCP_CONFIG="$HOME/.claude/mcp_servers.json"
mkdir -p "$(dirname "$CLAUDE_MCP_CONFIG")"

# Read existing config or start fresh
if [[ -f "$CLAUDE_MCP_CONFIG" ]]; then
  EXISTING=$(cat "$CLAUDE_MCP_CONFIG")
else
  EXISTING="{}"
fi

# Merge/overwrite the obsidian entry using node inline script
node -e "
const fs = require('fs');
const existing = JSON.parse(process.env.EXISTING || '{}');
existing.mcpServers = existing.mcpServers || {};
existing.mcpServers['obsidian'] = {
  command: 'npx',
  args: ['-y', 'obsidian-mcp', process.env.VAULT_PATH],
  description: 'Obsidian vault access via MCP'
};
fs.writeFileSync(process.env.CLAUDE_MCP_CONFIG, JSON.stringify(existing, null, 2));
console.log('✅  MCP config written to', process.env.CLAUDE_MCP_CONFIG);
" VAULT_PATH="$VAULT_PATH" CLAUDE_MCP_CONFIG="$CLAUDE_MCP_CONFIG" EXISTING="$EXISTING"

# ── 3. Write project-level .mcp.json (for Claude Code IDE integration) ──
PROJECT_MCP=".mcp.json"
cat > "$PROJECT_MCP" << JSONEOF
{
  "mcpServers": {
    "obsidian": {
      "command": "npx",
      "args": ["-y", "obsidian-mcp", "${VAULT_PATH}"],
      "description": "Read/write Obsidian vault notes"
    }
  }
}
JSONEOF
echo "✅  Project .mcp.json created"

# ── 4. Update .env with vault path ─────────────────────────────────
ENV_FILE="$(dirname "$0")/../.env"
if [[ -f "$ENV_FILE" ]]; then
  if grep -q "^OBSIDIAN_VAULT_PATH=" "$ENV_FILE"; then
    sed -i "s|^OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH=${VAULT_PATH}|" "$ENV_FILE"
  else
    echo "" >> "$ENV_FILE"
    echo "OBSIDIAN_VAULT_PATH=${VAULT_PATH}" >> "$ENV_FILE"
  fi
  echo "✅  OBSIDIAN_VAULT_PATH updated in .env"
fi

# ── 5. Initialize vault folder structure ───────────────────────────
echo "📁 Initializing vault folder structure..."
python3 - << PYEOF
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname('$0'), '..'))
from dotenv import load_dotenv
load_dotenv()
import os; os.environ['OBSIDIAN_VAULT_PATH'] = '$VAULT_PATH'
from shared.obsidian_client import ObsidianClient
client = ObsidianClient(vault_path='$VAULT_PATH')
if client.initialize_vault():
    print('✅  Vault folders initialized')
else:
    print('⚠️  Could not initialize vault (no vault_path configured)')
PYEOF

echo ""
echo "══════════════════════════════════════════"
echo "✅  Obsidian MCP setup complete!"
echo ""
echo "  Vault:    $VAULT_PATH"
echo "  MCP config: $CLAUDE_MCP_CONFIG"
echo "  Project:  .mcp.json"
echo ""
echo "  Next steps:"
echo "  1. Install Obsidian Local REST API plugin:"
echo "     https://obsidian.md/plugins?id=obsidian-local-rest-api"
echo "  2. Copy the API key from plugin settings → add to .env:"
echo "     OBSIDIAN_API_KEY=your_key_here"
echo "     OBSIDIAN_API_URL=http://localhost:27123"
echo "  3. Restart Claude Code to pick up the MCP server."
echo "══════════════════════════════════════════"
