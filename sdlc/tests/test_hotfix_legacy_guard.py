"""
Hotfix tests — legacy role pipeline blocked when project has SDLC tasks

Covers:
  - _check_and_start_pending_task() does NOT call receive_task when the project
    has ANY sdlc_tasks (regardless of which role those tasks belong to)
  - project with CEO sdlc_tasks + current_role=pm → legacy blocked
  - project with CEO sdlc_tasks + current_role=uxui → legacy blocked (further in pipeline)
  - project with NO sdlc_tasks + current_role=pm → legacy fires (receive_task called)
  - BaseAgent.process_task() raises NotImplementedError (no more silent stub output)

Discord and heavy LLM deps are stubbed out at the module level — discord.py is not
installed in the test environment.

Run: python3 sdlc/tests/test_hotfix_legacy_guard.py
"""

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Stub unavailable modules before importing base_agent ─────────────────────
for _mod in [
    "discord", "discord.ext", "discord.ext.commands",
    "dotenv", "httpx", "anthropic", "groq", "openai", "tiktoken",
]:
    sys.modules.setdefault(_mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, Project, SdlcTask
from shared.base_agent import BaseAgent


# ─── Minimal concrete agent (no Discord, no LLM) ──────────────────────────────

class _StubAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return "stub system prompt"


def _make_agent(storage: Storage, role_name: str) -> _StubAgent:
    """Create a _StubAgent with all heavy __init__ deps patched out."""
    with patch("shared.base_agent.CostTracker"), \
         patch("shared.base_agent.TimeLogger"), \
         patch("shared.base_agent.OutputProcessor"), \
         patch("shared.base_agent.LLMClient"):
        agent = _StubAgent()
    agent.storage = storage
    agent.role_name = role_name
    agent.bot = MagicMock()
    agent.bot.guilds = [MagicMock()]   # non-empty: legacy fires IF guard passes
    agent.receive_task = AsyncMock()   # track whether legacy path reached here
    return agent


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _project(project_id: str, current_role: str) -> Project:
    return Project(
        id=project_id, name="Test Project", description="test",
        created_at=datetime.utcnow().isoformat(), current_role=current_role,
        status="active", discord_guild_id="", approval_channel_id="",
    )


def _sdlc_task(storage: Storage, project_id: str, role: str, task_id: str):
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id=project_id, epic_id=f"{project_id}-E001",
        task_number=1, role=role, task_type="project_brief",
        title=f"Task {task_id}", description="",
        output_file="brief.md", output_format="markdown", depends_on="",
        status="pending", input_data="{}", output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
    )
    storage.create_sdlc_task(t)
    return t


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestLegacyGuard(unittest.TestCase):
    """_check_and_start_pending_task must not call receive_task when sdlc_tasks exist."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test.db")
        os.environ["DB_PATH"] = self.db_path
        self.storage = Storage(db_path=self.db_path)

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_blocked_when_ceo_sdlc_tasks_exist_and_current_role_pm(self):
        """
        Project has CEO sdlc_tasks but current_role = pm.
        Before the fix: list_sdlc_tasks(role="pm") → empty → legacy fires.
        After the fix:  list_sdlc_tasks() → non-empty → legacy blocked.
        """
        proj = _project("proj-test-1", current_role="pm")
        self.storage.create_project(proj)
        _sdlc_task(self.storage, proj.id, role="ceo", task_id="CEO01")

        agent = _make_agent(self.storage, "pm")
        asyncio.run(agent._check_and_start_pending_task())

        agent.receive_task.assert_not_called()

    def test_blocked_when_ceo_sdlc_tasks_exist_and_current_role_uxui(self):
        """Legacy pipeline blocked even when current_role has advanced further than the CEO tasks."""
        proj = _project("proj-test-2", current_role="uxui")
        self.storage.create_project(proj)
        _sdlc_task(self.storage, proj.id, role="ceo", task_id="CEO01-B")
        _sdlc_task(self.storage, proj.id, role="ceo", task_id="CEO02-B")

        agent = _make_agent(self.storage, "uxui")
        asyncio.run(agent._check_and_start_pending_task())

        agent.receive_task.assert_not_called()

    def test_blocked_for_all_roles_when_any_sdlc_task_exists(self):
        """Guard fires for pm, ba, sa, uxui — any role — when sdlc_tasks exist."""
        for role in ("pm", "ba", "sa", "uxui"):
            with self.subTest(role=role):
                proj = _project(f"proj-{role}", current_role=role)
                self.storage.create_project(proj)
                _sdlc_task(self.storage, proj.id, role="ceo", task_id=f"CEO-{role}")

                agent = _make_agent(self.storage, role)
                asyncio.run(agent._check_and_start_pending_task())
                agent.receive_task.assert_not_called()

    def test_legacy_fires_when_no_sdlc_tasks_exist(self):
        """When no sdlc_tasks exist the legacy pipeline runs normally (receive_task called)."""
        proj = _project("proj-legacy", current_role="pm")
        self.storage.create_project(proj)
        # No sdlc_tasks inserted

        agent = _make_agent(self.storage, "pm")
        asyncio.run(agent._check_and_start_pending_task())

        agent.receive_task.assert_called_once()


class TestProcessTaskStub(unittest.TestCase):
    """BaseAgent.process_task() must raise NotImplementedError — no silent stub output."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmpdir.name, "test.db")

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_process_task_raises_not_implemented(self):
        storage = Storage(db_path=os.environ["DB_PATH"])
        agent = _make_agent(storage, "pm")
        proj = _project("proj-stub", current_role="pm")

        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(agent.process_task(proj, {}))

        self.assertIn("pm", str(ctx.exception))
        self.assertIn("SDLC task flow", str(ctx.exception))

    def test_process_task_error_message_includes_role(self):
        """Each role's error message names the role for debuggability."""
        storage = Storage(db_path=os.environ["DB_PATH"])
        for role in ("ba", "sa", "dev"):
            agent = _make_agent(storage, role)
            proj = _project("proj-role", current_role=role)
            with self.assertRaises(NotImplementedError) as ctx:
                asyncio.run(agent.process_task(proj, {}))
            self.assertIn(role, str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
