"""
DEV Agent - Developer
Routing: score-based via model_router (qwen2.5-coder FREE → claude-haiku CHEAP → claude-sonnet SMART)
Fallback: automatic via call_llm() — never stops on billing/quota errors
"""

import os
import json
import subprocess
import tempfile
from shared.base_agent import BaseAgent
from shared.storage import Project
from shared.model_router import TaskType
from agents.dev.prompts import DEV_SYSTEM_PROMPT, build_dev_prompt


class DEVAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "dev"

    @property
    def system_prompt(self) -> str:
        return DEV_SYSTEM_PROMPT

    def _get_role_metrics(self, output_data: dict) -> dict:
        files = output_data.get("files", {})
        code_exts = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java")
        test_exts = ("test_", "_test.", ".spec.", "tests/")
        code_files = [f for f in files if f.endswith(code_exts) and not any(t in f for t in test_exts)]
        test_files = [f for f in files if any(t in f for t in test_exts)]
        test_res   = output_data.get("test_results", {})
        status     = "✅ Passed" if test_res.get("passed") else ("❌ Failed" if test_res else "—")
        lang       = output_data.get("language", "?")
        return {
            "💻 Language": lang,
            "📁 Code Files": str(len(code_files)),
            "🧪 Test Files": str(len(test_files)),
            "✅ Unit Tests": status,
        }

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count   = input_data.get("revision_count", 0)

        # Handle QA feedback (bug loop) — inject as revision context
        qa_feedback = input_data.get("role_feedback", {})
        if qa_feedback and not revision_comment:
            bugs     = qa_feedback.get("bugs_found", 0)
            severity = qa_feedback.get("severity_breakdown", {})
            qa_sum   = qa_feedback.get("summary", "")[:400]
            revision_comment = (
                f"⚠️ QA Bug Fix Required: {bugs} bugs found "
                f"(critical={severity.get('critical',0)}, high={severity.get('high',0)})\n"
                f"{qa_sum}"
            )
            revision_count = max(revision_count, 1)

        prompt = build_dev_prompt(prev, revision_comment, revision_count)
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
                "summary": f"DEV Implementation for {project.name}",
                "language": "python",
                "files": {"src/implementation.py": response},
                "test_commands": ["pytest tests/"],
                "qa_instructions": "รัน tests ตาม test_commands",
            }

        # พยายามรัน tests ถ้ามี
        output_data = await self._run_tests(output_data)
        return output_data

    async def _run_tests(self, output_data: dict) -> dict:
        """รัน Unit Tests จริงและเก็บผล"""
        files = output_data.get("files", {})
        test_commands = output_data.get("test_commands", [])

        if not test_commands:
            return output_data

        # บันทึก files ชั่วคราว
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w") as f:
                    f.write(str(content))

            # รัน test command แรก
            if test_commands:
                cmd = test_commands[0].split()
                try:
                    result = subprocess.run(
                        cmd, cwd=tmpdir, capture_output=True,
                        text=True, timeout=60
                    )
                    output_data["test_results"] = {
                        "command": test_commands[0],
                        "returncode": result.returncode,
                        "stdout": result.stdout[:1000],
                        "stderr": result.stderr[:500],
                        "passed": result.returncode == 0,
                    }
                except subprocess.TimeoutExpired:
                    output_data["test_results"] = {"error": "Test timeout"}
                except FileNotFoundError:
                    output_data["test_results"] = {"error": "Test runner not found"}

        return output_data



def main():
    token = os.getenv("DEV_DISCORD_TOKEN")
    if not token:
        raise ValueError("DEV_DISCORD_TOKEN not set")
    DEVAgent().run(token)

if __name__ == "__main__":
    main()
