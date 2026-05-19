"""
artifact_contracts — Role-level artifact contract definitions and validation.

Each SDLC role must produce specific document sections and/or secondary files.
This module is discord-free and importable in tests without discord.py.

Usage:
    result = validate_role_artifact_contract(
        role="ceo", task_type="project_brief",
        content=llm_output, output_format="markdown",
        output_dir="/app/outputs/.../ceo",
    )
    if result.status == "failed":
        # requeue with result.revision_comment
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

CONTRACT_VERSION = "1.0"


@dataclass
class ContractValidationResult:
    status: str                           # "passed" | "failed" | "skipped"
    contract_name: str
    contract_version: str = CONTRACT_VERSION
    missing_sections: list = field(default_factory=list)
    missing_artifacts: list = field(default_factory=list)
    revision_comment: str = ""


# ─── Contract Definitions ─────────────────────────────────────────────────────
# Each entry: { "sections": [...], "secondary_files": [...], "prompt_hint": str }
#
# sections   : list of {"name": str, "aliases": [str]}
#              — section passes if ANY alias is found (case-insensitive substring)
# secondary_files : list of str (exact required filename) or
#              {"any": [str]} (at least one of these files must exist)
# prompt_hint: short English hint injected at end of prompts (max ~200 chars)

_CONTRACTS: dict[str, dict[str, dict]] = {

    # ── CEO ──────────────────────────────────────────────────────────────────
    "ceo": {
        "project_brief": {
            "sections": [
                {"name": "business_goal", "aliases": ["เป้าหมายทางธุรกิจ", "business goal", "business objective"]},
                {"name": "success_metrics", "aliases": ["เกณฑ์ความสำเร็จ", "ตัวชี้วัด", "kpi", "success metric"]},
                {"name": "scope", "aliases": ["mvp scope", "นอก scope", "ขอบเขต", "scope"]},
                {"name": "risks", "aliases": ["ความเสี่ยง", "risk"]},
                {"name": "stakeholders", "aliases": ["ผู้มีส่วนได้เสีย", "stakeholder"]},
            ],
            "secondary_files": [],
            "prompt_hint": (
                "Required sections: เป้าหมายทางธุรกิจ (business goal), "
                "เกณฑ์ความสำเร็จ/KPI, Scope, ความเสี่ยง (risks), ผู้มีส่วนได้เสีย (stakeholders). "
                "Missing any section will cause automatic retry."
            ),
        },
        "epics": {
            "sections": [
                {"name": "epic_id", "aliases": ["epic-", "EPIC-"]},
                {"name": "acceptance_criteria", "aliases": ["acceptance criteria", "เกณฑ์การยอมรับ", "เกณฑ์"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: EPIC-NNN IDs and Acceptance Criteria per epic.",
        },
    },

    # ── PM ───────────────────────────────────────────────────────────────────
    "pm": {
        "project_charter": {
            "sections": [
                {"name": "objectives", "aliases": ["วัตถุประสงค์", "objective", "project purpose"]},
                {"name": "scope", "aliases": ["scope", "ขอบเขต"]},
                {"name": "stakeholders", "aliases": ["stakeholder", "ผู้มีส่วนได้เสีย"]},
                {"name": "milestone", "aliases": ["milestone", "ไทม์ไลน์", "timeline"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required sections: objectives, scope, stakeholders, milestone/timeline.",
        },
        "project_management_plan": {
            "sections": [
                {"name": "schedule", "aliases": ["schedule", "ตารางเวลา", "timeline"]},
                {"name": "resources", "aliases": ["resource", "ทรัพยากร"]},
                {"name": "milestone", "aliases": ["milestone"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: schedule, resources, milestone.",
        },
        "raci_matrix": {
            "sections": [
                {"name": "responsible", "aliases": ["responsible", "รับผิดชอบ"]},
                {"name": "accountable", "aliases": ["accountable"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required RACI columns: Responsible, Accountable.",
        },
        "risk_register": {
            "sections": [
                {"name": "risk_id", "aliases": ["risk-", "RISK-", "ความเสี่ยง", "R-"]},
                {"name": "probability", "aliases": ["probability", "likelihood", "โอกาส"]},
                {"name": "mitigation", "aliases": ["mitigation", "มาตรการ"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: Risk IDs, probability, mitigation actions.",
        },
        "communications_plan": {
            "sections": [
                {"name": "stakeholder", "aliases": ["stakeholder", "ผู้มีส่วนได้เสีย"]},
                {"name": "channel", "aliases": ["channel", "ช่องทาง", "communication"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: stakeholder list, communication channels.",
        },
        "project_status_report": {
            "sections": [
                {"name": "status", "aliases": ["status", "สถานะ"]},
                {"name": "milestone", "aliases": ["milestone", "สำเร็จ"]},
                {"name": "issues", "aliases": ["issue", "ปัญหา", "blocker", "risk"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: status, milestone progress, issues/blockers.",
        },
    },

    # ── BA ───────────────────────────────────────────────────────────────────
    "ba": {
        "brd": {
            "sections": [
                {"name": "functional_requirements", "aliases": [" fr-", "functional requirement", "ความต้องการฟังก์ชัน"]},
                {"name": "non_functional", "aliases": ["nfr-", "non-functional", "non functional"]},
                {"name": "business_rules", "aliases": ["br-", "business rule", "กฎทางธุรกิจ"]},
                {"name": "assumptions", "aliases": ["สมมติฐาน", "assumption"]},
                {"name": "scope", "aliases": ["ขอบเขต", "scope"]},
            ],
            "secondary_files": [],
            "prompt_hint": (
                "Required: FR-NNN functional requirements, NFR-NNN non-functional, "
                "BR-NNN business rules, assumptions, scope."
            ),
        },
        "srs": {
            "sections": [
                {"name": "functional_spec", "aliases": ["fr-", "functional", "ฟังก์ชัน"]},
                {"name": "non_functional", "aliases": ["nfr-", "non-functional", "non functional"]},
                {"name": "system_overview", "aliases": ["system overview", "overview", "ภาพรวม"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: functional spec (FR-NNN), non-functional (NFR-NNN), system overview.",
        },
        "user_stories": {
            "sections": [
                {"name": "story_id", "aliases": ["story-", "us-", "ในฐานะ", "as a"]},
                {"name": "acceptance_criteria", "aliases": ["acceptance criteria", "เงื่อนไขการยอมรับ", "given", "when"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: story IDs (STORY-NNN or US-NNN), acceptance criteria per story.",
        },
        "use_cases": {
            "sections": [
                {"name": "use_case_id", "aliases": ["uc-", "use case", "use-case"]},
                {"name": "actor", "aliases": ["actor", "ผู้ใช้งาน", "ผู้ดำเนินการ"]},
                {"name": "flow", "aliases": ["main flow", "basic flow", "ขั้นตอนหลัก", "flow"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: UC-NNN IDs, actors, main flow per use case.",
        },
        "data_dictionary": {
            "sections": [
                {"name": "field_name", "aliases": ["field name", "ชื่อ field", "column", "ฟิลด์"]},
                {"name": "data_type", "aliases": ["data type", "ประเภทข้อมูล", "type"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: field names, data types, descriptions.",
        },
    },

    # ── SA ───────────────────────────────────────────────────────────────────
    "sa": {
        "system_purpose": {
            "sections": [
                {"name": "system_purpose", "aliases": ["system purpose", "วัตถุประสงค์ระบบ", "วัตถุประสงค์"]},
                {"name": "scope", "aliases": ["scope", "ขอบเขต"]},
                {"name": "goals", "aliases": ["goal", "objective", "เป้าหมาย"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: system purpose, goals/objectives, scope.",
        },
        "scope_definition": {
            "sections": [
                {"name": "in_scope", "aliases": ["in-scope", "in scope", "ขอบเขตที่รวม"]},
                {"name": "out_scope", "aliases": ["out-of-scope", "out of scope", "out scope", "นอกขอบเขต"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: In-Scope list and Out-of-Scope list.",
        },
        "architecture": {
            "sections": [
                {"name": "diagram_syntax", "aliases": ["graph ", "flowchart ", "classDiagram", "C4Context", "C4Container", "architecture-beta"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid diagram syntax (graph/flowchart/classDiagram/C4Context).",
        },
        "sequence_diagram": {
            "sections": [
                {"name": "sequence_syntax", "aliases": ["sequenceDiagram", "participant "]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid sequenceDiagram with participant declarations.",
        },
        "activity_workflow": {
            "sections": [
                {"name": "flow_syntax", "aliases": ["flowchart ", "graph ", "stateDiagram", "state "]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid flowchart or stateDiagram syntax.",
        },
        "service_decomposition": {
            "sections": [
                {"name": "service", "aliases": ["service", "บริการ", "Service"]},
                {"name": "component", "aliases": ["component", "ส่วนประกอบ", "Component"]},
                {"name": "api_interface", "aliases": ["api", "interface", "Interface", "endpoint"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: services list, components, API/interfaces.",
        },
        "integration_landscape": {
            "sections": [
                {"name": "diagram_syntax", "aliases": ["graph ", "flowchart ", "C4Context", "integration", "-->"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid diagram showing integration points.",
        },
        "deployment_model": {
            "sections": [
                {"name": "diagram_syntax", "aliases": ["graph ", "flowchart ", "C4Deployment", "deployment", "container"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid deployment diagram.",
        },
        "database_schema": {
            "sections": [
                {"name": "create_table", "aliases": ["CREATE TABLE", "create table"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: SQL DDL with at least one CREATE TABLE statement.",
        },
        "api_spec": {
            "sections": [
                {"name": "openapi_version", "aliases": ["openapi:", 'openapi: "', "openapi: '"]},
                {"name": "paths", "aliases": ["paths:"]},
                {"name": "info", "aliases": ["info:"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid OpenAPI YAML with openapi version, info, and paths sections.",
        },
        "sa_data_dictionary": {
            "sections": [
                {"name": "entity", "aliases": ["entity", "table", "ตาราง", "Entity"]},
                {"name": "data_type", "aliases": ["data type", "type", "ประเภทข้อมูล"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: entity/table names, field definitions with data types.",
        },
    },

    # ── UXUI ─────────────────────────────────────────────────────────────────
    "uxui": {
        "user_flow": {
            "sections": [
                {"name": "diagram_syntax", "aliases": ["graph ", "flowchart ", "-->", "stateDiagram"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid flowchart/graph for user flow.",
        },
        "wireframe": {
            "sections": [
                {"name": "html_structure", "aliases": ["<html", "<body", "<div", "<!doctype"]},
                {"name": "styling", "aliases": ["class=", "tailwind", "style="]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid HTML with body/div elements and Tailwind/CSS classes.",
        },
        "design_system": {
            "sections": [
                {"name": "colors", "aliases": ["color", "สี", "palette", "Color"]},
                {"name": "typography", "aliases": ["typography", "font", "Typography", "ตัวอักษร"]},
                {"name": "components", "aliases": ["component", "Component", "ส่วนประกอบ"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: color palette, typography, component definitions.",
        },
        "ux_guidelines": {
            "sections": [
                {"name": "accessibility", "aliases": ["accessibility", "wcag", "a11y", "การเข้าถึง"]},
                {"name": "interaction", "aliases": ["interaction", "Interaction", "การโต้ตอบ"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: accessibility (WCAG) guidelines, interaction patterns.",
        },
    },

    # ── DEV ──────────────────────────────────────────────────────────────────
    "dev": {
        "frontend_structure": {
            "sections": [
                {"name": "tech_stack", "aliases": ["tech stack", "technology", "framework", "Tech Stack"]},
                {"name": "structure", "aliases": ["structure", "src/", "components/", "folder", "directory"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: tech stack table, project folder structure.",
        },
        "frontend_code": {
            "sections": [
                {"name": "files", "aliases": ["manifest", "Manifest", "component", ".tsx", ".jsx", ".ts"]},
                {"name": "code_blocks", "aliases": ["```"]},
            ],
            "secondary_files": ["workspace_manifest.json"],
            "prompt_hint": "Required: code implementation with ```, manifest. workspace_manifest.json must be saved.",
        },
        "backend_structure": {
            "sections": [
                {"name": "tech_stack", "aliases": ["tech stack", "technology", "framework", "Backend"]},
                {"name": "api_design", "aliases": ["api", "endpoint", "route", "controller", "service"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: tech stack, API/service design.",
        },
        "backend_code": {
            "sections": [
                {"name": "files", "aliases": ["manifest", "Manifest", ".py", ".ts", ".go", ".java", "implementation"]},
                {"name": "code_blocks", "aliases": ["```"]},
            ],
            "secondary_files": ["workspace_manifest.json"],
            "prompt_hint": "Required: code blocks, manifest. workspace_manifest.json must be saved.",
        },
        "unit_tests": {
            "sections": [
                {"name": "test_functions", "aliases": ["def test_", "it(", "describe(", "test(", "Test"]},
                {"name": "assertions", "aliases": ["expect(", "assert", "toBe", "assertEqual", "assertEqual"]},
            ],
            "secondary_files": ["workspace_manifest.json"],
            "prompt_hint": "Required: test functions with assertions. workspace_manifest.json must be saved.",
        },
        "dev_readme": {
            "sections": [
                {"name": "setup", "aliases": ["setup", "installation", "ติดตั้ง", "install", "Setup"]},
                {"name": "run", "aliases": ["npm run", "yarn", "python", "docker", "เริ่มต้น", "start"]},
                {"name": "env", "aliases": [".env", "environment variable", "ENV", "config"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: setup/installation steps, run commands, environment variables.",
        },
    },

    # ── QA ───────────────────────────────────────────────────────────────────
    "qa": {
        "qa_plan": {
            "sections": [
                {"name": "test_scope", "aliases": ["test scope", "in-scope", "ขอบเขตการทดสอบ", "Test Scope"]},
                {"name": "test_strategy", "aliases": ["test strategy", "กลยุทธ์การทดสอบ", "Test Strategy"]},
                {"name": "entry_exit", "aliases": ["entry criteria", "exit criteria", "เริ่มทดสอบเมื่อ", "สิ้นสุดเมื่อ"]},
                {"name": "test_environment", "aliases": ["test environment", "Test Environment", "staging", "environment"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: test scope, strategy, entry/exit criteria, environment.",
        },
        "test_cases": {
            "sections": [
                {"name": "test_case_id", "aliases": ["tc-", "test case", "Test Case"]},
                {"name": "expected_result", "aliases": ["expected result", "Expected Result", "ผลที่คาดหวัง"]},
                {"name": "test_steps", "aliases": ["step", "ขั้นตอน", "action", "Step"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: TC-NNN IDs, test steps, expected results.",
        },
        "test_scenarios": {
            "sections": [
                {"name": "scenario", "aliases": ["scenario", "Scenario", "สถานการณ์", "scen-"]},
                {"name": "precondition", "aliases": ["precondition", "เงื่อนไขเบื้องต้น", "given", "Given"]},
                {"name": "test_steps", "aliases": ["step", "ขั้นตอน", "action"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: scenario IDs, preconditions, test steps.",
        },
        "test_report": {
            "sections": [
                {"name": "summary", "aliases": ["summary", "สรุป", "executive summary", "Summary"]},
                {"name": "pass_fail_count", "aliases": ["pass", "fail", "ผ่าน", "ไม่ผ่าน"]},
                {"name": "defects", "aliases": ["defect", "bug", "Bug", "ปัญหา", "Defect"]},
            ],
            "secondary_files": [{"any": ["qa_execution_result.json", "test_execution_result.json"]}],
            "prompt_hint": "Required: summary, pass/fail counts, defect list. qa_execution_result.json must be saved.",
        },
    },

    # ── DEVOPS ────────────────────────────────────────────────────────────────
    "devops": {
        "pipeline_diagram": {
            "sections": [
                {"name": "diagram_syntax", "aliases": ["graph ", "flowchart ", "gitGraph", "-->", "ci"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: valid Mermaid CI/CD pipeline diagram.",
        },
        "dockerfile": {
            "sections": [
                {"name": "from_instruction", "aliases": ["FROM "]},
                {"name": "run_instruction", "aliases": ["RUN "]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: FROM and RUN instructions in Dockerfile.",
        },
        "docker_compose": {
            "sections": [
                {"name": "services", "aliases": ["services:"]},
                {"name": "image_or_build", "aliases": ["image:", "build:"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: services: block with image: or build: entries.",
        },
        "github_actions": {
            "sections": [
                {"name": "trigger", "aliases": ["on:", "on :", "push:", "pull_request:"]},
                {"name": "jobs", "aliases": ["jobs:"]},
                {"name": "steps", "aliases": ["steps:"]},
            ],
            "secondary_files": [],
            "prompt_hint": "Required: on: trigger, jobs:, steps: in GitHub Actions YAML.",
        },
        "deployment_guide": {
            "sections": [
                {"name": "prerequisites", "aliases": ["prerequisite", "ข้อกำหนดเบื้องต้น", "requirement", "ก่อน deploy"]},
                {"name": "steps", "aliases": ["step", "ขั้นตอน", "deploy", "Step"]},
                {"name": "environment", "aliases": ["environment", "ENV", "config", "configuration"]},
            ],
            "secondary_files": ["deployment_readiness_report.md"],
            "prompt_hint": "Required: prerequisites, deployment steps, environment config. deployment_readiness_report.md must be saved.",
        },
    },
}


# ─── Validation Logic ─────────────────────────────────────────────────────────

def _section_present(content: str, aliases: list[str]) -> bool:
    """Return True if any alias appears in content (case-insensitive)."""
    content_lower = content.lower()
    for alias in aliases:
        if alias.lower() in content_lower:
            return True
    return False


def _secondary_file_ok(
    output_dir: str,
    spec: "str | dict",
    generated_names: Optional[frozenset] = None,
    attempt_started_at: Optional[float] = None,
) -> bool:
    """
    Check one secondary file spec for freshness.

    Priority order:
    1. generated_names provided → check filename membership (exact set from artifact collector)
    2. attempt_started_at provided → file must exist AND mtime >= attempt_started_at
    3. Neither → just check file exists (backward-compatible)

    spec may be a string (single required filename) or {"any": [filename, ...]}
    meaning at least one of the listed files must satisfy the check.
    """
    candidates: list[str] = [spec] if isinstance(spec, str) else (
        spec.get("any", []) if isinstance(spec, dict) else []
    )
    for fname in candidates:
        if generated_names is not None:
            if fname in generated_names:
                return True
        else:
            fpath = os.path.join(output_dir, fname)
            if os.path.isfile(fpath):
                if attempt_started_at is None or os.path.getmtime(fpath) >= attempt_started_at:
                    return True
    return False


def validate_role_artifact_contract(
    role: str,
    task_type: str,
    content: str,
    output_format: str,  # noqa: ARG001 — reserved for future format-specific checks
    output_dir: Optional[str] = None,
    generated_artifacts: Optional[list] = None,
    attempt_started_at: Optional[float] = None,
) -> ContractValidationResult:
    """
    Validate that content + artifacts satisfy the role/task_type artifact contract.

    Parameters:
        generated_artifacts : list of artifact dicts from _collect_artifacts()
            e.g. [{"type": "workspace_manifest", "path": "workspace_manifest.json",
                   "ref": "/full/path/workspace_manifest.json"}]
            When provided, secondary file checks use this set exclusively —
            stale files left in output_dir from prior attempts are ignored.
        attempt_started_at  : wall-clock seconds (time.time()) marking when the
            current attempt began. Used as mtime lower-bound when
            generated_artifacts is absent. Prevents stale files from passing.

    Returns:
        status="skipped"  — no contract defined for this role/task_type
        status="passed"   — all required sections and files present
        status="failed"   — one or more requirements missing
    """
    contract = _CONTRACTS.get(role, {}).get(task_type)
    if not contract:
        return ContractValidationResult(
            status="skipped",
            contract_name=f"{role}:{task_type}",
        )

    missing_sections: list[str] = []
    for req in contract.get("sections", []):
        if not _section_present(content, req["aliases"]):
            missing_sections.append(req["name"])

    # Build filename set from explicit artifact list when provided
    _gen_names: Optional[frozenset] = None
    if generated_artifacts is not None:
        _gen_names = frozenset(
            name
            for a in generated_artifacts
            for name in filter(None, [
                a.get("path") or "",
                os.path.basename(a.get("ref", "")) if a.get("ref") else "",
            ])
        )

    missing_artifacts: list[str] = []
    _check_secondary = (output_dir is not None) or (_gen_names is not None)
    if _check_secondary:
        for spec in contract.get("secondary_files", []):
            if not _secondary_file_ok(
                output_dir or "",
                spec,
                _gen_names,
                attempt_started_at,
            ):
                fname = spec if isinstance(spec, str) else "/".join(
                    spec.get("any", [])
                )
                missing_artifacts.append(fname)

    if missing_sections or missing_artifacts:
        parts = []
        if missing_sections:
            parts.append(f"Missing sections: {', '.join(missing_sections)}")
        if missing_artifacts:
            parts.append(f"Missing files: {', '.join(missing_artifacts)}")
        return ContractValidationResult(
            status="failed",
            contract_name=f"{role}:{task_type}",
            missing_sections=missing_sections,
            missing_artifacts=missing_artifacts,
            revision_comment=f"[contract] {'; '.join(parts)}",
        )

    return ContractValidationResult(
        status="passed",
        contract_name=f"{role}:{task_type}",
    )


# ─── Prompt Block Builder ─────────────────────────────────────────────────────

def build_contract_prompt_block(role: str, task_type: str) -> str:
    """
    Return a short contract reminder block to append to task prompts.
    Returns empty string if no contract is defined.
    """
    contract = _CONTRACTS.get(role, {}).get(task_type)
    if not contract:
        return ""
    hint = contract.get("prompt_hint", "")
    if not hint:
        return ""
    return (
        "\n\n---\n"
        "## Output Contract (อย่าข้าม)\n"
        f"{hint}\n"
        "Output ที่ขาด section ที่กำหนดจะถูก reject อัตโนมัติและ requeue.\n"
        "---\n"
    )
