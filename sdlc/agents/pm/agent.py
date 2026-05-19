"""PM Agent - Project Manager"""

import os
import json
import sqlite3
import logging
from shared.base_agent import BaseAgent
from shared.storage import Project, SdlcTask
from agents.pm.prompts import PM_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class PMAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "pm"

    @property
    def system_prompt(self) -> str:
        return PM_SYSTEM_PROMPT

    async def _on_sdlc_task_completed(self, task: SdlcTask, content: str):
        """PM hooks: inject outputs into dependent PM tasks"""
        if task.task_type == "project_charter":
            self._inject_into_pm_deps(task.project_id, "project_charter_content", content)
            self._inject_into_pm_deps(task.project_id, "budget", "ตามที่กำหนดใน Project Charter")
        elif task.task_type in ("project_management_plan", "raci_matrix",
                                "risk_register", "communications_plan"):
            self._refresh_tasks_summary(task.project_id)
        await super()._on_sdlc_task_completed(task, content)  # G4 epic completion check

    def _inject_into_pm_deps(self, project_id: str, key: str, value: str):
        """Inject key=value into input_data of all pending PM tasks for this project"""
        project_epic_id = f"{project_id}-PROJECT"
        pm_tasks = self.storage.list_sdlc_tasks(project_id=project_id, role="pm")
        for t in pm_tasks:
            if t.status not in ("pending", "in_progress"):
                continue
            try:
                inp = json.loads(t.input_data or "{}")
                inp[key] = value
                with sqlite3.connect(self.storage.db_path) as conn:
                    conn.execute("UPDATE sdlc_tasks SET input_data=? WHERE id=?",
                                 (json.dumps(inp), t.id))
                    conn.commit()
            except Exception as e:
                logger.warning(f"[PM] inject {key} into {t.id}: {e}")

    def _refresh_tasks_summary(self, project_id: str):
        """Rebuild tasks_summary from all completed sdlc_tasks → inject into project_status_report"""
        all_tasks = self.storage.list_sdlc_tasks(project_id=project_id)
        completed = [t for t in all_tasks if t.status == "completed"]
        pending   = [t for t in all_tasks if t.status == "pending"]
        in_prog   = [t for t in all_tasks if t.status == "in_progress"]
        total     = len(all_tasks)

        lines = [f"## Task Summary — Project {project_id}",
                 f"- Total tasks: {total}",
                 f"- Completed: {len(completed)}",
                 f"- In Progress: {len(in_prog)}",
                 f"- Pending: {len(pending)}", "",
                 "| Task ID | Role | Type | Status |",
                 "|---------|------|------|--------|"]
        for t in sorted(completed + in_prog, key=lambda x: x.id)[:30]:
            lines.append(f"| {t.id} | {t.role.upper()} | {t.task_type} | {t.status} |")

        summary = "\n".join(lines)
        # Find project_status_report task and inject
        status_tasks = [t for t in all_tasks
                        if t.role == "pm" and t.task_type == "project_status_report"]
        for t in status_tasks:
            if t.status not in ("pending",):
                continue
            try:
                inp = json.loads(t.input_data or "{}")
                inp["tasks_summary"] = summary
                inp["budget"] = inp.get("budget", "ตามที่กำหนดใน Project Charter")
                with sqlite3.connect(self.storage.db_path) as conn:
                    conn.execute("UPDATE sdlc_tasks SET input_data=? WHERE id=?",
                                 (json.dumps(inp), t.id))
                    conn.commit()
            except Exception as e:
                logger.warning(f"[PM] refresh_tasks_summary for {t.id}: {e}")

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        duration = output_data.get("estimated_duration", "") or output_data.get("duration", "")
        if not duration:
            m = re.search(r'(\d+[-–]\d+\s*(?:week|month|sprint))', output_data.get("summary", ""), re.I)
            duration = m.group(0) if m else "—"
        sprints = output_data.get("total_sprints", "") or output_data.get("sprints", "")
        if not sprints:
            sprint_list = output_data.get("sprint_list", [])
            sprints = len(sprint_list) if sprint_list else "—"
        mvp = str(output_data.get("mvp_scope", "") or output_data.get("scope", ""))[:60] or "—"
        return {
            "📅 Duration": str(duration),
            "🔄 Sprints": str(sprints),
            "🎯 MVP Scope": mvp,
        }


def main():
    token = os.getenv("PM_DISCORD_TOKEN")
    if not token:
        raise ValueError("PM_DISCORD_TOKEN not set")
    agent = PMAgent()
    agent.run(token)


if __name__ == "__main__":
    main()
