"""
Export Project Output → Mac Desktop
รัน: python3 scripts/export_project_output.py [project_id]
ถ้าไม่ระบุ project_id → ใช้ project ล่าสุด
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────────
DB_PATH    = os.path.join(os.path.dirname(__file__), '..', 'data', 'sdlc.db')
MAC_DESKTOP = "/Users/socket9companylimited/Desktop"
EXPORT_DIR  = os.path.join(MAC_DESKTOP, "SDLC-Export")

ROLE_ORDER  = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
ROLE_EMOJI  = {
    "ceo": "👑", "pm": "📊", "ba": "📝", "sa": "🏛️",
    "uxui": "🎨", "dev": "💻", "qa": "🧪", "devops": "⚙️"
}

# ─── Helpers ──────────────────────────────────────────────────────

def get_project(db, project_id=None):
    if project_id:
        row = db.execute(
            "SELECT id, name, status, current_role, created_at FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id, name, status, current_role, created_at FROM projects ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return row


def get_tasks(db, project_id):
    rows = db.execute(
        """SELECT role, status, output_data, created_at, updated_at
           FROM role_tasks WHERE project_id=?
           ORDER BY created_at ASC""",
        (project_id,)
    ).fetchall()
    return rows


def write_files(role_dir: Path, files: dict):
    """Write files dict from agent output to disk."""
    for filename, content in files.items():
        if not content:
            continue
        filepath = role_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(content))


def export_project(project_id=None):
    db = sqlite3.connect(DB_PATH)
    project = get_project(db, project_id)

    if not project:
        print("❌ No project found.")
        return

    proj_id, proj_name, proj_status, current_role, created_at = project
    print(f"\n📦 Exporting Project: {proj_name} ({proj_id})")
    print(f"   Status: {proj_status} | Current Role: {current_role}")

    # ── Create export directory ──────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_root = Path(EXPORT_DIR) / f"{proj_id}_{proj_name.replace(' ', '_')}_{timestamp}"
    export_root.mkdir(parents=True, exist_ok=True)
    print(f"   📁 Export dir: {export_root}")

    # ── Write project summary ────────────────────────────────────
    summary_lines = [
        f"# Project Export: {proj_name}",
        f"",
        f"- **Project ID**: {proj_id}",
        f"- **Status**: {proj_status}",
        f"- **Current Stage**: {current_role}",
        f"- **Created**: {created_at}",
        f"- **Exported**: {datetime.now().isoformat()}",
        f"",
        f"## Pipeline Stages",
        f"",
    ]

    tasks = get_tasks(db, proj_id)

    # Index by role (last task per role)
    task_by_role = {}
    for role, status, output_data_str, created, updated in tasks:
        task_by_role[role] = (status, output_data_str, created, updated)

    # ── Process each role in pipeline order ─────────────────────
    completed_roles = []
    for role in ROLE_ORDER:
        if role not in task_by_role:
            continue

        status, output_data_str, created, updated = task_by_role[role]
        emoji = ROLE_EMOJI.get(role, "🤖")
        status_icon = {"approved": "✅", "waiting_approval": "⏳",
                       "completed": "✅", "failed": "❌",
                       "in_progress": "🔄"}.get(status, "❓")

        summary_lines.append(f"### {emoji} {role.upper()} — {status_icon} {status}")

        # Parse output
        output_data = {}
        if output_data_str:
            try:
                output_data = json.loads(output_data_str)
            except Exception:
                output_data = {"raw": output_data_str}

        files = output_data.get("files", {})
        summary_val = output_data.get("summary", "")

        if summary_val:
            summary_lines.append(f"**Summary**: {summary_val[:200]}")

        if files:
            summary_lines.append(f"**Files**: {', '.join(files.keys())}")
            # Write role folder
            role_num = ROLE_ORDER.index(role)
            role_dir = export_root / f"{role_num:02d}_{role}"
            role_dir.mkdir(exist_ok=True)
            write_files(role_dir, files)
            completed_roles.append(role)
            print(f"   {emoji} {role.upper()} ({status}) → {len(files)} files written")
        else:
            summary_lines.append("*(no output files)*")
            print(f"   {emoji} {role.upper()} ({status}) → no files")

        # Write extra fields (non-files, non-summary)
        extras = {k: v for k, v in output_data.items() if k not in ("files", "summary")}
        if extras:
            role_num = ROLE_ORDER.index(role)
            role_dir = export_root / f"{role_num:02d}_{role}"
            role_dir.mkdir(exist_ok=True)
            with open(role_dir / "_metadata.json", "w", encoding="utf-8") as f:
                json.dump(extras, f, ensure_ascii=False, indent=2)

        summary_lines.append("")

    # ── Write project summary file ──────────────────────────────
    summary_lines += [
        f"---",
        f"",
        f"## How to Use These Documents",
        f"",
        f"Each folder corresponds to one SDLC stage:",
        f"",
        f"```",
        f"00_ceo/    → Project Brief, Epics, Role Assignment",
        f"01_pm/     → Roadmap, Backlog, Sprint Plan, Risk Log",
        f"02_ba/     → User Stories, Acceptance Criteria, Business Rules",
        f"03_sa/     → Architecture, API Spec, Data Model, Security Design",
        f"04_uxui/   → User Flow, Wireframe, UI Spec, Design System",
        f"05_dev/    → Source Code, Unit Tests, Implementation Plan",
        f"06_qa/     → Test Cases, Test Results, Defect Report, Release Sign-off",
        f"07_devops/ → Dockerfile, CI/CD, Deployment Guide, Monitoring Plan",
        f"```",
    ]

    with open(export_root / "PROJECT_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    # ── Print result ─────────────────────────────────────────────
    print(f"\n✅ Export complete!")
    print(f"   📂 Location: {export_root}")
    print(f"   📋 Completed roles: {', '.join(completed_roles) or 'none yet'}")
    print(f"   📄 Open: {export_root / 'PROJECT_SUMMARY.md'}")
    return str(export_root)


# ─── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    project_id = sys.argv[1] if len(sys.argv) > 1 else None
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    export_project(project_id)
