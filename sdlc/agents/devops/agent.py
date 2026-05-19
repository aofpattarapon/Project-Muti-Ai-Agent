"""
DEVOPS Agent - DevOps Engineer
Routing: score-based via model_router (qwen2.5-coder FREE → claude-haiku CHEAP → claude-sonnet SMART)
Fallback: automatic via call_llm() — never stops on billing/quota errors
"""

import os
import json
import logging
from typing import Optional
from shared.base_agent import BaseAgent
from shared.storage import Project, SdlcTask
from shared.model_router import TaskType
from shared.web_bridge import get_bridge
from agents.devops.prompts import DEVOPS_SYSTEM_PROMPT, build_devops_prompt
from agents.devops.execution_helper import (
    DEVOPSExecutionHelper,
    _DEVOPS_CHECK_TASK_TYPES,
    format_execution_result,
)

logger = logging.getLogger(__name__)


class DEVOPSAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "devops"
        self._last_execution_result: Optional[dict] = None

    @property
    def system_prompt(self) -> str:
        return DEVOPS_SYSTEM_PROMPT

    def _get_next_role_override(self, output_data: dict) -> Optional[str]:
        """Route back to DEV if deployment checks detected code failures (not infra/blocked)."""
        if self._last_execution_result is None:
            return None
        helper = DEVOPSExecutionHelper(self.storage)
        routing = helper.decide_routing(self._last_execution_result)
        if routing == "rework_dev":
            return "dev"
        return None

    async def _pre_llm_hook(self, task: SdlcTask, input_data: dict) -> dict:
        """For deployment check tasks: run readiness checks and inject results into LLM context."""
        if task.task_type not in _DEVOPS_CHECK_TASK_TYPES:
            return {}
        helper = DEVOPSExecutionHelper(self.storage)
        result = helper.run_deployment_checks(task, input_data)
        self._last_execution_result = result
        return {
            "devops_execution_result": result,
            "devops_execution_context": format_execution_result(result),
        }

    async def _post_save_hook(self, task: SdlcTask, output_dir: str, content: str = "") -> None:
        """For deployment check tasks:
        - Save devops_execution_result.json + deployment_readiness_report.md
        - If failed (code issues): requeue DEV tasks for rework
        - If blocked (infra/tool): log warning, no auto-requeue
        """
        if task.task_type not in _DEVOPS_CHECK_TASK_TYPES or not self._last_execution_result:
            return

        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else ""

        helper = DEVOPSExecutionHelper(self.storage)
        helper.save_execution_artifact(task, output_dir, self._last_execution_result, project_name)

        routing = helper.decide_routing(self._last_execution_result)
        if routing == "rework_dev":
            requeued = helper.requeue_dev_tasks(task, self._last_execution_result)
            if requeued:
                logger.info(
                    f"[devops] {task.task_type} {task.id} deployment check failed — "
                    f"requeued DEV tasks: {requeued}"
                )
        elif routing == "blocked":
            summary = self._last_execution_result.get("summary", "")
            blockers = self._last_execution_result.get("deployment_blockers", [])
            logger.warning(
                f"[devops] {task.task_type} {task.id} deployment check blocked "
                f"({summary}) — infrastructure/tooling issue, human review required"
            )
            project = self.storage.get_project(task.project_id)
            project_name = project.name if project else ""
            try:
                await get_bridge().devops_blocked(
                    role_key=self.role_name,
                    project_id=task.project_id,
                    project_name=project_name,
                    task_name=task.title,
                    task_id=task.id,
                    blocked_summary=summary,
                    blockers=blockers,
                )
            except Exception as _blocked_err:
                logger.warning(f"[devops] devops_blocked web notify failed: {_blocked_err}")

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_devops_prompt(prev, revision_comment, revision_count)
        response = await self.call_llm(
            prompt=prompt,
            project_id=project.id,
            project_name=project.name,
            task_type=TaskType.CODE_GENERATION,
        )

        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                start, end = response.find("{"), response.rfind("}") + 1
                json_str = response[start:end]
            output_data = json.loads(json_str)
        except Exception:
            output_data = {
                "summary": f"DEVOPS Infrastructure for {project.name}",
                "files": {"deployment_guide.md": response},
                "deployment_steps": ["ดู deployment_guide.md"],
            }

        return output_data

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        services = output_data.get("services", [])
        if not services:
            svc = re.findall(
                r'\b(nginx|postgres|redis|rabbitmq|mongo|mysql|api|frontend|backend|worker)\b',
                output_data.get("summary", ""), re.I,
            )
            services = list(dict.fromkeys(svc))[:6]
        steps = output_data.get("deployment_steps", [])

        exec_status = "—"
        if self._last_execution_result:
            st = self._last_execution_result.get("status", "")
            icons = {
                "passed": "✅ Passed",
                "failed": "❌ Failed",
                "blocked": "🚫 Blocked",
                "skipped": "⏭️ Skipped",
            }
            exec_status = icons.get(st, st)

        return {
            "🚀 Services": ", ".join(services[:4]) if services else "—",
            "🔍 Deploy Checks": exec_status,
            "📋 Deploy Steps": str(len(steps)) if steps else "—",
        }


def main():
    token = os.getenv("DEVOPS_DISCORD_TOKEN")
    if not token:
        raise ValueError("DEVOPS_DISCORD_TOKEN not set")
    DEVOPSAgent().run(token)

if __name__ == "__main__":
    main()
