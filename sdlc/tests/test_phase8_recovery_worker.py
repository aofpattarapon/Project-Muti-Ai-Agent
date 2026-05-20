"""
Phase 8.2 Tests - Quota recovery worker + router cooldown avoidance.

Run: python3 sdlc/tests/test_phase8_recovery_worker.py
"""

import os
import asyncio
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.recovery_worker import RecoveryWorker
from shared.storage import Storage


def _future(seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()


def _past(seconds: int) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()


class RecoveryWorkerTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "sdlc.db")
        self.storage = Storage(db_path=self.db_path)
        self.worker = RecoveryWorker(storage=self.storage)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _insert_task(self, task_id: str, status: str = "in_progress", role: str = "dev"):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (task_id, "proj1", "epic1", 1, role, "backend_code", "out.md", status, now, now),
            )
            conn.commit()

    def test_run_once_requeues_expired_auto_pause(self):
        self._insert_task("task-expired")
        self.storage.pause_sdlc_task_for_provider(
            "task-expired", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )

        stats, _, _, _ = asyncio.run(self.worker.tick())

        task = self.storage.get_sdlc_task("task-expired")
        self.assertEqual(task.status, "pending")
        self.assertEqual(stats["requeued"], ["task-expired"])
        self.assertEqual(task.pause_reason, "")
        self.assertEqual(task.retry_after_at, "")

    def test_run_once_does_not_requeue_future_pause(self):
        self._insert_task("task-future")
        self.storage.pause_sdlc_task_for_provider(
            "task-future", "rate_limited", "groq", "groq/llama-3.3-70b", _future(3600)
        )

        stats, _, _, _ = asyncio.run(self.worker.tick())

        task = self.storage.get_sdlc_task("task-future")
        self.assertEqual(task.status, "paused")
        self.assertEqual(stats["requeued"], [])

    def test_run_once_never_requeues_manual_token_fix(self):
        self._insert_task("task-manual")
        self.storage.pause_sdlc_task_for_provider(
            "task-manual",
            "auth_error",
            "anthropic",
            "anthropic/claude-sonnet",
            _past(5),
            resume_policy="manual_token_fix",
        )

        stats, _, _, _ = asyncio.run(self.worker.tick())

        task = self.storage.get_sdlc_task("task-manual")
        self.assertEqual(task.status, "paused")
        self.assertEqual(stats["requeued"], [])

    def test_run_once_clears_expired_provider_cooldown(self):
        self.storage.set_provider_cooldown("groq", "groq/llama-3.3-70b", "rate_limited", _past(5))

        stats, _, _, _ = asyncio.run(self.worker.tick())

        self.assertEqual(stats["pruned"], 1)
        self.assertEqual(self.storage.get_active_provider_cooldowns(), [])

    def test_run_once_keeps_active_provider_cooldown(self):
        self.storage.set_provider_cooldown("groq", "groq/llama-3.3-70b", "rate_limited", _future(3600))

        stats, _, _, _ = asyncio.run(self.worker.tick())

        self.assertEqual(stats["pruned"], 0)
        self.assertEqual(len(self.storage.get_active_provider_cooldowns()), 1)

    def test_run_once_defers_when_provider_cooldown_still_active(self):
        retry_at = _future(600)
        self._insert_task("task-deferred")
        self.storage.pause_sdlc_task_for_provider(
            "task-deferred", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )
        self.storage.set_provider_cooldown("groq", "groq/llama-3.3-70b", "rate_limited", retry_at)

        stats, _, _, _ = asyncio.run(self.worker.tick())

        task = self.storage.get_sdlc_task("task-deferred")
        self.assertEqual(task.status, "paused")
        self.assertEqual(task.retry_after_at, retry_at)
        self.assertEqual(stats["deferred"], ["task-deferred"])
        self.assertEqual(stats["requeued"], [])

    def test_dry_run_does_not_mutate_ready_task(self):
        self._insert_task("task-dry")
        self.storage.pause_sdlc_task_for_provider(
            "task-dry", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )
        dry_worker = RecoveryWorker(storage=self.storage, dry_run=True)

        stats, _, _, _ = asyncio.run(dry_worker.tick())

        task = self.storage.get_sdlc_task("task-dry")
        self.assertEqual(task.status, "paused")
        self.assertEqual(stats["requeued"], ["task-dry"])
        self.assertTrue(stats["dry_run"])

    def test_worker_does_not_claim_or_execute_tasks(self):
        self._insert_task("task-expired")
        self.storage.pause_sdlc_task_for_provider(
            "task-expired", "rate_limited", "groq", "groq/llama-3.3-70b", _past(5)
        )

        with patch.object(self.storage, "claim_sdlc_task") as claim:
            asyncio.run(self.worker.tick())

        claim.assert_not_called()


class RouterCooldownTest(unittest.TestCase):
    def test_best_free_for_role_respects_provider_exclusion(self):
        from shared.model_router import best_free_for_role

        key, cfg = best_free_for_role("qa", exclude_providers=["groq"])
        self.assertNotEqual(cfg.provider, "groq")
        self.assertNotEqual(key, "groq/llama-3.3-70b")

    def test_active_cooldown_blocks_model(self):
        from shared import model_router
        from shared.model_router import MODELS

        cfg = MODELS["groq/llama-3.3-70b"]
        self.assertTrue(
            model_router._is_cooling_down(
                "groq/llama-3.3-70b",
                cfg,
                cooldown_providers=set(),
                cooldown_models={"groq/llama-3.3-70b"},
            )
        )

    def test_active_cooldown_blocks_provider(self):
        from shared import model_router
        from shared.model_router import MODELS

        cfg = MODELS["groq/llama-3.3-70b"]
        self.assertTrue(
            model_router._is_cooling_down(
                "groq/llama-3.3-70b",
                cfg,
                cooldown_providers={"groq"},
                cooldown_models=set(),
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
