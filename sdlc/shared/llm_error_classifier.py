"""
LLM Error Classifier — provider-agnostic quota/rate/context/auth/timeout detection.

classify_llm_error(exc_or_message) → LLMErrorInfo

Error categories (pause_reason values):
  quota_exceeded          — daily/monthly quota depleted
  rate_limited            — per-minute request or token rate limit hit
  context_limit_exceeded  — prompt too long for model
  provider_unavailable    — 5xx, overloaded, capacity, connection reset
  auth_error              — 401/403, invalid key, unauthorized
  timeout                 — request timed out
  unknown_llm_error       — retriable but unclassified

Non-recoverable:
  auth_error → resume_policy="manual_token_fix"  (human must rotate key)

All others → resume_policy="auto" (recovery worker will requeue after cooldown)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─── Result type ─────────────────────────────────────────────────────────────

@dataclass
class LLMErrorInfo:
    is_quota_error: bool       # True → task should pause, not fail
    error_type: str            # quota_exceeded | rate_limited | context_limit_exceeded |
                               # provider_unavailable | auth_error | timeout | unknown_llm_error
                               # or "transient" (not quota-related, normal retry)
    http_status: int           # 0 if not HTTP
    retry_after_seconds: int   # hint from Retry-After header or heuristic default
    resume_policy: str         # "auto" | "manual_token_fix"
    provider_hint: str         # detected provider name or "" if unknown
    raw_message: str           # truncated original error message

    @property
    def should_pause(self) -> bool:
        """True iff the task should be paused rather than retried immediately."""
        return self.is_quota_error

    @property
    def is_manual(self) -> bool:
        return self.resume_policy == "manual_token_fix"


# ─── Classification tables ────────────────────────────────────────────────────

# (pattern, error_type, resume_policy, retry_after_seconds)
_RULES: list[tuple[str, str, str, int]] = [
    # ── Auth — manual fix required ──────────────────────────────────────────
    (r"\b(401|403|unauthorized|invalid.?api.?key|authentication.?fail|invalid.?key|"
     r"bad.?credentials|permission.?denied|forbidden)\b",
     "auth_error", "manual_token_fix", 3600),

    # ── Quota exhausted ─────────────────────────────────────────────────────
    (r"\b(quota.?exceeded|daily.?quota|monthly.?quota|usage.?limit|"
     r"credit.?exhausted|out.?of.?credit|billing|"
     r"out.?of.?(extra.?)?usage|usage.?exceeded|"
     r"you.?re.?out|extra.?usage)\b",
     "quota_exceeded", "auto", 3600),

    # ── Rate limit ───────────────────────────────────────────────────────────
    (r"\b(429|rate.?limit|too.?many.?requests?|requests?.?per.?(minute|second|day)|"
     r"tpm|rpm|rph|rps|tokens.?per.?minute|throughput.?limit)\b",
     "rate_limited", "auto", 60),

    # ── Context / token limit ────────────────────────────────────────────────
    (r"\b(context.?(window|length|limit)|maximum.?context|prompt.?too.?long|"
     r"exceeds.?max.?(token|length)|input.?too.?long|max.?token|"
     r"context.?overflow|too.?many.?tokens)\b",
     "context_limit_exceeded", "auto", 0),

    # ── Provider overloaded / capacity ──────────────────────────────────────
    (r"\b(529|overloaded|capacity|server.?error|service.?unavailable|"
     r"503|502|500|internal.?server|bad.?gateway|"
     r"connection.?reset|connection.?error|eof.?error|broken.?pipe|"
     r"connect.?error|network.?error|provider.?unavailable)\b",
     "provider_unavailable", "auto", 120),

    # ── Timeout ──────────────────────────────────────────────────────────────
    (r"\b(timeout|timed.?out|read.?timeout|connect.?timeout|request.?timeout)\b",
     "timeout", "auto", 60),
]

# Compiled once
_COMPILED_RULES: list[tuple[re.Pattern, str, str, int]] = [
    (re.compile(pattern, re.IGNORECASE), etype, policy, retry_s)
    for pattern, etype, policy, retry_s in _RULES
]

# Provider name hints
_PROVIDER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(anthropic|claude)\b", re.I), "anthropic"),
    (re.compile(r"\b(openai|gpt)\b",       re.I), "openai"),
    (re.compile(r"\b(groq)\b",             re.I), "groq"),
    (re.compile(r"\b(ollama)\b",           re.I), "ollama"),
    (re.compile(r"\b(google|gemini)\b",    re.I), "google"),
    (re.compile(r"\b(cohere)\b",           re.I), "cohere"),
    (re.compile(r"\b(mistral)\b",          re.I), "mistral"),
]

# Exception class names that map directly to a type
_EXCEPTION_NAME_RULES: dict[str, tuple[str, str, int]] = {
    "TimeoutError":               ("timeout",              "auto", 60),
    "ReadTimeout":                ("timeout",              "auto", 60),
    "ConnectTimeout":             ("timeout",              "auto", 60),
    "ConnectError":               ("provider_unavailable", "auto", 120),
    "RemoteProtocolError":        ("provider_unavailable", "auto", 120),
    "AuthenticationError":        ("auth_error",           "manual_token_fix", 3600),
    "PermissionDeniedError":      ("auth_error",           "manual_token_fix", 3600),
    "RateLimitError":             ("rate_limited",         "auto", 60),
    "APIStatusError":             ("provider_unavailable", "auto", 120),
    "OverloadedError":            ("provider_unavailable", "auto", 120),
    "InternalServerError":        ("provider_unavailable", "auto", 120),
}


def _extract_retry_after(msg: str) -> Optional[int]:
    """Parse 'retry after N seconds' or 'Retry-After: N' from error message."""
    m = re.search(
        r"(?:retry.?after|retry_after|wait)\D*?(\d+)\s*s(?:ec(?:ond)?s?)?",
        msg, re.IGNORECASE,
    )
    if m:
        return int(m.group(1))
    m = re.search(r"retry.?after:\s*(\d+)", msg, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _detect_provider(msg: str) -> str:
    for pattern, name in _PROVIDER_PATTERNS:
        if pattern.search(msg):
            return name
    return ""


def classify_llm_error(exc_or_message) -> LLMErrorInfo:
    """
    Classify an LLM error as quota/rate/context/auth/timeout/provider/transient.

    Parameters
    ----------
    exc_or_message : Exception or str
        The exception raised during an LLM call, or its string representation.

    Returns
    -------
    LLMErrorInfo
        is_quota_error=True means the task should pause (not count as task failure).
    """
    if isinstance(exc_or_message, BaseException):
        exc_name = type(exc_or_message).__name__
        msg = str(exc_or_message)
    else:
        exc_name = ""
        msg = str(exc_or_message)

    raw = (msg or "")[:500]
    msg_lower = (exc_name + " " + msg).lower()

    # ── HTTP status code extraction ──────────────────────────────────────────
    http_status = 0
    m = re.search(r"\b(4\d{2}|5\d{2})\b", msg)
    if m:
        http_status = int(m.group(1))

    # ── Exception class name fast path ───────────────────────────────────────
    for exc_class, (etype, policy, default_retry) in _EXCEPTION_NAME_RULES.items():
        if exc_name == exc_class:
            retry_s = _extract_retry_after(msg) or default_retry
            return LLMErrorInfo(
                is_quota_error=True,
                error_type=etype,
                http_status=http_status,
                retry_after_seconds=retry_s,
                resume_policy=policy,
                provider_hint=_detect_provider(msg_lower),
                raw_message=raw,
            )

    # ── Pattern-based matching ────────────────────────────────────────────────
    for pattern, etype, policy, default_retry in _COMPILED_RULES:
        if pattern.search(msg_lower):
            retry_s = _extract_retry_after(msg) or default_retry
            return LLMErrorInfo(
                is_quota_error=True,
                error_type=etype,
                http_status=http_status,
                retry_after_seconds=retry_s,
                resume_policy=policy,
                provider_hint=_detect_provider(msg_lower),
                raw_message=raw,
            )

    # ── Transient / not quota-related ────────────────────────────────────────
    return LLMErrorInfo(
        is_quota_error=False,
        error_type="transient",
        http_status=http_status,
        retry_after_seconds=0,
        resume_policy="auto",
        provider_hint=_detect_provider(msg_lower),
        raw_message=raw,
    )
