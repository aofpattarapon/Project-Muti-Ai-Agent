"""UXUI Agent - UX/UI Designer"""

import os
import json
from shared.base_agent import BaseAgent
from shared.storage import Project
from agents.uxui.prompts import UXUI_SYSTEM_PROMPT, build_uxui_prompt


class UXUIAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "uxui"

    @property
    def system_prompt(self) -> str:
        return UXUI_SYSTEM_PROMPT

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_uxui_prompt(prev, revision_comment, revision_count)
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
                "summary": f"UXUI Design for {project.name}",
                "files": {"wireframe_spec.md": response},
                "dev_instructions": "ดู wireframe_spec.md",
            }

    def _get_role_metrics(self, output_data: dict) -> dict:
        pages      = output_data.get("pages", [])
        files      = output_data.get("files", {})
        html_files = [f for f in files if f.endswith(".html")]
        components = output_data.get("components", [])
        return {
            "📱 Screens": str(len(pages)) if pages else "—",
            "🎨 Components": str(len(components)) if components else "—",
            "🖼️ HTML Wireframes": str(len(html_files)) if html_files else "0",
        }


def main():
    token = os.getenv("UXUI_DISCORD_TOKEN")
    if not token:
        raise ValueError("UXUI_DISCORD_TOKEN not set")
    UXUIAgent().run(token)

if __name__ == "__main__":
    main()
