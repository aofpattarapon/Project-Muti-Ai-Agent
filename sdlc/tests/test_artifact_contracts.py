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


if __name__ == "__main__":
    unittest.main(verbosity=2)
