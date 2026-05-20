"""
Task Catalog — นิยาม tasks ทุก role พร้อม output format และ dependency
แต่ละ role จะได้รับ tasks เหล่านี้ต่อ 1 epic (หรือ per-project สำหรับ PM/DevOps)
"""

from typing import List, Dict

# ── Catalog Definition ────────────────────────────────────────────────────────
# "scope": "epic"    → สร้าง N ชุดต่อ N epics
# "scope": "project" → สร้าง 1 ชุดต่อ project

TASK_CATALOG: Dict[str, List[dict]] = {
    "ceo": [
        {
            "task_type": "project_brief",
            "title": "Project Brief",
            "output_file": "project_brief.md",
            "output_format": "markdown",
            "depends_on_types": [],
            "scope": "project",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "epics",
            "title": "Epics (Jira-style)",
            "output_file": "epics.md",
            "output_format": "markdown",
            "depends_on_types": ["project_brief"],
            "scope": "project",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
    ],
    "pm": [
        {
            "task_type": "project_charter",
            "title": "Project Charter",
            "output_file": "project_charter.docx",
            "output_format": "word",
            "depends_on_types": [],
            "scope": "project",
        },
        {
            "task_type": "project_management_plan",
            "title": "แผนบริหารโครงการ",
            "output_file": "project_management_plan.docx",
            "output_format": "word",
            "depends_on_types": ["project_charter"],
            "scope": "project",
        },
        {
            "task_type": "project_plan_excel",
            "title": "Excel Project Plan (MS-Project style)",
            "output_file": "project_plan.xlsx",
            "output_format": "excel",
            "depends_on_types": ["project_management_plan"],
            "scope": "project",
        },
        {
            "task_type": "raci_matrix",
            "title": "RACI Matrix",
            "output_file": "raci_matrix.xlsx",
            "output_format": "excel",
            "depends_on_types": ["project_management_plan"],
            "scope": "project",
        },
        {
            "task_type": "risk_register",
            "title": "Risk Register",
            "output_file": "risk_register.docx",
            "output_format": "word",
            "depends_on_types": ["project_management_plan"],
            "scope": "project",
        },
        {
            "task_type": "communications_plan",
            "title": "Communications Management Plan",
            "output_file": "communications_plan.docx",
            "output_format": "word",
            "depends_on_types": ["project_management_plan"],
            "scope": "project",
        },
        {
            "task_type": "project_status_report",
            "title": "Project Status Report",
            "output_file": "project_status_report.docx",
            "output_format": "word",
            "depends_on_types": ["communications_plan", "risk_register"],
            "scope": "project",
        },
    ],
    "ba": [
        {
            "task_type": "brd",
            "title": "Business Requirements Document (BRD)",
            "output_file": "BRD.docx",
            "output_format": "word",
            "depends_on_types": [],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "srs",
            "title": "Software Requirements Specification (SRS)",
            "output_file": "SRS.docx",
            "output_format": "word",
            "depends_on_types": ["brd"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "user_stories",
            "title": "User Stories & Acceptance Criteria",
            "output_file": "user_stories.xlsx",
            "output_format": "excel",
            "depends_on_types": ["brd"],
            "scope": "epic",
        },
        {
            "task_type": "use_cases",
            "title": "Use Case Specification",
            "output_file": "use_cases.docx",
            "output_format": "word",
            "depends_on_types": ["user_stories"],
            "scope": "epic",
        },
        {
            "task_type": "data_dictionary",
            "title": "Data Dictionary",
            "output_file": "data_dictionary.xlsx",
            "output_format": "excel",
            "depends_on_types": ["srs"],
            "scope": "epic",
        },
    ],
    "sa": [
        {
            "task_type": "system_purpose",
            "title": "System Purpose & Goals",
            "output_file": "system_purpose_goals.docx",
            "output_format": "word",
            "depends_on_types": [],
            "scope": "epic",
        },
        {
            "task_type": "scope_definition",
            "title": "In-Scope / Out-of-Scope",
            "output_file": "scope_in_out.docx",
            "output_format": "word",
            "depends_on_types": ["system_purpose"],
            "scope": "epic",
        },
        {
            "task_type": "architecture",
            "title": "Architecture Diagram",
            "output_file": "architecture_diagram.mmd",
            "output_format": "mermaid",
            "depends_on_types": ["scope_definition"],
            "scope": "epic",
        },
        {
            "task_type": "sequence_diagram",
            "title": "Sequence Diagram",
            "output_file": "sequence_diagram.mmd",
            "output_format": "mermaid",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "activity_workflow",
            "title": "Activity & Workflow Diagram",
            "output_file": "activity_workflow.mmd",
            "output_format": "mermaid",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "service_decomposition",
            "title": "Service Decomposition",
            "output_file": "service_decomposition.docx",
            "output_format": "word",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "integration_landscape",
            "title": "Integration Landscape",
            "output_file": "integration_landscape.mmd",
            "output_format": "mermaid",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "deployment_model",
            "title": "Deployment Model",
            "output_file": "deployment_model.mmd",
            "output_format": "mermaid",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "database_schema",
            "title": "Database Schema (SQL DDL)",
            "output_file": "database_schema.sql",
            "output_format": "sql",
            "depends_on_types": ["architecture"],
            "scope": "epic",
        },
        {
            "task_type": "api_spec",
            "title": "API Specification (OpenAPI YAML)",
            "output_file": "api_spec.yaml",
            "output_format": "yaml",
            "depends_on_types": ["sequence_diagram"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "sa_data_dictionary",
            "title": "SA Data Dictionary",
            "output_file": "sa_data_dictionary.xlsx",
            "output_format": "excel",
            "depends_on_types": ["database_schema"],
            "scope": "epic",
        },
    ],
    "uxui": [
        {
            "task_type": "user_flow",
            "title": "User Flow Diagram",
            "output_file": "user_flow.mmd",
            "output_format": "mermaid",
            "depends_on_types": [],
            "scope": "epic",
        },
        {
            "task_type": "wireframe",
            "title": "Wireframe (HTML + Tailwind)",
            "output_file": "wireframe.html",
            "output_format": "html",
            "depends_on_types": ["user_flow"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "design_system",
            "title": "Design System",
            "output_file": "design_system.docx",
            "output_format": "word",
            "depends_on_types": ["user_flow"],
            "scope": "epic",
        },
        {
            "task_type": "ux_guidelines",
            "title": "UX Guidelines & Accessibility",
            "output_file": "ux_guidelines.docx",
            "output_format": "word",
            "depends_on_types": ["design_system"],
            "scope": "epic",
        },
    ],
    "dev": [
        {
            "task_type": "frontend_structure",
            "title": "Frontend Structure & Component Plan",
            "output_file": "frontend_structure.md",
            "output_format": "markdown",
            "depends_on_types": [],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "frontend_code",
            "title": "Frontend Implementation",
            "output_file": "frontend_code_manifest.md",
            "output_format": "code_multi",
            "depends_on_types": ["frontend_structure"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "backend_structure",
            "title": "Backend Structure & API Plan",
            "output_file": "backend_structure.md",
            "output_format": "markdown",
            "depends_on_types": [],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "backend_code",
            "title": "Backend Implementation",
            "output_file": "backend_code_manifest.md",
            "output_format": "code_multi",
            "depends_on_types": ["backend_structure"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "unit_tests",
            "title": "Unit Tests",
            "output_file": "unit_tests_manifest.md",
            "output_format": "code_multi",
            "depends_on_types": ["frontend_code", "backend_code"],
            "scope": "epic",
            "preferred_model": "claude-cli/claude-sonnet-4-6",
        },
        {
            "task_type": "dev_readme",
            "title": "Developer README",
            "output_file": "README_dev.md",
            "output_format": "markdown",
            "depends_on_types": ["unit_tests"],
            "scope": "epic",
        },
    ],
    "qa": [
        {
            "task_type": "qa_plan",
            "title": "QA Plan",
            "output_file": "qa_plan.docx",
            "output_format": "word",
            "depends_on_types": [],
            "scope": "epic",
        },
        {
            "task_type": "test_cases",
            "title": "Test Cases",
            "output_file": "test_cases.xlsx",
            "output_format": "excel",
            "depends_on_types": ["qa_plan"],
            "scope": "epic",
        },
        {
            "task_type": "test_scenarios",
            "title": "Test Scenarios",
            "output_file": "test_scenarios.xlsx",
            "output_format": "excel",
            "depends_on_types": ["test_cases"],
            "scope": "epic",
        },
        {
            "task_type": "test_report",
            "title": "Test Report",
            "output_file": "test_report.docx",
            "output_format": "word",
            "depends_on_types": ["test_scenarios"],
            "scope": "epic",
        },
    ],
    "devops": [
        {
            "task_type": "pipeline_diagram",
            "title": "CI/CD Pipeline Diagram",
            "output_file": "pipeline_diagram.mmd",
            "output_format": "mermaid",
            "depends_on_types": [],
            "scope": "project",
            "preferred_model": "ollama/deepseek-r1",
        },
        {
            "task_type": "dockerfile",
            "title": "Dockerfile",
            "output_file": "Dockerfile",
            "output_format": "dockerfile",
            "depends_on_types": [],
            "scope": "project",
            "preferred_model": "ollama/qwen2.5-coder",
        },
        {
            "task_type": "docker_compose",
            "title": "Docker Compose",
            "output_file": "docker-compose.yml",
            "output_format": "yaml",
            "depends_on_types": ["dockerfile"],
            "scope": "project",
            "preferred_model": "ollama/qwen2.5-coder",
        },
        {
            "task_type": "github_actions",
            "title": "GitHub Actions CI/CD",
            "output_file": ".github/workflows/ci.yml",
            "output_format": "yaml",
            "depends_on_types": ["docker_compose"],
            "scope": "project",
            "preferred_model": "ollama/qwen2.5-coder",
        },
        {
            "task_type": "deployment_guide",
            "title": "Deployment Guide",
            "output_file": "deployment_guide.docx",
            "output_format": "word",
            "depends_on_types": ["github_actions"],
            "scope": "project",
            "preferred_model": "ollama/deepseek-r1",
        },
    ],
}

# Cross-role dependency order within an epic
# UXUI และ DEV frontend รอ SA ทำ architecture ก่อน
# DEV backend รอ SA api_spec
# QA รอ DEV dev_readme
# DevOps รอ QA test_report (project-level)
CROSS_ROLE_DEPS: Dict[str, Dict[str, str]] = {
    # role → {task_type: depends_on_role:task_type}
    "ba":   {"brd":                 "pm:project_charter"},
    "sa":   {"system_purpose":      "ba:data_dictionary"},
    "uxui": {"user_flow":           "sa:api_spec"},
    "dev":  {"frontend_structure":  "uxui:wireframe",
             "backend_structure":   "sa:api_spec"},
    "qa":   {"qa_plan":             "dev:dev_readme",
             "test_cases":          "ba:user_stories"},   # QA needs user stories for test cases
}


def build_project_tasks(
    project_id: str,
    epics: List[dict],       # [{"number": 1, "id": "...", "title": "...", ...}]
    include_roles: List[str] = None,
) -> List[dict]:
    """
    สร้าง task definitions ทั้งหมดสำหรับ project
    คืน list of dicts ที่ PM ใช้ INSERT ลง DB
    """
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    include_roles = include_roles or list(TASK_CATALOG.keys())
    project_epic_id = f"{project_id}-PROJECT"

    # ── map task_type → task_id สำหรับ resolve dependencies ─────────────────
    # key: "{epic_id}:{role}:{task_type}"  value: task_id
    type_to_id: dict = {}

    tasks_out: List[dict] = []

    def make_task_id(epic_id: str, role: str, task_number: int) -> str:
        return f"{epic_id}-{role.upper()[:2]}{task_number:02d}"

    def resolve_deps(role: str, task_type: str, epic_id: str) -> str:
        """Resolve depends_on_types → actual task IDs (comma-separated)"""
        catalog_entry = next(
            (t for t in TASK_CATALOG.get(role, []) if t["task_type"] == task_type), None
        )
        if not catalog_entry:
            return ""

        dep_ids = []
        # Intra-role deps (same role, same epic)
        for dep_type in catalog_entry.get("depends_on_types", []):
            key = f"{epic_id}:{role}:{dep_type}"
            if key in type_to_id:
                dep_ids.append(type_to_id[key])

        # Cross-role deps — try same-epic scope first, fall back to project scope
        # (needed when an epic-level role depends on a project-level role, e.g. ba→pm)
        cross = CROSS_ROLE_DEPS.get(role, {})
        if task_type in cross:
            cross_ref = cross[task_type]  # e.g. "sa:api_spec" or "pm:project_charter"
            cross_role, cross_type = cross_ref.split(":")
            key = f"{epic_id}:{cross_role}:{cross_type}"
            if key in type_to_id:
                dep_ids.append(type_to_id[key])
            else:
                # project-level dep (e.g. ba→pm where pm uses project_epic_id)
                key = f"{project_epic_id}:{cross_role}:{cross_type}"
                if key in type_to_id:
                    dep_ids.append(type_to_id[key])

        return ",".join(dep_ids)

    # ── CEO tasks (project-level) ────────────────────────────────────────────
    if "ceo" in include_roles:
        for i, tdef in enumerate(TASK_CATALOG["ceo"], start=1):
            tid = f"{project_epic_id}-CEO{i:02d}"
            type_to_id[f"{project_epic_id}:ceo:{tdef['task_type']}"] = tid
            tasks_out.append({
                "id": tid, "project_id": project_id, "epic_id": project_epic_id,
                "task_number": i, "role": "ceo", "task_type": tdef["task_type"],
                "title": tdef["title"], "description": "",
                "output_file": tdef["output_file"], "output_format": tdef["output_format"],
                "depends_on": "", "status": "pending",
                "input_data": "{}", "output_data": "{}",
                "approval_msg_id": "", "revision_count": 0, "notes": "",
                "created_at": now, "updated_at": now,
            })

    # ── PM tasks (project-level) ─────────────────────────────────────────────
    if "pm" in include_roles:
        for i, tdef in enumerate(TASK_CATALOG["pm"], start=1):
            tid = f"{project_epic_id}-PM{i:02d}"
            type_to_id[f"{project_epic_id}:pm:{tdef['task_type']}"] = tid
            tasks_out.append({
                "id": tid, "project_id": project_id, "epic_id": project_epic_id,
                "task_number": i, "role": "pm", "task_type": tdef["task_type"],
                "title": tdef["title"], "description": "",
                "output_file": tdef["output_file"], "output_format": tdef["output_format"],
                "depends_on": resolve_deps("pm", tdef["task_type"], project_epic_id),
                "status": "pending",
                "input_data": "{}", "output_data": "{}",
                "approval_msg_id": "", "revision_count": 0, "notes": "",
                "created_at": now, "updated_at": now,
            })

    # ── Epic-level tasks (BA, SA, UXUI, DEV, QA) ────────────────────────────
    epic_roles = [r for r in ["ba", "sa", "uxui", "dev", "qa"] if r in include_roles]

    for epic in epics:
        epic_id = epic["id"]

        for role in epic_roles:
            for i, tdef in enumerate(TASK_CATALOG[role], start=1):
                tid = f"{epic_id}-{role.upper()[:2]}{i:02d}"
                type_to_id[f"{epic_id}:{role}:{tdef['task_type']}"] = tid

        for role in epic_roles:
            for i, tdef in enumerate(TASK_CATALOG[role], start=1):
                tid = type_to_id[f"{epic_id}:{role}:{tdef['task_type']}"]
                dep_str = resolve_deps(role, tdef["task_type"], epic_id)
                tasks_out.append({
                    "id": tid, "project_id": project_id, "epic_id": epic_id,
                    "task_number": i, "role": role, "task_type": tdef["task_type"],
                    "title": f"[{epic['title']}] {tdef['title']}",
                    "description": epic.get("goal", ""),
                    "output_file": tdef["output_file"],
                    "output_format": tdef["output_format"],
                    "depends_on": dep_str, "status": "pending",
                    "input_data": json.dumps({
                        "epic_id": epic_id,
                        "epic_title": epic.get("title", ""),
                        "epic_goal": epic.get("goal", ""),
                        "epic_priority": epic.get("priority", "P1"),
                        "user_stories": epic.get("user_stories", []),
                    }),
                    "output_data": "{}", "approval_msg_id": "",
                    "revision_count": 0, "notes": "",
                    "created_at": now, "updated_at": now,
                })

    # ── DevOps tasks (project-level) ─────────────────────────────────────────
    # G7: DevOps pipeline_diagram waits for ALL epics' last DEV task (dev_readme)
    #     and dockerfile waits for ALL epics' last SA task (api_spec)
    #     so DevOps never starts before the development work is done.
    if "devops" in include_roles:
        _all_dev_readme_ids  = [type_to_id[k] for k in type_to_id if k.endswith(":dev:dev_readme")]
        _all_sa_api_spec_ids = [type_to_id[k] for k in type_to_id if k.endswith(":sa:api_spec")]
        _all_qa_report_ids   = [type_to_id[k] for k in type_to_id if k.endswith(":qa:test_report")]

        _devops_gate: Dict[str, List[str]] = {
            "pipeline_diagram": _all_dev_readme_ids + _all_sa_api_spec_ids,
            "dockerfile":       _all_dev_readme_ids,
            "deployment_guide": _all_qa_report_ids,
        }

        devops_task_ids: List[str] = []
        for i, tdef in enumerate(TASK_CATALOG["devops"], start=1):
            tid = f"{project_epic_id}-DO{i:02d}"
            type_to_id[f"{project_epic_id}:devops:{tdef['task_type']}"] = tid
            devops_task_ids.append(tid)

        for i, tdef in enumerate(TASK_CATALOG["devops"], start=1):
            tid = devops_task_ids[i - 1]
            intra_deps = resolve_deps("devops", tdef["task_type"], project_epic_id)
            gate_deps  = _devops_gate.get(tdef["task_type"], [])
            all_deps   = list(filter(None, intra_deps.split(","))) + gate_deps
            tasks_out.append({
                "id": tid, "project_id": project_id, "epic_id": project_epic_id,
                "task_number": i, "role": "devops", "task_type": tdef["task_type"],
                "title": tdef["title"], "description": "",
                "output_file": tdef["output_file"], "output_format": tdef["output_format"],
                "depends_on": ",".join(dict.fromkeys(all_deps)),  # dedup, preserve order
                "status": "pending",
                "input_data": "{}", "output_data": "{}",
                "approval_msg_id": "", "revision_count": 0, "notes": "",
                "created_at": now, "updated_at": now,
            })

    return tasks_out


import json
