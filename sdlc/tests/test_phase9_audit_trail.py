"""
Phase 9.3 Tests — Agent pause/resume audit trail

Covers:
  - WebAppBridge.post_event() sends correct payload to _post
  - RecoveryWorker emits agent.task.resumed.auto event when requeuing a task
  - RecoveryWorker dry_run skips event emission
  - agent.task.paused event shape is correct (unit test)

Run: python3 sdlc/tests/test_phase9_audit_trail.py
"""

import os
import sys
import asyncio
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.recovery_worker import RecoveryWorker
from shared.storage import Storage


def _past(seconds: int) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()


def _future(seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()


def _run(coro):
    return asyncio.run(coro)


# ─── WebAppBridge.post_event ─────────────────────────────────────────────────

class TestWebBridgePostEvent(unittest.TestCase):
    """post_event() sends a correct minimal ingest payload via _post."""

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge()
        self.bridge.enabled = True
        self._posted = []

        async def fake_post(payload):
            self._posted.append(payload)
            return True

        self.bridge._post = fake_post

    def test_post_event_sends_correct_event_type(self):
        _run(self.bridge.post_event(
            role_key="dev",
            event_type="agent.task.paused",
            task_name="Backend Code",
            status="paused",
            summary="Task paused: rate_limited on groq.",
            sdlc_task_id="task-abc",
            project_id="proj-1",
            metadata={"pause_reason": "rate_limited", "pause_provider": "groq"},
            actor="system",
        ))
        self.assertEqual(len(self._posted), 1)
        payload = self._posted[0]
        self.assertEqual(payload["eventType"], "agent.task.paused")
        self.assertEqual(payload["status"], "paused")
        self.assertEqual(payload["sdlc_task_id"], "task-abc")
        self.assertEqual(payload["metadata"]["pause_reason"], "rate_limited")
        self.assertEqual(payload["metadata"]["actor"], "system")

    def test_post_event_resumed_discord_includes_actor(self):
        _run(self.bridge.post_event(
            role_key="dev",
            event_type="agent.task.resumed.discord",
            task_name="backend_code",
            status="pending",
            summary="Task resumed via Discord.",
            sdlc_task_id="task-xyz",
            actor="Off#1234",
        ))
        payload = self._posted[0]
        self.assertEqual(payload["eventType"], "agent.task.resumed.discord")
        self.assertEqual(payload["metadata"]["actor"], "Off#1234")

    def test_post_event_disabled_bridge_returns_false(self):
        from shared.web_bridge import WebAppBridge
        disabled_bridge = WebAppBridge()
        disabled_bridge.enabled = False
        result = _run(disabled_bridge.post_event(
            role_key="dev",
            event_type="agent.task.paused",
            task_name="task",
            status="paused",
            summary="test",
        ))
        self.assertFalse(result)

    def test_post_event_auto_resume_payload(self):
        _run(self.bridge.post_event(
            role_key="dev",
            event_type="agent.task.resumed.auto",
            task_name="Backend Code",
            status="pending",
            summary="Task auto-requeued by recovery worker.",
            sdlc_task_id="task-auto",
            project_id="proj-1",
            metadata={"pause_reason": "rate_limited", "pause_provider": "groq"},
            actor="recovery_worker",
        ))
        payload = self._posted[0]
        self.assertEqual(payload["eventType"], "agent.task.resumed.auto")
        self.assertEqual(payload["metadata"]["actor"], "recovery_worker")


# ─── RecoveryWorker event emission ───────────────────────────────────────────

class TestRecoveryWorkerAuditEvents(unittest.TestCase):
    """RecoveryWorker calls get_bridge().post_event() on auto-requeue."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "sdlc.db")
        self.storage = Storage(db_path=self.db_path)
        self.worker = RecoveryWorker(storage=self.storage)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _insert_task(self, task_id: str, role: str = "dev"):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, title, output_file, "
                "status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, "proj1", "epic1", 1, role, "backend_code",
                 "Backend Code Task", "out.md", "in_progress", now, now),
            )
            conn.commit()

    def test_auto_requeue_emits_resumed_auto_event(self):
        """When a task is requeued, post_event is called with agent.task.resumed.auto."""
        self._insert_task("task-requeue")
        self.storage.pause_sdlc_task_for_provider(
            "task-requeue", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )

        mock_bridge = MagicMock()
        mock_bridge.post_event = AsyncMock(return_value=True)

        with patch("agents.recovery_worker.get_bridge", return_value=mock_bridge):
            asyncio.run(self.worker.tick())

        mock_bridge.post_event.assert_called_once()
        call_kwargs = mock_bridge.post_event.call_args.kwargs
        self.assertEqual(call_kwargs["event_type"], "agent.task.resumed.auto")
        self.assertEqual(call_kwargs["sdlc_task_id"], "task-requeue")
        self.assertEqual(call_kwargs["status"], "pending")

    def test_dry_run_does_not_emit_event(self):
        """dry_run=True skips both DB mutation and event emission."""
        self._insert_task("task-dry-audit")
        self.storage.pause_sdlc_task_for_provider(
            "task-dry-audit", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )
        dry_worker = RecoveryWorker(storage=self.storage, dry_run=True)

        mock_bridge = MagicMock()
        mock_bridge.post_event = AsyncMock(return_value=True)

        with patch("agents.recovery_worker.get_bridge", return_value=mock_bridge):
            asyncio.run(dry_worker.tick())

        mock_bridge.post_event.assert_not_called()

    def test_deferred_task_does_not_emit_event(self):
        """Deferred tasks (still in provider cooldown) must not emit a resumed event."""
        self._insert_task("task-defer-audit")
        self.storage.pause_sdlc_task_for_provider(
            "task-defer-audit", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )
        self.storage.set_provider_cooldown("groq", "groq/llama-3.3-70b", "rate_limited", _future(600))

        mock_bridge = MagicMock()
        mock_bridge.post_event = AsyncMock(return_value=True)

        with patch("agents.recovery_worker.get_bridge", return_value=mock_bridge):
            asyncio.run(self.worker.tick())

        mock_bridge.post_event.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
