"""
Obsidian REST API Client (Option 2)
====================================
Connects to Obsidian via the "Local REST API" community plugin.
Install plugin: https://obsidian.md/plugins?id=obsidian-local-rest-api

Required .env:
  OBSIDIAN_API_URL=http://localhost:27123
  OBSIDIAN_API_KEY=your_api_key       # from plugin settings
  OBSIDIAN_VAULT_PATH=/path/to/vault  # local filesystem path (for direct writes)

Vault structure this client manages:
  {vault}/
  ├── 00-DNA/           role prompts + style DNA
  ├── 01-Projects/      per-project notes
  ├── 02-Patterns/      reusable patterns per role
  ├── 03-Outputs/       agent output archives
  ├── 04-Lessons/       post-project retrospectives
  └── 05-Cron-Logs/     hermes cron job logs
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── Vault Folder Structure ───────────────────────────────────────────────────

VAULT_FOLDERS = {
    "dna":      "00-DNA",
    "projects": "01-Projects",
    "patterns": "02-Patterns",
    "outputs":  "03-Outputs",
    "lessons":  "04-Lessons",
    "cron":     "05-Cron-Logs",
}


class ObsidianClient:
    """
    REST API client for Obsidian Local REST API plugin.
    Falls back to direct filesystem writes if plugin is unavailable.
    """

    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        vault_path: str = None,
    ):
        self.api_url    = (api_url or os.getenv("OBSIDIAN_API_URL", "http://localhost:27123")).rstrip("/")
        self.api_key    = api_key or os.getenv("OBSIDIAN_API_KEY", "")
        self.vault_path = vault_path or os.getenv("OBSIDIAN_VAULT_PATH", "")
        self._available: Optional[bool] = None  # cached availability check

    # ─── Connection ───────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if Obsidian REST API is reachable."""
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f"{self.api_url}/", timeout=2,
                             headers=self._headers())
            self._available = r.status_code in (200, 401)
        except Exception:
            self._available = False
        return self._available

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    # ─── CRUD ─────────────────────────────────────────────────────────────────

    def read_note(self, path: str) -> Optional[str]:
        """
        Read note content by vault-relative path (e.g. '01-Projects/ecommerce.md').
        Returns content string or None if not found.
        """
        if self.is_available():
            try:
                r = requests.get(
                    f"{self.api_url}/vault/{path}",
                    headers=self._headers(),
                    timeout=10,
                )
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                logger.warning(f"[Obsidian] REST read failed for {path}: {e}")

        # Fallback: direct filesystem read
        if self.vault_path:
            full = Path(self.vault_path) / path
            if full.exists():
                return full.read_text(encoding="utf-8")
        return None

    def write_note(self, path: str, content: str, append: bool = False) -> bool:
        """
        Write or append to a note. Creates parent folders automatically.
        Returns True on success.
        """
        if self.is_available():
            try:
                method = "post" if append else "put"
                r = getattr(requests, method)(
                    f"{self.api_url}/vault/{path}",
                    headers=self._headers(),
                    data=content.encode("utf-8"),
                    timeout=15,
                )
                if r.status_code in (200, 201, 204):
                    logger.debug(f"[Obsidian] wrote {path} via REST API")
                    return True
            except Exception as e:
                logger.warning(f"[Obsidian] REST write failed for {path}: {e}")

        # Fallback: direct filesystem write
        if self.vault_path:
            full = Path(self.vault_path) / path
            full.parent.mkdir(parents=True, exist_ok=True)
            if append and full.exists():
                existing = full.read_text(encoding="utf-8")
                content = existing + "\n" + content
            full.write_text(content, encoding="utf-8")
            logger.debug(f"[Obsidian] wrote {path} via filesystem")
            return True

        logger.error(f"[Obsidian] Cannot write {path} — no API and no vault path configured")
        return False

    def list_notes(self, folder: str = "") -> list[str]:
        """List all note paths under a folder."""
        if self.is_available():
            try:
                url = f"{self.api_url}/vault/{folder}/" if folder else f"{self.api_url}/vault/"
                r = requests.get(url, headers=self._headers(), timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    return data.get("files", [])
            except Exception as e:
                logger.warning(f"[Obsidian] REST list failed: {e}")

        # Fallback: filesystem
        if self.vault_path:
            base = Path(self.vault_path) / folder if folder else Path(self.vault_path)
            if base.exists():
                return [
                    str(p.relative_to(self.vault_path))
                    for p in base.rglob("*.md")
                ]
        return []

    def search_notes(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search notes by text. Returns list of {path, content, score}.
        Uses REST API search if available, otherwise simple grep.
        """
        if self.is_available():
            try:
                r = requests.post(
                    f"{self.api_url}/search/simple/",
                    headers=self._headers(),
                    params={"query": query, "contextLength": 200},
                    timeout=15,
                )
                if r.status_code == 200:
                    results = r.json()
                    return [
                        {
                            "path":    item.get("filename", ""),
                            "content": " ".join(
                                m.get("match", {}).get("context", "")
                                for m in item.get("matches", [])[:3]
                            ),
                            "score": len(item.get("matches", [])),
                        }
                        for item in results[:limit]
                    ]
            except Exception as e:
                logger.warning(f"[Obsidian] REST search failed: {e}")

        # Fallback: simple keyword grep across vault files
        return self._grep_search(query, limit)

    def delete_note(self, path: str) -> bool:
        """Delete a note."""
        if self.is_available():
            try:
                r = requests.delete(
                    f"{self.api_url}/vault/{path}",
                    headers=self._headers(),
                    timeout=10,
                )
                if r.status_code in (200, 204):
                    return True
            except Exception as e:
                logger.warning(f"[Obsidian] REST delete failed: {e}")

        if self.vault_path:
            full = Path(self.vault_path) / path
            if full.exists():
                full.unlink()
                return True
        return False

    # ─── High-level helpers ───────────────────────────────────────────────────

    def save_role_dna(self, role: str, dna: dict) -> bool:
        """Sync DNA to Obsidian vault (00-DNA folder)."""
        path = f"{VAULT_FOLDERS['dna']}/{role}-dna.md"
        content = _dna_to_markdown(role, dna)
        return self.write_note(path, content)

    def save_project_note(
        self,
        project_id: str,
        project_name: str,
        role: str,
        content: str,
    ) -> bool:
        """Save agent output as project note (03-Outputs)."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        path = f"{VAULT_FOLDERS['outputs']}/{project_id}/{date_str}-{role}.md"
        header = (
            f"---\n"
            f"project: {project_name}\n"
            f"project_id: {project_id}\n"
            f"role: {role}\n"
            f"date: {date_str}\n"
            f"tags: [output, {role}, {project_id}]\n"
            f"---\n\n"
            f"# {role.upper()} Output — {project_name}\n\n"
        )
        return self.write_note(path, header + content)

    def save_lesson(self, title: str, content: str, tags: list[str] = None) -> bool:
        """Save post-project lesson to 04-Lessons."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        slug = title.lower().replace(" ", "-")[:40]
        path = f"{VAULT_FOLDERS['lessons']}/{date_str}-{slug}.md"
        header = (
            f"---\n"
            f"title: {title}\n"
            f"date: {date_str}\n"
            f"tags: [lesson{', ' + ', '.join(tags) if tags else ''}]\n"
            f"---\n\n"
            f"# {title}\n\n"
        )
        return self.write_note(path, header + content)

    def save_cron_log(self, job_name: str, status: str, summary: str) -> bool:
        """Append cron job log entry to 05-Cron-Logs."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        ts = datetime.utcnow().strftime("%H:%M:%S")
        path = f"{VAULT_FOLDERS['cron']}/{date_str}-cron.md"
        entry = f"\n## [{ts}] {job_name} — {status}\n{summary}\n"
        return self.write_note(path, entry, append=True)

    def get_project_context(self, project_id: str, project_name: str) -> str:
        """
        Get all relevant notes for a project — used for context injection.
        Returns condensed string suitable for injection into LLM prompt.
        """
        parts = []

        # Project-specific notes
        notes = self.list_notes(f"{VAULT_FOLDERS['projects']}/{project_id}")
        for note_path in notes[:5]:
            content = self.read_note(note_path)
            if content:
                parts.append(f"[{note_path}]\n{content[:600]}")

        # Search for project name in outputs
        results = self.search_notes(project_name, limit=3)
        for r in results:
            if r["content"]:
                parts.append(f"[relevant: {r['path']}]\n{r['content'][:400]}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def initialize_vault(self) -> bool:
        """Create vault folder structure if it doesn't exist."""
        if not self.vault_path:
            logger.warning("[Obsidian] No vault path configured — cannot initialize")
            return False
        for folder in VAULT_FOLDERS.values():
            (Path(self.vault_path) / folder).mkdir(parents=True, exist_ok=True)
        # Create README
        readme = (
            "# Multi-AI Agent SDLC Vault\n\n"
            "This vault is the knowledge base for the multi-agent SDLC system.\n\n"
            "## Folders\n"
            "- `00-DNA/` — Role prompts and style DNA (synced from bootstrap)\n"
            "- `01-Projects/` — Per-project notes, decisions, constraints\n"
            "- `02-Patterns/` — Reusable patterns per role\n"
            "- `03-Outputs/` — Agent output archives\n"
            "- `04-Lessons/` — Post-project retrospectives\n"
            "- `05-Cron-Logs/` — Hermes cron job logs\n"
        )
        return self.write_note("README.md", readme)

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _grep_search(self, query: str, limit: int) -> list[dict]:
        """Simple keyword search across filesystem vault."""
        if not self.vault_path:
            return []
        results = []
        keywords = query.lower().split()
        for md_file in Path(self.vault_path).rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
                text_lower = text.lower()
                score = sum(text_lower.count(kw) for kw in keywords)
                if score > 0:
                    # Find best matching snippet
                    idx = text_lower.find(keywords[0]) if keywords else 0
                    snippet = text[max(0, idx-50): idx+300].strip()
                    results.append({
                        "path":    str(md_file.relative_to(self.vault_path)),
                        "content": snippet,
                        "score":   score,
                    })
            except Exception:
                continue
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _dna_to_markdown(role: str, dna: dict) -> str:
    """Convert DNA dict to readable markdown note."""
    lines = [
        f"---",
        f"role: {role}",
        f"type: dna",
        f"model: {dna.get('_model_used', 'unknown')}",
        f"updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"tags: [dna, {role}]",
        f"---",
        f"",
        f"# {role.upper()} Role DNA",
        f"",
        f"## Compressed System Prompt",
        f"",
        dna.get("compressed_system_prompt", "_not yet bootstrapped_"),
        f"",
        f"## Harness Behavior",
        f"",
        dna.get("harness_behavior", ""),
        f"",
        f"## Format Rules",
        f"",
    ]
    for rule in dna.get("format_rules", []):
        lines.append(f"- {rule}")
    lines += [
        f"",
        f"## Anti-Patterns (DO NOT DO)",
        f"",
    ]
    for ap in dna.get("anti_patterns", []):
        lines.append(f"- {ap}")
    lines += [
        f"",
        f"## Few-Shot Example",
        f"",
        f"```",
        dna.get("few_shot_snippet", ""),
        f"```",
        f"",
        f"## Token Compression Tips",
        f"",
        dna.get("token_compression_tips", ""),
    ]
    return "\n".join(lines)


# ─── Singleton ────────────────────────────────────────────────────────────────
_obsidian_instance: Optional[ObsidianClient] = None

def get_obsidian() -> ObsidianClient:
    global _obsidian_instance
    if _obsidian_instance is None:
        _obsidian_instance = ObsidianClient()
    return _obsidian_instance
