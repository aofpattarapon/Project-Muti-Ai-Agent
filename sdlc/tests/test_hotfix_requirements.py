"""
Hotfix tests — full requirements preserved through SDLC pipeline & stage gates

Covers:
  1. _build_sdlc_context() uses input_data["requirements"] (full text) over
     project.description (truncated to 500 chars).
  2. Full requirements text (>500 chars, containing "MVP timeline: 4 weeks")
     survives into the context dict passed to LLM prompts.
  3. CEO _start_project_from_text() extracts clean project_name even when
     attachment content starts with "!new <name> |" or "## Attachment:" header.
  4. Stage gates: BA brd depends on PM project_charter via CROSS_ROLE_DEPS.
  5. UXUI design_system depends on user_flow (intra-role), not immediately ready.
  6. build_project_tasks() resolves BA→PM cross-scope dependency correctly.

Run: python3 sdlc/tests/test_hotfix_requirements.py
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, Project, SdlcTask
from shared.task_catalog import TASK_CATALOG, CROSS_ROLE_DEPS, build_project_tasks
from shared.base_agent import BaseAgent


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _StubAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return "stub"


def _make_agent(storage: Storage) -> _StubAgent:
    with patch("shared.base_agent.CostTracker"), \
         patch("shared.base_agent.TimeLogger"), \
         patch("shared.base_agent.OutputProcessor"), \
         patch("shared.base_agent.LLMClient"):
        agent = _StubAgent()
    agent.storage = storage
    agent.role_name = "pm"
    return agent


def _make_sdlc_task(project_id: str, task_type: str, input_data: dict,
                    epic_id: str = None) -> SdlcTask:
    now = datetime.utcnow().isoformat()
    pid = f"{project_id}-PROJECT"
    return SdlcTask(
        id=f"{pid}-XX01", project_id=project_id,
        epic_id=epic_id or pid,
        task_number=1, role="pm", task_type=task_type,
        title="Test Task", description="",
        output_file="out.md", output_format="markdown",
        depends_on="", status="pending",
        input_data=json.dumps(input_data),
        output_data="{}", approval_msg_id="",
        revision_count=0, notes="",
        created_at=now, updated_at=now,
    )


# ─── 1 & 2: _build_sdlc_context requirements fix ────────────────────────────

class TestBuildSdlcContextRequirements(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])
        self.agent = _make_agent(self.storage)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def _create_project(self, project_id: str, description: str = "") -> Project:
        proj = Project(
            id=project_id, name="Test Project",
            description=description,
            created_at=datetime.utcnow().isoformat(),
            current_role="pm", status="active",
            discord_guild_id="", approval_channel_id="",
        )
        self.storage.create_project(proj)
        return proj

    def test_full_requirements_preferred_over_project_description(self):
        """input_data['requirements'] must be used, not the 500-char truncated description."""
        # Place important constraint AFTER the 500-char truncation point
        full_req = ("A" * 490) + " | MVP timeline: 4 weeks"
        short_desc = full_req[:500]  # project.description — truncated, does NOT contain timeline
        self.assertNotIn("MVP timeline: 4 weeks", short_desc)

        proj = self._create_project("PROJ01", description=short_desc)
        task = _make_sdlc_task("PROJ01", "project_charter", {"requirements": full_req})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertIn("MVP timeline: 4 weeks", ctx["requirements"])

    def test_requirements_in_context_is_full_length(self):
        """Context requirements must be ≥ 500 chars when input_data has long requirements."""
        long_req = "Feature: Paper Trading Bot\nMVP timeline: 4 weeks\n" + ("detail " * 100)
        self.assertGreater(len(long_req), 500)

        proj = self._create_project("PROJ02", description=long_req[:500])
        task = _make_sdlc_task("PROJ02", "project_charter", {"requirements": long_req})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertGreater(len(ctx["requirements"]), 500)
        self.assertIn("MVP timeline: 4 weeks", ctx["requirements"])

    def test_falls_back_to_project_description_when_no_requirements_in_input(self):
        """When input_data has no 'requirements', fall back to project.description."""
        proj = self._create_project("PROJ03", description="Short project desc")
        task = _make_sdlc_task("PROJ03", "project_charter", {})  # no requirements key

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertEqual(ctx["requirements"], "Short project desc")

    def test_empty_input_requirements_falls_back(self):
        """Empty string in input_data['requirements'] falls back to project.description."""
        proj = self._create_project("PROJ04", description="Fallback desc")
        task = _make_sdlc_task("PROJ04", "project_charter", {"requirements": ""})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertEqual(ctx["requirements"], "Fallback desc")


# ─── 3: CEO project_name extraction from attachment content ──────────────────

class TestCEOProjectNameExtraction(unittest.IsolatedAsyncioTestCase):

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.guild.id = "123"
        ctx.channel.id = "456"
        ctx.send = AsyncMock()
        return ctx

    def _make_agent(self, storage):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.ceo.agent import CEOAgent
        with patch("shared.base_agent.CostTracker"), \
             patch("shared.base_agent.TimeLogger"), \
             patch("shared.base_agent.OutputProcessor"), \
             patch("shared.base_agent.LLMClient"):
            agent = CEOAgent.__new__(CEOAgent)
        agent.storage = storage
        agent.role_name = "ceo"
        agent.bot = MagicMock()
        return agent

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    async def test_clean_pipe_format_extracts_name(self):
        """Normal !new command: requirements = 'Project Name | description'"""
        agent = self._make_agent(self.storage)
        ctx = self._make_ctx()
        with patch("shared.web_bridge.get_bridge") as mock_bridge:
            mock_bridge.return_value.hot_cache_update = AsyncMock()
            await agent._start_project_from_text(ctx, "Paper Trading Bot MVP | Build a trading bot")
        # Find the created project
        projects = self.storage.list_active_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Paper Trading Bot MVP")

    async def test_attachment_with_command_prefix_extracts_name(self):
        """Attachment content starts with '!new Paper Trading Bot MVP |'"""
        agent = self._make_agent(self.storage)
        ctx = self._make_ctx()
        combined = (
            "## Attachment: requirements.txt\n"
            "!new Paper Trading Bot MVP | Build a system for paper trading\n"
            "MVP timeline: 4 weeks\nUsers: 10 traders"
        )
        with patch("shared.web_bridge.get_bridge") as mock_bridge:
            mock_bridge.return_value.hot_cache_update = AsyncMock()
            await agent._start_project_from_text(ctx, combined)
        projects = self.storage.list_active_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Paper Trading Bot MVP")

    async def test_attachment_header_alone_not_used_as_name(self):
        """'## Attachment: filename' line must NOT become the project name."""
        agent = self._make_agent(self.storage)
        ctx = self._make_ctx()
        combined = (
            "## Attachment: requirements.txt\n"
            "Trading Platform | A full trading platform\nMVP: 6 weeks"
        )
        with patch("shared.web_bridge.get_bridge") as mock_bridge:
            mock_bridge.return_value.hot_cache_update = AsyncMock()
            await agent._start_project_from_text(ctx, combined)
        projects = self.storage.list_active_projects()
        self.assertEqual(len(projects), 1)
        self.assertNotIn("Attachment", projects[0].name)
        self.assertEqual(projects[0].name, "Trading Platform")

    async def test_requirements_full_text_stored_in_ceo_task_input(self):
        """Full requirements text (>500 chars) must be in CEO task input_data['requirements']."""
        agent = self._make_agent(self.storage)
        ctx = self._make_ctx()
        long_req = "ACME App | " + "Feature detail. " * 50 + "\nMVP timeline: 4 weeks"
        self.assertGreater(len(long_req), 500)
        with patch("shared.web_bridge.get_bridge") as mock_bridge:
            mock_bridge.return_value.hot_cache_update = AsyncMock()
            await agent._start_project_from_text(ctx, long_req)
        projects = self.storage.list_active_projects()
        self.assertEqual(len(projects), 1)
        proj_id = projects[0].id
        ceo_tasks = self.storage.list_sdlc_tasks(project_id=proj_id, role="ceo")
        self.assertTrue(ceo_tasks, "CEO tasks should exist")
        brief_task = next(t for t in ceo_tasks if t.task_type == "project_brief")
        inp = json.loads(brief_task.input_data)
        self.assertIn("MVP timeline: 4 weeks", inp["requirements"])
        self.assertGreater(len(inp["requirements"]), 500)


# ─── 4: CROSS_ROLE_DEPS stage gate: BA → PM ──────────────────────────────────

class TestStageGates(unittest.TestCase):

    def test_ba_brd_depends_on_pm_project_charter_in_cross_role_deps(self):
        """BA brd stage gate: CROSS_ROLE_DEPS must declare ba.brd → pm:project_charter."""
        ba_deps = CROSS_ROLE_DEPS.get("ba", {})
        self.assertIn("brd", ba_deps, "ba.brd must have a cross-role dep")
        self.assertEqual(ba_deps["brd"], "pm:project_charter")

    def test_uxui_design_system_depends_on_user_flow_intra_role(self):
        """UXUI design_system must have depends_on_types: ['user_flow']."""
        uxui_tasks = {t["task_type"]: t for t in TASK_CATALOG["uxui"]}
        self.assertIn("user_flow", uxui_tasks["design_system"]["depends_on_types"])

    def test_build_project_tasks_ba_brd_gets_pm_dep(self):
        """build_project_tasks() must set BA brd.depends_on to PM project_charter task ID."""
        epics = [{"id": "P1-E001", "title": "Epic 1", "goal": "goal", "priority": "P1"}]
        tasks = build_project_tasks("P1", epics, include_roles=["pm", "ba"])

        task_by_id = {t["id"]: t for t in tasks}
        pm_charter = next(
            (t for t in tasks if t["role"] == "pm" and t["task_type"] == "project_charter"), None
        )
        ba_brd = next(
            (t for t in tasks if t["role"] == "ba" and t["task_type"] == "brd"), None
        )

        self.assertIsNotNone(pm_charter, "PM project_charter task must exist")
        self.assertIsNotNone(ba_brd, "BA brd task must exist")
        self.assertIn(pm_charter["id"], ba_brd["depends_on"],
                      f"BA brd.depends_on={ba_brd['depends_on']!r} must include PM charter {pm_charter['id']!r}")

    def test_build_project_tasks_uxui_design_system_depends_on_user_flow(self):
        """UXUI design_system.depends_on must include user_flow task ID."""
        epics = [{"id": "P2-E001", "title": "Epic 1", "goal": "goal", "priority": "P1"}]
        tasks = build_project_tasks("P2", epics, include_roles=["sa", "uxui"])

        user_flow = next(
            (t for t in tasks if t["role"] == "uxui" and t["task_type"] == "user_flow"), None
        )
        design_system = next(
            (t for t in tasks if t["role"] == "uxui" and t["task_type"] == "design_system"), None
        )

        self.assertIsNotNone(user_flow)
        self.assertIsNotNone(design_system)
        self.assertIn(user_flow["id"], design_system["depends_on"],
                      f"design_system.depends_on={design_system['depends_on']!r} must include user_flow {user_flow['id']!r}")

    def test_ceo_tasks_have_preferred_model(self):
        """Both CEO tasks must specify preferred_model = claude-cli/claude-sonnet-4-6."""
        for tdef in TASK_CATALOG["ceo"]:
            self.assertEqual(
                tdef.get("preferred_model"), "claude-cli/claude-sonnet-4-6",
                f"CEO task {tdef['task_type']!r} missing preferred_model",
            )

    def test_stage_gate_order_pm_starts_before_ba(self):
        """With BA→PM dep, PM project_charter has no deps; BA brd depends on PM."""
        epics = [{"id": "P3-E001", "title": "Epic 1", "goal": "g", "priority": "P0"}]
        tasks = build_project_tasks("P3", epics, include_roles=["pm", "ba", "sa"])

        pm_charter = next(t for t in tasks if t["role"] == "pm" and t["task_type"] == "project_charter")
        ba_brd = next(t for t in tasks if t["role"] == "ba" and t["task_type"] == "brd")

        self.assertEqual(pm_charter["depends_on"], "",
                         "PM project_charter should have no deps (starts first)")
        self.assertNotEqual(ba_brd["depends_on"], "",
                            "BA brd must have a dependency (stage gate)")


# ─── 7: _build_sdlc_context project_brief fix ────────────────────────────────

class TestBuildSdlcContextProjectBrief(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])
        self.agent = _make_agent(self.storage)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def _create_project(self, project_id: str, description: str = "") -> Project:
        proj = Project(
            id=project_id, name="Test Project",
            description=description,
            created_at=datetime.utcnow().isoformat(),
            current_role="pm", status="active",
            discord_guild_id="", approval_channel_id="",
        )
        self.storage.create_project(proj)
        return proj

    def test_project_brief_from_input_data_preferred_over_description(self):
        """input_data['project_brief'] must win over truncated project.description."""
        full_brief = "## Full Brief\n" + ("Detail section. " * 50) + "\nTimeline: 4 weeks"
        short_desc = full_brief[:500]
        self.assertNotIn("Timeline: 4 weeks", short_desc)

        self._create_project("PB01", description=short_desc)
        task = _make_sdlc_task("PB01", "project_charter", {"project_brief": full_brief})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertIn("Timeline: 4 weeks", ctx["project_brief"])
        self.assertGreater(len(ctx["project_brief"]), 500)

    def test_project_brief_content_fallback(self):
        """input_data['project_brief_content'] (CEO epics task key) also works."""
        content = "## Brief Content\nSome content here\nTimeline: 6 weeks"
        self._create_project("PB02", description="short desc")
        task = _make_sdlc_task("PB02", "epics", {"project_brief_content": content})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertIn("Timeline: 6 weeks", ctx["project_brief"])

    def test_project_brief_falls_back_to_description_when_no_input_key(self):
        """Falls back to project.description when input_data has no brief keys."""
        self._create_project("PB03", description="Fallback project desc")
        task = _make_sdlc_task("PB03", "project_charter", {})

        ctx = self.agent._build_sdlc_context(task, "Test Project", json.loads(task.input_data))

        self.assertEqual(ctx["project_brief"], "Fallback project desc")


# ─── 8: _get_completed_ceo_task accepts "approved" status ────────────────────

class TestGetCompletedCEOTask(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmp.name, "test.db")
        self.storage = Storage(db_path=os.environ["DB_PATH"])
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.ceo.agent import CEOAgent
        with patch("shared.base_agent.CostTracker"), \
             patch("shared.base_agent.TimeLogger"), \
             patch("shared.base_agent.OutputProcessor"), \
             patch("shared.base_agent.LLMClient"):
            self.agent = CEOAgent.__new__(CEOAgent)
        self.agent.storage = self.storage
        self.agent.role_name = "ceo"

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def _make_ceo_task(self, project_id: str, task_type: str, status: str) -> SdlcTask:
        now = datetime.utcnow().isoformat()
        pid = f"{project_id}-PROJECT"
        t = SdlcTask(
            id=f"{pid}-CEO01", project_id=project_id,
            epic_id=pid, task_number=1, role="ceo", task_type=task_type,
            title="CEO task", description="",
            output_file="brief.md", output_format="markdown",
            depends_on="", status=status,
            input_data=json.dumps({"requirements": "req text"}),
            output_data="## Project Brief\nContent here",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
        )
        self.storage.create_sdlc_task(t)
        return t

    def test_finds_task_with_completed_status(self):
        self._make_ceo_task("PC01", "project_brief", "completed")
        result = self.agent._get_completed_ceo_task("PC01", "project_brief")
        self.assertIsNotNone(result)
        self.assertEqual(result.task_type, "project_brief")

    def test_finds_task_with_approved_status(self):
        """Manual approval flow sets CEO tasks to 'approved', not 'completed'."""
        self._make_ceo_task("PC02", "project_brief", "approved")
        result = self.agent._get_completed_ceo_task("PC02", "project_brief")
        self.assertIsNotNone(result, "_get_completed_ceo_task must find 'approved' tasks")
        self.assertEqual(result.status, "approved")

    def test_does_not_find_pending_task(self):
        self._make_ceo_task("PC03", "project_brief", "pending")
        result = self.agent._get_completed_ceo_task("PC03", "project_brief")
        self.assertIsNone(result)

    def test_downstream_project_brief_empty_when_ceo_brief_only_approved(self):
        """
        Regression: before fix, approved CEO task returned None → brief_content=""
        → all PM/BA/SA tasks got input_data['project_brief'] = "".
        After fix, brief_content is populated from the approved task.
        """
        t = self._make_ceo_task("PC04", "project_brief", "approved")
        result = self.agent._get_completed_ceo_task("PC04", "project_brief")
        self.assertIsNotNone(result)
        brief_content = result.output_data
        self.assertIn("Project Brief", brief_content,
                      "Downstream tasks must receive non-empty project_brief")


if __name__ == "__main__":
    unittest.main(verbosity=2)
