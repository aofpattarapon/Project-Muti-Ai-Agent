"""
QAExecutionHelper — business logic for QA execution checks and DEV rework routing.

Intentionally free of Discord/bot imports so it can be unit-tested in any
environment without discord.py installed.
"""

import json
import logging
import os
from typing import Optional

from shared.storage import Storage, SdlcTask
from shared.test_runner import run_quality_checks, format_execution_result

logger = logging.getLogger(__name__)

# DEV task types that represent code implementation.
# Only these are eligible for QA-triggered rework requeue — not docs or design tasks.
_DEV_REWORK_TASK_TYPES = frozenset([
    "backend_code",
    "frontend_code",
    "unit_tests",
])

# npm script names that are allowed to execute.
# Note: the script names are allowlisted, but the script *contents* are defined
# by the project's package.json (project-controlled, not hardcoded here).
_ALLOWED_NPM_SCRIPTS = frozenset(["test", "build", "lint"])


class QAExecutionHelper:
    """
    Encapsulates all QA execution logic that is independent of Discord/bot runtime.
    Instantiate once per task; reuse the same instance across pre/post hooks.
    """

    def __init__(self, storage: Storage, output_base: str = ""):
        self.storage = storage
        self.output_base = output_base or os.getenv("OUTPUT_BASE_PATH", "/app/outputs")

    # ─── Project path resolution ──────────────────────────────────────────────

    def resolve_project_path(self, task: SdlcTask, input_data: dict) -> str:
        """Determine the filesystem path to run checks on.
        Priority: explicit override in input_data → DEV output dir → project dir."""
        if "project_path" in input_data:
            return input_data["project_path"]
        dev_dir = os.path.join(
            self.output_base, "projects", task.project_id, task.epic_id, "dev"
        )
        if os.path.isdir(dev_dir):
            return dev_dir
        return os.path.join(self.output_base, "projects", task.project_id)

    # ─── Execution ────────────────────────────────────────────────────────────

    def run_execution_checks(self, task: SdlcTask, input_data: dict) -> dict:
        """Run quality checks on the project path resolved from the task context."""
        project_path = self.resolve_project_path(task, input_data)
        return run_quality_checks(project_path, timeout_seconds=60)

    # ─── Artifact saving ──────────────────────────────────────────────────────

    def save_execution_artifact(
        self, task: SdlcTask, output_dir: str, result: dict
    ) -> None:
        """Write qa_execution_result.json alongside the main task artifact."""
        result_path = os.path.join(output_dir, "qa_execution_result.json")
        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"[qa] could not save qa_execution_result.json: {exc}")

    # ─── Routing decision ─────────────────────────────────────────────────────

    def decide_action(self, result: dict) -> str:
        """
        Map execution result status to a routing action.

        Returns:
            "rework"  — status == "failed": DEV implementation tasks should be requeued
            "blocked" — status == "blocked": infrastructure/timeout issue, human review needed
            "passed"  — all checks passed, normal flow
            "skipped" — no test env / no files, non-blocking
        """
        status = result.get("status", "skipped")
        if status == "failed":
            return "rework"
        if status == "blocked":
            return "blocked"
        return status  # "passed" or "skipped"

    # ─── DEV rework ───────────────────────────────────────────────────────────

    def build_feedback_message(self, result: dict) -> str:
        """Format failed checks into a concise role_feedback string for DEV tasks."""
        failed_checks = [
            c for c in result.get("checks", [])
            if c["status"] == "failed"
        ]
        if not failed_checks:
            return f"[qa-execution] {result.get('summary', 'execution failed')}"

        lines = [
            f"[qa-execution] {result.get('summary', 'checks failed')}",
            "Failed checks:",
        ]
        for c in failed_checks[:5]:
            tail = (c.get("stderr_tail") or c.get("stdout_tail") or "")[-150:].strip()
            lines.append(
                f"  - {c['name']} ({c.get('command', '')}): "
                f"{tail or c.get('skip_reason', 'no output')}"
            )
        return "\n".join(lines)

    def requeue_dev_tasks(self, task: SdlcTask, result: dict) -> list:
        """
        Requeue DEV implementation tasks in the same epic for rework.

        Only targets task types in _DEV_REWORK_TASK_TYPES — avoids touching docs,
        design, or structural tasks that don't need to change when tests fail.

        Returns list of task IDs that were successfully requeued.
        """
        feedback = self.build_feedback_message(result)
        note = (
            f"QA execution failed: {result.get('summary', 'see role_feedback')} "
            "— rework requested"
        )
        all_dev_tasks = self.storage.list_sdlc_tasks(task.project_id, role="dev")
        requeued = []
        for dev_task in all_dev_tasks:
            if dev_task.epic_id != task.epic_id:
                continue
            if dev_task.task_type not in _DEV_REWORK_TASK_TYPES:
                continue
            try:
                self.storage.update_sdlc_task_input_data(
                    dev_task.id, {"role_feedback": feedback}
                )
                if self.storage.requeue_for_rework(dev_task.id, note):
                    requeued.append(dev_task.id)
                    logger.info(f"[qa] requeued DEV task {dev_task.id} for rework")
            except Exception as exc:
                logger.warning(f"[qa] could not requeue {dev_task.id}: {exc}")
        return requeued

    # ─── Role override (old process_task flow) ────────────────────────────────

    def get_role_override(
        self,
        output_data: dict,
        execution_result: Optional[dict],
    ) -> Optional[str]:
        """
        Decide next-role override for the legacy process_task flow.

        Rules:
          failed  → "dev"  (tests failed, rework needed)
          blocked → None   (infra/timeout issue — needs human or DEVOPS, not auto-DEV)
          Legacy bug severity check still routes critical/high → "dev"
        """
        status = (execution_result or {}).get("status")
        if status == "failed":
            return "dev"
        if status == "blocked":
            # Infrastructure issue — do not auto-route to DEV
            return None

        # Legacy: route by bug severity when no execution result
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
