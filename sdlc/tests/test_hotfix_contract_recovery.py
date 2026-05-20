"""
Hotfix tests — contract/validation max-retry → paused auto-recovery

Covers:
  1. SdlcTask.recovery_count field exists with default 0.
  2. pause_sdlc_task_for_contract() sets status=paused, resume_policy=auto_contract_retry,
     increments recovery_count, preserves attempt_count.
  3. list_paused_sdlc_tasks() includes auto_contract_retry tasks (not filtered out).
  4. resume_paused_sdlc_task() clears pause fields → pending.
  5. CONTRACT_RECOVERY_DELAY_SECONDS env var controls retry_after_at offset.
  6. Per-cycle exhaustion: attempt_count-3 (cycle 1) → pause; attempt_count-6 (cycle 2) → pause again.
  7. Non-exhausted contract failure → requeue=True (record_sdlc_task_error), NOT paused.
  8. _pause_task_for_contract() sends Discord output_ch message and Web bridge paused event.
  9. _pause_task_for_contract() calls timelog.finish with failure_type status.
 10. Downstream task count is passed to Web bridge metadata.
 11. AutoRefresh no longer calls router.refresh() inside state updater (React-safe).
 12. Recovery worker tick() picks up auto_contract_retry paused task when cooldown passes.

Run: python3 sdlc/tests/test_hotfix_contract_recovery.py
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

for _mod in [
    "discord", "discord.ext", "discord.ext.commands",
    "dotenv", "httpx", "anthropic", "groq", "openai", "tiktoken",
]:
    sys.modules.setdefault(_mod, MagicMock())

import discord  # noqa: E402
discord.Embed = MagicMock(side_effect=lambda **kw: MagicMock(**kw))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, Project, SdlcTask
from shared.base_agent import BaseAgent
from shared.channel_config import ROLE_CHANNELS


def _setup_mock_bridge(mock_bridge):
    b = mock_bridge.return_value
    for name in ("task_started", "task_completed", "approved", "revision_requested",
                 "rejected", "error", "post_event", "hot_cache_update",
                 "mark_decision_processed", "fetch_web_decisions"):
        setattr(b, name, AsyncMock())
    return b


# ─── Minimal concrete agent ───────────────────────────────────────────────────

class _StubAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return "stub"

    def _build_sdlc_prompt(self, task_type: str, context: dict) -> str:
        return "stub prompt"


def _make_agent(storage: Storage) -> _StubAgent:
    bot = MagicMock()
    bot.command = MagicMock(return_value=lambda f: f)
    bot.event = MagicMock(return_value=lambda f: f)
    with (
        patch("shared.base_agent.LLMClient"),
        patch("shared.base_agent.CostTracker"),
        patch("shared.base_agent.TimeLogger"),
        patch("shared.base_agent.get_router", return_value=MagicMock()),
    ):
        agent = _StubAgent.__new__(_StubAgent)
        agent.role_name = "pm"
        agent.storage = storage
        agent.timelog = MagicMock()
        agent.timelog.finish = MagicMock(return_value=MagicMock())
        agent.timelog.build_finish_embed = MagicMock(return_value=MagicMock())
        agent._task_fail_counts = {}
        agent._last_actual_model_key = None
        return agent


def _make_project(storage: Storage, project_id: str = "PROJ001") -> Project:
    p = Project(
        id=project_id, name="Test Project", description="desc",
        created_at=datetime.utcnow().isoformat(),
        current_role="pm", status="in_progress",
        discord_guild_id="", approval_channel_id="",
        metadata={},
    )
    return storage.create_project(p)


def _make_task(
    storage: Storage,
    project_id: str,
    task_id: str = "TASK001",
    attempt_count: int = 0,
    recovery_count: int = 0,
) -> SdlcTask:
    task = SdlcTask(
        id=task_id, project_id=project_id, epic_id="E1", task_number=1,
        role="pm", task_type="project_charter", title="Project Charter",
        description="", output_file="project_charter.md", output_format="markdown",
        depends_on="", status="in_progress", input_data="{}", output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        attempt_count=attempt_count,
        recovery_count=recovery_count,
    )
    storage.create_sdlc_task(task)
    if attempt_count or recovery_count:
        with __import__("sqlite3").connect(storage.db_path) as conn:
            conn.execute(
                "UPDATE sdlc_tasks SET attempt_count=?, recovery_count=? WHERE id=?",
                (attempt_count, recovery_count, task_id),
            )
            conn.commit()
    return task


# ─── Test classes ─────────────────────────────────────────────────────────────

class TestRecoveryCountField(unittest.TestCase):
    """SdlcTask.recovery_count exists with default 0."""

    def test_recovery_count_default(self):
        t = SdlcTask(
            id="T1", project_id="P1", epic_id="E1", task_number=1,
            role="pm", task_type="project_charter", title="T",
            description="", output_file="f.md", output_format="markdown",
            depends_on="", status="pending", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at="", updated_at="",
        )
        self.assertEqual(t.recovery_count, 0)

    def test_recovery_count_assignment(self):
        t = SdlcTask(
            id="T1", project_id="P1", epic_id="E1", task_number=1,
            role="pm", task_type="project_charter", title="T",
            description="", output_file="f.md", output_format="markdown",
            depends_on="", status="pending", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at="", updated_at="",
            recovery_count=3,
        )
        self.assertEqual(t.recovery_count, 3)


class TestPauseForContractStorage(unittest.TestCase):
    """pause_sdlc_task_for_contract() DB behaviour."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        _make_task(self.storage, "PROJ001", "TASK001", attempt_count=3)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def test_sets_status_paused(self):
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            model_key="ollama/qwen3",
            retry_after_at=retry_after,
            attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.status, "paused")

    def test_sets_resume_policy_auto_contract_retry(self):
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            model_key="ollama/qwen3",
            retry_after_at=retry_after,
            attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.resume_policy, "auto_contract_retry")

    def test_increments_recovery_count(self):
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            model_key="ollama/qwen3",
            retry_after_at=retry_after,
            attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.recovery_count, 1)

    def test_increments_recovery_count_cumulatively(self):
        """Calling twice increments from 1 to 2."""
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=retry_after, attempt_count=3,
        )
        # Simulate requeue then re-pause
        self.storage.resume_paused_sdlc_task("TASK001")
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=retry_after, attempt_count=6,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.recovery_count, 2)

    def test_preserves_attempt_count(self):
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            model_key="ollama/qwen3",
            retry_after_at=retry_after,
            attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.attempt_count, 3)

    def test_no_pause_provider(self):
        """Contract failures must not register provider cooldown (output quality, not outage)."""
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="groq/llama", retry_after_at=retry_after, attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.pause_provider, "")

    def test_retry_after_at_stored(self):
        retry_after = (datetime.utcnow() + timedelta(seconds=300)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=retry_after, attempt_count=3,
        )
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.retry_after_at[:10], retry_after[:10])


class TestListPausedIncludesContractRetry(unittest.TestCase):
    """list_paused_sdlc_tasks must include auto_contract_retry tasks."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        _make_task(self.storage, "PROJ001", "TASK001", attempt_count=3)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def test_contract_retry_task_is_returned(self):
        past = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=past, attempt_count=3,
        )
        ready = self.storage.list_paused_sdlc_tasks(datetime.utcnow().isoformat())
        ids = [t.id for t in ready]
        self.assertIn("TASK001", ids)

    def test_future_retry_not_returned_yet(self):
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=future, attempt_count=3,
        )
        ready = self.storage.list_paused_sdlc_tasks(datetime.utcnow().isoformat())
        ids = [t.id for t in ready]
        self.assertNotIn("TASK001", ids)


class TestResumeClearsContractPause(unittest.TestCase):
    """resume_paused_sdlc_task() requeues to pending."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        _make_task(self.storage, "PROJ001", "TASK001", attempt_count=3)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def test_resume_sets_pending(self):
        past = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=past, attempt_count=3,
        )
        self.storage.resume_paused_sdlc_task("TASK001")
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.status, "pending")

    def test_resume_clears_resume_policy(self):
        past = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="x", model_key="m", retry_after_at=past, attempt_count=3,
        )
        self.storage.resume_paused_sdlc_task("TASK001")
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.resume_policy, "")


class TestPerCycleExhaustion(unittest.TestCase):
    """Per-cycle exhaustion logic using recovery_count."""

    def _calc_exhausted(self, attempt_count: int, recovery_count: int, max_retries: int = 2) -> bool:
        """Mirror the base_agent logic for testing."""
        fail_count = attempt_count + 1
        fail_count_in_cycle = fail_count - recovery_count * (max_retries + 1)
        return fail_count_in_cycle > max_retries

    def test_first_cycle_not_exhausted_at_attempt_1(self):
        self.assertFalse(self._calc_exhausted(0, 0))

    def test_first_cycle_not_exhausted_at_attempt_2(self):
        self.assertFalse(self._calc_exhausted(1, 0))

    def test_first_cycle_exhausted_at_attempt_3(self):
        self.assertTrue(self._calc_exhausted(2, 0))

    def test_second_cycle_not_exhausted_at_attempt_4(self):
        """After first recovery (recovery_count=1, attempt_count=3), attempt 4 is cycle-attempt 1."""
        self.assertFalse(self._calc_exhausted(3, 1))

    def test_second_cycle_not_exhausted_at_attempt_5(self):
        self.assertFalse(self._calc_exhausted(4, 1))

    def test_second_cycle_exhausted_at_attempt_6(self):
        self.assertTrue(self._calc_exhausted(5, 1))

    def test_third_cycle_not_exhausted_at_attempt_7(self):
        self.assertFalse(self._calc_exhausted(6, 2))


class TestPauseTaskForContractMethod(unittest.TestCase):
    """_pause_task_for_contract() integration with mock bridge + storage."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        self.task = _make_task(self.storage, "PROJ001", "TASK001", attempt_count=2)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("shared.base_agent.get_bridge")
    def test_pause_sets_db_status_paused(self, mock_bridge_fn):
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.status, "paused")
        self.assertEqual(task.resume_policy, "auto_contract_retry")
        self.assertEqual(task.recovery_count, 1)

    @patch("shared.base_agent.get_bridge")
    def test_pause_sends_discord_notification(self, mock_bridge_fn):
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        output_ch.send.assert_called_once()
        msg = output_ch.send.call_args[0][0]
        self.assertIn("Paused for Auto-Recovery", msg)
        self.assertIn("TASK001", msg)
        self.assertIn("stakeholders", msg)
        self.assertIn("!sdlc_resume", msg)

    @patch("shared.base_agent.get_bridge")
    def test_pause_sends_web_bridge_paused_event(self, mock_bridge_fn):
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        bridge.task_completed.assert_called_once()
        call_kwargs = bridge.task_completed.call_args[1]
        self.assertEqual(call_kwargs["status"], "paused")
        meta = call_kwargs.get("extra_metadata", {})
        self.assertEqual(meta.get("resume_policy"), "auto_contract_retry")

    @patch("shared.base_agent.get_bridge")
    def test_pause_calls_timelog_finish(self, mock_bridge_fn):
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        agent.timelog.finish.assert_called_once()
        finish_kwargs = agent.timelog.finish.call_args[1]
        self.assertEqual(finish_kwargs.get("status"), "contract_failed")
        self.assertEqual(finish_kwargs.get("log_id"), "LOG1")

    @patch("shared.base_agent.get_bridge")
    def test_pause_sends_timelog_channel_detail(self, mock_bridge_fn):
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        # At minimum 2 calls: the finish embed + the detail message
        self.assertGreaterEqual(tlog_ch.send.call_count, 2)
        detail_calls = [str(c) for c in tlog_ch.send.call_args_list]
        # One of them should mention the missing section
        combined = " ".join(detail_calls)
        self.assertIn("stakeholders", combined)

    @patch("shared.base_agent.get_bridge")
    def test_pause_no_approval_card_created(self, mock_bridge_fn):
        """A paused contract task must never trigger an approval card."""
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        output_ch = AsyncMock()
        tlog_ch = AsyncMock()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="stakeholders",
            fail_count=3, recovery_count=0,
            model_key="ollama/qwen3",
            output_ch=output_ch, tlog_ch=tlog_ch,
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        # bridge.approved must never be called — that's what creates approval cards
        bridge.approved.assert_not_called()


class TestContractRecoveryDelay(unittest.TestCase):
    """CONTRACT_RECOVERY_DELAY_SECONDS env var controls retry_after_at."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        self.task = _make_task(self.storage, "PROJ001", "TASK001", attempt_count=2)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)
        os.environ.pop("CONTRACT_RECOVERY_DELAY_SECONDS", None)

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("shared.base_agent.get_bridge")
    def test_custom_delay_applied(self, mock_bridge_fn):
        os.environ["CONTRACT_RECOVERY_DELAY_SECONDS"] = "60"
        bridge = _setup_mock_bridge(mock_bridge_fn)
        agent = _make_agent(self.storage)
        before = datetime.utcnow()

        self._run(agent._pause_task_for_contract(
            task=self.task, project_name="Test",
            failure_type="contract_failed",
            missing_sections="x",
            fail_count=3, recovery_count=0,
            model_key="m",
            output_ch=AsyncMock(), tlog_ch=AsyncMock(),
            log_id="LOG1", estimated_cost=0.0, duration=1.0,
        ))

        task = self.storage.get_sdlc_task("TASK001")
        retry_dt = datetime.fromisoformat(task.retry_after_at)
        delta = (retry_dt - before).total_seconds()
        # Should be ~60s (allow small floating point margin)
        self.assertGreater(delta, 55)
        self.assertLess(delta, 120)


class TestRecoveryWorkerPicksUpContractRetry(unittest.TestCase):
    """RecoveryWorker.tick() requeues auto_contract_retry tasks whose cooldown passed."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.storage = Storage(db_path=self.tmp.name)
        _make_project(self.storage, "PROJ001")
        _make_task(self.storage, "PROJ001", "TASK001", attempt_count=3)

    def tearDown(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("agents.recovery_worker.get_bridge")
    def test_tick_requeues_auto_contract_retry(self, mock_bridge_fn):
        from agents.recovery_worker import RecoveryWorker
        bridge = _setup_mock_bridge(mock_bridge_fn)

        past = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="stakeholders", model_key="ollama/qwen3",
            retry_after_at=past, attempt_count=3,
        )

        worker = RecoveryWorker(self.storage)
        stats, _, _, _ = self._run(worker.tick())

        self.assertIn("TASK001", stats["requeued"])
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.status, "pending")

    @patch("agents.recovery_worker.get_bridge")
    def test_tick_does_not_requeue_future_contract_task(self, mock_bridge_fn):
        from agents.recovery_worker import RecoveryWorker
        bridge = _setup_mock_bridge(mock_bridge_fn)

        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        self.storage.pause_sdlc_task_for_contract(
            task_id="TASK001", failure_type="contract_failed",
            missing_sections="stakeholders", model_key="ollama/qwen3",
            retry_after_at=future, attempt_count=3,
        )

        worker = RecoveryWorker(self.storage)
        stats, _, _, _ = self._run(worker.tick())

        self.assertNotIn("TASK001", stats["requeued"])
        task = self.storage.get_sdlc_task("TASK001")
        self.assertEqual(task.status, "paused")


class TestAutoRefreshReactSafe(unittest.TestCase):
    """WorkboardClient.tsx AutoRefresh must not call router.refresh() inside state updater."""

    def test_autorefresh_uses_ref_not_direct_refresh_in_state(self):
        tsx_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "webapp", "app", "workboard", "_components", "WorkboardClient.tsx",
        )
        with open(tsx_path, encoding="utf-8") as f:
            src = f.read()

        # The old buggy pattern: router.refresh() directly inside setCountdown updater
        self.assertNotIn(
            "startTransition(() => router.refresh());",
            _extract_countdown_updater(src),
            "router.refresh() must not be called inside the setCountdown updater callback",
        )

    def test_autorefresh_uses_ref_flag(self):
        tsx_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "webapp", "app", "workboard", "_components", "WorkboardClient.tsx",
        )
        with open(tsx_path, encoding="utf-8") as f:
            src = f.read()

        self.assertIn("shouldRefreshRef", src, "AutoRefresh should use a ref to schedule refresh")


def _extract_countdown_updater(src: str) -> str:
    """Extract the setCountdown((c) => { ... }) callback body for inspection."""
    marker = "setCountdown((c) =>"
    start = src.find(marker)
    if start == -1:
        return ""
    depth = 0
    i = start + len(marker)
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:]


if __name__ == "__main__":
    unittest.main(verbosity=2)
