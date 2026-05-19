"""
QA Agent - Quality Assurance
สร้าง QA documents + รัน real quality checks ก่อนสร้าง test_report
ถ้าพบ critical/high bugs หรือ execution fail → ส่งกลับ DEV
"""

import json
import os
import subprocess
import tempfile
from typing import Optional

from shared.base_agent import BaseAgent
from shared.storage import Project, SdlcTask
from shared.test_runner import run_quality_checks, format_execution_result

from agents.qa.prompts import QA_SYSTEM_PROMPT, build_qa_prompt


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
        """Route back to DEV if critical/high bugs found or execution failed."""
        # Check execution result first
        exec_result = (
            self._last_execution_result
            or output_data.get("qa_execution_result")
        )
        if exec_result and exec_result.get("status") == "failed":
            return "dev"

        # Original logic: route by bug severity
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

    # ─── SDLC hooks ───────────────────────────────────────────────────────────

    async def _pre_llm_hook(self, task: SdlcTask, input_data: dict) -> dict:
        """For test_report: run quality checks and return results as context."""
        if task.task_type != "test_report":
            return {}

        project_path = self._resolve_project_path(task, input_data)
        result = run_quality_checks(project_path, timeout_seconds=60)
        self._last_execution_result = result

        return {
            "qa_execution_result": result,
            "qa_execution_formatted": format_execution_result(result),
        }

    async def _post_save_hook(self, task: SdlcTask, output_dir: str) -> None:
        """For test_report: save execution JSON artifact + inject DEV feedback if failed."""
        if task.task_type != "test_report" or not self._last_execution_result:
            return

        # Save qa_execution_result.json alongside test_report
        result_path = os.path.join(output_dir, "qa_execution_result.json")
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as fh:
                json.dump(self._last_execution_result, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                f"[qa] could not save qa_execution_result.json: {exc}"
            )

        # If execution failed, inject feedback into DEV tasks for the same epic
        if self._last_execution_result.get("status") == "failed":
            self._inject_dev_feedback(task)

    def _inject_dev_feedback(self, task: SdlcTask) -> None:
        """Inject role_feedback into DEV tasks in the same epic so DEV sees what failed."""
        result = self._last_execution_result
        if not result:
            return

        failed_checks = [
            c for c in result.get("checks", [])
            if c["status"] == "failed"
        ]
        if not failed_checks:
            return

        summary_lines = [
            f"[qa-execution] {result.get('summary', 'checks failed')}",
            "Failed checks:",
        ]
        for c in failed_checks[:5]:
            tail = (c.get("stderr_tail") or c.get("stdout_tail") or "")[-150:].strip()
            summary_lines.append(
                f"  - {c['name']}: {tail or c.get('skip_reason', 'no output')}"
            )
        feedback = "\n".join(summary_lines)

        # Find DEV tasks in same epic and inject feedback
        all_dev_tasks = self.storage.list_sdlc_tasks(task.project_id, role="dev")
        for dev_task in all_dev_tasks:
            if dev_task.epic_id != task.epic_id:
                continue
            try:
                self.storage.update_sdlc_task_input_data(
                    dev_task.id, {"role_feedback": feedback}
                )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    f"[qa] could not inject feedback into {dev_task.id}: {exc}"
                )

    def _resolve_project_path(self, task: SdlcTask, input_data: dict) -> str:
        # 1. Explicit override in input_data
        if "project_path" in input_data:
            return input_data["project_path"]
        # 2. DEV output directory for the same epic
        output_base = os.getenv("OUTPUT_BASE_PATH", "/app/outputs")
        dev_dir = os.path.join(
            output_base, "projects", task.project_id, task.epic_id, "dev"
        )
        if os.path.isdir(dev_dir):
            return dev_dir
        # 3. Project-wide output directory (may not exist — test_runner handles that)
        return os.path.join(output_base, "projects", task.project_id)

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
