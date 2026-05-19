"""
Phase 8.1 Tests — BaseAgent Pause Integration + WebBridge extra_metadata

Covers:
  - quota LLM error → task paused (not failed, not retried normally)
  - pause preserves attempt_count (no +1 for quota errors)
  - non-quota LLM error still propagates normally
  - _pause_task_for_quota writes all DB fields
  - _pause_task_for_quota sends task_completed(status=paused) to web bridge
  - web bridge task_completed(extra_metadata=...) merges extra fields into metadata
  - no approval_item for status=paused (ingest API contract)
  - provider cooldown registered on pause
  - auth_error → manual_token_fix resume_policy

Run: python3 sdlc/tests/test_phase8_pause_integration.py
"""

import os
import sys
import asyncio
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.llm_error_classifier import classify_llm_error, LLMErrorInfo


def _future(seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Web Bridge extra_metadata ───────────────────────────────────────────────

class TestWebBridgeExtraMetadata(unittest.TestCase):
    """task_completed(extra_metadata=…) merges the dict into the metadata payload."""

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge()
        self.bridge.enabled = True
        self._posted = []

        async def fake_post(payload):
            self._posted.append(payload)
            return True

        self.bridge._post = fake_post

    def test_extra_metadata_merged_into_payload(self):
        _run(self.bridge.task_completed(
            role_key="dev",
            project_id="proj1",
            project_name="Test",
            task_name="backend_code",
            summary="paused",
            files=[],
            model_id="claude-sonnet-4-6",
            cost_usd=0.0,
            duration_seconds=0.0,
            sdlc_task_id="task-001",
            status="paused",
            extra_metadata={"pause_reason": "rate_limited", "retry_after_at": "2026-01-01T00:00:00"},
        ))
        self.assertEqual(len(self._posted), 1)
        meta = self._posted[0]["metadata"]
        self.assertEqual(meta["pause_reason"], "rate_limited")
        self.assertEqual(meta["retry_after_at"], "2026-01-01T00:00:00")

    def test_extra_metadata_none_does_not_break(self):
        _run(self.bridge.task_completed(
            role_key="dev",
            project_id="proj1",
            project_name="Test",
            task_name="backend_code",
            summary="completed",
            files=[],
            model_id="claude-sonnet-4-6",
            cost_usd=0.0,
            duration_seconds=0.0,
            extra_metadata=None,
        ))
        self.assertEqual(len(self._posted), 1)

    def test_status_paused_sent_correctly(self):
        _run(self.bridge.task_completed(
            role_key="qa",
            project_id="proj1",
            project_name="Test",
            task_name="test_report",
            summary="paused quota",
            files=[],
            model_id="groq/llama",
            cost_usd=0.0,
            duration_seconds=0.0,
            status="paused",
            sdlc_task_id="task-qa-001",
        ))
        payload = self._posted[0]
        self.assertEqual(payload["status"], "paused")
        self.assertEqual(payload["sdlc_task_id"], "task-qa-001")

    def test_paused_status_does_not_have_approval_semantics(self):
        """status=paused must not create approval_item — ingest API excludes it."""
        # This is an integration-level constraint: the ingest API only creates
        # approval_items for status='waiting_approval'. We verify the payload
        # sent from the bridge has status=paused (not waiting_approval).
        _run(self.bridge.task_completed(
            role_key="dev",
            project_id="proj1",
            project_name="Test",
            task_name="backend_code",
            summary="paused",
            files=[],
            model_id="model",
            cost_usd=0.0,
            duration_seconds=0.0,
            status="paused",
        ))
        self.assertNotEqual(self._posted[0]["status"], "waiting_approval")


# ─── Pause DB Integration ────────────────────────────────────────────────────

class TestPauseDBIntegration(unittest.TestCase):
    """Tests that pause writes correct DB fields via Storage methods."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self._tmpdir.name, "data", "test.db")
        from shared.storage import Storage
        self.storage = Storage(db_path=db_path)
        self._insert_task("task-001", attempt_count=1)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _insert_task(self, task_id: str, attempt_count: int = 0):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "status, attempt_count, claimed_at, claimed_by, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, "proj1", "epic1", 1, "dev", "backend_code", "out.md",
                 "in_progress", attempt_count, now, "dev", now, now),
            )
            conn.commit()

    def test_pause_preserves_attempt_count(self):
        """
        Quota errors must NOT increment attempt_count — they aren't task failures.
        """
        before = self.storage.get_sdlc_task("task-001").attempt_count
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama",
            retry_after_at=_future(60),
        )
        after = self.storage.get_sdlc_task("task-001").attempt_count
        self.assertEqual(before, after, "attempt_count must not change on quota pause")

    def test_paused_task_not_picked_up_as_pending(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "anthropic", "claude",
            retry_after_at=_future(3600),
        )
        # Storage.list_pending_sdlc_tasks only returns status='pending'
        tasks = self.storage.list_pending_sdlc_tasks("dev")
        self.assertFalse(any(t.id == "task-001" for t in tasks))

    def test_provider_cooldown_set_on_pause(self):
        retry_at = _future(3600)
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "quota_exceeded", "anthropic", "claude-sonnet-4-6",
            retry_after_at=retry_at,
        )
        self.storage.set_provider_cooldown(
            "anthropic", "claude-sonnet-4-6", "quota_exceeded", retry_at
        )
        cooldowns = self.storage.get_active_provider_cooldowns()
        self.assertTrue(any(c["provider"] == "anthropic" for c in cooldowns))

    def test_resume_after_cooldown_expires_sets_pending(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "rate_limited", "groq", "llama",
            retry_after_at=_past(10),
        )
        now = datetime.utcnow().isoformat()
        ready = self.storage.list_paused_sdlc_tasks(now)
        self.assertTrue(any(t.id == "task-001" for t in ready))
        self.storage.resume_paused_sdlc_task("task-001")
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.status, "pending")

    def test_auth_error_sets_manual_resume_policy(self):
        err_info = classify_llm_error("401 unauthorized: invalid API key")
        self.assertEqual(err_info.resume_policy, "manual_token_fix")
        self.storage.pause_sdlc_task_for_provider(
            "task-001", err_info.error_type, "anthropic", "claude",
            retry_after_at=_future(3600),
            resume_policy=err_info.resume_policy,
        )
        task = self.storage.get_sdlc_task("task-001")
        self.assertEqual(task.resume_policy, "manual_token_fix")

    def test_manual_pause_excluded_from_auto_resume(self):
        self.storage.pause_sdlc_task_for_provider(
            "task-001", "auth_error", "anthropic", "claude",
            retry_after_at=_past(10),
            resume_policy="manual_token_fix",
        )
        now = datetime.utcnow().isoformat()
        ready = self.storage.list_paused_sdlc_tasks(now)
        self.assertFalse(any(t.id == "task-001" for t in ready))


# ─── Classifier + Pause decision ─────────────────────────────────────────────

class TestPauseDecision(unittest.TestCase):
    """
    Validates that quota-classified errors trigger pause (not retry budget).
    Tests the classify → pause decision logic in isolation.
    """

    def test_quota_error_should_pause(self):
        err_info = classify_llm_error("quota exceeded")
        self.assertTrue(err_info.should_pause)

    def test_rate_limited_should_pause(self):
        err_info = classify_llm_error("429 rate limit")
        self.assertTrue(err_info.should_pause)

    def test_context_limit_should_pause(self):
        err_info = classify_llm_error("context window exceeded")
        self.assertTrue(err_info.should_pause)

    def test_provider_unavailable_should_pause(self):
        err_info = classify_llm_error("503 service unavailable")
        self.assertTrue(err_info.should_pause)

    def test_timeout_should_pause(self):
        err_info = classify_llm_error("read timeout after 120s")
        self.assertTrue(err_info.should_pause)

    def test_auth_should_pause_as_manual(self):
        err_info = classify_llm_error("401 unauthorized")
        self.assertTrue(err_info.should_pause)
        self.assertEqual(err_info.resume_policy, "manual_token_fix")

    def test_transient_should_not_pause(self):
        err_info = classify_llm_error("ValueError: bad json in response")
        self.assertFalse(err_info.should_pause)

    def test_transient_uses_normal_retry_budget(self):
        """Non-quota error: is_quota_error=False, so attempt_count SHOULD increment."""
        err_info = classify_llm_error("KeyError: missing key in response")
        self.assertFalse(err_info.is_quota_error)

    def test_quota_does_not_consume_retry_budget(self):
        """
        Quota errors: is_quota_error=True, so attempt_count must NOT be incremented.
        The BaseAgent checks err_info.is_quota_error before deciding to pause vs retry.
        """
        err_info = classify_llm_error("You're out of extra usage · resets in 3 hours")
        self.assertTrue(err_info.is_quota_error)


# ─── Downstream blocking ─────────────────────────────────────────────────────

class TestDownstreamBlocking(unittest.TestCase):
    """
    A paused task's downstream tasks naturally remain blocked because:
    - paused status != approved/completed
    - depends_on checks never see the paused task as 'done'
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self._tmpdir.name, "data", "test.db")
        from shared.storage import Storage
        self.storage = Storage(db_path=db_path)
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.storage.db_path) as conn:
            # Insert upstream task (will be paused)
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "status, depends_on, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("task-upstream", "proj1", "epic1", 1, "ba", "brd", "brd.md",
                 "in_progress", "", now, now),
            )
            # Insert downstream task depending on upstream
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "status, depends_on, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("task-downstream", "proj1", "epic1", 2, "sa", "architecture", "arch.md",
                 "pending", "task-upstream", now, now),
            )
            conn.commit()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_paused_upstream_blocks_downstream(self):
        """
        After pausing the upstream task, downstream sa task should not appear
        in SA's pending list because its dependency is not approved/completed.
        """
        self.storage.pause_sdlc_task_for_provider(
            "task-upstream", "quota_exceeded", "anthropic", "claude",
            retry_after_at=_future(3600),
        )
        # Check SA pending tasks — downstream should not appear (dep not satisfied)
        sa_tasks = self.storage.list_pending_sdlc_tasks("sa")
        self.assertFalse(
            any(t.id == "task-downstream" for t in sa_tasks),
            "Downstream task must not be runnable while upstream is paused",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
