"""
QA Agent - Quality Assurance
รัน Tests จริง + สร้าง Test Documentation
ถ้าพบ critical/high bugs → ส่งกลับ DEV แก้ไขอัตโนมัติ
"""

import os
import json
import subprocess
import tempfile
from typing import Optional
from shared.base_agent import BaseAgent
from shared.storage import Project

from agents.qa.prompts import QA_SYSTEM_PROMPT, build_qa_prompt


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "qa"

    @property
    def system_prompt(self) -> str:
        return QA_SYSTEM_PROMPT

    async def process_task(self, project: Project, input_data: dict) -> dict:
        prev = input_data.get("previous_output", {})
        revision_comment = input_data.get("revision_comment", "")
        revision_count = input_data.get("revision_count", 0)

        prompt = build_qa_prompt(prev, revision_comment, revision_count)
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
            output_data = json.loads(json_str)
        except Exception:
            output_data = {
                "summary": f"QA Report for {project.name}",
                "files": {"test_plan.md": response},
                "devops_instructions": "ดู test_plan.md",
            }

        # รัน tests จริงถ้ามี
        prev_files = prev.get("files", {})
        output_data = await self._execute_tests(output_data, prev_files)
        return output_data

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        stats    = output_data.get("test_stats", {})
        bugs     = output_data.get("bugs_found", 0) or 0
        severity = output_data.get("severity_breakdown", {})
        # Fallback: extract from summary text
        summary  = output_data.get("summary", "")
        total    = stats.get("total", "") or (re.search(r'(\d+)\s*test', summary, re.I) or [None,"?"])[1]
        passed   = stats.get("passed", "") or "?"
        coverage = stats.get("coverage", "") or "?"
        crit     = severity.get("critical", 0) or 0
        high     = severity.get("high", 0) or 0
        return {
            "🧪 Tests": f"{passed}/{total} passed",
            "📊 Coverage": f"{coverage}%",
            "🐛 Bugs Found": f"{bugs} ({crit} crit / {high} high)",
        }

    def _get_next_role_override(self, output_data: dict) -> Optional[str]:
        """Send back to DEV if critical or high severity bugs were found."""
        try:
            bugs = int(output_data.get("bugs_found", 0) or 0)
        except (ValueError, TypeError):
            bugs = 0
        if bugs <= 0:
            return None
        severity = output_data.get("severity_breakdown", {})
        try:
            critical = int(severity.get("critical", 0) or 0)
            high     = int(severity.get("high", 0) or 0)
        except (ValueError, TypeError):
            critical = high = 0
        if critical > 0 or high > 0:
            return "dev"
        return None

    def _get_code_summary(self, files: dict) -> str:
        code_content = []
        for fname, content in files.items():
            if fname.endswith((".py", ".js", ".ts", ".go")) and not fname.startswith("test"):
                code_content.append(f"### {fname}\n{str(content)[:500]}")
        return "\n\n".join(code_content[:3]) or "ไม่มี source code"

    async def _execute_tests(self, output_data: dict, dev_files: dict) -> dict:
        """รัน pytest tests จริง"""
        files      = output_data.get("files", {})
        test_files = {k: v for k, v in files.items() if "test" in k and k.endswith(".py")}
        if not test_files:
            return output_data

        with tempfile.TemporaryDirectory() as tmpdir:
            for fname, content in dev_files.items():
                if fname.endswith((".py",)):
                    fpath = os.path.join(tmpdir, fname)
                    os.makedirs(os.path.dirname(fpath), exist_ok=True)
                    with open(fpath, "w") as f:
                        f.write(str(content))
            for fname, content in test_files.items():
                fpath = os.path.join(tmpdir, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w") as f:
                    f.write(str(content))
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", "--tb=short", "-v", "--co"],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60
                )
                output_data["actual_test_run"] = {
                    "command": "pytest --tb=short -v",
                    "returncode": result.returncode,
                    "output": result.stdout[:2000],
                    "passed": result.returncode == 0,
                }
            except Exception as e:
                output_data["actual_test_run"] = {"error": str(e)}

        return output_data


def main():
    token = os.getenv("QA_DISCORD_TOKEN")
    if not token:
        raise ValueError("QA_DISCORD_TOKEN not set")
    QAAgent().run(token)

if __name__ == "__main__":
    main()
