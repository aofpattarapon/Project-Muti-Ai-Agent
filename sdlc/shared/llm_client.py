"""
LLM Client — รองรับ Anthropic, OpenAI, Groq, Ollama
ทำงานร่วมกับ ModelRouter เพื่อ route อัตโนมัติ
"""

import os
import time
import httpx
import asyncio
import tiktoken
from enum import Enum
from typing import Optional

from shared.model_router import (
    ModelConfig, ModelTier, TaskType, MODELS, CostTracker, get_router,
    best_free_for_role, score_for_role,
)


# Groq pre-flight payload guard: reject before HTTP call to avoid 413 errors.
# ~100K chars ≈ 25K tokens — conservative for free-tier rate limits.
GROQ_MAX_PAYLOAD_CHARS = 100_000


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GROQ = "groq"
    OLLAMA = "ollama"


class LLMClient:
    """
    Unified LLM Client ที่ call provider จริง
    รองรับ: Anthropic, OpenAI, Groq, Ollama
    """

    def __init__(self, model_config: ModelConfig = None, model_key: str = "", provider=None, model: str = ""):
        if model_config is None and provider is not None:
            prov = provider.value if isinstance(provider, LLMProvider) else str(provider)
            model_key = f"{prov}/{model}" if model else prov
            model_config = MODELS.get(model_key) or ModelConfig(
                provider=prov, model_id=model or prov,
                tier=ModelTier.FREE,
                cost_per_1k_input=0.0, cost_per_1k_output=0.0,
                max_tokens=4096, description="custom",
            )
        self.config = model_config
        self.model_key = model_key
        self.tracker = CostTracker()

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        role: str = "",
        project_id: str = "",
        complexity_score: int = 50,
        use_dna: bool = True,
    ) -> str:
        """
        ส่ง prompt ไปยัง LLM และรับ response
        พร้อม cost tracking อัตโนมัติ
        """
        provider = self.config.provider
        is_free_model = self.config.tier.value == "free"

        # DNA injection for free models — replace/enhance system prompt with DNA
        effective_system = system_prompt
        if use_dna and role and is_free_model:
            try:
                from shared.dna_bootstrap import get_dna_bootstrap
                dna = get_dna_bootstrap()
                enhanced = dna.build_dna_system_prompt(role, system_prompt)
                if enhanced and enhanced != system_prompt:
                    effective_system = enhanced
                    print(f"[LLM] 🧬 DNA injected for {role} "
                          f"({len(system_prompt)} → {len(effective_system)} chars)")
            except Exception as _dna_err:
                pass  # DNA injection is optional — never block the call

        start = time.time()
        try:
            if provider == "claude-cli":
                response_text = await self._call_claude_cli(effective_system, user_message, max_tokens)
            elif provider == "anthropic":
                response_text = await self._call_anthropic(effective_system, user_message, max_tokens)
            elif provider == "openai":
                response_text = await self._call_openai(effective_system, user_message, max_tokens)
            elif provider == "groq":
                response_text = await self._call_groq(effective_system, user_message, max_tokens)
            elif provider == "ollama":
                response_text = await self._call_ollama(effective_system, user_message, max_tokens)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as primary_err:
            # ── Multi-step fallback chain on quota/auth/timeout ──────────
            # Chain: primary → claude-cli → gpt-4o-mini → hermes3 (never stops)
            err_str = str(primary_err).lower()
            # 413 = provider rejected payload as too large — route to a different provider
            is_payload_too_large = any(k in err_str for k in (
                "413", "payload too large", "request entity too large", "request too large",
            ))
            is_retriable = is_payload_too_large or any(k in err_str for k in (
                "401", "429", "quota", "credit", "billing",
                "unauthorized", "rate limit", "timeout", "timedout",
                "connection", "connect", "eof", "broken pipe",
                # claude-cli specific: "You're out of extra usage · resets ..."
                "out of extra usage", "extra usage", "usage limit",
                "out of usage", "usage exceeded", "you're out",
                # anthropic api specific
                "overloaded", "capacity", "529",
            )) or type(primary_err).__name__ in (
                "TimeoutError", "asyncio.TimeoutError", "ConnectError",
                "ReadTimeout", "RemoteProtocolError",
            )

            if not is_retriable:
                raise

            # ── Score-based fallback chain ────────────────────────────────────
            # 1. Try best free model for role (score-ranked)
            # 2. If role unknown, use static fallback chain
            # Inject DNA into fallback free models for quality continuity

            tried_keys = {self.model_key}
            fallback_tried = False
            _last_err_str = str(primary_err).lower()

            # 413: exclude the failing provider — it rejected the payload size.
            # Retrying with another model from the same provider will produce the same error.
            _payload_reject_provider: str = self.config.provider if is_payload_too_large else ""

            # If role is known, build score-ranked fallback list
            if role:
                # Get all FREE models sorted by score for this role, excluding already tried
                from shared.model_router import MODELS as _MODELS, ModelTier as _MT
                from shared.model_router import _get_available_providers_cached
                available_providers = _get_available_providers_cached()
                free_candidates = [
                    (k, cfg, score_for_role(k, role))
                    for k, cfg in _MODELS.items()
                    if cfg.tier == _MT.FREE
                    and cfg.provider in available_providers
                    and k not in tried_keys
                    and cfg.provider != _payload_reject_provider
                ]
                free_candidates.sort(key=lambda x: x[2], reverse=True)
                # Append cheap models as last resort
                cheap_candidates = [
                    (k, cfg, score_for_role(k, role))
                    for k, cfg in _MODELS.items()
                    if cfg.tier == _MT.CHEAP
                    and cfg.provider in available_providers
                    and k not in tried_keys
                    and cfg.provider != _payload_reject_provider
                    and (cfg.provider != "openai" or os.getenv("OPENAI_API_KEY"))
                ]
                cheap_candidates.sort(key=lambda x: x[2], reverse=True)
                ranked_fallbacks = free_candidates + cheap_candidates
            else:
                # Static fallback when role is unknown — also exclude 413 provider
                ranked_fallbacks = [
                    ("claude-cli/claude-sonnet-4-6", MODELS.get("claude-cli/claude-sonnet-4-6"), 7),
                    ("openai/gpt-4o-mini",           MODELS.get("openai/gpt-4o-mini"),           6),
                    ("groq/llama-3.3-70b",           MODELS.get("groq/llama-3.3-70b"),           6),
                    ("ollama/hermes3",                MODELS.get("ollama/hermes3"),               2),
                ]
                ranked_fallbacks = [
                    (k, cfg, s) for k, cfg, s in ranked_fallbacks
                    if cfg and k not in tried_keys and cfg.provider != _payload_reject_provider
                ]

            for fb_key, fb_cfg, fb_score in ranked_fallbacks:
                if not fb_cfg:
                    continue
                tried_keys.add(fb_key)

                # Map provider to caller
                _caller_map = {
                    "claude-cli": self._call_claude_cli,
                    "anthropic":  self._call_anthropic,
                    "openai":     self._call_openai,
                    "groq":       self._call_groq,
                    "ollama":     self._call_ollama,
                }
                fb_caller = _caller_map.get(fb_cfg.provider)
                if not fb_caller:
                    continue

                # For free model fallbacks — inject DNA if available
                fb_system = effective_system
                if fb_cfg.tier.value == "free" and role and use_dna:
                    try:
                        from shared.dna_bootstrap import get_dna_bootstrap
                        fb_system = get_dna_bootstrap().build_dna_system_prompt(role, system_prompt)
                    except Exception:
                        pass

                try:
                    # Back off before each fallback attempt if the last error was a rate limit
                    if "429" in _last_err_str or "rate limit" in _last_err_str:
                        await asyncio.sleep(2)

                    print(f"[LLM] ⚠️  {self.model_key} failed "
                          f"({type(primary_err).__name__}: {str(primary_err)[:60] or 'no msg'}). "
                          f"Trying {fb_key} (score={fb_score}/10)...")
                    # Swap config so _call_* methods use the fallback model_id
                    _orig_config = self.config
                    self.config = fb_cfg
                    try:
                        response_text = await fb_caller(fb_system, user_message, max_tokens)
                    finally:
                        self.config = _orig_config
                    self.model_key = f"{fb_key} (fallback)"
                    fallback_tried = True
                    break
                except Exception as fb_err:
                    _last_err_str = str(fb_err).lower()
                    if "429" in _last_err_str or "rate limit" in _last_err_str:
                        await asyncio.sleep(2)
                    print(f"[LLM] ⚠️  {fb_key} also failed: {type(fb_err).__name__}: {str(fb_err)[:80]}")
                    continue

            if not fallback_tried:
                raise primary_err

        elapsed = time.time() - start

        # ── Auto save style ref for paid model calls ──────────
        if role and not is_free_model and use_dna:
            try:
                from shared.dna_bootstrap import get_dna_bootstrap
                get_dna_bootstrap().save_style_ref(role, response_text, self.model_key)
            except Exception:
                pass

        # ── Cost Tracking ──────────────────────────────────────
        input_tokens  = self._count_tokens(system_prompt + user_message)
        output_tokens = self._count_tokens(response_text)
        cost = self.config.estimate_cost(input_tokens, output_tokens)

        self.tracker.record(
            role=role,
            project_id=project_id,
            model_key=self.model_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            complexity_score=complexity_score,
            task_description=user_message[:100],
        )

        tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(self.config.tier, "")
        print(
            f"[LLM] {tier_emoji} {self.model_key} | "
            f"in={input_tokens} out={output_tokens} | "
            f"cost=${cost:.5f} | {elapsed:.1f}s"
        )

        return response_text

    # ─── Provider Implementations ──────────────────────────────────

    async def _call_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        """Anthropic Claude API"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model_id,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    async def _call_claude_cli(self, system: str, user: str, max_tokens: int) -> str:
        """Use the local `claude` CLI (Claude Code) — no API key needed."""
        import shutil
        claude_bin = shutil.which("claude") or os.path.expanduser("~/.npm-global/bin/claude")
        model = self.config.model_id if self.config else "claude-sonnet-4-6"
        full_prompt = f"{system}\n\n---\n\n{user}" if system else user
        # Strip ANTHROPIC_API_KEY so the CLI uses its own stored OAuth credentials
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        proc = await asyncio.create_subprocess_exec(
            claude_bin, "--print", "--model", model,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()), timeout=600
        )
        if proc.returncode != 0:
            # Combine stdout+stderr so the error message is always captured
            err = (stdout.decode().strip() + " " + stderr.decode().strip()).strip()[:400]
            raise RuntimeError(f"claude CLI error: {err}")
        return stdout.decode().strip()

    async def _call_openai(self, system: str, user: str, max_tokens: int) -> str:
        """OpenAI API (GPT-4o, GPT-4o-mini)"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model_id,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _call_groq(self, system: str, user: str, max_tokens: int) -> str:
        """Groq API — supports Llama3, Qwen3, Llama4 Scout (Free Tier)"""
        # Pre-flight size guard: check before API key so routing kicks in immediately
        total_chars = len(system) + len(user)
        if total_chars > GROQ_MAX_PAYLOAD_CHARS:
            raise ValueError(
                f"413 Payload too large for Groq: {total_chars} chars "
                f"(limit ~{GROQ_MAX_PAYLOAD_CHARS}) — re-routing to non-Groq model"
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        model_id = self.config.model_id
        payload: dict = {
            "model":      model_id,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.7,
        }

        # Qwen3 supports reasoning_effort — disable thinking for speed/cost
        # (thinking mode adds <think>...</think> tokens we don't need)
        if "qwen3" in model_id.lower():
            payload["reasoning_effort"] = "none"

        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            # Strip residual <think>...</think> blocks if reasoning leaked through
            import re as _re
            content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()
            return content

    async def _call_ollama(self, system: str, user: str, max_tokens: int) -> str:
        """Ollama Local LLM — ฟรี 100%"""
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        async with httpx.AsyncClient(timeout=300) as client:  # local อาจช้า
            r = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": self.config.model_id,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    },
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

    def _count_tokens(self, text: str) -> int:
        """นับ tokens แบบ approximate"""
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4  # rough fallback: 1 token ≈ 4 chars


# ─── Factory Function ─────────────────────────────────────────────

def create_client_for_role(
    role: str,
    prompt: str,
    project_id: str = "",
    force_tier: Optional[ModelTier] = None,
    task_type: Optional[TaskType] = None,
    system_prompt: str = "",
) -> tuple["LLMClient", int]:
    """
    สร้าง LLMClient ที่เหมาะสมสำหรับ role + prompt นี้
    ผ่าน ModelRouter อัตโนมัติ

    task_type   — ระบุประเภทงาน เช่น code_generation, reasoning, status
    system_prompt — ส่งมาเพื่อ token count จริง (context fit check)

    Returns: (LLMClient, complexity_score)
    """
    router = get_router()
    full_context = (system_prompt + "\n\n" + prompt).strip() if system_prompt else prompt
    config, key, complexity = router.route(
        prompt, role, project_id, force_tier,
        task_type=task_type,
        full_context=full_context,
    )
    client = LLMClient(model_config=config, model_key=key)
    return client, complexity
