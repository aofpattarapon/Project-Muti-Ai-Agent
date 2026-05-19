"""
QA Agent - Quality Assurance
สร้าง QA documents + รัน real quality checks ก่อนสร้าง test_report
ถ้า execution failed → requeue DEV code tasks สำหรับ rework
ถ้า execution blocked → human/DEVOPS intervention (ไม่ auto-route)
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Optional

from shared.base_agent import BaseAgent
from shared.storage import Project, SdlcTask
from shared.test_runner import format_execution_result
from agents.qa.execution_helper import QAExecutionHelper
from agents.qa.prompts import QA_SYSTEM_PROMPT, build_qa_prompt

logger = logging.getLogger(__name__)


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.role_name = "qa"
        self._last_execution_result: Optional[dict] = None  # set by _pre_llm_hook

    @property
    def system_prompt(self) -> str:
        return QA_SYSTEM_PROMPT

    # ─── Legacy process_task (old-style Discord flow) ─────────────────────────

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

        prev_files = prev.get("files", {})
        output_data = await self._execute_legacy_tests(output_data, prev_files)
        return output_data

    def _get_role_metrics(self, output_data: dict) -> dict:
        import re
        stats    = output_data.get("test_stats", {})
        bugs     = output_data.get("bugs_found", 0) or 0
        severity = output_data.get("severity_breakdown", {})
        summary  = output_data.get("summary", "")
        total    = stats.get("total", "") or (re.search(r'(\d+)\s*test', summary, re.I) or [None, "?"])[1]
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
        """Route back to DEV if critical/high bugs found or execution failed.
        Note: blocked (timeout/infra) does NOT auto-route to DEV — needs human review."""
        helper = QAExecutionHelper(self.storage)
        return helper.get_role_override(output_data, self._last_execution_result)

    # ─── SDLC hooks ───────────────────────────────────────────────────────────

    async def _pre_llm_hook(self, task: SdlcTask, input_data: dict) -> dict:
        """For test_report: run quality checks and inject results into LLM context."""
        if task.task_type != "test_report":
            return {}
        helper = QAExecutionHelper(self.storage)
        result = helper.run_execution_checks(task, input_data)
        self._last_execution_result = result
        return {
            "qa_execution_result": result,
            "qa_execution_formatted": format_execution_result(result),
        }

    async def _post_save_hook(self, task: SdlcTask, output_dir: str, content: str = "") -> None:
        """For test_report:
        - Save qa_execution_result.json
        - If failed: requeue DEV code tasks for rework
        - If blocked: log warning for human/infra review (no auto-requeue)
        """
        if task.task_type != "test_report" or not self._last_execution_result:
            return

        helper = QAExecutionHelper(self.storage)
        helper.save_execution_artifact(task, output_dir, self._last_execution_result)

        action = helper.decide_action(self._last_execution_result)
        if action == "rework":
            requeued = helper.requeue_dev_tasks(task, self._last_execution_result)
            if requeued:
                logger.info(
                    f"[qa] test_report {task.id} execution failed — requeued DEV tasks: {requeued}"
                )
        elif action == "blocked":
            logger.warning(
                f"[qa] test_report {task.id} execution blocked "
                f"({self._last_execution_result.get('summary', '')}) — "
                "infrastructure/timeout issue, human or DEVOPS review needed"
            )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_code_summary(self, files: dict) -> str:
        code_content = []
        for fname, content in files.items():
            if fname.endswith((".py", ".js", ".ts", ".go")) and not fname.startswith("test"):
                code_content.append(f"### {fname}\n{str(content)[:500]}")
        return "\n\n".join(code_content[:3]) or "ไม่มี source code"

    async def _execute_legacy_tests(self, output_data: dict, dev_files: dict) -> dict:
        """รัน pytest tests จริงในรูปแบบ legacy process_task flow."""
        files      = output_data.get("files", {})
        test_files = {k: v for k, v in files.items() if "test" in k and k.endswith(".py")}
        if not test_files:
            return output_data

        with tempfile.TemporaryDirectory() as tmpdir:
            for fname, content in dev_files.items():
                if fname.endswith(".py"):
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
                    ["python3", "-m", "pytest", "--tb=short", "-v"],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60,
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
