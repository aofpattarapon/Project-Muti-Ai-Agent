"""
Phase 8.0 Tests — LLM Error Classifier + DB Pause Schema + Storage API

Covers:
  - quota_exceeded classification (daily/monthly/extra usage/billing)
  - rate_limited with retry_after hint
  - context_limit_exceeded
  - auth_error → manual_token_fix resume policy
  - provider_unavailable (5xx/connection/overloaded)
  - timeout (class name + string)
  - transient errors NOT classified as quota
  - exception class name fast path
  - provider hint detection
  - retry_after_seconds extraction from message
  - pause_sdlc_task_for_provider writes all fields + clears claim
  - paused task does NOT appear in pending list
  - list_paused_sdlc_tasks respects retry_after_at threshold
  - manual_token_fix tasks excluded from auto-resume list
  - resume_paused_sdlc_task clears all pause fields → pending
  - resume only acts on paused tasks (idempotent for non-paused)
  - set_provider_cooldown upserts (later deadline wins)
  - get_active_provider_cooldowns filters by now
  - clear_provider_cooldown by provider+model and by provider only

Run: python3 sdlc/tests/test_phase8_classifier_db.py
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.llm_error_classifier import classify_llm_error, LLMErrorInfo


def _future(seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()


# ─── LLM Error Classifier ────────────────────────────────────────────────────

class TestQuotaExceeded(unittest.TestCase):

    def test_daily_quota_string(self):
        r = classify_llm_error("Error 429: daily quota exceeded")
        self.assertEqual(r.error_type, "quota_exceeded")
        self.assertTrue(r.is_quota_error)

    def test_monthly_quota_string(self):
        r = classify_llm_error("monthly quota reached for account")
        self.assertEqual(r.error_type, "quota_exceeded")

    def test_out_of_extra_usage_claude_cli(self):
        r = classify_llm_error("You're out of extra usage · resets in 3 hours")
        self.assertEqual(r.error_type, "quota_exceeded")
        self.assertTrue(r.should_pause)

    def test_credit_exhausted(self):
        r = classify_llm_error("credit exhausted — please top up billing")
        self.assertEqual(r.error_type, "quota_exceeded")

    def test_usage_limit(self):
        r = classify_llm_error("usage limit reached for this period")
        self.assertEqual(r.error_type, "quota_exceeded")

    def test_billing_string(self):
        r = classify_llm_error("billing issue: account suspended")
        self.assertEqual(r.error_type, "quota_exceeded")

    def test_resume_policy_is_auto(self):
        r = classify_llm_error("quota exceeded")
        self.assertEqual(r.resume_policy, "auto")
        self.assertFalse(r.is_manual)


class TestRateLimited(unittest.TestCase):

    def test_429_status(self):
        r = classify_llm_error("HTTP 429: too many requests")
        self.assertEqual(r.error_type, "rate_limited")
        self.assertTrue(r.is_quota_error)

    def test_rate_limit_string(self):
        r = classify_llm_error("rate limit exceeded, retry after 30 seconds")
        self.assertEqual(r.error_type, "rate_limited")

    def test_retry_after_extracted(self):
        r = classify_llm_error("429 rate limit: retry after 45 seconds")
        self.assertEqual(r.error_type, "rate_limited")
        self.assertEqual(r.retry_after_seconds, 45)

    def test_tpm_rpm_limit(self):
        r = classify_llm_error("TPM limit hit for this model tier")
        self.assertEqual(r.error_type, "rate_limited")

    def test_requests_per_minute(self):
        r = classify_llm_error("Too many requests per minute (rpm)")
        self.assertEqual(r.error_type, "rate_limited")

    def test_default_retry_60s(self):
        r = classify_llm_error("rate limit")
        self.assertEqual(r.retry_after_seconds, 60)


class TestContextLimit(unittest.TestCase):

    def test_context_window_string(self):
        r = classify_llm_error("context window exceeded: 128k tokens")
        self.assertEqual(r.error_type, "context_limit_exceeded")
        self.assertTrue(r.is_quota_error)

    def test_prompt_too_long(self):
        r = classify_llm_error("prompt too long for this model")
        self.assertEqual(r.error_type, "context_limit_exceeded")

    def test_exceeds_max_tokens(self):
        r = classify_llm_error("input exceeds max token limit")
        self.assertEqual(r.error_type, "context_limit_exceeded")

    def test_retry_after_is_zero(self):
        r = classify_llm_error("context limit exceeded")
        self.assertEqual(r.retry_after_seconds, 0)


class TestAuthError(unittest.TestCase):

    def test_401_string(self):
        r = classify_llm_error("HTTP 401: unauthorized")
        self.assertEqual(r.error_type, "auth_error")
        self.assertTrue(r.is_quota_error)

    def test_invalid_api_key(self):
        r = classify_llm_error("Invalid API key provided")
        self.assertEqual(r.error_type, "auth_error")

    def test_resume_policy_manual(self):
        r = classify_llm_error("authentication failed: bad credentials")
        self.assertEqual(r.resume_policy, "manual_token_fix")
        self.assertTrue(r.is_manual)

    def test_403_forbidden(self):
        r = classify_llm_error("403 Forbidden")
        self.assertEqual(r.error_type, "auth_error")


class TestProviderUnavailable(unittest.TestCase):

    def test_503_string(self):
        r = classify_llm_error("503 Service Unavailable")
        self.assertEqual(r.error_type, "provider_unavailable")
        self.assertTrue(r.is_quota_error)

    def test_overloaded(self):
        r = classify_llm_error("Model is currently overloaded. Please try again.")
        self.assertEqual(r.error_type, "provider_unavailable")

    def test_529_anthropic(self):
        r = classify_llm_error("529: API capacity exceeded")
        self.assertEqual(r.error_type, "provider_unavailable")

    def test_connection_reset(self):
        r = classify_llm_error("connection reset by peer")
        self.assertEqual(r.error_type, "provider_unavailable")

    def test_eof_error(self):
        r = classify_llm_error("EOFError: eof error on connection")
        self.assertEqual(r.error_type, "provider_unavailable")

    def test_default_retry_120s(self):
        r = classify_llm_error("server error 500")
        self.assertEqual(r.retry_after_seconds, 120)


class TestTimeout(unittest.TestCase):

    def test_timeout_string(self):
        r = classify_llm_error("request timed out after 120s")
        self.assertEqual(r.error_type, "timeout")
        self.assertTrue(r.is_quota_error)

    def test_read_timeout(self):
        r = classify_llm_error("ReadTimeout: server did not respond")
        self.assertEqual(r.error_type, "timeout")

    def test_timeout_exception_class(self):
        exc = TimeoutError("operation timed out")
        r = classify_llm_error(exc)
        self.assertEqual(r.error_type, "timeout")

    def test_connect_timeout(self):
        r = classify_llm_error("connect timeout while connecting to api.anthropic.com")
        self.assertEqual(r.error_type, "timeout")


class TestTransient(unittest.TestCase):

    def test_value_error_not_quota(self):
        r = classify_llm_error(ValueError("bad output format"))
        self.assertFalse(r.is_quota_error)
        self.assertEqual(r.error_type, "transient")

    def test_generic_string_not_quota(self):
        r = classify_llm_error("JSON decode error in response")
        self.assertFalse(r.is_quota_error)
        self.assertEqual(r.error_type, "transient")

    def test_unknown_string(self):
        r = classify_llm_error("something completely unexpected happened")
        self.assertFalse(r.should_pause)


class TestExceptionClassNameFastPath(unittest.TestCase):

    def _make_exc(self, cls_name: str, msg: str = "error"):
        exc_type = type(cls_name, (Exception,), {})
        return exc_type(msg)

    def test_rate_limit_error_class(self):
        exc = self._make_exc("RateLimitError", "rate limit hit")
        r = classify_llm_error(exc)
        self.assertEqual(r.error_type, "rate_limited")

    def test_authentication_error_class(self):
        exc = self._make_exc("AuthenticationError", "invalid key")
        r = classify_llm_error(exc)
        self.assertEqual(r.error_type, "auth_error")
        self.assertEqual(r.resume_policy, "manual_token_fix")

    def test_overloaded_error_class(self):
        exc = self._make_exc("OverloadedError", "model is busy")
        r = classify_llm_error(exc)
        self.assertEqual(r.error_type, "provider_unavailable")

    def test_connect_error_class(self):
        exc = self._make_exc("ConnectError", "connection refused")
        r = classify_llm_error(exc)
        self.assertEqual(r.error_type, "provider_unavailable")


class TestProviderHintDetection(unittest.TestCase):

    def test_anthropic_hint(self):
        r = classify_llm_error("anthropic: 429 rate limit")
        self.assertEqual(r.provider_hint, "anthropic")

    def test_openai_hint(self):
        r = classify_llm_error("openai quota exceeded")
        self.assertEqual(r.provider_hint, "openai")

    def test_groq_hint(self):
        r = classify_llm_error("groq rate limit hit")
        self.assertEqual(r.provider_hint, "groq")

    def test_no_hint(self):
        r = classify_llm_error("rate limit")
        self.assertEqual(r.provider_hint, "")


class TestRetryAfterExtraction(unittest.TestCase):

    def test_retry_after_seconds(self):
        r = classify_llm_error("rate limit: retry after 120 seconds")
        self.assertEqual(r.retry_after_seconds, 120)

    def test_retry_after_header_format(self):
        r = classify_llm_error("429 Retry-After: 30 rate limit")
        self.assertEqual(r.retry_after_seconds, 30)

    def test_wait_n_seconds(self):
        r = classify_llm_error("Too many requests. Wait 90 secs before retrying.")
        self.assertEqual(r.retry_after_seconds, 90)

    def test_no_retry_hint_uses_default(self):
        r = classify_llm_error("429 rate limit")
        self.assertEqual(r.retry_after_seconds, 60)  # default for rate_limited


# ─── Storage DB Pause Methods ────────────────────────────────────────────────

class StorageTestBase(unittest.TestCase):
    """Mixin providing a temp-db Storage instance."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self._tmpdir.name, "data", "test.db")
        from shared.storage import Storage
        self.storage = Storage(db_path=db_path)
        self._insert_task("task-001", "pending")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _insert_task(self, task_id: str, status: str = "pending", attempt_count: int = 0):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "status, attempt_count, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, "proj1", "epic1", 1, "dev", "backend_code", "out.md",
                 status, attempt_count, now, now),
            )
            conn.execute(
                "UPDATE sdlc_tasks SET claimed_at=?, claimed_by='dev' WHERE id=?",
                (now, task_id),
            )
            conn.commit()


class TestPauseSdlcTask(StorageTestBase):

    def test_pause_sets_status_paused(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "anthropic", "claude-sonnet-4-6",
            retry_after_at=_future(60),
        )
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.status, "paused")

    def test_pause_sets_all_fields(self):
        ra = _future(3600)
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "openai", "gpt-4o",
            retry_after_at=ra, error="daily quota hit", resume_policy="auto",
        )
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.pause_reason, "quota_exceeded")
        self.assertEqual(task.pause_provider, "openai")
        self.assertEqual(task.pause_model, "gpt-4o")
        self.assertEqual(task.retry_after_at, ra)
        self.assertEqual(task.last_error, "daily quota hit")
        self.assertEqual(task.resume_policy, "auto")
        self.assertNotEqual(task.paused_at, "")

    def test_pause_clears_claim(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama-3.3-70b",
            retry_after_at=_future(60),
        )
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.claimed_at, "")
        self.assertEqual(task.claimed_by, "")

    def test_paused_task_not_returned_as_pending(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "anthropic", "claude-sonnet-4-6",
            retry_after_at=_future(3600),
        )
        # Pending tasks poll — paused tasks must not appear
        with sqlite3.connect(self.storage.db_path) as conn:
            rows = conn.execute(
                "SELECT id FROM sdlc_tasks WHERE role='dev' AND status='pending'"
            ).fetchall()
        self.assertFalse(any(r[0] == "task-001" for r in rows))


class TestListPausedTasks(StorageTestBase):

    def test_ready_tasks_returned(self):
        """retry_after_at in the past → task is ready to resume."""
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama",
            retry_after_at=_past(10),
        )
        now = datetime.utcnow().isoformat()
        tasks = self.storage.list_paused_sdlc_tasks(now)
        self.assertTrue(any(t.id == "task-001" for t in tasks))

    def test_not_yet_ready_excluded(self):
        """retry_after_at in the future → not returned."""
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "anthropic", "claude",
            retry_after_at=_future(3600),
        )
        now = datetime.utcnow().isoformat()
        tasks = self.storage.list_paused_sdlc_tasks(now)
        self.assertFalse(any(t.id == "task-001" for t in tasks))

    def test_manual_token_fix_excluded_from_auto_resume(self):
        """manual_token_fix tasks are never auto-resumed."""
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "auth_error", "anthropic", "claude",
            retry_after_at=_past(10), resume_policy="manual_token_fix",
        )
        now = datetime.utcnow().isoformat()
        tasks = self.storage.list_paused_sdlc_tasks(now)
        self.assertFalse(any(t.id == "task-001" for t in tasks))

    def test_empty_retry_after_always_returned(self):
        """Empty retry_after_at (no deadline) → always ready."""
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "provider_unavailable", "ollama", "hermes3",
            retry_after_at="",
        )
        now = datetime.utcnow().isoformat()
        tasks = self.storage.list_paused_sdlc_tasks(now)
        self.assertTrue(any(t.id == "task-001" for t in tasks))


class TestResumePausedTask(StorageTestBase):

    def test_resume_sets_pending(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama",
            retry_after_at=_past(10),
        )
        self.storage.resume_paused_sdlc_task("task-001")
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.status, "pending")

    def test_resume_clears_pause_fields(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "openai", "gpt-4o",
            retry_after_at=_past(10), resume_policy="auto",
        )
        self.storage.resume_paused_sdlc_task("task-001")
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.pause_reason, "")
        self.assertEqual(task.pause_provider, "")
        self.assertEqual(task.pause_model, "")
        self.assertEqual(task.retry_after_at, "")
        self.assertEqual(task.paused_at, "")
        self.assertEqual(task.resume_policy, "")

    def test_resume_clears_claim_fields(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama",
            retry_after_at=_past(10),
        )
        self.storage.resume_paused_sdlc_task("task-001")
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.claimed_at, "")
        self.assertEqual(task.claimed_by, "")

    def test_resume_only_affects_paused_tasks(self):
        """Calling resume on a pending task is a no-op (already pending)."""
        # task-001 is pending (not paused) — resume should not change anything
        self.storage.resume_paused_sdlc_task("task-001")
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.status, "pending")  # unchanged

    def test_resume_nonexistent_task_no_error(self):
        """Resuming a non-existent task ID should not raise."""
        try:
            self.storage.resume_paused_sdlc_task("nonexistent-task")
        except Exception as e:
            self.fail(f"resume_paused_sdlc_task raised unexpectedly: {e}")


# ─── Provider Cooldown ────────────────────────────────────────────────────────

class TestProviderCooldown(StorageTestBase):

    def test_set_and_get_cooldown(self):
        ra = _future(3600)
        self.storage.set_provider_cooldown("anthropic", "claude-sonnet-4-6", "quota_exceeded", ra)
        cooldowns = self.storage.get_active_provider_cooldowns()
        self.assertTrue(any(
            c["provider"] == "anthropic" and c["model"] == "claude-sonnet-4-6"
            for c in cooldowns
        ))

    def test_expired_cooldown_not_returned(self):
        self.storage.set_provider_cooldown("groq", "llama", "rate_limited", _past(10))
        cooldowns = self.storage.get_active_provider_cooldowns()
        self.assertFalse(any(c["provider"] == "groq" for c in cooldowns))

    def test_upsert_later_deadline_wins(self):
        earlier = _future(60)
        later = _future(3600)
        self.storage.set_provider_cooldown("openai", "gpt-4o", "quota_exceeded", earlier)
        self.storage.set_provider_cooldown("openai", "gpt-4o", "quota_exceeded", later)
        cooldowns = self.storage.get_active_provider_cooldowns()
        rec = next(c for c in cooldowns if c["provider"] == "openai")
        self.assertEqual(rec["retry_after_at"], later)

    def test_upsert_earlier_deadline_does_not_override(self):
        later = _future(3600)
        earlier = _future(60)
        self.storage.set_provider_cooldown("openai", "gpt-4o-mini", "quota_exceeded", later)
        self.storage.set_provider_cooldown("openai", "gpt-4o-mini", "quota_exceeded", earlier)
        cooldowns = self.storage.get_active_provider_cooldowns()
        rec = next(c for c in cooldowns if c["model"] == "gpt-4o-mini")
        self.assertEqual(rec["retry_after_at"], later)  # later remains

    def test_clear_cooldown_by_provider_and_model(self):
        self.storage.set_provider_cooldown("anthropic", "haiku", "rate_limited", _future(3600))
        self.storage.clear_provider_cooldown("anthropic", "haiku")
        cooldowns = self.storage.get_active_provider_cooldowns()
        self.assertFalse(any(c["provider"] == "anthropic" and c["model"] == "haiku" for c in cooldowns))

    def test_clear_cooldown_by_provider_only(self):
        self.storage.set_provider_cooldown("groq", "model-a", "rate_limited", _future(3600))
        self.storage.set_provider_cooldown("groq", "model-b", "rate_limited", _future(3600))
        self.storage.clear_provider_cooldown("groq")
        cooldowns = self.storage.get_active_provider_cooldowns()
        self.assertFalse(any(c["provider"] == "groq" for c in cooldowns))

    def test_multiple_providers_independent(self):
        self.storage.set_provider_cooldown("anthropic", "", "quota_exceeded", _future(3600))
        self.storage.set_provider_cooldown("openai", "", "rate_limited", _future(1800))
        cooldowns = self.storage.get_active_provider_cooldowns()
        providers = {c["provider"] for c in cooldowns}
        self.assertIn("anthropic", providers)
        self.assertIn("openai", providers)

    def test_cooldown_fields_stored_correctly(self):
        ra = _future(120)
        self.storage.set_provider_cooldown("groq", "llama-3.3-70b", "rate_limited", ra)
        cooldowns = self.storage.get_active_provider_cooldowns()
        rec = next(c for c in cooldowns if c["provider"] == "groq")
        self.assertEqual(rec["reason"], "rate_limited")
        self.assertEqual(rec["retry_after_at"], ra)


if __name__ == "__main__":
    unittest.main(verbosity=2)
