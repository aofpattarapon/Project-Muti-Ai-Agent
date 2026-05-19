"""
Obsidian RAG — Retrieval-Augmented Generation from Obsidian vault.
Fetches relevant notes and injects them as context into LLM prompts.

Usage:
    from shared.obsidian_rag import ObsidianRAG, get_rag
    rag = get_rag()
    context = rag.get_context_for_task(role="ba", project_id="proj-123", query="user auth requirements")
    # inject `context` into your system prompt or user message
"""

import re
import logging
from typing import Optional

from shared.obsidian_client import ObsidianClient, get_obsidian, VAULT_FOLDERS

logger = logging.getLogger(__name__)

# Max chars injected per source so we don't blow the context window
MAX_CHARS_PER_NOTE  = 800
MAX_TOTAL_CHARS     = 3000
MAX_SEARCH_RESULTS  = 5


class ObsidianRAG:
    """
    Retrieves relevant vault notes and builds a compact context string
    suitable for injecting into LLM prompts.

    Three retrieval paths (combined, deduplicated):
      1. Project notes     — {01-Projects}/{project_id}/
      2. Role DNA          — {00-DNA}/{role}-dna.md
      3. Semantic search   — keyword search across vault
    """

    def __init__(self, client: ObsidianClient = None):
        self._obs = client or get_obsidian()

    # ─── Public API ───────────────────────────────────────────────────────────

    def get_context_for_task(
        self,
        role: str,
        project_id: str = "",
        project_name: str = "",
        query: str = "",
        include_dna: bool = False,
        max_chars: int = MAX_TOTAL_CHARS,
    ) -> str:
        """
        Build a context string for injecting into an LLM call.

        Args:
            role        — agent role (ba, dev, sa, …)
            project_id  — filter by project (optional)
            project_name— used for keyword search (optional)
            query       — additional search query (optional)
            include_dna — include DNA/system-prompt note (usually already injected)
            max_chars   — hard cap on returned context length

        Returns:
            Markdown-formatted context string, or "" if nothing found.
        """
        parts: list[tuple[str, str]] = []  # (source_label, content)

        # 1. Project-specific notes
        if project_id:
            parts += self._fetch_project_notes(project_id)

        # 2. DNA note (skip if caller already injects DNA via dna_bootstrap)
        if include_dna and role:
            dna_content = self._fetch_dna_note(role)
            if dna_content:
                parts.append((f"DNA:{role}", dna_content))

        # 3. Keyword search — project name + query combined
        search_terms = " ".join(filter(None, [project_name, query])).strip()
        if search_terms:
            parts += self._search_vault(search_terms, exclude_ids={p[0] for p in parts})

        if not parts:
            return ""

        # Deduplicate by label, truncate, and assemble
        seen: set[str] = set()
        assembled: list[str] = []
        total = 0
        for label, content in parts:
            if label in seen:
                continue
            seen.add(label)
            snippet = content.strip()[:MAX_CHARS_PER_NOTE]
            block = f"<!-- Obsidian: {label} -->\n{snippet}"
            if total + len(block) > max_chars:
                break
            assembled.append(block)
            total += len(block)

        if not assembled:
            return ""

        return (
            "## Context from Knowledge Base\n\n"
            + "\n\n---\n\n".join(assembled)
            + "\n\n---\n"
        )

    def get_lessons_for_role(self, role: str, limit: int = 3) -> str:
        """Return recent lessons relevant to a role — append to system prompt."""
        results = self._obs.search_notes(role, limit=limit)
        lessons = [
            r for r in results
            if VAULT_FOLDERS["lessons"].lower() in r["path"].lower()
        ]
        if not lessons:
            return ""
        lines = ["## Past Lessons\n"]
        for item in lessons[:limit]:
            lines.append(f"- [{item['path']}] {item['content'][:200]}")
        return "\n".join(lines)

    def get_patterns_for_role(self, role: str) -> str:
        """Return role-specific reusable patterns from 02-Patterns."""
        folder = f"{VAULT_FOLDERS['patterns']}/{role}"
        notes = self._obs.list_notes(folder)
        parts = []
        for path in notes[:3]:
            content = self._obs.read_note(path)
            if content:
                parts.append(f"**{path}**\n{content.strip()[:600]}")
        return "\n\n".join(parts) if parts else ""

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _fetch_project_notes(self, project_id: str) -> list[tuple[str, str]]:
        folder = f"{VAULT_FOLDERS['projects']}/{project_id}"
        note_paths = self._obs.list_notes(folder)
        results = []
        for path in note_paths[:4]:
            content = self._obs.read_note(path)
            if content:
                results.append((path, content))
        return results

    def _fetch_dna_note(self, role: str) -> Optional[str]:
        path = f"{VAULT_FOLDERS['dna']}/{role}-dna.md"
        return self._obs.read_note(path)

    def _search_vault(
        self,
        query: str,
        exclude_ids: set[str] = None,
        limit: int = MAX_SEARCH_RESULTS,
    ) -> list[tuple[str, str]]:
        exclude_ids = exclude_ids or set()
        results = self._obs.search_notes(query, limit=limit + len(exclude_ids))
        out = []
        for item in results:
            if item["path"] in exclude_ids:
                continue
            if item["content"]:
                out.append((item["path"], item["content"]))
            if len(out) >= limit:
                break
        return out


# ─── Token estimation helper ──────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Rough token count without importing tiktoken."""
    return max(1, len(text) // 4)


# ─── Context budget helper ────────────────────────────────────────────────────

def build_rag_context(
    role: str,
    project_id: str = "",
    project_name: str = "",
    query: str = "",
    token_budget: int = 600,
) -> str:
    """
    Convenience function: build Obsidian RAG context within a token budget.
    Returns empty string if Obsidian unavailable.
    """
    try:
        rag = get_rag()
        max_chars = token_budget * 4  # 1 token ≈ 4 chars
        return rag.get_context_for_task(
            role=role,
            project_id=project_id,
            project_name=project_name,
            query=query,
            max_chars=max_chars,
        )
    except Exception as e:
        logger.debug(f"[RAG] Obsidian context unavailable: {e}")
        return ""


# ─── Singleton ────────────────────────────────────────────────────────────────

_rag_instance: Optional[ObsidianRAG] = None


def get_rag() -> ObsidianRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ObsidianRAG()
    return _rag_instance
