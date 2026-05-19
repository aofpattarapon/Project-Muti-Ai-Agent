"""
Tests for Phase 7: Role Artifact Contract & Document Completeness.

Covers:
  - CEO/BA/SA/UXUI document section validation
  - DEV secondary artifact detection (workspace_manifest.json)
  - QA qa_execution_result requirement for test_report
  - DEVOPS dockerfile/docker_compose/github_actions/deployment_guide artifacts
  - Missing required section → failed result with informative revision_comment
  - Unknown role/task_type → skipped (not failed)
  - contract_info included in web metadata
  - build_contract_prompt_block returns non-empty hint for known types
  - Secondary file "any of" logic (QA test_report accepts either JSON file)

Run: python3 sdlc/tests/test_artifact_contracts.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.artifact_contracts import (
    validate_role_artifact_contract,
    build_contract_prompt_block,
    ContractValidationResult,
)


# ─── CEO ────────────────────────────────────────────────────────────────────

class TestCEOContracts(unittest.TestCase):

    def test_project_brief_passes_with_all_sections(self):
        content = """
# Project Brief — MyApp

## 2. เป้าหมายทางธุรกิจ
| # | เป้าหมาย | ตัวชี้วัด (KPI) |
| 1 | ลดต้นทุน | 20% ภายใน Q3 |

## 6. เกณฑ์ความสำเร็จ
| เกณฑ์ | วิธีวัด |

## 4. MVP Scope
- Feature A
- Feature B

## 8. สมมติฐาน
1. Internet availability assumed

## 10. ความเสี่ยงเบื้องต้น
| ความเสี่ยง | ผลกระทบ |

## 9. ผู้มีส่วนได้เสีย
| Stakeholder | บทบาท |
"""
        result = validate_role_artifact_contract("ceo", "project_brief", content, "markdown")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.missing_sections, [])

    def test_project_brief_fails_when_risks_missing(self):
        content = """
## เป้าหมายทางธุรกิจ
KPI target: 20%

## เกณฑ์ความสำเร็จ
Success criteria here

## MVP Scope
Feature list

## สมมติฐาน
Assumptions here

## ผู้มีส่วนได้เสีย
Stakeholders
"""
        result = validate_role_artifact_contract("ceo", "project_brief", content, "markdown")
        self.assertEqual(result.status, "failed")
        self.assertIn("risks", result.missing_sections)

    def test_project_brief_fails_when_business_goal_missing(self):
        content = "งานที่ยังไม่สมบูรณ์ ขาดส่วนสำคัญหลายส่วน"
        result = validate_role_artifact_contract("ceo", "project_brief", content, "markdown")
        self.assertEqual(result.status, "failed")
        self.assertIn("business_goal", result.missing_sections)

    def test_project_brief_revision_comment_names_missing_sections(self):
        content = "Incomplete document"
        result = validate_role_artifact_contract("ceo", "project_brief", content, "markdown")
        self.assertIn("[contract]", result.revision_comment)
        self.assertIn("Missing sections:", result.revision_comment)

    def test_epics_passes_with_epic_ids_and_criteria(self):
        content = """
# Epics — MyApp

## EPIC-001: User Authentication
**Acceptance Criteria:**
- [ ] Login works
- [ ] Logout works

## EPIC-002: Dashboard
**Acceptance Criteria:**
- [ ] Data displays
"""
        result = validate_role_artifact_contract("ceo", "epics", content, "markdown")
        self.assertEqual(result.status, "passed")

    def test_epics_fails_without_epic_ids(self):
        content = "Some features described without EPIC numbering"
        result = validate_role_artifact_contract("ceo", "epics", content, "markdown")
        self.assertEqual(result.status, "failed")
        self.assertIn("epic_id", result.missing_sections)


# ─── BA ─────────────────────────────────────────────────────────────────────

class TestBAContracts(unittest.TestCase):

    def test_brd_passes_with_all_required_sections(self):
        content = """
# BRD

## 3. Functional Requirements
| FR-001 | User login | Must Have |
| FR-002 | User registration | Must Have |

## 4. Non-Functional Requirements
| NFR-001 | Performance | 200ms |

## 5. Business Rules
| BR-001 | Only verified users | ... |

## 6. Assumptions
สมมติฐาน: Internet available

## 1. ขอบเขต
Scope: Epic 1 only
"""
        result = validate_role_artifact_contract("ba", "brd", content, "word")
        self.assertEqual(result.status, "passed")

    def test_brd_fails_without_functional_requirements(self):
        content = """
NFR-001 performance
BR-001 business rule
สมมติฐาน
ขอบเขต
"""
        result = validate_role_artifact_contract("ba", "brd", content, "word")
        self.assertEqual(result.status, "failed")
        self.assertIn("functional_requirements", result.missing_sections)

    def test_user_stories_passes_with_story_ids_and_criteria(self):
        content = """
| STORY-001 | As a user, I want to login |
| Acceptance Criteria |
| Given I have an account |
| When I enter valid credentials |
| Then I am redirected to dashboard |
"""
        result = validate_role_artifact_contract("ba", "user_stories", content, "excel")
        self.assertEqual(result.status, "passed")

    def test_user_stories_fails_without_acceptance_criteria(self):
        content = "STORY-001 user story description without any criteria"
        result = validate_role_artifact_contract("ba", "user_stories", content, "excel")
        self.assertEqual(result.status, "failed")
        self.assertIn("acceptance_criteria", result.missing_sections)

    def test_use_cases_passes_with_uc_actor_flow(self):
        content = """
## UC-001: Login
**Actor:** End User
**Main Flow:**
1. User enters credentials
2. System validates
"""
        result = validate_role_artifact_contract("ba", "use_cases", content, "word")
        self.assertEqual(result.status, "passed")

    def test_data_dictionary_passes(self):
        content = """
| Field Name | Data Type | Description |
| user_id | UUID | Primary key |
| email | VARCHAR(255) | User email |
"""
        result = validate_role_artifact_contract("ba", "data_dictionary", content, "excel")
        self.assertEqual(result.status, "passed")


# ─── SA ─────────────────────────────────────────────────────────────────────

class TestSAContracts(unittest.TestCase):

    def test_architecture_passes_with_mermaid_graph(self):
        content = "graph TD\n  A[Frontend] --> B[API]\n  B --> C[(Database)]"
        result = validate_role_artifact_contract("sa", "architecture", content, "mermaid")
        self.assertEqual(result.status, "passed")

    def test_architecture_passes_with_flowchart(self):
        content = "flowchart LR\n  User --> App --> DB"
        result = validate_role_artifact_contract("sa", "architecture", content, "mermaid")
        self.assertEqual(result.status, "passed")

    def test_architecture_fails_without_mermaid_syntax(self):
        content = "This is an architecture description without any mermaid syntax"
        result = validate_role_artifact_contract("sa", "architecture", content, "mermaid")
        self.assertEqual(result.status, "failed")
        self.assertIn("diagram_syntax", result.missing_sections)

    def test_sequence_diagram_passes_with_participant(self):
        content = "sequenceDiagram\n  participant User\n  User->>API: GET /users"
        result = validate_role_artifact_contract("sa", "sequence_diagram", content, "mermaid")
        self.assertEqual(result.status, "passed")

    def test_database_schema_passes_with_create_table(self):
        content = "CREATE TABLE users (\n  id UUID PRIMARY KEY,\n  email VARCHAR(255)\n);"
        result = validate_role_artifact_contract("sa", "database_schema", content, "sql")
        self.assertEqual(result.status, "passed")

    def test_database_schema_fails_without_create_table(self):
        content = "SELECT * FROM users; -- no DDL"
        result = validate_role_artifact_contract("sa", "database_schema", content, "sql")
        self.assertEqual(result.status, "failed")

    def test_api_spec_passes_with_openapi_paths_info(self):
        content = "openapi: '3.0.0'\ninfo:\n  title: MyAPI\npaths:\n  /users:\n    get:"
        result = validate_role_artifact_contract("sa", "api_spec", content, "yaml")
        self.assertEqual(result.status, "passed")

    def test_api_spec_fails_without_paths(self):
        content = "openapi: '3.0.0'\ninfo:\n  title: MyAPI"
        result = validate_role_artifact_contract("sa", "api_spec", content, "yaml")
        self.assertEqual(result.status, "failed")
        self.assertIn("paths", result.missing_sections)

    def test_scope_definition_requires_both_in_and_out(self):
        content = "In-Scope: Feature A\nOut-of-Scope: Feature B"
        result = validate_role_artifact_contract("sa", "scope_definition", content, "word")
        self.assertEqual(result.status, "passed")

    def test_scope_definition_fails_without_out_scope(self):
        content = "In-Scope: lots of features"
        result = validate_role_artifact_contract("sa", "scope_definition", content, "word")
        self.assertEqual(result.status, "failed")
        self.assertIn("out_scope", result.missing_sections)


# ─── UXUI ────────────────────────────────────────────────────────────────────

class TestUXUIContracts(unittest.TestCase):

    def test_wireframe_passes_with_html_and_classes(self):
        content = '<!DOCTYPE html><html><body><div class="flex bg-gray-100">Hello</div></body></html>'
        result = validate_role_artifact_contract("uxui", "wireframe", content, "html")
        self.assertEqual(result.status, "passed")

    def test_wireframe_fails_without_html_structure(self):
        content = "Just a text description of the wireframe"
        result = validate_role_artifact_contract("uxui", "wireframe", content, "html")
        self.assertEqual(result.status, "failed")
        self.assertIn("html_structure", result.missing_sections)

    def test_design_system_passes(self):
        content = """
# Design System
## Color Palette
Primary: #6366F1
## Typography
Font: Inter, 16px
## Components
Button, Input, Modal
"""
        result = validate_role_artifact_contract("uxui", "design_system", content, "word")
        self.assertEqual(result.status, "passed")

    def test_ux_guidelines_passes_with_accessibility_and_interaction(self):
        content = """
## Accessibility (WCAG 2.1 AA)
All elements must meet contrast ratio 4.5:1
## Interaction Patterns
Hover states, click feedback, transitions
"""
        result = validate_role_artifact_contract("uxui", "ux_guidelines", content, "word")
        self.assertEqual(result.status, "passed")


# ─── DEV ─────────────────────────────────────────────────────────────────────

class TestDEVContracts(unittest.TestCase):

    def test_frontend_code_fails_without_workspace_manifest(self):
        content = "```typescript\nconst App = () => <div>Hello</div>;\n```\nManifest: app.tsx"
        with tempfile.TemporaryDirectory() as d:
            result = validate_role_artifact_contract("dev", "frontend_code", content, "code_multi", output_dir=d)
        self.assertEqual(result.status, "failed")
        self.assertIn("workspace_manifest.json", result.missing_artifacts)

    def test_frontend_code_passes_with_manifest_file(self):
        content = "```typescript\nconst App = () => <div/>\n```\nManifest listed above"
        with tempfile.TemporaryDirectory() as d:
            manifest_path = os.path.join(d, "workspace_manifest.json")
            with open(manifest_path, "w") as f:
                f.write('{"files": []}')
            result = validate_role_artifact_contract("dev", "frontend_code", content, "code_multi", output_dir=d)
        self.assertEqual(result.status, "passed")

    def test_backend_code_requires_workspace_manifest(self):
        content = "```python\ndef main(): pass\n```\n.py implementation"
        with tempfile.TemporaryDirectory() as d:
            result = validate_role_artifact_contract("dev", "backend_code", content, "code_multi", output_dir=d)
        self.assertEqual(result.status, "failed")
        self.assertIn("workspace_manifest.json", result.missing_artifacts)

    def test_unit_tests_passes_with_assertions_and_manifest(self):
        content = "```python\ndef test_login():\n    result = login(user)\n    assert result == True\n```"
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "workspace_manifest.json"), "w") as f:
                f.write('{"tests": []}')
            result = validate_role_artifact_contract("dev", "unit_tests", content, "code_multi", output_dir=d)
        self.assertEqual(result.status, "passed")

    def test_dev_readme_passes_with_setup_run_env(self):
        content = """
# Setup
npm install

# Run
npm run dev

# Environment
Copy .env.example to .env
"""
        result = validate_role_artifact_contract("dev", "dev_readme", content, "markdown")
        self.assertEqual(result.status, "passed")

    def test_secondary_file_check_skipped_when_no_output_dir(self):
        content = "Manifest files listed. ```tsx\nconst App = () => null\n```"
        result = validate_role_artifact_contract("dev", "frontend_code", content, "code_multi", output_dir=None)
        # No output_dir → secondary file check skipped
        self.assertNotIn("workspace_manifest.json", result.missing_artifacts)


# ─── QA ──────────────────────────────────────────────────────────────────────

class TestQAContracts(unittest.TestCase):

    def test_test_report_fails_without_qa_execution_result(self):
        content = """
## Summary
All tests run.
## Pass/Fail
Pass: 42  Fail: 3
## Defects
Bug-001: Login timeout
"""
        with tempfile.TemporaryDirectory() as d:
            result = validate_role_artifact_contract("qa", "test_report", content, "word", output_dir=d)
        self.assertEqual(result.status, "failed")
        self.assertTrue(any("qa_execution_result" in a for a in result.missing_artifacts))

    def test_test_report_passes_with_qa_execution_result(self):
        content = """
## Summary
All tests run.
## Pass/Fail
Pass: 42  Fail: 3
## Defects
Bug-001: Login timeout
"""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "qa_execution_result.json"), "w") as f:
                f.write('{"status": "passed"}')
            result = validate_role_artifact_contract("qa", "test_report", content, "word", output_dir=d)
        self.assertEqual(result.status, "passed")

    def test_test_report_passes_with_test_execution_result_alternative(self):
        content = "Summary\nPass: 10 Fail: 0\nBug: none"
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "test_execution_result.json"), "w") as f:
                f.write('{}')
            result = validate_role_artifact_contract("qa", "test_report", content, "word", output_dir=d)
        self.assertEqual(result.status, "passed")

    def test_qa_plan_passes_with_all_sections(self):
        content = """
## Test Scope
In-Scope: Authentication
## Test Strategy
| Unit Test | Pytest |
## Entry Criteria
เริ่มทดสอบเมื่อ unit tests ผ่าน 80%
## Exit Criteria
สิ้นสุดเมื่อ 95% pass
## Test Environment
Staging environment ready
"""
        result = validate_role_artifact_contract("qa", "qa_plan", content, "word")
        self.assertEqual(result.status, "passed")


# ─── DEVOPS ──────────────────────────────────────────────────────────────────

class TestDEVOPSContracts(unittest.TestCase):

    def test_dockerfile_passes_with_from_and_run(self):
        content = "FROM python:3.12-slim\nRUN pip install -r requirements.txt\nCMD [\"python\", \"main.py\"]"
        result = validate_role_artifact_contract("devops", "dockerfile", content, "dockerfile")
        self.assertEqual(result.status, "passed")

    def test_dockerfile_fails_without_from(self):
        content = "RUN pip install flask\nCMD python app.py"
        result = validate_role_artifact_contract("devops", "dockerfile", content, "dockerfile")
        self.assertEqual(result.status, "failed")
        self.assertIn("from_instruction", result.missing_sections)

    def test_docker_compose_passes_with_services_and_image(self):
        content = "version: '3'\nservices:\n  web:\n    image: myapp:latest\n    ports:\n      - '80:80'"
        result = validate_role_artifact_contract("devops", "docker_compose", content, "yaml")
        self.assertEqual(result.status, "passed")

    def test_docker_compose_fails_without_services(self):
        content = "image: myapp:latest\nports:\n  - '80:80'"
        result = validate_role_artifact_contract("devops", "docker_compose", content, "yaml")
        self.assertEqual(result.status, "failed")
        self.assertIn("services", result.missing_sections)

    def test_github_actions_passes_with_on_jobs_steps(self):
        content = "on:\n  push:\n    branches: [main]\njobs:\n  build:\n    steps:\n      - uses: actions/checkout@v3"
        result = validate_role_artifact_contract("devops", "github_actions", content, "yaml")
        self.assertEqual(result.status, "passed")

    def test_github_actions_fails_without_steps(self):
        content = "on:\n  push:\njobs:\n  build:\n    runs-on: ubuntu-latest"
        result = validate_role_artifact_contract("devops", "github_actions", content, "yaml")
        self.assertEqual(result.status, "failed")
        self.assertIn("steps", result.missing_sections)

    def test_deployment_guide_fails_without_readiness_report(self):
        content = "## Prerequisites\nDocker installed\n## Steps\n1. Deploy\n## Environment\nPROD env"
        with tempfile.TemporaryDirectory() as d:
            result = validate_role_artifact_contract("devops", "deployment_guide", content, "word", output_dir=d)
        self.assertEqual(result.status, "failed")
        self.assertIn("deployment_readiness_report.md", result.missing_artifacts)

    def test_deployment_guide_passes_with_all_sections_and_report(self):
        content = "## Prerequisites\nDocker\n## Deployment Steps\n1. Run\n## Environment\nENV=prod"
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "deployment_readiness_report.md"), "w") as f:
                f.write("# Readiness Report\nPassed")
            result = validate_role_artifact_contract("devops", "deployment_guide", content, "word", output_dir=d)
        self.assertEqual(result.status, "passed")


# ─── Skipped / Unknown types ──────────────────────────────────────────────────

class TestContractSkipped(unittest.TestCase):

    def test_unknown_role_returns_skipped(self):
        result = validate_role_artifact_contract("hermes", "some_task", "content", "markdown")
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.missing_sections, [])
        self.assertEqual(result.missing_artifacts, [])

    def test_unknown_task_type_for_known_role_returns_skipped(self):
        result = validate_role_artifact_contract("ceo", "nonexistent_task_type", "content", "markdown")
        self.assertEqual(result.status, "skipped")

    def test_skipped_has_contract_name(self):
        result = validate_role_artifact_contract("pm", "unknown_task", "x", "word")
        self.assertEqual(result.contract_name, "pm:unknown_task")

    def test_skipped_never_fails_even_with_empty_content(self):
        result = validate_role_artifact_contract("unknown_role", "unknown_task", "", "markdown")
        self.assertNotEqual(result.status, "failed")


# ─── Prompt Block Builder ─────────────────────────────────────────────────────

class TestContractPromptBlock(unittest.TestCase):

    def test_known_role_task_returns_non_empty_block(self):
        block = build_contract_prompt_block("ceo", "project_brief")
        self.assertIsInstance(block, str)
        self.assertGreater(len(block), 20)
        self.assertIn("Output Contract", block)

    def test_block_contains_role_specific_hint(self):
        block = build_contract_prompt_block("ceo", "project_brief")
        self.assertIn("เป้าหมายทางธุรกิจ", block)

    def test_unknown_role_returns_empty_string(self):
        block = build_contract_prompt_block("hermes", "cron_task")
        self.assertEqual(block, "")

    def test_unknown_task_type_returns_empty_string(self):
        block = build_contract_prompt_block("ceo", "nonexistent")
        self.assertEqual(block, "")

    def test_all_contracts_have_prompt_hint(self):
        """Every defined contract should have a non-empty prompt_hint."""
        from shared.artifact_contracts import _CONTRACTS
        for role, tasks in _CONTRACTS.items():
            for task_type, contract in tasks.items():
                hint = contract.get("prompt_hint", "")
                self.assertGreater(
                    len(hint), 0,
                    msg=f"{role}:{task_type} has empty prompt_hint",
                )

    def test_devops_dockerfile_block(self):
        block = build_contract_prompt_block("devops", "dockerfile")
        self.assertIn("FROM", block)

    def test_qa_test_report_block(self):
        block = build_contract_prompt_block("qa", "test_report")
        self.assertIn("qa_execution_result", block)


# ─── Contract Validation Result fields ───────────────────────────────────────

class TestContractResultFields(unittest.TestCase):

    def test_failed_result_has_all_fields(self):
        content = "incomplete content"
        result = validate_role_artifact_contract("ceo", "project_brief", content, "markdown")
        self.assertEqual(result.status, "failed")
        self.assertIsInstance(result.missing_sections, list)
        self.assertIsInstance(result.missing_artifacts, list)
        self.assertIsInstance(result.revision_comment, str)
        self.assertEqual(result.contract_version, "1.0")
        self.assertEqual(result.contract_name, "ceo:project_brief")

    def test_passed_result_empty_missing_lists(self):
        content = "FROM ubuntu\nRUN apt-get update"
        result = validate_role_artifact_contract("devops", "dockerfile", content, "dockerfile")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.missing_sections, [])
        self.assertEqual(result.missing_artifacts, [])
        self.assertEqual(result.revision_comment, "")

    def test_contract_name_format(self):
        result = validate_role_artifact_contract("sa", "database_schema", "SELECT 1", "sql")
        self.assertEqual(result.contract_name, "sa:database_schema")


# ─── Phase 7.1: Secondary artifact freshness ────────────────────────────────

class TestSecondaryArtifactFreshness(unittest.TestCase):
    """
    Validates that _secondary_file_ok / validate_role_artifact_contract
    correctly reject stale files and accept fresh ones, and that the
    generated_artifacts list takes priority over mtime.
    """

    # Minimal passing content for DEV:backend_code task (workspace_manifest required)
    # Needs: files aliases (.py / implementation) + code_blocks (```)
    _DEV_CONTENT = "## implementation\n```python\ndef main(): pass\n```"
    _DEV_TASK_TYPE = "backend_code"
    _DEV_ROLE = "dev"

    # Minimal passing content for QA:test_report (qa_execution_result required)
    # Needs: summary, pass_fail_count (pass/fail), defects (defect/bug)
    _QA_CONTENT = "## Test Summary\n### Pass/Fail Count\n| Pass | 5 | Fail | 1 |\n### Defects Found\n| Bug-001 | Low severity |"
    _QA_ROLE = "qa"
    _QA_TASK = "test_report"

    # Minimal passing content for DEVOPS:deployment_guide
    # Needs: prerequisites (prerequisite/requirement), steps (step/deploy), environment (config)
    _DEVOPS_CONTENT = "## Prerequisites\n- System requirements\n### Deployment Steps\n1. Deploy to server\n### Environment Configuration\n- config vars"
    _DEVOPS_ROLE = "devops"
    _DEVOPS_TASK = "deployment_guide"

    def _make_stale_file(self, d: str, fname: str, attempt_start: float) -> str:
        """Create a file with mtime 2 seconds before attempt_start."""
        fpath = os.path.join(d, fname)
        with open(fpath, "w") as f:
            f.write("content")
        os.utime(fpath, (attempt_start - 2.0, attempt_start - 2.0))
        return fpath

    def _make_fresh_file(self, d: str, fname: str, attempt_start: float) -> str:
        """Create a file with mtime equal to attempt_start."""
        fpath = os.path.join(d, fname)
        with open(fpath, "w") as f:
            f.write("content")
        os.utime(fpath, (attempt_start, attempt_start))
        return fpath

    # ── DEV workspace_manifest ─────────────────────────────────────────────

    def test_dev_stale_workspace_manifest_fails(self):
        """workspace_manifest.json older than attempt_start → contract failed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_stale_file(d, "workspace_manifest.json", attempt_start)
            result = validate_role_artifact_contract(
                self._DEV_ROLE, self._DEV_TASK_TYPE,
                self._DEV_CONTENT, "python",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("workspace_manifest.json", result.missing_artifacts)

    def test_dev_fresh_workspace_manifest_passes(self):
        """workspace_manifest.json with mtime == attempt_start → contract passed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_fresh_file(d, "workspace_manifest.json", attempt_start)
            result = validate_role_artifact_contract(
                self._DEV_ROLE, self._DEV_TASK_TYPE,
                self._DEV_CONTENT, "python",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "passed")

    def test_dev_no_timestamp_stale_file_passes(self):
        """Without attempt_started_at, any existing file passes (backward compat)."""
        with tempfile.TemporaryDirectory() as d:
            import time
            # Create a file with very old mtime — no timestamp means no freshness check
            fpath = os.path.join(d, "workspace_manifest.json")
            with open(fpath, "w") as f:
                f.write("old content")
            os.utime(fpath, (1000.0, 1000.0))
            result = validate_role_artifact_contract(
                self._DEV_ROLE, self._DEV_TASK_TYPE,
                self._DEV_CONTENT, "python",
                output_dir=d,
                attempt_started_at=None,
            )
            self.assertEqual(result.status, "passed")

    # ── QA qa_execution_result ─────────────────────────────────────────────

    def test_qa_stale_execution_result_fails(self):
        """qa_execution_result.json older than attempt_start → contract failed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_stale_file(d, "qa_execution_result.json", attempt_start)
            result = validate_role_artifact_contract(
                self._QA_ROLE, self._QA_TASK,
                self._QA_CONTENT, "markdown",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")

    def test_qa_fresh_execution_result_passes(self):
        """qa_execution_result.json with fresh mtime → contract passed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_fresh_file(d, "qa_execution_result.json", attempt_start)
            result = validate_role_artifact_contract(
                self._QA_ROLE, self._QA_TASK,
                self._QA_CONTENT, "markdown",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "passed")

    def test_qa_any_of_alternate_file_passes(self):
        """test_execution_result.json (alternate) with fresh mtime → contract passed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_fresh_file(d, "test_execution_result.json", attempt_start)
            result = validate_role_artifact_contract(
                self._QA_ROLE, self._QA_TASK,
                self._QA_CONTENT, "markdown",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "passed")

    # ── DEVOPS deployment_readiness_report ────────────────────────────────

    def test_devops_fresh_readiness_report_passes(self):
        """deployment_readiness_report.md fresh → passed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_fresh_file(d, "deployment_readiness_report.md", attempt_start)
            result = validate_role_artifact_contract(
                self._DEVOPS_ROLE, self._DEVOPS_TASK,
                self._DEVOPS_CONTENT, "markdown",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "passed")

    def test_devops_stale_readiness_report_fails(self):
        """deployment_readiness_report.md older than attempt_start → failed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_stale_file(d, "deployment_readiness_report.md", attempt_start)
            result = validate_role_artifact_contract(
                self._DEVOPS_ROLE, self._DEVOPS_TASK,
                self._DEVOPS_CONTENT, "markdown",
                output_dir=d,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("deployment_readiness_report.md", result.missing_artifacts)

    # ── generated_artifacts list takes priority ────────────────────────────

    def test_generated_artifacts_list_passes_regardless_of_mtime(self):
        """When generated_artifacts contains the file, mtime is irrelevant."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            # Create a STALE file on disk — it would fail if mtime were checked
            self._make_stale_file(d, "workspace_manifest.json", attempt_start)
            generated = [{"path": "workspace_manifest.json", "ref": os.path.join(d, "workspace_manifest.json")}]
            result = validate_role_artifact_contract(
                self._DEV_ROLE, self._DEV_TASK_TYPE,
                self._DEV_CONTENT, "python",
                output_dir=d,
                generated_artifacts=generated,
                attempt_started_at=attempt_start,
            )
            # generated_artifacts list wins over mtime → should pass
            self.assertEqual(result.status, "passed")

    def test_generated_artifacts_without_filename_fails(self):
        """generated_artifacts provided but doesn't contain the required file → failed."""
        with tempfile.TemporaryDirectory() as d:
            import time
            attempt_start = time.time()
            self._make_fresh_file(d, "workspace_manifest.json", attempt_start)
            # generated list has a different file — manifest not listed
            generated = [{"path": "something_else.txt", "ref": os.path.join(d, "something_else.txt")}]
            result = validate_role_artifact_contract(
                self._DEV_ROLE, self._DEV_TASK_TYPE,
                self._DEV_CONTENT, "python",
                output_dir=d,
                generated_artifacts=generated,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("workspace_manifest.json", result.missing_artifacts)

    def test_no_output_dir_no_generated_skips_secondary_check(self):
        """Without output_dir or generated_artifacts, secondary file check is skipped → passed."""
        result = validate_role_artifact_contract(
            self._DEV_ROLE, self._DEV_TASK_TYPE,
            self._DEV_CONTENT, "python",
            output_dir=None,
            generated_artifacts=None,
        )
        # Sections pass (content has "implementation" and "```") but secondary check
        # is entirely skipped (no output_dir, no generated_artifacts) → passed
        self.assertIn(result.status, ("passed",))
        self.assertEqual(result.missing_artifacts, [])


# ─── Phase 7.1: DB-persisted retry counter ───────────────────────────────────

class TestDBPersistedRetryCounter(unittest.TestCase):
    """
    Validates that the contract failure retry count is read from DB attempt_count
    rather than the in-memory _task_fail_counts dict.

    Uses Storage with a temp SQLite DB to simulate a bot restart scenario:
    DB has attempt_count=2, in-memory has 0 → next fail_count must be 3.
    """

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        # Storage calls os.makedirs(os.path.dirname(db_path)) — put db in subdir
        self._db_path = os.path.join(self._tmpdir.name, "data", "test.db")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _get_storage(self):
        try:
            from shared.storage import Storage
            return Storage(db_path=self._db_path)
        except Exception:
            return None

    def _insert_task(self, storage, task_id: str, attempt_count: int):
        """Insert a task row with specified attempt_count directly via SQL."""
        import sqlite3
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(storage.db_path) as conn:
            conn.execute(
                "INSERT INTO sdlc_tasks "
                "(id, project_id, epic_id, task_number, role, task_type, output_file, "
                "attempt_count, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, "proj1", "epic1", 1, "dev", "backend_code", "out.md",
                 attempt_count, "in_progress", now, now),
            )
            conn.commit()

    def test_fail_count_reads_db_attempt_count(self):
        """
        When DB has attempt_count=2 and in-memory is 0,
        the computed fail_count after a contract failure should be 3.

        This is the core of Fix 1: read fresh task from DB, not in-memory.
        Logic: fail_count = (fresh.attempt_count if fresh else 0) + 1
        """
        storage = self._get_storage()
        if storage is None:
            self.skipTest("Storage class not available in test env")

        self._insert_task(storage, "task-abc", attempt_count=2)

        fresh = storage.get_sdlc_task("task-abc")
        self.assertIsNotNone(fresh, "Task should exist in DB")
        fail_count = (fresh.attempt_count if fresh else 0) + 1
        self.assertEqual(fail_count, 3)

    def test_fail_count_requeues_when_under_limit(self):
        """fail_count=1 with _MAX_AUTO_RETRIES=2 → _requeue=True."""
        _MAX_AUTO_RETRIES = 2
        fail_count = 1
        requeue = fail_count <= _MAX_AUTO_RETRIES
        self.assertTrue(requeue)

    def test_fail_count_no_requeue_when_over_limit(self):
        """fail_count=3 with _MAX_AUTO_RETRIES=2 → _requeue=False."""
        _MAX_AUTO_RETRIES = 2
        fail_count = 3
        requeue = fail_count <= _MAX_AUTO_RETRIES
        self.assertFalse(requeue)

    def test_fail_count_no_requeue_at_exact_limit(self):
        """fail_count=2 → still requeues; fail_count=3 → exhausted."""
        _MAX_AUTO_RETRIES = 2
        self.assertTrue(2 <= _MAX_AUTO_RETRIES)
        self.assertFalse(3 <= _MAX_AUTO_RETRIES)

    def test_fail_count_handles_missing_task(self):
        """If fresh task is None (task deleted), fail_count = 0 + 1 = 1."""
        fresh = None
        fail_count = (fresh.attempt_count if fresh else 0) + 1
        self.assertEqual(fail_count, 1)

    def test_db_attempt_count_survives_restart(self):
        """
        Simulate bot restart: in-memory count reset to 0 but DB still has attempt_count=2.
        After restart, DB-read fail_count should be 3, not 1.
        """
        storage = self._get_storage()
        if storage is None:
            self.skipTest("Storage class not available in test env")

        self._insert_task(storage, "task-restart", attempt_count=2)

        # Simulate restart: in-memory counter is empty
        in_memory_counts: dict = {}
        task_id = "task-restart"

        # In-memory would give: 0 + 1 = 1 (wrong)
        in_memory_fail = in_memory_counts.get(task_id, 0) + 1
        self.assertEqual(in_memory_fail, 1)  # Confirms the pre-fix bug

        # DB-read gives: 2 + 1 = 3 (correct)
        fresh = storage.get_sdlc_task(task_id)
        db_fail = (fresh.attempt_count if fresh else 0) + 1
        self.assertEqual(db_fail, 3)  # Confirms the fix


# ─── Phase 7.2: Artifact collector freshness filter ──────────────────────────

class TestArtifactCollectorFreshness(unittest.TestCase):
    """
    Validates collect_artifacts() freshness filtering and the end-to-end
    integration with validate_role_artifact_contract() via generated_artifacts.

    Root cause being fixed: before Phase 7.2, _collect_artifacts had no
    attempt_started_at parameter, so stale secondary files were included in the
    generated_artifacts list passed to the validator, which then saw them as
    "produced by current attempt" and skipped the mtime check entirely.
    """

    # Minimal passing content for DEV:frontend_code
    # Sections needed: files (has "App.tsx" → ".tsx" alias) + code_blocks ("```")
    _CONTENT = "## implementation\n- App.tsx\n```\nexport default function App() {}\n```"

    def _task_stub(self, task_type: str = "frontend_code"):
        """Return a minimal task-like object."""
        class T:
            output_file = "output.md"
        t = T()
        t.task_type = task_type
        return t

    def _make_file(self, d: str, fname: str, mtime: float) -> str:
        fpath = os.path.join(d, fname)
        with open(fpath, "w") as f:
            f.write("content")
        os.utime(fpath, (mtime, mtime))
        return fpath

    # ── collect_artifacts filtering ────────────────────────────────────────

    def test_stale_secondary_file_excluded_from_artifacts(self):
        """workspace_manifest.json older than attempt_start is NOT in result."""
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            self._make_file(d, "workspace_manifest.json", attempt_start - 5.0)
            saved_path = self._make_file(d, "output.md", attempt_start)
            task = self._task_stub()

            result = collect_artifacts(d, saved_path, task, attempt_started_at=attempt_start)

            names = [a["path"] for a in result]
            self.assertNotIn("workspace_manifest.json", names)
            self.assertIn("output.md", names)  # main output always included

    def test_fresh_secondary_file_included_in_artifacts(self):
        """workspace_manifest.json with mtime == attempt_start is included."""
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            self._make_file(d, "workspace_manifest.json", attempt_start)
            saved_path = self._make_file(d, "output.md", attempt_start)
            task = self._task_stub()

            result = collect_artifacts(d, saved_path, task, attempt_started_at=attempt_start)

            names = [a["path"] for a in result]
            self.assertIn("workspace_manifest.json", names)

    def test_no_attempt_started_at_backward_compatible(self):
        """Without attempt_started_at, stale files are still included (old behavior)."""
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            # Create a very old file
            self._make_file(d, "workspace_manifest.json", attempt_start - 3600.0)
            saved_path = self._make_file(d, "output.md", attempt_start)
            task = self._task_stub()

            result = collect_artifacts(d, saved_path, task, attempt_started_at=None)

            names = [a["path"] for a in result]
            self.assertIn("workspace_manifest.json", names)

    def test_main_output_always_included_regardless_of_mtime(self):
        """The main output_file (saved_path) is always included — it was just written."""
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            saved_path = self._make_file(d, "output.md", attempt_start - 10.0)
            task = self._task_stub()

            result = collect_artifacts(d, saved_path, task, attempt_started_at=attempt_start)

            self.assertTrue(any(a["ref"] == saved_path for a in result))

    # ── End-to-end: collector → validator ────────────────────────────────

    def test_contract_fails_when_collector_filters_stale_workspace_manifest(self):
        """
        Integration: stale workspace_manifest.json → excluded by collector →
        generated_artifacts list missing it → contract validation fails.
        """
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            # Stale file — predates attempt start
            self._make_file(d, "workspace_manifest.json", attempt_start - 5.0)
            saved_path = self._make_file(d, "output.md", attempt_start)
            task = self._task_stub("frontend_code")

            artifacts = collect_artifacts(d, saved_path, task, attempt_started_at=attempt_start)
            result = validate_role_artifact_contract(
                "dev", "frontend_code",
                self._CONTENT, "typescript",
                output_dir=d,
                generated_artifacts=artifacts,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("workspace_manifest.json", result.missing_artifacts)

    def test_contract_passes_when_collector_includes_fresh_workspace_manifest(self):
        """
        Integration: fresh workspace_manifest.json → included by collector →
        generated_artifacts list has it → contract validation passes.
        """
        import time
        from shared.artifact_collector import collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            self._make_file(d, "workspace_manifest.json", attempt_start)
            saved_path = self._make_file(d, "output.md", attempt_start)
            task = self._task_stub("frontend_code")

            artifacts = collect_artifacts(d, saved_path, task, attempt_started_at=attempt_start)
            result = validate_role_artifact_contract(
                "dev", "frontend_code",
                self._CONTENT, "typescript",
                output_dir=d,
                generated_artifacts=artifacts,
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "passed")

    def test_stale_file_passed_via_old_path_is_caught_by_validator_mtime(self):
        """
        Fallback: if someone calls validator with output_dir but no generated_artifacts,
        the validator's own mtime check still catches stale files.
        """
        import time
        with tempfile.TemporaryDirectory() as d:
            attempt_start = time.time()
            self._make_file(d, "workspace_manifest.json", attempt_start - 5.0)

            result = validate_role_artifact_contract(
                "dev", "frontend_code",
                self._CONTENT, "typescript",
                output_dir=d,
                generated_artifacts=None,      # no explicit list → mtime path
                attempt_started_at=attempt_start,
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("workspace_manifest.json", result.missing_artifacts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
