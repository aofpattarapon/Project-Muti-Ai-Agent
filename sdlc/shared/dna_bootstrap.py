"""
DNA Bootstrap — Phase 0
=======================
Uses a paid model (claude-sonnet/opus) ONCE per project type to create:
  1. Optimized compressed system prompt for each role (~500 tokens)
  2. Output format template with exact structure
  3. Condensed few-shot example (~300 tokens)
  4. Harness behavior description

DNA is stored in SQLite and injected into free model calls as context,
dramatically improving free model output quality without per-call cost.

Usage:
    bootstrapper = DNABootstrap()
    await bootstrapper.bootstrap_all(project_context="E-commerce platform...")
    dna = bootstrapper.get_dna("ba")
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ALL_ROLES = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]


class DNABootstrap:
    """Creates and retrieves role DNA using paid model distillation."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DB_PATH", "/app/data/sdlc.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_dna_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE,
                    role TEXT,
                    cache_type TEXT,
                    content TEXT,
                    model_used TEXT,
                    project_context_hash TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()

    # ─── DNA Creation ─────────────────────────────────────────────────────────

    async def bootstrap_role(
        self,
        role: str,
        project_context: str = "",
        force_refresh: bool = False,
    ) -> dict:
        """
        Use paid model to create optimized DNA for one role.
        Returns the DNA dict and stores it in DB.
        """
        from shared.role_schemas import ROLE_OUTPUT_SPECS, get_role_template
        from shared.llm_client import LLMClient
        from shared.model_router import MODELS, ModelTier

        cache_key = f"{role}_dna"
        existing = self.get_dna(role)
        if existing and not force_refresh:
            logger.info(f"[DNA] Using cached DNA for {role}")
            return existing

        spec = ROLE_OUTPUT_SPECS.get(role)
        if not spec:
            logger.warning(f"[DNA] No spec for role {role}")
            return {}

        logger.info(f"[DNA] Bootstrapping {role} DNA via paid model...")

        # Use claude-cli first (free), fall back to anthropic paid
        model_key = "claude-cli/claude-sonnet-4-6"
        model_cfg = MODELS.get(model_key) or MODELS.get("anthropic/claude-sonnet")
        if model_cfg is None:
            model_key = next(
                (k for k, v in MODELS.items() if v.tier.value in ("smart", "cheap")),
                "claude-cli/claude-sonnet-4-6"
            )
            model_cfg = MODELS[model_key]

        client = LLMClient(model_config=model_cfg, model_key=model_key)

        system = (
            "You are an expert prompt engineer and SDLC consultant. "
            "Your task: create a concise but comprehensive role DNA package "
            "that will guide a smaller free LLM to produce high-quality outputs "
            "matching the standard of a top-tier model like Claude Sonnet. "
            "Be precise, actionable, and compressed — every token counts."
        )

        context_section = (
            f"\nProject context:\n{project_context[:600]}\n" if project_context else ""
        )

        prompt = f"""Create a DNA package for the **{role.upper()}** agent role in a multi-agent SDLC system.
{context_section}
Role responsibilities:
- Required output sections: {', '.join(spec.required_sections)}
- Must generate these file types: {', '.join(f[1] for f in spec.output_files)}
- Mermaid diagrams required: {', '.join(spec.mermaid_types) or 'none'}
- Target output token budget: {spec.token_budget}

Output format template (reference):
{spec.template}

Return a JSON object with these exact keys:
{{
  "compressed_system_prompt": "<optimized system prompt ~500 tokens — role identity, core rules, output quality expectations>",
  "harness_behavior": "<how to approach tasks: reasoning style, decision depth, language mix Thai/English, quality bar>",
  "format_rules": ["<rule 1>", "<rule 2>", ...],
  "few_shot_snippet": "<condensed example showing ideal output structure for this role, ~300 tokens>",
  "anti_patterns": ["<what NOT to do — common free model mistakes for this role>"],
  "token_compression_tips": "<how to be concise without losing quality>"
}}

Return ONLY valid JSON. No markdown wrapper, no explanation."""

        try:
            raw = await client.complete(
                system_prompt=system,
                user_message=prompt,
                max_tokens=2000,
            )
            # Strip markdown wrapper if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            dna = json.loads(raw)
        except Exception as e:
            logger.error(f"[DNA] Failed to parse DNA for {role}: {e}")
            dna = _fallback_dna(role, spec)

        self._store_dna(cache_key, role, "dna", dna, model_key)
        logger.info(f"[DNA] ✅ DNA stored for {role} ({len(json.dumps(dna))} chars)")

        # Sync DNA to Obsidian vault (non-blocking — never fails the bootstrap)
        try:
            from shared.obsidian_client import get_obsidian
            obs = get_obsidian()
            obs.save_role_dna(role, {**dna, "_model_used": model_key})
            logger.debug(f"[DNA] Synced {role} DNA to Obsidian vault")
        except Exception as _obs_err:
            logger.debug(f"[DNA] Obsidian sync skipped: {_obs_err}")

        return dna

    async def bootstrap_all(
        self,
        project_context: str = "",
        force_refresh: bool = False,
    ) -> dict[str, dict]:
        """Bootstrap DNA for all 8 SDLC roles. Returns {role: dna_dict}."""
        results = {}
        for role in _ALL_ROLES:
            try:
                dna = await self.bootstrap_role(
                    role, project_context=project_context, force_refresh=force_refresh
                )
                results[role] = dna
            except Exception as e:
                logger.error(f"[DNA] bootstrap_all failed for {role}: {e}")
                results[role] = {}
        return results

    # ─── Style Reference (from paid model output) ─────────────────────────────

    def save_style_ref(self, role: str, raw_output: str, model_used: str):
        """
        Called after every paid model task completion.
        Extracts style DNA from output and saves for future free model injection.
        """
        style_ref = _extract_style_ref(raw_output)
        cache_key = f"{role}_style_ref"
        self._store_dna(cache_key, role, "style_ref", style_ref, model_used)
        logger.debug(f"[DNA] Style ref saved for {role} from {model_used}")

    def get_style_ref(self, role: str) -> Optional[str]:
        """Return compressed style reference string for injection into free model prompt."""
        data = self._load_dna(f"{role}_style_ref")
        if not data:
            return None
        ref = data.get("content", {})
        if not ref:
            return None
        parts = []
        if ref.get("sample_snippet"):
            parts.append(f"[STYLE REF — mirror this format]\n{ref['sample_snippet']}")
        if ref.get("format_patterns"):
            parts.append(f"Format rules observed: {ref['format_patterns']}")
        if ref.get("output_structure"):
            parts.append(f"Required sections: {', '.join(ref['output_structure'])}")
        return "\n".join(parts) if parts else None

    # ─── DNA Retrieval ────────────────────────────────────────────────────────

    def get_dna(self, role: str) -> Optional[dict]:
        """Return cached DNA dict for role, or None if not bootstrapped yet."""
        return self._load_dna(f"{role}_dna")

    def build_dna_system_prompt(self, role: str, base_system_prompt: str) -> str:
        """
        Build the effective system prompt for a free model call:
        Uses compressed DNA if available, otherwise falls back to base.
        Also appends style_ref if available.
        """
        dna = self.get_dna(role)
        style_ref = self.get_style_ref(role)

        if not dna:
            # No DNA yet — use base prompt but inject role template
            from shared.role_schemas import get_role_template
            template = get_role_template(role)
            return f"{base_system_prompt}\n\n{template}" if template else base_system_prompt

        # Build compressed prompt from DNA
        parts = []

        compressed = dna.get("compressed_system_prompt", "")
        if compressed:
            parts.append(compressed)
        else:
            parts.append(base_system_prompt)

        harness = dna.get("harness_behavior", "")
        if harness:
            parts.append(f"\n[HARNESS]\n{harness}")

        rules = dna.get("format_rules", [])
        if rules:
            parts.append("\n[FORMAT RULES]\n" + "\n".join(f"- {r}" for r in rules))

        snippet = dna.get("few_shot_snippet", "")
        if snippet:
            parts.append(f"\n[EXAMPLE OUTPUT STRUCTURE]\n{snippet}")

        anti = dna.get("anti_patterns", [])
        if anti:
            parts.append("\n[AVOID]\n" + "\n".join(f"- {a}" for a in anti))

        if style_ref:
            parts.append(f"\n{style_ref}")

        return "\n".join(parts)

    def has_dna(self, role: str) -> bool:
        return self._load_dna(f"{role}_dna") is not None

    # ─── DB helpers ──────────────────────────────────────────────────────────

    def _store_dna(
        self, cache_key: str, role: str, cache_type: str, content: dict, model_used: str
    ):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO model_dna_cache
                    (cache_key, role, cache_type, content, model_used, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    content=excluded.content,
                    model_used=excluded.model_used,
                    updated_at=excluded.updated_at
            """, (cache_key, role, cache_type, json.dumps(content), model_used, now, now))
            conn.commit()

    def _load_dna(self, cache_key: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT content FROM model_dna_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def list_cached_roles(self) -> list[dict]:
        """List all cached DNA entries."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT role, cache_type, model_used, updated_at
                FROM model_dna_cache ORDER BY role, cache_type
            """).fetchall()
        return [
            {"role": r[0], "type": r[1], "model": r[2], "updated_at": r[3]}
            for r in rows
        ]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_style_ref(raw_output: str) -> dict:
    """
    Extract condensed style reference from a paid model's output.
    Preserves structure + first 600 chars as sample snippet.
    """
    import re

    # Extract section headings
    headings = re.findall(r"^#{1,3}\s+(.+)$", raw_output, re.MULTILINE)
    structure = headings[:10]

    # Detect format patterns used
    patterns = []
    if "```mermaid" in raw_output:
        patterns.append("mermaid diagrams")
    if re.search(r"\|[-| :]+\|", raw_output):
        patterns.append("markdown tables")
    if re.search(r"^\d+\.", raw_output, re.MULTILINE):
        patterns.append("numbered lists")
    if "```" in raw_output:
        langs = re.findall(r"```(\w+)", raw_output)
        if langs:
            patterns.append(f"code blocks: {', '.join(set(langs))}")

    # Sample: first 600 chars of content
    sample = raw_output[:600].strip()

    return {
        "output_structure": structure,
        "format_patterns":  ", ".join(patterns) if patterns else "markdown prose",
        "sample_snippet":   sample,
        "total_length":     len(raw_output),
    }


def _fallback_dna(role: str, spec) -> dict:
    """Minimal DNA when paid model is unavailable for bootstrap."""
    from shared.role_schemas import get_role_template
    return {
        "compressed_system_prompt": (
            f"You are the {role.upper()} agent in a multi-agent SDLC system. "
            f"Produce high-quality, structured output following the provided template exactly. "
            f"Be thorough, precise, and professional."
        ),
        "harness_behavior": (
            "Think step-by-step. Always include all required sections. "
            "Use tables for structured data. Use Mermaid for diagrams. "
            "Mix Thai and English naturally — Thai for context, English for technical terms."
        ),
        "format_rules": [
            "Always include all required sections",
            "Use tables for comparative or list data",
            "Include Mermaid diagrams where specified",
            "Keep explanations concise — prefer structure over prose",
            "End with a brief summary of decisions made",
        ],
        "few_shot_snippet": get_role_template(role)[:500],
        "anti_patterns": [
            "Do NOT produce only prose without structure",
            "Do NOT skip required sections",
            "Do NOT use light/dark theming hints in output",
            "Do NOT truncate tables mid-way",
        ],
        "token_compression_tips": (
            "Use bullet points instead of long paragraphs. "
            "Abbreviate obvious terms. Keep table rows concise."
        ),
    }


# ─── Singleton ────────────────────────────────────────────────────────────────
import re

_dna_instance: Optional[DNABootstrap] = None

def get_dna_bootstrap() -> DNABootstrap:
    global _dna_instance
    if _dna_instance is None:
        _dna_instance = DNABootstrap()
    return _dna_instance
