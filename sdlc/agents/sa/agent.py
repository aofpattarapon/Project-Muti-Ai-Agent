"""SA Agent - System Architect"""

import os
import json
import logging
from shared.base_agent import BaseAgent
from shared.storage import Project, SdlcTask
from agents.sa.prompts import SA_SYSTEM_PROMPT, build_sa_prompt

logger = logging.getLogger(__name__)


class SAAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "sa"

    @property
    def system_prompt(self) -> str:
        return SA_SYSTEM_PROMPT

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_sa_prompt(prev, revision_comment, revision_count)
        response = await self.call_llm(
            prompt=prompt,
            project_id=project.id,
            project_name=project.name,
        )

        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                start, end = response.find("{"), response.rfind("}") + 1
                json_str = response[start:end]
            return json.loads(json_str)
        except Exception:
            return {
                "summary": f"SA Architecture for {project.name}",
                "files": {"system_architecture.md": response},
                "dev_instructions": "ดูรายละเอียดใน system_architecture.md",
            }

    async def _on_sdlc_task_completed(self, task: SdlcTask, content: str):
        """SA hook: super() handles epic + project completion checks.
        _build_sdlc_context auto-injects SA outputs (api_spec, database_schema, etc.)
        into downstream tasks (UXUI, DEV) via the key_map — no manual injection needed.
        """
        await super()._on_sdlc_task_completed(task, content)
        logger.debug(
            f"[SA] completed {task.task_type} ({task.id}) — "
            f"context will be auto-read by UXUI/DEV via _build_sdlc_context"
        )

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        tech       = output_data.get("tech_stack", {})
        components = output_data.get("components", [])
        summary    = output_data.get("summary", "")

        def _t(key, pattern):
            v = tech.get(key, "")
            if not v:
                m = re.search(pattern, summary, re.I)
                v = m.group(0) if m else "—"
            return str(v)

        return {
            "🏗️ Components": str(len(components)) if components else "—",
            "🖥️ Frontend": _t("frontend", r'React|Next\.?js|Vue|Angular|Flutter'),
            "⚙️ Backend": _t("backend", r'FastAPI|Django|Express|Node|Go|Spring'),
            "🗄️ Database": _t("database", r'PostgreSQL|MySQL|MongoDB|Redis|SQLite'),
        }


def main():
    token = os.getenv("SA_DISCORD_TOKEN")
    if not token:
        raise ValueError("SA_DISCORD_TOKEN not set")
    SAAgent().run(token)

if __name__ == "__main__":
    main()
