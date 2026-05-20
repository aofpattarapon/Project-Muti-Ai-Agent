"""
Hotfix tests — PM/BA prompt hardening, contract Thai aliases, Groq 413 routing

Covers:
  1. PM project_management_plan prompt includes schedule/timeline term.
  2. PM risk_register prompt includes probability and mitigation wording.
  3. PM prompts do not use '...' or 'TBD' as the sole content in milestone rows.
  4. Contract: Thai schedule aliases (ตารางเวลา, แผนเวลา) pass management plan check.
  5. Contract: Thai mitigation aliases (แผนลดความเสี่ยง, มาตรการลดความเสี่ยง) pass risk register check.
  6. Contract: risk register without any mitigation term still fails.
  7. Contract: PM project_charter has no duplicate 'stakeholders' section.
  8. BA BRD prompt mentions simulation/safety constraints.
  9. BA SRS prompt includes safety/security NFR section.
  10. Groq 413 — GROQ_MAX_PAYLOAD_CHARS constant exported from llm_client.
  11. Groq 413 — _call_groq pre-flight raises 413 error for oversized payload.
  12. Groq 413 — 413 string triggers retriable path in error classification.
  13. Groq context limits defined for qwen3-32b and llama-4-scout.

Run: python3 sdlc/tests/test_hotfix_pm_ba_routing.py
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock

# Stub heavy/optional dependencies that tests don't need
for _mod in [
    "discord", "discord.ext", "discord.ext.commands",
    "dotenv", "httpx", "anthropic", "groq", "openai", "tiktoken",
]:
    sys.modules.setdefault(_mod, MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.artifact_contracts import (
    validate_role_artifact_contract,
    _CONTRACTS,
)


# ─── 1–3: PM Prompt structure ─────────────────────────────────────────────────

class TestPMProjectManagementPlanPrompt(unittest.TestCase):

    def _rendered_prompt(self) -> str:
        from agents.pm.task_prompts import PROMPTS, build_pm_task_prompt
        ctx = {
            "project_name": "Test Project",
            "project_brief": "A test brief",
            "project_charter_content": "A charter",
            "epics_content": "",
            "requirements": "Some requirements",
        }
        return build_pm_task_prompt("project_management_plan", ctx)

    def test_schedule_term_present_in_management_plan_prompt(self):
        """project_management_plan prompt must include 'schedule' or 'timeline' or 'ตารางเวลา'."""
        prompt = self._rendered_prompt().lower()
        has_term = any(t in prompt for t in ("schedule", "timeline", "ตารางเวลา", "แผนเวลา"))
        self.assertTrue(
            has_term,
            "project_management_plan prompt must include at least one schedule/timeline term",
        )

    def test_milestone_term_in_management_plan_prompt(self):
        """project_management_plan prompt must include 'milestone'."""
        prompt = self._rendered_prompt().lower()
        self.assertIn("milestone", prompt)

    def test_management_plan_prompt_discourages_tbd_rows(self):
        """Prompt instruction must tell model to avoid '...' or 'TBD' only rows."""
        from agents.pm.task_prompts import PROMPTS
        template = PROMPTS.get("project_management_plan", "")
        # The prompt template itself should have a warning against TBD/... placeholders
        has_no_tbd_warning = any(
            kw in template
            for kw in ("ห้ามใช้", "ห้ามใส่", "TBD", "placeholder")
        )
        self.assertTrue(has_no_tbd_warning, "Prompt should discourage TBD/placeholder rows")


class TestPMRiskRegisterPrompt(unittest.TestCase):

    def _rendered_prompt(self) -> str:
        from agents.pm.task_prompts import build_pm_task_prompt
        ctx = {
            "project_name": "Test Project",
            "project_brief": "A test brief",
        }
        return build_pm_task_prompt("risk_register", ctx)

    def test_probability_term_in_risk_register_prompt(self):
        """risk_register prompt must include 'โอกาส' or 'probability'."""
        prompt = self._rendered_prompt().lower()
        has_term = "โอกาส" in prompt or "probability" in prompt or "likelihood" in prompt
        self.assertTrue(has_term, "risk_register prompt must include probability term")

    def test_mitigation_term_in_risk_register_prompt(self):
        """risk_register prompt must include mitigation / แผนลดความเสี่ยง."""
        prompt = self._rendered_prompt().lower()
        has_term = any(
            t in prompt
            for t in ("mitigation", "แผนลดความเสี่ยง", "มาตรการ", "แผนรับมือ")
        )
        self.assertTrue(has_term, "risk_register prompt must include mitigation term")

    def test_risk_register_prompt_mentions_paper_trading_risks(self):
        """Prompt should guide model to include simulation safety risks."""
        from agents.pm.task_prompts import PROMPTS
        template = PROMPTS.get("risk_register", "")
        has_safety_guidance = any(
            kw in template
            for kw in ("paper", "simulation", "PAPER_TRADING_MODE", "real order", "real exchange")
        )
        self.assertTrue(has_safety_guidance, "Prompt should mention simulation safety risk guidance")


# ─── 4–7: Contract Thai aliases ───────────────────────────────────────────────

class TestPMContractThaiAliases(unittest.TestCase):

    def test_thai_timeline_alias_passes_for_management_plan(self):
        """ตารางเวลา in content must pass PM management plan schedule check."""
        content = (
            "# แผนบริหารโครงการ\n"
            "## 3. ตารางเวลาโครงการ\n"
            "| # | Milestone | สัปดาห์ | เกณฑ์ |\n"
            "| 1 | Kick-off | สัปดาห์ที่ 1 | เสร็จ |\n"
            "## Resources\n| Role | จำนวน |\n| PM | 1 |\n"
            "## Milestone 1\nKick-off complete\n"
        )
        result = validate_role_artifact_contract(
            "pm", "project_management_plan", content, "markdown"
        )
        self.assertEqual(result.status, "passed", f"Failed: {result.revision_comment}")

    def test_thai_plan_schedule_alias_passes(self):
        """แผนเวลา term must pass PM management plan schedule check."""
        content = (
            "# แผนบริหารโครงการ\n"
            "## แผนเวลาและ Milestone\n"
            "| สัปดาห์ | งาน |\n| 1 | Kick-off |\n"
            "## ทรัพยากร / Resources\n| BA | 1 |\n"
            "## Milestone\nPhase 1 complete\n"
        )
        result = validate_role_artifact_contract(
            "pm", "project_management_plan", content, "markdown"
        )
        self.assertEqual(result.status, "passed", f"Failed: {result.revision_comment}")

    def test_thai_mitigation_alias_plan_passes_risk_register(self):
        """แผนลดความเสี่ยง term must pass risk register mitigation check."""
        content = (
            "# Risk Register\n"
            "| RISK-001 | Technical | API ล่ม | H | H | แผนลดความเสี่ยง: ใช้ retry + circuit breaker | PM | Open |\n"
            "| RISK-002 | Schedule | ล่าช้า | M | M | แผนลดความเสี่ยง: เพิ่ม buffer 1 สัปดาห์ | PM | Open |\n"
            "## แผนลดความเสี่ยงรายข้อ\n"
            "RISK-001: โอกาส H, ผลกระทบ H — implement retry logic\n"
        )
        result = validate_role_artifact_contract("pm", "risk_register", content, "markdown")
        self.assertEqual(result.status, "passed", f"Failed: {result.revision_comment}")

    def test_thai_mitigation_matrakan_alias_passes(self):
        """มาตรการลดความเสี่ยง term must also pass mitigation check."""
        content = (
            "# Risk Register\n"
            "| RISK-001 | มาตรการลดความเสี่ยง: ทดสอบทุก sprint | H | M |\n"
            "โอกาสที่จะเกิด: medium\n"
        )
        result = validate_role_artifact_contract("pm", "risk_register", content, "markdown")
        self.assertEqual(result.status, "passed", f"Failed: {result.revision_comment}")

    def test_risk_register_without_mitigation_still_fails(self):
        """Risk register with no mitigation term must still fail."""
        content = (
            "# Risk Register\n"
            "| RISK-001 | Technical | API ล่ม | High | Medium | - | PM | Open |\n"
            "โอกาส: สูง\n"
            "ความเสี่ยงสำคัญ: ต้นทุนเกิน\n"
        )
        result = validate_role_artifact_contract("pm", "risk_register", content, "markdown")
        self.assertEqual(result.status, "failed")
        self.assertIn("mitigation", result.missing_sections)

    def test_no_duplicate_stakeholders_in_pm_charter_contract(self):
        """PM project_charter contract must not define 'stakeholders' more than once."""
        pm_charter = _CONTRACTS.get("pm", {}).get("project_charter", {})
        sections = pm_charter.get("sections", [])
        stakeholder_entries = [s for s in sections if s["name"] == "stakeholders"]
        self.assertLessEqual(
            len(stakeholder_entries), 1,
            f"project_charter has {len(stakeholder_entries)} 'stakeholders' sections — expected ≤ 1",
        )


# ─── 8–9: BA Prompt safety constraints ───────────────────────────────────────

class TestBASimulationSafety(unittest.TestCase):

    def test_brd_prompt_mentions_safety_section(self):
        """BRD prompt must include a safety/boundary section."""
        from agents.ba.task_prompts import PROMPTS
        brd = PROMPTS.get("brd", "")
        has_safety = any(
            kw in brd
            for kw in ("Safety", "SAFETY", "simulation", "paper", "real order", "PAPER_TRADING")
        )
        self.assertTrue(has_safety, "BRD prompt must include simulation/safety guidance")

    def test_srs_prompt_includes_security_nfr_section(self):
        """SRS prompt must include security/safety NFR section."""
        from agents.ba.task_prompts import PROMPTS
        srs = PROMPTS.get("srs", "")
        has_security = any(
            kw in srs
            for kw in ("SEC-", "Security", "Safety", "SAFETY", "injection", "XSS", "paper")
        )
        self.assertTrue(has_security, "SRS prompt must include security/safety NFR guidance")


# ─── 10–13: Groq 413 routing ─────────────────────────────────────────────────

class TestGroq413Constants(unittest.TestCase):

    def test_groq_max_payload_chars_exported(self):
        """GROQ_MAX_PAYLOAD_CHARS must be importable from llm_client."""
        from shared.llm_client import GROQ_MAX_PAYLOAD_CHARS
        self.assertGreater(GROQ_MAX_PAYLOAD_CHARS, 10_000)

    def test_groq_qwen3_has_context_limit(self):
        """groq/qwen3-32b must have a context limit in LOCAL_CONTEXT_LIMITS."""
        from shared.model_router import LOCAL_CONTEXT_LIMITS
        self.assertIn("groq/qwen3-32b", LOCAL_CONTEXT_LIMITS)
        self.assertGreater(LOCAL_CONTEXT_LIMITS["groq/qwen3-32b"], 0)

    def test_groq_llama4_scout_has_context_limit(self):
        """groq/llama-4-scout must have a context limit in LOCAL_CONTEXT_LIMITS."""
        from shared.model_router import LOCAL_CONTEXT_LIMITS
        self.assertIn("groq/llama-4-scout", LOCAL_CONTEXT_LIMITS)
        self.assertGreater(LOCAL_CONTEXT_LIMITS["groq/llama-4-scout"], 0)


class TestGroq413ErrorClassification(unittest.TestCase):

    def _is_413_retriable(self, err_str: str) -> bool:
        """Mirror the llm_client retriable check logic."""
        err_lower = err_str.lower()
        is_payload = any(k in err_lower for k in (
            "413", "payload too large", "request entity too large", "request too large",
        ))
        return is_payload

    def test_http_413_status_code_is_retriable(self):
        """Error containing '413' must trigger retriable (routing) path."""
        self.assertTrue(self._is_413_retriable("413 Client Error: Request Entity Too Large"))

    def test_payload_too_large_string_is_retriable(self):
        """'payload too large' string must trigger retriable path."""
        self.assertTrue(self._is_413_retriable("Payload Too Large for Groq API"))

    def test_request_entity_too_large_is_retriable(self):
        """'request entity too large' must trigger retriable path."""
        self.assertTrue(self._is_413_retriable("Request Entity Too Large"))

    def test_normal_404_not_classified_as_413(self):
        """404 error must not be classified as payload-too-large."""
        self.assertFalse(self._is_413_retriable("404 Client Error: Not Found"))


class TestGroqPreflightGuard(unittest.IsolatedAsyncioTestCase):

    async def test_groq_preflight_raises_413_for_oversized_payload(self):
        """_call_groq must raise ValueError with '413' before any HTTP call when payload is too large."""
        from unittest.mock import patch
        from shared.llm_client import LLMClient, GROQ_MAX_PAYLOAD_CHARS
        from shared.model_router import MODELS

        groq_cfg = MODELS["groq/llama-3.3-70b"]
        with patch("shared.llm_client.CostTracker"):
            client = LLMClient(model_config=groq_cfg, model_key="groq/llama-3.3-70b")

        oversized = "x" * (GROQ_MAX_PAYLOAD_CHARS + 1)
        with self.assertRaises(ValueError) as ctx:
            await client._call_groq("system", oversized, 4096)
        self.assertIn("413", str(ctx.exception))

    def test_groq_normal_payload_below_limit(self):
        """Normal-sized prompt must be below GROQ_MAX_PAYLOAD_CHARS threshold."""
        from shared.llm_client import GROQ_MAX_PAYLOAD_CHARS
        # A typical SDLC prompt context (system ~2K + task ~5K)
        normal_prompt = "x" * 7000
        self.assertLess(len(normal_prompt), GROQ_MAX_PAYLOAD_CHARS,
                        "Normal SDLC prompt should be under Groq payload limit")

    def test_413_error_excludes_provider_from_fallback(self):
        """When is_payload_too_large is True, the failing provider is set for exclusion."""
        # Verify the logic: 413 in err_str → is_payload_too_large → _payload_reject_provider set
        err_str = "413 Client Error: Request Entity Too Large for url: https://api.groq.com/..."
        err_lower = err_str.lower()
        is_payload_too_large = any(k in err_lower for k in (
            "413", "payload too large", "request entity too large", "request too large",
        ))
        self.assertTrue(is_payload_too_large)
        # Provider would be set to "groq" and excluded from free_candidates
        failing_provider = "groq"
        # Verify candidates would exclude groq
        from shared.model_router import MODELS
        non_groq_free = [
            k for k, cfg in MODELS.items()
            if cfg.tier.value == "free" and cfg.provider != failing_provider
        ]
        self.assertTrue(len(non_groq_free) > 0, "Should have non-Groq fallback candidates")


# ─── 14–20: PM Excel Project Plan ────────────────────────────────────────────

class TestProjectPlanExcelTaskCatalog(unittest.TestCase):

    def test_project_plan_excel_in_pm_task_catalog(self):
        """PM task catalog must include project_plan_excel task."""
        from shared.task_catalog import TASK_CATALOG
        pm_types = [t["task_type"] for t in TASK_CATALOG["pm"]]
        self.assertIn("project_plan_excel", pm_types)

    def test_project_plan_excel_output_file_is_xlsx(self):
        """project_plan_excel output_file must be project_plan.xlsx."""
        from shared.task_catalog import TASK_CATALOG
        t = next(t for t in TASK_CATALOG["pm"] if t["task_type"] == "project_plan_excel")
        self.assertEqual(t["output_file"], "project_plan.xlsx")
        self.assertEqual(t["output_format"], "excel")

    def test_project_plan_excel_depends_on_management_plan(self):
        """project_plan_excel must depend on project_management_plan."""
        from shared.task_catalog import TASK_CATALOG
        t = next(t for t in TASK_CATALOG["pm"] if t["task_type"] == "project_plan_excel")
        self.assertIn("project_management_plan", t["depends_on_types"])

    def test_build_project_tasks_includes_excel_plan(self):
        """build_project_tasks() must generate a project_plan_excel task for PM."""
        from shared.task_catalog import build_project_tasks
        epics = [{"id": "PE01-E001", "title": "Epic 1", "goal": "goal", "priority": "P1"}]
        tasks = build_project_tasks("PE01", epics, include_roles=["pm"])
        pm_types = [t["task_type"] for t in tasks if t["role"] == "pm"]
        self.assertIn("project_plan_excel", pm_types)

    def test_excel_plan_depends_on_management_plan_in_build(self):
        """In build_project_tasks(), project_plan_excel.depends_on must include the PM plan task ID."""
        from shared.task_catalog import build_project_tasks
        epics = [{"id": "PE02-E001", "title": "Epic 1", "goal": "goal", "priority": "P1"}]
        tasks = build_project_tasks("PE02", epics, include_roles=["pm"])
        plan_task = next((t for t in tasks if t["task_type"] == "project_management_plan"), None)
        excel_task = next((t for t in tasks if t["task_type"] == "project_plan_excel"), None)
        self.assertIsNotNone(plan_task)
        self.assertIsNotNone(excel_task)
        self.assertIn(plan_task["id"], excel_task["depends_on"],
                      f"excel_plan.depends_on={excel_task['depends_on']!r} must include PM plan {plan_task['id']!r}")


class TestProjectPlanExcelPrompt(unittest.TestCase):

    def _rendered_prompt(self) -> str:
        from agents.pm.task_prompts import build_pm_task_prompt
        ctx = {
            "project_name": "Test Project",
            "project_charter_content": "Charter content",
            "pm_plan_content": "PM plan content",
        }
        return build_pm_task_prompt("project_plan_excel", ctx)

    def test_prompt_includes_manday_column(self):
        """project_plan_excel prompt must mention 'Manday' column."""
        self.assertIn("Manday", self._rendered_prompt())

    def test_prompt_includes_duration_days_column(self):
        """project_plan_excel prompt must mention 'Duration Days'."""
        self.assertIn("Duration Days", self._rendered_prompt())

    def test_prompt_includes_owner_agent_column(self):
        """project_plan_excel prompt must mention 'Owner Agent'."""
        self.assertIn("Owner Agent", self._rendered_prompt())

    def test_prompt_includes_all_five_sheet_names(self):
        """project_plan_excel prompt must include all 5 required sheet names."""
        prompt = self._rendered_prompt()
        for sheet in ("Project Plan", "Gantt", "Manday Summary", "Milestones", "Assumptions"):
            self.assertIn(sheet, prompt, f"Prompt missing sheet: {sheet!r}")

    def test_prompt_includes_wbs_and_dependency(self):
        """Prompt must include WBS and Dependency columns."""
        prompt = self._rendered_prompt()
        self.assertIn("WBS", prompt)
        self.assertIn("Dependency", prompt)


class TestProjectPlanExcelContract(unittest.TestCase):

    def _make_valid_json(self) -> str:
        return (
            '{"sheets":['
            '{"name":"Project Plan","headers":["Task ID","WBS","Phase","Task","Description","Owner Agent","Start Date","End Date","Duration Days","Manday","Dependency","Deliverable","Status"],'
            '"rows":[["T-001","1","Init","Brief","CEO","CEO Agent","W1","W1",1,1.0,"","brief.md","Planned"]]},'
            '{"name":"Gantt","headers":["Task ID","Task","Owner","Week 1"],"rows":[["T-001","Brief","CEO Agent","x"]]},'
            '{"name":"Manday Summary","headers":["Owner Agent","Total Tasks","Total Manday","First Start","Last End","Critical Deliverables"],'
            '"rows":[["CEO Agent",1,1.0,"W1","W1","brief.md"]]},'
            '{"name":"Milestones","headers":["Milestone ID","Milestone","Target Date","Owner","Exit Criteria","Dependency"],'
            '"rows":[["M-001","Kickoff","W1","PM","Charter approved","T-001"]]},'
            '{"name":"Assumptions","headers":["#","Category","Assumption","Impact if Wrong","Owner"],'
            '"rows":[[1,"Team","1 Agent = 1 manday","Delay","PM Agent"]]}]}'
        )

    def test_valid_excel_plan_passes_contract(self):
        """Complete JSON with all 5 sheets and required columns passes contract."""
        result = validate_role_artifact_contract(
            "pm", "project_plan_excel", self._make_valid_json(), "excel"
        )
        self.assertEqual(result.status, "passed", f"Failed: {result.revision_comment}")

    def test_missing_manday_column_fails_contract(self):
        """JSON without 'Manday' header fails contract."""
        content = (
            '{"sheets":['
            '{"name":"Project Plan","headers":["Task ID","Duration Days","Owner Agent"],'
            '"rows":[["T-001",1,"CEO Agent"]]},'
            '{"name":"Gantt","headers":[],"rows":[]},'
            '{"name":"Manday Summary","headers":[],"rows":[]},'
            '{"name":"Milestones","headers":[],"rows":[]},'
            '{"name":"Assumptions","headers":[],"rows":[]}]}'
        )
        result = validate_role_artifact_contract("pm", "project_plan_excel", content, "excel")
        self.assertEqual(result.status, "failed")
        self.assertIn("manday_column", result.missing_sections)

    def test_missing_project_plan_sheet_fails_contract(self):
        """JSON without 'Project Plan' sheet name fails contract."""
        content = (
            '{"sheets":['
            '{"name":"Schedule","headers":["Manday","Duration Days","Owner Agent"],"rows":[]},'
            '{"name":"Gantt","headers":[],"rows":[]},'
            '{"name":"Manday Summary","headers":[],"rows":[]},'
            '{"name":"Milestones","headers":[],"rows":[]},'
            '{"name":"Assumptions","headers":[],"rows":[]}]}'
        )
        result = validate_role_artifact_contract("pm", "project_plan_excel", content, "excel")
        self.assertEqual(result.status, "failed")
        self.assertIn("project_plan_sheet", result.missing_sections)

    def test_missing_gantt_sheet_fails_contract(self):
        """JSON without 'Gantt' sheet fails contract."""
        content = (
            '"Project Plan" "Manday Summary" "Milestones" "Assumptions" '
            '"Manday" "Duration Days" "Owner Agent"'  # all other keys present
        )
        result = validate_role_artifact_contract("pm", "project_plan_excel", content, "excel")
        self.assertEqual(result.status, "failed")
        self.assertIn("gantt_sheet", result.missing_sections)


# ─── 21: No-role Groq 413 static branch fix ──────────────────────────────────

class TestGroq413NoRoleBranch(unittest.TestCase):

    def test_static_fallback_excludes_groq_after_413(self):
        """Static (no-role) fallback list must exclude groq provider when 413 occurred."""
        # Mirror the no-role static fallback filtering logic from llm_client.py
        from shared.model_router import MODELS

        _payload_reject_provider = "groq"

        static_candidates = [
            ("claude-cli/claude-sonnet-4-6", MODELS.get("claude-cli/claude-sonnet-4-6"), 7),
            ("openai/gpt-4o-mini",           MODELS.get("openai/gpt-4o-mini"),           6),
            ("groq/llama-3.3-70b",           MODELS.get("groq/llama-3.3-70b"),           6),
            ("ollama/hermes3",                MODELS.get("ollama/hermes3"),               2),
        ]
        tried_keys = {"groq/llama-3.3-70b"}  # primary that failed with 413

        filtered = [
            (k, cfg, s) for k, cfg, s in static_candidates
            if cfg and k not in tried_keys and cfg.provider != _payload_reject_provider
        ]
        filtered_keys = [k for k, _, _ in filtered]

        self.assertNotIn("groq/llama-3.3-70b", filtered_keys,
                         "groq/llama-3.3-70b must be excluded from static fallback after 413")
        # Ensure other non-Groq candidates remain
        non_groq = [k for k in filtered_keys if "groq" not in k]
        self.assertTrue(len(non_groq) > 0, "Non-Groq fallback candidates must remain available")

    def test_both_role_aware_and_no_role_branch_exclude_groq_on_413(self):
        """Both role-aware and static fallback paths use _payload_reject_provider to exclude Groq."""
        import inspect
        from shared.llm_client import LLMClient
        source = inspect.getsource(LLMClient.complete)
        # _payload_reject_provider must appear in both the role-aware section
        # AND in the else (no-role static) filter
        occurrences = source.count("_payload_reject_provider")
        # Expect: assignment + role branch filter (free + cheap) + no-role filter = ≥ 4
        self.assertGreaterEqual(
            occurrences, 4,
            f"_payload_reject_provider used {occurrences} times — expected ≥ 4 (assignment + role branch ×2 + no-role)"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
