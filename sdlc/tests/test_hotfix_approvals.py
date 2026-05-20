"""
Hotfix tests — bi-directional SDLC approvals

Covers:
  1. _execute_sdlc_task posts approval card to #{role}-approve (not output)
     and stores approval_msg_id from the approve-channel message.
  2. approval_msg_id comes from the approve channel, NOT the output channel.
  3. Discord !approve replies update sdlc.db and sync to web approval_item.
  4. Web decision _execute_web_decision uses role-specific #{role}-approve,
     not DISCORD_APPROVAL_CHANNEL_ID env var.
  5. Contract-failed tasks (status="blocked") do NOT create approval_items.
  6. Auto-approve mode does NOT set approval_msg_id (no card posted).

Run: python3 sdlc/tests/test_hotfix_approvals.py
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

for _mod in [
    "discord", "discord.ext", "discord.ext.commands",
    "dotenv", "httpx", "anthropic", "groq", "openai", "tiktoken",
]:
    sys.modules.setdefault(_mod, MagicMock())

import discord  # noqa: E402 (MagicMock from above)
discord.Embed = MagicMock(side_effect=lambda **kw: MagicMock(**kw))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, Project, SdlcTask
from shared.base_agent import BaseAgent
from shared.channel_config import ROLE_CHANNELS


def _setup_mock_bridge(mock_bridge):
    """Configure all async methods on a mock bridge so they can be awaited."""
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


def _make_agent(storage: Storage, role: str = "pm") -> _StubAgent:
    with patch("shared.base_agent.CostTracker"), \
         patch("shared.base_agent.TimeLogger"), \
         patch("shared.base_agent.OutputProcessor"), \
         patch("shared.base_agent.LLMClient"):
        agent = _StubAgent()
    agent.storage = storage
    agent.role_name = role
    agent.bot = MagicMock()
    return agent


def _make_task(storage: Storage, project_id: str, task_id: str,
               role: str = "pm", approval_mode: str = "manual") -> SdlcTask:
    now = datetime.utcnow().isoformat()
    epic_id = f"{project_id}-PROJECT"
    t = SdlcTask(
        id=task_id, project_id=project_id, epic_id=epic_id,
        task_number=1, role=role, task_type="project_charter",
        title="Project Charter", description="",
        output_file="project_charter.docx", output_format="word",
        depends_on="", status="in_progress",
        input_data=json.dumps({"requirements": "Build something", "project_name": "Test"}),
        output_data="", approval_msg_id="",
        revision_count=0, notes="",
        created_at=now, updated_at=now,
    )
    storage.create_sdlc_task(t)
    proj = Project(
        id=project_id, name="Test Project", description="test",
        created_at=now, current_role=role, status="in_progress",
        discord_guild_id="999", approval_channel_id="",
        metadata={"approval_mode": approval_mode},
    )
    storage.create_project(proj)
    return t


# ─── 1 & 2: Approval card posted to approve channel ──────────────────────────

class TestApprovalChannelRouting(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def _make_guild(self):
        """Build a mock guild with named channels tracked by name."""
        guild = MagicMock()
        sent_to: dict[str, list] = {}

        async def _get_ch(guild_obj, name):
            ch = MagicMock()
            ch.name = name
            ch.send = AsyncMock(return_value=MagicMock(id=int(hash(name) % 10**9)))
            sent_to[name] = ch
            return ch

        guild.sent_to = sent_to
        return guild, _get_ch

    def test_manual_mode_posts_approval_card_to_approve_channel(self):
        """In manual mode, approval card must go to #{role}-approve, not output."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-APP1", "PROJ-APP1-PROJECT-PM01",
                          role="pm", approval_mode="manual")

        sent_channels: list[str] = []

        async def _recording_get_ch(guild_obj, name):
            ch = MagicMock()
            ch.name = name
            ch.send = AsyncMock(return_value=MagicMock(id=1234567890))
            sent_channels.append(name)
            return ch

        _ok_contract = MagicMock(status="ok", contract_name="", revision_comment="",
                                 missing_sections=[], missing_artifacts=[])

        with patch("shared.channel_config.get_guild_channel", side_effect=_recording_get_ch), \
             patch("shared.base_agent.save_task_output", return_value="/tmp/out.docx"), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "call_llm", AsyncMock(return_value="Charter content")), \
             patch.object(agent, "_build_sdlc_context", return_value={}), \
             patch("shared.artifact_contracts.validate_role_artifact_contract", return_value=_ok_contract), \
             patch("shared.artifact_validator.validate_artifact", return_value=(True, "")), \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()), \
             patch("shared.base_agent.get_router") as mock_router:
            _setup_mock_bridge(mock_bridge)
            mock_router.return_value.get_routing_summary.return_value = {
                "model_id": "test-model", "tier": "free", "provider": "test"
            }
            asyncio.run(agent._execute_sdlc_task(task, MagicMock()))

        # Approve channel must have been fetched
        self.assertIn("pm-approve", sent_channels,
                      f"pm-approve not in fetched channels: {sent_channels}")

    def test_manual_mode_approval_msg_id_comes_from_approve_channel(self):
        """approval_msg_id must be the approve-channel message id, not output-channel id."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-APP2", "PROJ-APP2-PROJECT-PM01",
                          role="pm", approval_mode="manual")

        APPROVE_MSG_ID = 777888999
        OUTPUT_MSG_ID  = 111222333

        async def _channel_factory(guild_obj, name):
            ch = MagicMock()
            ch.name = name
            if name == "pm-approve":
                ch.send = AsyncMock(return_value=MagicMock(id=APPROVE_MSG_ID))
            else:
                ch.send = AsyncMock(return_value=MagicMock(id=OUTPUT_MSG_ID))
            return ch

        _ok_contract = MagicMock(status="ok", contract_name="", revision_comment="",
                                 missing_sections=[], missing_artifacts=[])

        with patch("shared.channel_config.get_guild_channel", side_effect=_channel_factory), \
             patch("shared.base_agent.save_task_output", return_value="/tmp/out.docx"), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "call_llm", AsyncMock(return_value="Charter content")), \
             patch.object(agent, "_build_sdlc_context", return_value={}), \
             patch("shared.artifact_contracts.validate_role_artifact_contract", return_value=_ok_contract), \
             patch("shared.artifact_validator.validate_artifact", return_value=(True, "")), \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()), \
             patch("shared.base_agent.get_router") as mock_router:
            _setup_mock_bridge(mock_bridge)
            mock_router.return_value.get_routing_summary.return_value = {
                "model_id": "test-model", "tier": "free", "provider": "test"
            }
            asyncio.run(agent._execute_sdlc_task(task, MagicMock()))

        fresh = self.storage.get_sdlc_task(task.id)
        self.assertIsNotNone(fresh)
        self.assertEqual(
            fresh.approval_msg_id, str(APPROVE_MSG_ID),
            f"approval_msg_id={fresh.approval_msg_id!r} should be approve-channel id {APPROVE_MSG_ID}"
        )
        self.assertNotEqual(
            fresh.approval_msg_id, str(OUTPUT_MSG_ID),
            "approval_msg_id must NOT be the output-channel message id"
        )

    def test_auto_mode_does_not_store_approval_msg_id(self):
        """In auto mode no approval card is posted; approval_msg_id must remain empty."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-APP3", "PROJ-APP3-PROJECT-PM01",
                          role="pm", approval_mode="auto")

        async def _channel_factory(guild_obj, name):
            ch = MagicMock()
            ch.name = name
            ch.send = AsyncMock(return_value=MagicMock(id=99999))
            return ch

        _ok_contract = MagicMock(status="ok", contract_name="", revision_comment="",
                                 missing_sections=[], missing_artifacts=[])

        with patch("shared.channel_config.get_guild_channel", side_effect=_channel_factory), \
             patch("shared.base_agent.save_task_output", return_value="/tmp/out.docx"), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "call_llm", AsyncMock(return_value="Charter content")), \
             patch.object(agent, "_build_sdlc_context", return_value={}), \
             patch("shared.artifact_contracts.validate_role_artifact_contract", return_value=_ok_contract), \
             patch("shared.artifact_validator.validate_artifact", return_value=(True, "")), \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()), \
             patch("shared.base_agent.get_router") as mock_router:
            _setup_mock_bridge(mock_bridge)
            mock_router.return_value.get_routing_summary.return_value = {
                "model_id": "test-model", "tier": "free", "provider": "test"
            }
            asyncio.run(agent._execute_sdlc_task(task, MagicMock()))

        fresh = self.storage.get_sdlc_task(task.id)
        self.assertIsNotNone(fresh)
        self.assertEqual(fresh.approval_msg_id, "",
                         "Auto-approve must not store approval_msg_id")


# ─── 3: Discord !approve syncs to web ────────────────────────────────────────

class TestDiscordApproveSync(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_discord_approve_updates_sdlc_task_status(self):
        """!approve in Discord must set sdlc_task status → 'approved' in sdlc.db."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-DA1", "PROJ-DA1-PROJECT-PM01",
                          role="pm", approval_mode="manual")
        # Simulate task is waiting approval with a known approval_msg_id
        self.storage.update_sdlc_task_status(task.id, "waiting_approval")
        self.storage.set_sdlc_task_approval_msg(task.id, "DISCORD_MSG_123")

        from shared.base_agent import DecisionAction
        mock_intent = MagicMock()
        mock_intent.action = DecisionAction.APPROVE
        mock_intent.note = ""

        message = MagicMock()
        message.author = "TestUser#1234"
        message.channel.send = AsyncMock()

        with patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()):
            mock_bridge.return_value.approved = AsyncMock()
            asyncio.run(agent._handle_sdlc_decision(message, task, mock_intent))

        fresh = self.storage.get_sdlc_task(task.id)
        self.assertEqual(fresh.status, "approved")

    def test_discord_approve_calls_bridge_with_sdlc_task_id(self):
        """!approve must call get_bridge().approved() with the correct sdlc_task_id."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-DA2", "PROJ-DA2-PROJECT-PM01",
                          role="pm", approval_mode="manual")
        self.storage.update_sdlc_task_status(task.id, "waiting_approval")

        from shared.base_agent import DecisionAction
        mock_intent = MagicMock()
        mock_intent.action = DecisionAction.APPROVE
        mock_intent.note = ""

        message = MagicMock()
        message.author = "TestUser#1234"
        message.channel.send = AsyncMock()

        captured_kwargs = {}
        async def _capture_approved(**kwargs):
            captured_kwargs.update(kwargs)

        with patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()):
            mock_bridge.return_value.approved = _capture_approved
            asyncio.run(agent._handle_sdlc_decision(message, task, mock_intent))

        self.assertEqual(captured_kwargs.get("sdlc_task_id"), task.id)


# ─── 4: Web decision uses role-specific approve channel ──────────────────────

class TestWebDecisionRoleChannel(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        os.environ.pop("DISCORD_APPROVAL_CHANNEL_ID", None)
        self.storage = Storage(db_path=os.environ["DB_PATH"])

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_web_decision_notification_sent_to_role_approve_channel(self):
        """Web decision notification must go to #{role}-approve, not global env var channel."""
        agent = _make_agent(self.storage, "ba")
        task = _make_task(self.storage, "PROJ-WD1", "PROJ-WD1-PROJECT-BA01",
                          role="ba", approval_mode="manual")
        self.storage.update_sdlc_task_status(task.id, "waiting_approval")

        channels_fetched: list[str] = []

        async def _recording_get_ch(guild_obj, name):
            channels_fetched.append(name)
            ch = MagicMock()
            ch.name = name
            ch.send = AsyncMock()
            return ch

        agent.bot = MagicMock()
        agent.bot.guilds = [MagicMock()]
        agent.bot.guilds[0].get_channel = MagicMock(return_value=None)

        item = {
            "id": 1,
            "status": "approved",
            "task_name": task.title,
            "decision_note": "",
            "approver": "web-ui",
            "sdlc_task_id": task.id,
        }

        with patch("shared.base_agent.get_guild_channel", side_effect=_recording_get_ch), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()):
            mock_bridge.return_value.approved = AsyncMock()
            mock_bridge.return_value.mark_decision_processed = AsyncMock()
            asyncio.run(agent._execute_web_decision(item))

        self.assertIn("ba-approve", channels_fetched,
                      f"Web decision must notify ba-approve; got: {channels_fetched}")
        # Must NOT use DISCORD_APPROVAL_CHANNEL_ID (which is not in env)
        agent.bot.guilds[0].get_channel.assert_not_called()

    def test_web_decision_does_not_rely_on_global_env_var(self):
        """_execute_web_decision must work even when DISCORD_APPROVAL_CHANNEL_ID is unset."""
        os.environ.pop("DISCORD_APPROVAL_CHANNEL_ID", None)
        agent = _make_agent(self.storage, "sa")
        task = _make_task(self.storage, "PROJ-WD2", "PROJ-WD2-PROJECT-SA01",
                          role="sa", approval_mode="manual")
        self.storage.update_sdlc_task_status(task.id, "waiting_approval")

        agent.bot = MagicMock()
        agent.bot.guilds = [MagicMock()]

        async def _ch_factory(guild_obj, name):
            ch = MagicMock()
            ch.send = AsyncMock()
            return ch

        item = {
            "id": 2, "status": "approved", "task_name": task.title,
            "decision_note": "", "approver": "web-ui",
            "sdlc_task_id": task.id,
        }
        with patch("shared.base_agent.get_guild_channel", side_effect=_ch_factory), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "_on_sdlc_task_completed", AsyncMock()):
            mock_bridge.return_value.approved = AsyncMock()
            mock_bridge.return_value.mark_decision_processed = AsyncMock()
            # Must not raise even without DISCORD_APPROVAL_CHANNEL_ID
            asyncio.run(agent._execute_web_decision(item))


# ─── 5: Contract-failed tasks don't create approval items ─────────────────────

class TestContractFailedNoApproval(unittest.TestCase):
    """Contract-failed tasks post status='blocked', NOT 'waiting_approval'.
    The ingest handler creates approval_items only for 'waiting_approval'.
    This is confirmed via the bridge payload."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_contract_failed_calls_bridge_with_blocked_status(self):
        """_execute_sdlc_task must call task_completed(status='blocked') on contract failure."""
        agent = _make_agent(self.storage, "pm")
        task = _make_task(self.storage, "PROJ-CF1", "PROJ-CF1-PROJECT-PM01",
                          role="pm", approval_mode="manual")

        bridge_calls: list[dict] = []
        async def _capture_task_completed(**kwargs):
            bridge_calls.append(kwargs)

        async def _ch_factory(guild_obj, name):
            ch = MagicMock()
            ch.send = AsyncMock(return_value=MagicMock(id=1))
            return ch

        _fail_contract = MagicMock(
            status="failed",
            contract_name="project_charter",
            revision_comment="Missing section: Constraints",
            missing_sections=["Constraints"],
            missing_artifacts=[],
        )

        with patch("shared.channel_config.get_guild_channel", side_effect=_ch_factory), \
             patch("shared.base_agent.save_task_output", return_value="/tmp/out.docx"), \
             patch("shared.base_agent.get_bridge") as mock_bridge, \
             patch.object(agent, "call_llm", AsyncMock(return_value="Charter content")), \
             patch.object(agent, "_build_sdlc_context", return_value={}), \
             patch("shared.artifact_contracts.validate_role_artifact_contract", return_value=_fail_contract), \
             patch("shared.artifact_validator.validate_artifact", return_value=(True, "")), \
             patch("shared.base_agent.get_router") as mock_router:
            _setup_mock_bridge(mock_bridge)
            mock_bridge.return_value.task_completed = _capture_task_completed
            mock_router.return_value.get_routing_summary.return_value = {
                "model_id": "test-model", "tier": "free", "provider": "test"
            }
            asyncio.run(agent._execute_sdlc_task(task, MagicMock()))

        # Must have called task_completed with status="blocked"
        self.assertTrue(bridge_calls, "bridge.task_completed must be called on contract failure")
        blocked_call = next(
            (c for c in bridge_calls if c.get("status") == "blocked"), None
        )
        self.assertIsNotNone(blocked_call,
                             f"task_completed must be called with status='blocked', got: {bridge_calls}")
        # approval_msg_id must remain empty (no approval card posted)
        fresh = self.storage.get_sdlc_task(task.id)
        self.assertEqual(fresh.approval_msg_id if fresh else "", "")


# ─── 6: Role approve channel is correct for every role ───────────────────────

class TestApproveChannelNames(unittest.TestCase):

    def test_every_role_has_approve_channel(self):
        """Every SDLC role must have a role_ch.approve name ending in '-approve'."""
        for role in ("ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"):
            role_ch = ROLE_CHANNELS.get(role)
            self.assertIsNotNone(role_ch, f"Missing ROLE_CHANNELS entry for {role!r}")
            self.assertTrue(
                role_ch.approve.endswith("-approve"),
                f"role_ch.approve={role_ch.approve!r} for {role!r} should end in '-approve'"
            )
            self.assertEqual(role_ch.approve, f"{role}-approve",
                             f"{role} approve channel should be '{role}-approve'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
