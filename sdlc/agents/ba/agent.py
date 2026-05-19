"""BA Agent - Business Analyst"""

import os
import json
from shared.base_agent import BaseAgent
from shared.storage import Project
from agents.ba.prompts import BA_SYSTEM_PROMPT, build_ba_prompt


class BAAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "ba"

    @property
    def system_prompt(self) -> str:
        return BA_SYSTEM_PROMPT

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_ba_prompt(prev, revision_comment, revision_count)
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
                "summary": f"BA Analysis for {project.name}",
                "files": {"BRD.md": response},
                "sa_instructions": "ดูรายละเอียดใน BRD.md",
            }

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        us_list  = output_data.get("user_stories", [])
        us_count = len(us_list) if us_list else output_data.get("total_user_stories", "")
        if not us_count:
            m = re.search(r'(\d+)\s*(user stor|US)', output_data.get("summary", ""), re.I)
            us_count = m.group(1) if m else "—"
        uc_list  = output_data.get("use_cases", [])
        uc_count = len(uc_list) if uc_list else output_data.get("total_use_cases", "")
        if not uc_count:
            m = re.search(r'(\d+)\s*use case', output_data.get("summary", ""), re.I)
            uc_count = m.group(1) if m else "—"
        return {
            "📝 User Stories": str(us_count),
            "🔍 Use Cases": str(uc_count),
        }


def main():
    token = os.getenv("BA_DISCORD_TOKEN")
    if not token:
        raise ValueError("BA_DISCORD_TOKEN not set")
    BAAgent().run(token)

if __name__ == "__main__":
    main()
