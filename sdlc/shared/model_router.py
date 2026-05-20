"""
Dynamic Model Router — เลือก LLM อัตโนมัติ ประหยัด Credit
============================================================

Logic:
  1. Task-type routing — code/reasoning/status ใช้ local model ที่เหมาะสมก่อนเสมอ
  2. Context fit check — ถ้า prompt ยาวเกิน context limit ของ local model → escalate อัตโนมัติ
  3. Complexity score (0-100) → tier fallback สำหรับงานทั่วไป
  4. Budget guard — ถ้า daily spend เกิน DAILY_BUDGET_USD → Tier FREE ทันที

Local stack:
  hermes3:3b        → status, formatting, housekeeping
  qwen3:8b          → planning, requirements, medium tasks
  qwen2.5-coder:7b  → code generation, scripts, CI/CD
  deepseek-r1:7b    → reasoning, debugging, architecture critique
"""

import os
import re
import json
import time
import logging
import sqlite3
from datetime import date, datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# ─── Model Tiers ─────────────────────────────────────────────────

class ModelTier(str, Enum):
    FREE   = "free"    # Ollama local หรือ Groq — $0
    CHEAP  = "cheap"   # Claude Haiku / GPT-4o-mini — ~$0.001/call
    SMART  = "smart"   # Claude Sonnet / GPT-4o — ~$0.01/call


# ─── Task Types ───────────────────────────────────────────────────

class TaskType(str, Enum):
    CODE_GENERATION = "code_generation"  # เขียน code, scripts, tests
    REASONING       = "reasoning"         # วิเคราะห์, debug, architecture critique
    PLANNING        = "planning"          # requirements, planning docs
    REVIEW          = "review"            # review output, QA validation
    STATUS          = "status"            # status update, notification, housekeeping
    GENERIC         = "generic"           # ทั่วไป — ใช้ score-based routing


@dataclass
class ModelConfig:
    provider: str          # "anthropic" | "openai" | "groq" | "ollama"
    model_id: str          # model string ที่ส่งให้ API
    tier: ModelTier
    cost_per_1k_input: float   # USD per 1K input tokens
    cost_per_1k_output: float  # USD per 1K output tokens
    max_tokens: int
    description: str

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000 * self.cost_per_1k_input +
                output_tokens / 1000 * self.cost_per_1k_output)


# ─── Available Models ─────────────────────────────────────────────

MODELS: dict[str, ModelConfig] = {
    # ── Claude CLI (uses local `claude` binary — no API key needed) ─
    "claude-cli/claude-sonnet-4-6": ModelConfig(
        provider="claude-cli", model_id="claude-sonnet-4-6",
        tier=ModelTier.SMART,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="Claude Sonnet via claude CLI — uses active session, no API key",
    ),
    "claude-cli/claude-haiku-4-5": ModelConfig(
        provider="claude-cli", model_id="claude-haiku-4-5",
        tier=ModelTier.CHEAP,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="Claude Haiku via claude CLI — fast, no API key",
    ),

    # ── Tier 0: FREE ──────────────────────────────────────────────
    "ollama/hermes3": ModelConfig(
        provider="ollama", model_id="hermes3:3b",
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="Hermes3 3B Local — ฟรี, status/housekeeping, instruction-following ดี",
    ),
    "ollama/qwen3": ModelConfig(
        provider="ollama", model_id="qwen3:8b",    # upgrade to :14b after: ollama pull qwen3:14b
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="Qwen3 8B Local — planning, requirements, Thai language",
    ),
    "ollama/qwen2.5-coder": ModelConfig(
        provider="ollama", model_id="qwen2.5-coder:7b",  # upgrade to :14b after pull
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="Qwen Coder 7B Local — ฟรี, code generation ดีมาก",
    ),
    "ollama/deepseek-r1": ModelConfig(
        provider="ollama", model_id="deepseek-r1:7b",    # upgrade to :14b after pull
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=8192,
        description="DeepSeek-R1 7B Local — reasoning, debug, architecture critique",
    ),
    "groq/llama-3.1-8b": ModelConfig(
        provider="groq", model_id="llama-3.1-8b-instant",
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,  # Free tier
        max_tokens=8000,
        description="Groq Llama3.1 8B — ฟรี, เร็วมาก, reasoning พอได้",
    ),
    "groq/llama-3.3-70b": ModelConfig(
        provider="groq", model_id="llama-3.3-70b-versatile",
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=32768,
        description="Groq Llama3.3 70B — ฟรี, ฉลาดกว่า 8B มาก",
    ),
    "groq/qwen3-32b": ModelConfig(
        provider="groq", model_id="qwen/qwen3-32b",
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=32768,
        description="Groq Qwen3 32B — ฟรี, คุณภาพเทียบ Claude Haiku, reasoning+code ดีมาก",
    ),
    "groq/llama-4-scout": ModelConfig(
        provider="groq", model_id="meta-llama/llama-4-scout-17b-16e-instruct",
        tier=ModelTier.FREE,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        max_tokens=131072,  # 128K context!
        description="Groq Llama4 Scout 17B — ฟรี, context 128K, multimodal-ready",
    ),

    # ── Tier 1: CHEAP ─────────────────────────────────────────────
    "anthropic/claude-haiku": ModelConfig(
        provider="anthropic", model_id="claude-haiku-4-5",
        tier=ModelTier.CHEAP,
        cost_per_1k_input=0.00025, cost_per_1k_output=0.00125,
        max_tokens=4096,
        description="Claude Haiku — ถูกมาก, reasoning ดี, ภาษาไทยดี",
    ),
    "openai/gpt-4o-mini": ModelConfig(
        provider="openai", model_id="gpt-4o-mini",
        tier=ModelTier.CHEAP,
        cost_per_1k_input=0.00015, cost_per_1k_output=0.0006,
        max_tokens=16384,
        description="GPT-4o-mini — ถูกกว่า Haiku, context ใหญ่กว่า",
    ),

    # ── Tier 2: SMART ─────────────────────────────────────────────
    "anthropic/claude-sonnet": ModelConfig(
        provider="anthropic", model_id="claude-sonnet-4-5",
        tier=ModelTier.SMART,
        cost_per_1k_input=0.003, cost_per_1k_output=0.015,
        max_tokens=8192,
        description="Claude Sonnet — ฉลาดมาก, งาน complex",
    ),
    "openai/gpt-4o": ModelConfig(
        provider="openai", model_id="gpt-4o",
        tier=ModelTier.SMART,
        cost_per_1k_input=0.005, cost_per_1k_output=0.015,
        max_tokens=8192,
        description="GPT-4o — ฉลาดมาก, multimodal",
    ),
}


# ─── Model Score Matrix (1-10 per role) ──────────────────────────
# Score = how well this model fits this role for typical tasks
# Criteria: instruction following, output structure, domain expertise, context handling

MODEL_SCORE_MATRIX: dict[str, dict[str, int]] = {
    # tier FREE — local (14B models = 85-90% Claude quality for their specialties)
    "ollama/hermes3":       {"ceo":2,"pm":2,"ba":2,"sa":2,"uxui":2,"dev":3,"qa":3,"devops":3},
    "ollama/qwen3":         {"ceo":6,"pm":7,"ba":7,"sa":7,"uxui":6,"dev":6,"qa":7,"devops":6},
    "ollama/qwen2.5-coder": {"ceo":2,"pm":3,"ba":3,"sa":6,"uxui":2,"dev":9,"qa":8,"devops":9},
    "ollama/deepseek-r1":   {"ceo":6,"pm":6,"ba":7,"sa":9,"uxui":5,"dev":8,"qa":8,"devops":8},
    # tier FREE — Groq cloud
    "groq/llama-3.1-8b":    {"ceo":4,"pm":4,"ba":4,"sa":4,"uxui":3,"dev":5,"qa":5,"devops":4},
    "groq/llama-3.3-70b":   {"ceo":7,"pm":7,"ba":7,"sa":7,"uxui":6,"dev":7,"qa":7,"devops":6},
    # Groq Qwen3-32B: reasoning+code ดีมาก — ใกล้เคียง Claude Haiku (score 8 สำหรับงาน technical)
    "groq/qwen3-32b":       {"ceo":7,"pm":8,"ba":8,"sa":8,"uxui":7,"dev":8,"qa":8,"devops":8},
    # Groq Llama4 Scout: context 128K ดีมากสำหรับงานที่ต้อง context ยาว
    "groq/llama-4-scout":   {"ceo":7,"pm":7,"ba":7,"sa":7,"uxui":7,"dev":7,"qa":7,"devops":7},
    # tier CHEAP
    "anthropic/claude-haiku":{"ceo":7,"pm":7,"ba":7,"sa":7,"uxui":7,"dev":6,"qa":7,"devops":6},
    "openai/gpt-4o-mini":   {"ceo":7,"pm":7,"ba":7,"sa":7,"uxui":7,"dev":7,"qa":7,"devops":7},
    # tier SMART
    "anthropic/claude-sonnet":{"ceo":9,"pm":9,"ba":9,"sa":9,"uxui":9,"dev":9,"qa":9,"devops":9},
    "openai/gpt-4o":        {"ceo":9,"pm":9,"ba":9,"sa":9,"uxui":9,"dev":9,"qa":9,"devops":9},
    "claude-cli/claude-sonnet-4-6":{"ceo":9,"pm":9,"ba":9,"sa":9,"uxui":9,"dev":9,"qa":9,"devops":9},
    "claude-cli/claude-haiku-4-5": {"ceo":7,"pm":7,"ba":7,"sa":7,"uxui":7,"dev":7,"qa":7,"devops":7},
}


def best_free_for_role(
    role: str,
    exclude: list[str] = None,
    exclude_providers: list[str] = None,
) -> tuple[str, "ModelConfig"]:
    """
    Return (model_key, ModelConfig) of highest-scoring FREE model for this role.
    Excludes models in the exclude list (e.g., ones that already failed).
    Skips models whose provider is not available.
    """
    exclude = set(exclude or [])
    exclude_providers = set(exclude_providers or [])
    # Check available providers (cached check — fast)
    available = _get_available_providers_cached()

    best_key: str = None
    best_cfg: ModelConfig = None
    best_score: int = -1

    for model_key, cfg in MODELS.items():
        if cfg.tier != ModelTier.FREE:
            continue
        if model_key in exclude:
            continue
        if cfg.provider in exclude_providers:
            continue
        if cfg.provider not in available:
            continue
        scores = MODEL_SCORE_MATRIX.get(model_key, {})
        score = scores.get(role, 0)
        if score > best_score:
            best_score = score
            best_key   = model_key
            best_cfg   = cfg

    # Ultimate fallback
    if not best_key:
        best_key = "ollama/hermes3"
        best_cfg = MODELS["ollama/hermes3"]
        if "ollama" in exclude_providers:
            logger.warning("[Router] WARNING: hermes3 last-resort used despite ollama cooldown")

    return best_key, best_cfg


def score_for_role(model_key: str, role: str) -> int:
    """Return the score (0-10) of a model for a specific role."""
    return MODEL_SCORE_MATRIX.get(model_key, {}).get(role, 0)


_available_providers_cache: set[str] = None

def _get_available_providers_cached() -> set[str]:
    """Provider availability check — cached for process lifetime."""
    global _available_providers_cache
    if _available_providers_cache is not None:
        return _available_providers_cache

    available: set[str] = set()
    if os.getenv("ANTHROPIC_API_KEY"):
        available.add("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        available.add("openai")
    if os.getenv("GROQ_API_KEY"):
        available.add("groq")
    # claude-cli — check if binary exists
    import shutil
    if shutil.which("claude") or os.path.exists(os.path.expanduser("~/.npm-global/bin/claude")):
        available.add("claude-cli")
    # Ollama
    import urllib.request
    try:
        urllib.request.urlopen(
            os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/tags", timeout=2
        )
        available.add("ollama")
    except Exception:
        pass

    _available_providers_cache = available
    return available


# ─── Role → Model Preferences ────────────────────────────────────
# แต่ละ role มี preferred model ต่อ tier (ใช้เมื่อ task_type=GENERIC หรือ PLANNING/REVIEW)

ROLE_MODEL_PREFERENCES: dict[str, dict[ModelTier, list[str]]] = {
    "ceo":    {
        ModelTier.FREE:  ["groq/llama-3.3-70b", "ollama/qwen3", "ollama/hermes3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku"],
        ModelTier.SMART: ["anthropic/claude-sonnet"],
    },
    "pm":     {
        ModelTier.FREE:  ["groq/llama-3.3-70b", "ollama/qwen3", "ollama/hermes3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku"],
        ModelTier.SMART: ["anthropic/claude-sonnet"],
    },
    "ba":     {
        ModelTier.FREE:  ["groq/llama-3.3-70b", "ollama/qwen3", "ollama/hermes3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku"],
        ModelTier.SMART: ["anthropic/claude-sonnet"],
    },
    "sa":     {
        # SA เน้น reasoning → deepseek-r1 เป็น free-tier แรก
        ModelTier.FREE:  ["ollama/deepseek-r1", "groq/llama-3.3-70b", "ollama/qwen3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku", "openai/gpt-4o-mini"],
        ModelTier.SMART: ["anthropic/claude-sonnet", "openai/gpt-4o"],
    },
    "uxui":   {
        ModelTier.FREE:  ["groq/llama-3.3-70b", "ollama/qwen3", "ollama/hermes3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku"],
        ModelTier.SMART: ["anthropic/claude-sonnet"],
    },
    "dev":    {
        # DEV: code first, reasoning second
        ModelTier.FREE:  ["ollama/qwen2.5-coder", "ollama/deepseek-r1", "ollama/hermes3"],
        ModelTier.CHEAP: ["openai/gpt-4o-mini", "anthropic/claude-haiku"],
        ModelTier.SMART: ["openai/gpt-4o", "anthropic/claude-sonnet"],
    },
    "qa":     {
        ModelTier.FREE:  ["ollama/qwen3", "groq/llama-3.3-70b", "ollama/hermes3"],
        ModelTier.CHEAP: ["anthropic/claude-haiku"],
        ModelTier.SMART: ["anthropic/claude-sonnet"],
    },
    "devops": {
        # DEVOPS: script/config first, reasoning for risk analysis
        ModelTier.FREE:  ["ollama/qwen2.5-coder", "ollama/deepseek-r1", "ollama/hermes3"],
        ModelTier.CHEAP: ["openai/gpt-4o-mini", "anthropic/claude-haiku"],
        ModelTier.SMART: ["openai/gpt-4o"],
    },
}


# ─── Task-Type Routing Tables ─────────────────────────────────────

# Context token limits สำหรับ local models (conservative — ป้องกัน truncation)
LOCAL_CONTEXT_LIMITS: dict[str, int] = {
    "ollama/hermes3":        5500,   # 3B model — limit ต่ำสุด
    "ollama/qwen3":          6500,
    "ollama/qwen2.5-coder":  6500,
    "ollama/deepseek-r1":    6500,
    "groq/llama-3.1-8b":     7000,
    "groq/llama-3.3-70b":   30000,
}

# task_type → local model ที่เริ่มใช้ก่อนเสมอ (bypass score routing)
TASK_TYPE_START_MODEL: dict[str, str] = {
    TaskType.CODE_GENERATION: "ollama/qwen2.5-coder",
    TaskType.REASONING:       "ollama/deepseek-r1",
    TaskType.STATUS:          "ollama/hermes3",
}

# task_type → complexity score ที่ต้อง escalate ออกจาก start model
# (ถ้า score >= threshold → ไม่ใช้ start model, ใช้ score-based routing แทน)
TASK_TYPE_ESCALATION_SCORE: dict[str, int] = {
    TaskType.CODE_GENERATION: 82,   # code escalate ขึ้น cloud เฉพาะ very critical
    TaskType.REASONING:       76,   # deepseek-r1 รับได้ส่วนใหญ่
    TaskType.STATUS:          101,  # ไม่ escalate status เลย
}


def _estimate_tokens(text: str) -> int:
    """Approximate token count — 1 token ≈ 4 chars (fast, no tokenizer needed)"""
    return len(text) // 4


def _fits_context(model_key: str, token_count: int) -> bool:
    """True ถ้า prompt tokens ไม่เกิน context limit ของ model"""
    limit = LOCAL_CONTEXT_LIMITS.get(model_key)
    if limit is None:
        return True  # cloud models — ไม่มี limit ใน router
    return token_count <= limit


def _active_cooldown_blocks() -> tuple[set[str], set[str]]:
    """Return (providers, model_keys) currently cooling down."""
    try:
        from shared.storage import Storage
        cooldowns = Storage().get_active_provider_cooldowns()
    except Exception:
        return set(), set()

    providers: set[str] = set()
    model_keys: set[str] = set()
    for cooldown in cooldowns:
        provider = cooldown.get("provider") or ""
        model = cooldown.get("model") or ""
        if provider:
            providers.add(provider)
        if model:
            model_keys.add(model)
    return providers, model_keys


def _is_cooling_down(model_key: str, cfg: ModelConfig, cooldown_providers: set[str], cooldown_models: set[str]) -> bool:
    return model_key in cooldown_models or cfg.provider in cooldown_providers


# ─── Complexity Analyzer ─────────────────────────────────────────

class ComplexityAnalyzer:
    """
    วิเคราะห์ความซับซ้อนของ prompt → score 0-100
    ใช้ heuristics ง่ายๆ (ไม่ต้องเรียก LLM)
    """

    # Keywords ที่บ่งบอกงานซับซ้อน
    COMPLEX_KEYWORDS = [
        "architecture", "design pattern", "security", "scalable",
        "microservice", "distributed", "database schema", "api spec",
        "openapi", "system design", "infrastructure", "deployment",
        "kubernetes", "docker", "ci/cd", "pipeline", "algorithm",
        "optimization", "performance", "concurrency", "async",
        "วิเคราะห์", "ออกแบบระบบ", "สถาปัตยกรรม", "ฐานข้อมูล",
        "รายละเอียด", "ครบถ้วน", "comprehensive", "complex",
    ]

    SIMPLE_KEYWORDS = [
        "สรุป", "summary", "list", "รายการ", "enumerate",
        "format", "convert", "translate", "ตอบสั้น", "brief",
        "simple", "basic", "quick", "ง่ายๆ",
    ]

    def score(self, prompt: str, role: str) -> int:
        """
        คำนวณ complexity score 0-100
        """
        score = 40  # baseline

        text = prompt.lower()

        # ── ความยาว prompt ──────────────────────────────────────
        words = len(prompt.split())
        if words > 500:  score += 20
        elif words > 200: score += 10
        elif words < 50:  score -= 10

        # ── Complex keywords ───────────────────────────────────
        complex_count = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in text)
        score += min(complex_count * 5, 25)

        # ── Simple keywords ────────────────────────────────────
        simple_count = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in text)
        score -= min(simple_count * 5, 20)

        # ── Role-based baseline adjustment ────────────────────
        role_baselines = {
            "ceo":    35,   # บทบาทสั่งงาน ไม่ต้องซับซ้อน
            "pm":     40,   # Planning ปานกลาง
            "ba":     45,   # Requirements analysis ปานกลาง-สูง
            "sa":     60,   # Architecture — มักซับซ้อน
            "uxui":   35,   # UI spec — ปานกลาง
            "dev":    55,   # Coding — มักซับซ้อน
            "qa":     40,   # Testing — ปานกลาง
            "devops": 50,   # Infra — ปานกลาง-สูง
        }
        role_adj = role_baselines.get(role, 40) - 40
        score += role_adj

        # ── Revision → ลด complexity (งานเดิม แค่แก้ไข) ────
        if "revision" in text or "แก้ไข" in text or "revise" in text:
            score -= 15

        # ── Clamp 0-100 ───────────────────────────────────────
        return max(0, min(100, score))

    def classify_tier(self, score: int) -> ModelTier:
        free_threshold  = int(os.getenv("COMPLEXITY_FREE_THRESHOLD",  "40"))
        cheap_threshold = int(os.getenv("COMPLEXITY_CHEAP_THRESHOLD", "70"))

        if score < free_threshold:
            return ModelTier.FREE
        elif score < cheap_threshold:
            return ModelTier.CHEAP
        else:
            return ModelTier.SMART


# ─── Cost Tracker ─────────────────────────────────────────────────

class CostTracker:
    """
    ติดตาม API cost ต่อวัน — บันทึก SQLite
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DB_PATH", "/app/data/sdlc.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    date TEXT,
                    role TEXT,
                    project_id TEXT,
                    model_key TEXT,
                    provider TEXT,
                    tier TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_usd REAL,
                    complexity_score INTEGER,
                    task_description TEXT
                )
            """)
            conn.commit()

    def record(
        self,
        role: str,
        project_id: str,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        complexity_score: int,
        task_description: str = "",
    ):
        model = MODELS.get(model_key)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO llm_usage
                   (ts, date, role, project_id, model_key, provider, tier,
                    input_tokens, output_tokens, cost_usd, complexity_score, task_description)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.utcnow().isoformat(),
                    date.today().isoformat(),
                    role, project_id, model_key,
                    model.provider if model else "unknown",
                    model.tier if model else "unknown",
                    input_tokens, output_tokens, cost_usd,
                    complexity_score, task_description[:200],
                ),
            )
            conn.commit()

    def today_spend(self) -> float:
        today = date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE date = ?",
                (today,)
            ).fetchone()
        return row[0] if row else 0.0

    def today_summary(self) -> dict:
        today = date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT model_key, tier, COUNT(*), SUM(input_tokens),
                       SUM(output_tokens), SUM(cost_usd)
                FROM llm_usage
                WHERE date = ?
                GROUP BY model_key, tier
                ORDER BY SUM(cost_usd) DESC
            """, (today,)).fetchall()
        return {
            "date": today,
            "total_spend": sum(r[5] for r in rows),
            "budget": float(os.getenv("DAILY_BUDGET_USD", "1.00")),
            "breakdown": [
                {
                    "model": r[0], "tier": r[1], "calls": r[2],
                    "input_tokens": r[3], "output_tokens": r[4],
                    "cost_usd": round(r[5], 5),
                }
                for r in rows
            ],
        }

    def is_over_budget(self) -> bool:
        budget = float(os.getenv("DAILY_BUDGET_USD", "1.00"))
        return self.today_spend() >= budget


# ─── Model Router ─────────────────────────────────────────────────

class ModelRouter:
    """
    เลือก model ที่ถูกที่สุดที่ยังทำงานได้ดี
    """

    def __init__(self):
        self.analyzer   = ComplexityAnalyzer()
        self.tracker    = CostTracker()
        self._available_providers: set[str] = set()
        self._check_available_providers()

    def _check_available_providers(self):
        """ตรวจสอบว่า provider ไหน configure แล้ว"""
        if os.getenv("ANTHROPIC_API_KEY"):
            self._available_providers.add("anthropic")
        if os.getenv("OPENAI_API_KEY"):
            self._available_providers.add("openai")
        if os.getenv("GROQ_API_KEY"):
            self._available_providers.add("groq")
        # Ollama — ตรวจสอบ connection
        import urllib.request
        try:
            urllib.request.urlopen(
                os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/tags",
                timeout=2
            )
            self._available_providers.add("ollama")
        except Exception:
            pass  # Ollama not available

    def route(
        self,
        prompt: str,
        role: str,
        project_id: str = "",
        force_tier: Optional[ModelTier] = None,
        task_type: Optional[TaskType] = None,
        full_context: str = "",
    ) -> tuple[ModelConfig, str, int]:
        """
        เลือก model ที่เหมาะสม

        task_type  — ถ้าระบุ จะ route ไป local model ที่เหมาะก่อน (bypass score)
        full_context — system_prompt + user_message สำหรับ token count จริง

        Returns: (ModelConfig, model_key, complexity_score)
        """
        # 1. Token count — ใช้สำหรับ context fit check
        prompt_tokens = _estimate_tokens(full_context or prompt)
        cooldown_providers, cooldown_models = _active_cooldown_blocks()

        # 2. Complexity score
        complexity = self.analyzer.score(prompt, role)
        target_tier = force_tier or self.analyzer.classify_tier(complexity)

        # 3. Budget guard — ถ้า over budget ให้ใช้ best free model สำหรับ role นี้
        if self.tracker.is_over_budget() and target_tier != ModelTier.FREE:
            import logging
            logging.warning(
                f"[Router] Daily budget exceeded! Forcing best FREE for role={role} "
                f"(spend=${self.tracker.today_spend():.4f})"
            )
            # ใช้ score matrix เลือก free model ที่ดีที่สุดสำหรับ role นี้
            best_key, best_cfg = best_free_for_role(
                role,
                exclude=list(cooldown_models),
                exclude_providers=list(cooldown_providers),
            )
            logging.warning(f"[Router] Budget fallback → {best_key} (score={score_for_role(best_key, role)}/10)")
            return best_cfg, best_key, complexity

        budget_remaining = max(0, float(os.getenv("DAILY_BUDGET_USD", "1.00")) - self.tracker.today_spend())
        tier_emoji_map   = {"free": "🆓", "cheap": "💰", "smart": "🧠"}

        # 4. Task-type routing — ลอง local model ที่เหมาะก่อน (ถ้าไม่ force_tier)
        if task_type and not force_tier and task_type in TASK_TYPE_START_MODEL:
            start_key = TASK_TYPE_START_MODEL[task_type]
            start_cfg = MODELS.get(start_key)
            escalation_threshold = TASK_TYPE_ESCALATION_SCORE.get(task_type, 80)

            provider_ok  = start_cfg and start_cfg.provider in self._available_providers
            cooldown_ok  = bool(start_cfg) and not _is_cooling_down(
                start_key, start_cfg, cooldown_providers, cooldown_models
            )
            context_ok   = _fits_context(start_key, prompt_tokens)
            score_ok     = complexity < escalation_threshold
            budget_ok    = target_tier == ModelTier.FREE or not self.tracker.is_over_budget()

            if provider_ok and cooldown_ok and context_ok and score_ok:
                te = tier_emoji_map.get(start_cfg.tier, "?")
                print(
                    f"[Router] role={role} task={task_type} complexity={complexity} "
                    f"tokens={prompt_tokens} → {start_key} {te} "
                    f"| budget_remaining=${budget_remaining:.3f}"
                )
                return start_cfg, start_key, complexity

            # Log ว่าทำไม task-type model ถูก skip
            if not context_ok:
                print(
                    f"[Router] {start_key} context overflow "
                    f"({prompt_tokens} > {LOCAL_CONTEXT_LIMITS.get(start_key, '?')} tokens) → escalating"
                )
            elif not score_ok:
                print(
                    f"[Router] score {complexity} ≥ escalation threshold {escalation_threshold} "
                    f"for {task_type} → score-based routing"
                )
            elif not cooldown_ok:
                print(f"[Router] {start_key} provider/model cooldown active → score-based routing")

        # 5. Score-based routing — ลอง tier fallback ตามลำดับ
        #    พร้อม context fit check ในแต่ละ candidate
        preferences = ROLE_MODEL_PREFERENCES.get(role, {})
        tier_fallback = {
            ModelTier.SMART: [ModelTier.SMART, ModelTier.CHEAP, ModelTier.FREE],
            ModelTier.CHEAP: [ModelTier.CHEAP, ModelTier.FREE],
            ModelTier.FREE:  [ModelTier.FREE],
        }

        selected_key    = None
        selected_config = None
        actual_tier     = target_tier

        for tier in tier_fallback[target_tier]:
            cands = preferences.get(tier, [])
            for key in cands:
                cfg = MODELS.get(key)
                if not cfg or cfg.provider not in self._available_providers:
                    continue
                if _is_cooling_down(key, cfg, cooldown_providers, cooldown_models):
                    print(f"[Router] {key} provider/model cooldown active → skip")
                    continue
                if not _fits_context(key, prompt_tokens):
                    print(f"[Router] {key} context overflow ({prompt_tokens} tokens) → skip")
                    continue
                selected_key    = key
                selected_config = cfg
                actual_tier     = tier
                break
            if selected_key:
                break

        # 6. Last resort — hermes3 เสมอ (ไม่มี context limit check ที่นี่ — better than nothing)
        if not selected_key:
            selected_key    = "ollama/hermes3"
            selected_config = MODELS["ollama/hermes3"]
            actual_tier     = ModelTier.FREE
            if "ollama" in cooldown_providers:
                logger.warning("[Router] WARNING: hermes3 last-resort used despite ollama cooldown")

        te = tier_emoji_map.get(actual_tier, "?")
        task_label = f" task={task_type}" if task_type else ""
        print(
            f"[Router] role={role}{task_label} complexity={complexity} "
            f"tokens={prompt_tokens} tier={actual_tier} {te} → {selected_key} "
            f"| budget_remaining=${budget_remaining:.3f}"
        )

        return selected_config, selected_key, complexity

    def get_routing_summary(
        self,
        prompt: str,
        role: str,
        task_type: Optional[TaskType] = None,
        full_context: str = "",
    ) -> dict:
        """
        ส่งคืนข้อมูล routing ทั้งหมด (ใช้แสดงใน Discord)
        """
        config, key, complexity = self.route(
            prompt, role, task_type=task_type, full_context=full_context
        )
        today = self.tracker.today_summary()
        prompt_tokens = _estimate_tokens(full_context or prompt)
        return {
            "model_key": key,
            "model_id": config.model_id,
            "provider": config.provider,
            "tier": config.tier,
            "task_type": task_type or TaskType.GENERIC,
            "complexity_score": complexity,
            "prompt_tokens": prompt_tokens,
            "estimated_cost": config.estimate_cost(prompt_tokens, 1000),
            "today_spend": today["total_spend"],
            "budget_remaining": max(0, today["budget"] - today["total_spend"]),
        }


# ─── Singleton ────────────────────────────────────────────────────
_router_instance: Optional[ModelRouter] = None

def get_router() -> ModelRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
