"""
DEVOPS Agent - DevOps Engineer
Routing: score-based via model_router (qwen2.5-coder FREE → claude-haiku CHEAP → claude-sonnet SMART)
Fallback: automatic via call_llm() — never stops on billing/quota errors
"""

import os
import json
import subprocess
from shared.base_agent import BaseAgent
from shared.storage import Project
from shared.model_router import TaskType
from agents.devops.prompts import DEVOPS_SYSTEM_PROMPT, build_devops_prompt


class DEVOPSAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "devops"

    @property
    def system_prompt(self) -> str:
        return DEVOPS_SYSTEM_PROMPT

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_devops_prompt(prev, revision_comment, revision_count)
        response = await self.call_llm(
            prompt=prompt,
            project_id=project.id,
            project_name=project.name,
            task_type=TaskType.CODE_GENERATION,  # routes to qwen2.5-coder free first
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

        # Validate Dockerfile syntax ถ้ามี
        output_data = await self._validate_docker(output_data)
        return output_data

    async def _validate_docker(self, output_data: dict) -> dict:
        """ตรวจสอบ Dockerfile syntax"""
        dockerfile = output_data.get("files", {}).get("Dockerfile")
        if not dockerfile:
            return output_data

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix="Dockerfile", delete=False) as f:
            f.write(dockerfile)
            fname = f.name

        try:
            result = subprocess.run(
                ["docker", "build", "--check", "-f", fname, "."],
                capture_output=True, text=True, timeout=30
            )
            output_data["dockerfile_valid"] = result.returncode == 0
            output_data["dockerfile_check"] = result.stdout + result.stderr
        except FileNotFoundError:
            output_data["dockerfile_valid"] = "Docker not available in sandbox"
        except Exception as e:
            output_data["dockerfile_valid"] = f"Check failed: {e}"
        finally:
            os.unlink(fname)

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
        valid = output_data.get("dockerfile_valid", "")
        docker = "✅ Valid" if valid is True else (f"⚠️ {str(valid)[:30]}" if valid else "—")
        return {
            "🚀 Services": ", ".join(services[:4]) if services else "—",
            "🐳 Dockerfile": docker,
            "📋 Deploy Steps": str(len(steps)) if steps else "—",
        }


def main():
    token = os.getenv("DEVOPS_DISCORD_TOKEN")
    if not token:
        raise ValueError("DEVOPS_DISCORD_TOKEN not set")
    DEVOPSAgent().run(token)

if __name__ == "__main__":
    main()
