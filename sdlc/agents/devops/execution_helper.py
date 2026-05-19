"""
DEVOPSExecutionHelper — deployment readiness checks and artifact generation.

Zero Discord imports — fully unit-testable in any environment.

Safety rules:
  - Commands are hardcoded allowlist only (never from LLM output)
  - No actual deployment or destructive actions
  - .env values are never read — only .env.example structure is inspected
  - workspace_path validated under OUTPUT_BASE_PATH/DEV_WORKSPACE_BASE
"""

import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Optional

from shared.storage import Storage, SdlcTask
from shared.dev_workspace import WorkspacePathError, resolve_workspace as _resolve_ws_base

logger = logging.getLogger(__name__)

_OUTPUT_TAIL_CHARS = 500

# Task types that trigger pre-LLM execution checks
_DEVOPS_CHECK_TASK_TYPES = frozenset([
    "dockerfile", "docker_compose", "github_actions", "deployment_guide",
])

# DEV task types eligible for QA/DEVOPS-triggered rework (same set as QAExecutionHelper)
_DEV_REWORK_TASK_TYPES = frozenset(["backend_code", "frontend_code", "unit_tests"])


# ─── Internal check result helpers ───────────────────────────────────────────

def _check_result(
    name: str,
    command: str,
    status: str,
    returncode: Optional[int] = None,
    duration_seconds: float = 0.0,
    stdout_tail: str = "",
    stderr_tail: str = "",
    skip_reason: str = "",
) -> dict:
    return {
        "name": name,
        "command": command,
        "status": status,
        "returncode": returncode,
        "duration_seconds": round(duration_seconds, 2),
        "stdout_tail": stdout_tail[-_OUTPUT_TAIL_CHARS:] if stdout_tail else "",
        "stderr_tail": stderr_tail[-_OUTPUT_TAIL_CHARS:] if stderr_tail else "",
        "skip_reason": skip_reason,
    }


def _run_cmd(name: str, cmd: list, cwd: str, timeout: int) -> dict:
    """Run a hardcoded allowlisted command and return a check result dict."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        duration = time.monotonic() - t0
        status = "passed" if proc.returncode == 0 else "failed"
        return _check_result(
            name=name, command=" ".join(cmd), status=status,
            returncode=proc.returncode, duration_seconds=duration,
            stdout_tail=proc.stdout, stderr_tail=proc.stderr,
        )
    except subprocess.TimeoutExpired:
        return _check_result(
            name=name, command=" ".join(cmd), status="blocked",
            duration_seconds=time.monotonic() - t0,
            skip_reason=f"timed out after {timeout}s",
        )
    except FileNotFoundError:
        return _check_result(
            name=name, command=" ".join(cmd), status="skipped",
            skip_reason=f"command not found: {cmd[0]}",
        )
    except Exception as exc:
        return _check_result(
            name=name, command=" ".join(cmd), status="skipped",
            skip_reason=str(exc),
        )


# ─── Stack detection ──────────────────────────────────────────────────────────

def _detect_stack(project_path: str) -> list:
    """Identify technology stack from workspace contents."""
    stack = []
    try:
        top_files = set(os.listdir(project_path))
    except OSError:
        return stack

    if "package.json" in top_files:
        stack.append("node")

    if (any(f.startswith("Dockerfile") for f in top_files)
            or "docker-compose.yml" in top_files
            or "docker-compose.yaml" in top_files):
        stack.append("docker")

    # Walk for Python files (skip hidden dirs and caches)
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("__pycache__", "node_modules")
        ]
        if any(f.endswith(".py") for f in files):
            stack.append("python")
            break

    return stack


# ─── Individual check runners ─────────────────────────────────────────────────

def _run_python_checks(project_path: str, timeout: int) -> list:
    """Syntax-check Python files with py_compile."""
    py_files = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in ("__pycache__", "node_modules")
        ]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
        if len(py_files) >= 50:
            break

    if not py_files:
        return [_check_result(
            "python:py_compile", "python3 -m py_compile",
            "skipped", skip_reason="no .py files found in workspace",
        )]
    return [_run_cmd(
        "python:py_compile",
        ["python3", "-m", "py_compile"] + py_files,
        project_path, timeout,
    )]


def _run_node_checks(project_path: str, timeout: int) -> list:
    """Validate package.json and run allowlisted npm scripts."""
    pkg_path = os.path.join(project_path, "package.json")
    checks = []

    # Validate package.json parses correctly (config issue → DEV rework)
    try:
        with open(pkg_path, encoding="utf-8") as fh:
            pkg = json.load(fh)
        checks.append(_check_result(
            "node:package_json", "json parse", "passed",
            stdout_tail="package.json is valid JSON",
        ))
    except Exception as exc:
        checks.append(_check_result(
            "node:package_json", "json parse", "failed",
            stderr_tail=f"package.json parse error: {exc}",
        ))
        return checks  # scripts cannot run with invalid package.json

    if not shutil.which("npm"):
        # npm missing for a Node project — infrastructure issue → blocked
        checks.append(_check_result(
            "node:npm", "npm", "blocked",
            skip_reason="npm not found in PATH — required for Node.js project",
        ))
        return checks

    scripts = set(pkg.get("scripts", {}).keys())
    # Script *names* are allowlisted — contents come from project's package.json
    # and are not inspected here. Only run in trusted workspace environments.
    for script_name in ("build", "lint"):
        if script_name not in scripts:
            checks.append(_check_result(
                f"node:{script_name}", f"npm run {script_name}",
                "skipped",
                skip_reason=f"'{script_name}' not defined in package.json scripts",
            ))
        else:
            checks.append(_run_cmd(
                f"node:{script_name}",
                ["npm", "run", script_name, "--if-present"],
                project_path, timeout,
            ))
    return checks


def _run_docker_compose_check(project_path: str, timeout: int) -> Optional[dict]:
    """Validate docker-compose config syntax. Returns None if no compose file found."""
    compose_file = next(
        (f for f in ("docker-compose.yml", "docker-compose.yaml")
         if os.path.exists(os.path.join(project_path, f))),
        None,
    )
    if not compose_file:
        return None

    has_docker = bool(shutil.which("docker"))
    has_compose_v1 = bool(shutil.which("docker-compose"))

    if not has_docker and not has_compose_v1:
        return _check_result(
            "docker:compose_config", "docker compose config",
            "blocked",
            skip_reason="docker and docker-compose not found — required for Docker project",
        )

    if has_docker:
        result = _run_cmd(
            "docker:compose_config", ["docker", "compose", "config"],
            project_path, timeout,
        )
        if "not a docker command" not in (result.get("stderr_tail") or ""):
            return result

    if has_compose_v1:
        return _run_cmd(
            "docker:compose_config", ["docker-compose", "config"],
            project_path, timeout,
        )

    return _check_result(
        "docker:compose_config", "docker compose config",
        "blocked",
        skip_reason="docker compose plugin not available",
    )


def _validate_dockerfile_static(project_path: str) -> Optional[dict]:
    """Static validation: Dockerfile must have a FROM instruction. No docker execution."""
    top_files = set(os.listdir(project_path)) if os.path.isdir(project_path) else set()
    dockerfiles = [f for f in top_files if f.startswith("Dockerfile")]
    if not dockerfiles:
        return None

    dockerfile = os.path.join(project_path, dockerfiles[0])
    try:
        with open(dockerfile, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        non_comment = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        has_from = any(l.upper().startswith("FROM") for l in non_comment)
        if has_from:
            return _check_result(
                "docker:dockerfile_syntax", f"static validation: {dockerfiles[0]}",
                "passed", stdout_tail=f"FROM instruction found in {dockerfiles[0]}",
            )
        return _check_result(
            "docker:dockerfile_syntax", f"static validation: {dockerfiles[0]}",
            "failed", stderr_tail=f"No FROM instruction found in {dockerfiles[0]}",
        )
    except Exception as exc:
        return _check_result(
            "docker:dockerfile_syntax", f"static validation: {dockerfiles[0]}",
            "failed", stderr_tail=str(exc),
        )


def _check_env_file(project_path: str) -> Optional[dict]:
    """Inspect .env.example for variable count. Never reads .env values."""
    env_example = os.path.join(project_path, ".env.example")
    if not os.path.isfile(env_example):
        return _check_result(
            "env:env_example", "", "skipped",
            skip_reason=".env.example not found — cannot validate required env vars",
        )

    try:
        with open(env_example, encoding="utf-8", errors="replace") as fh:
            raw_lines = [l.strip() for l in fh if l.strip() and not l.strip().startswith("#")]
        var_names = [l.split("=")[0].strip() for l in raw_lines if "=" in l]
        env_dot = os.path.join(project_path, ".env")
        env_present = os.path.isfile(env_dot)
        msg = (
            f".env.example defines {len(var_names)} vars; "
            f".env {'present' if env_present else 'MISSING (create before deploy)'}"
        )
        status = "passed" if env_present else "skipped"
        return _check_result("env:env_example", "", status, stdout_tail=msg)
    except Exception as exc:
        return _check_result(
            "env:env_example", "", "skipped",
            skip_reason=f"could not read .env.example: {exc}",
        )


# ─── Result builder ───────────────────────────────────────────────────────────

def _build_result(
    checks: list,
    workspace_path: str = "",
    detected_stack: Optional[list] = None,
) -> dict:
    failed  = [c for c in checks if c["status"] == "failed"]
    passed  = [c for c in checks if c["status"] == "passed"]
    blocked = [c for c in checks if c["status"] == "blocked"]
    skipped = [c for c in checks if c["status"] == "skipped"]

    if not checks:
        overall = "skipped"
    elif blocked:
        # Any blocked check (required tool missing / timeout) → blocked overall
        overall = "blocked"
    elif failed:
        overall = "failed"
    elif passed:
        overall = "passed"
    else:
        overall = "skipped"

    deployment_blockers = []
    for c in blocked + failed:
        reason = c.get("skip_reason") or ""
        tail = (c.get("stderr_tail") or c.get("stdout_tail") or "")[-120:].strip()
        detail = reason or tail
        if detail:
            deployment_blockers.append(f"{c['name']}: {detail}")

    parts = []
    if passed:
        parts.append(f"{len(passed)} passed")
    if failed:
        parts.append(f"{len(failed)} failed")
    if blocked:
        parts.append(f"{len(blocked)} blocked")
    if skipped:
        parts.append(f"{len(skipped)} skipped")
    summary = ", ".join(parts) if parts else "no checks ran"

    return {
        "status": overall,
        "summary": summary,
        "workspace_path": workspace_path,
        "detected_stack": detected_stack or [],
        "checks": checks,
        "deployment_blockers": deployment_blockers,
        "release_notes": [],
        "failed_count": len(failed),
        "passed_count": len(passed),
        "blocked_count": len(blocked),
        "skipped_count": len(skipped),
    }


# ─── Public runner ────────────────────────────────────────────────────────────

def run_deployment_checks(project_path: str, timeout_seconds: int = 120) -> dict:
    """
    Run deployment readiness checks on project_path.
    Commands are hardcoded allowlist only — no LLM-provided execution.

    Returns result dict with schema:
    {status, summary, workspace_path, detected_stack, checks,
     deployment_blockers, release_notes, failed_count, ...}
    """
    if not project_path or not os.path.isdir(project_path):
        return _build_result(
            [_check_result(
                "setup", "", "skipped",
                skip_reason=(
                    f"workspace not found or not a directory: {project_path!r}"
                    if project_path else "no workspace path provided"
                ),
            )],
            workspace_path=project_path or "",
        )

    stack = _detect_stack(project_path)
    if not stack:
        return _build_result(
            [_check_result(
                "setup", "", "skipped",
                skip_reason="no recognized stack detected (no package.json, .py files, or Dockerfile)",
            )],
            workspace_path=project_path,
            detected_stack=[],
        )

    per_check_timeout = max(10, timeout_seconds // 4)
    checks = []

    if "python" in stack:
        checks.extend(_run_python_checks(project_path, per_check_timeout))

    if "node" in stack:
        checks.extend(_run_node_checks(project_path, per_check_timeout))

    if "docker" in stack:
        compose_check = _run_docker_compose_check(project_path, per_check_timeout)
        if compose_check:
            checks.append(compose_check)
        df_check = _validate_dockerfile_static(project_path)
        if df_check:
            checks.append(df_check)

    env_check = _check_env_file(project_path)
    if env_check:
        checks.append(env_check)

    return _build_result(checks, workspace_path=project_path, detected_stack=stack)


# ─── Formatting ───────────────────────────────────────────────────────────────

def format_execution_result(result: dict) -> str:
    """Format run_deployment_checks result as human-readable string for LLM prompts."""
    if not result:
        return "ไม่มีข้อมูล DEVOPS execution"
    status = result.get("status", "unknown").upper()
    summary = result.get("summary", "")
    stack = ", ".join(result.get("detected_stack", [])) or "ไม่ระบุ"
    ws = result.get("workspace_path", "")

    lines = [f"**Deployment Readiness:** {status} — {summary}"]
    if stack != "ไม่ระบุ":
        lines.append(f"**Stack:** {stack}")
    if ws:
        lines.append(f"**Workspace:** {ws}")
    lines.append("")

    blockers = result.get("deployment_blockers", [])
    if blockers:
        lines.append("**Deployment Blockers:**")
        for b in blockers[:5]:
            lines.append(f"  ❌ {b}")
        lines.append("")

    icons = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "blocked": "🚫"}
    for check in result.get("checks", []):
        icon = icons.get(check["status"], "?")
        cmd = check.get("command", "") or check.get("name", "")
        lines.append(f"{icon} **{check['name']}**" + (f" (`{cmd}`)" if cmd else ""))
        if check.get("skip_reason"):
            lines.append(f"   ↳ {check['skip_reason']}")
        if check["status"] == "failed":
            tail = (check.get("stderr_tail") or check.get("stdout_tail") or "")[-200:]
            if tail:
                lines.append(f"   ↳ {tail.strip()}")

    return "\n".join(lines)


# ─── Report builder ───────────────────────────────────────────────────────────

def build_deployment_report(result: dict, task_id: str, project_name: str = "") -> str:
    """Generate deployment_readiness_report.md content from check results."""
    status = result.get("status", "unknown")
    icons = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "blocked": "🚫"}
    icon = icons.get(status, "?")
    stack = ", ".join(result.get("detected_stack", [])) or "ไม่ระบุ"
    ws = result.get("workspace_path", "ไม่ระบุ")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Deployment Readiness Report",
        f"**Project:** {project_name or 'N/A'}  |  **Task:** `{task_id}`  |  **Date:** {now}",
        f"**Status:** {icon} {status.upper()} — {result.get('summary', '')}",
        "",
        f"## Stack Detected\n{stack}",
        f"\n## Workspace\n`{ws}`",
        "",
        "## Checks",
        "| Check | Status | Duration | Detail |",
        "|-------|--------|---------|--------|",
    ]
    for c in result.get("checks", []):
        chk_icon = icons.get(c["status"], "?")
        dur = f"{c.get('duration_seconds', 0):.2f}s"
        detail = (c.get("skip_reason") or
                  (c.get("stderr_tail") or c.get("stdout_tail") or "")[-80:].strip() or "")
        lines.append(f"| {c['name']} | {chk_icon} {c['status']} | {dur} | {detail} |")

    blockers = result.get("deployment_blockers", [])
    if blockers:
        lines += ["", "## Deployment Blockers"]
        for b in blockers:
            lines.append(f"- ❌ {b}")

    notes = result.get("release_notes", [])
    if notes:
        lines += ["", "## Release Notes"]
        for n in notes:
            lines.append(f"- {n}")

    lines += ["", "## Next Steps"]
    if status == "passed":
        lines.append("All checks passed. Proceed with manual deployment approval.")
    elif status == "blocked":
        lines.append("Infrastructure or tooling issue detected. Human review required before deployment.")
        lines.append("Do not route to DEV automatically — this is an environment/infra issue.")
    elif status == "failed":
        lines.append("Application or configuration failures found. Route to DEV for rework.")
        for b in blockers[:3]:
            lines.append(f"  - Fix: {b}")
    else:
        lines.append("No actionable checks ran. Verify workspace path and stack detection.")

    return "\n".join(lines) + "\n"


# ─── DEVOPSExecutionHelper ────────────────────────────────────────────────────

class DEVOPSExecutionHelper:
    """
    Encapsulates DEVOPS deployment readiness logic.
    Discord-free — fully testable without discord.py.
    """

    def __init__(self, storage: Storage, output_base: str = ""):
        self.storage = storage
        self.output_base = output_base or os.getenv("OUTPUT_BASE_PATH", "/app/outputs")

    # ─── Workspace resolution ─────────────────────────────────────────────────

    def resolve_workspace(self, task: SdlcTask, input_data: dict) -> str:
        """
        Resolve workspace root with fallback to project-level workspace.
        Priority:
          1. input_data["workspace_path"] — validated under allowed base
          2. output_base/projects/{project_id}/{epic_id}/workspace  (if exists)
          3. output_base/projects/{project_id}/workspace
        """
        epic_ws = _resolve_ws_base(
            project_id=task.project_id,
            epic_id=task.epic_id,
            input_data=input_data,
            output_base=self.output_base,
        )
        # If explicit workspace_path was given, return the validated result directly
        if "workspace_path" in input_data:
            return epic_ws
        # Auto-select: prefer epic workspace if it exists, else project workspace
        if os.path.isdir(epic_ws):
            return epic_ws
        return os.path.join(self.output_base, "projects", task.project_id, "workspace")

    # ─── Checks ───────────────────────────────────────────────────────────────

    def run_deployment_checks(self, task: SdlcTask, input_data: dict) -> dict:
        """Run deployment readiness checks on the resolved workspace."""
        workspace = self.resolve_workspace(task, input_data)
        return run_deployment_checks(workspace, timeout_seconds=90)

    # ─── Routing ──────────────────────────────────────────────────────────────

    def decide_routing(self, result: dict) -> str:
        """
        Map check result to routing action.

        Returns:
          "rework_dev" — application/code failure → requeue DEV tasks
          "blocked"    — infra/tool/timeout issue → human review, no auto-DEV
          "normal"     — passed or skipped → normal DEVOPS flow
        """
        status = result.get("status", "skipped")
        if status == "blocked":
            return "blocked"
        if status == "failed":
            # If any failed check is actually a blocked (tool/timeout) → treat as blocked
            for c in result.get("checks", []):
                if c["status"] == "blocked":
                    return "blocked"
            return "rework_dev"
        return "normal"

    # ─── DEV rework ───────────────────────────────────────────────────────────

    def build_feedback_message(self, result: dict) -> str:
        """Build role_feedback string for DEV tasks from failed checks."""
        failed = [c for c in result.get("checks", []) if c["status"] == "failed"]
        if not failed:
            return f"[devops-execution] {result.get('summary', 'deployment checks failed')}"

        lines = [
            f"[devops-execution] {result.get('summary', 'checks failed')}",
            "Deployment readiness checks failed:",
        ]
        for c in failed[:5]:
            tail = (c.get("stderr_tail") or c.get("stdout_tail") or "")[-150:].strip()
            lines.append(
                f"  - {c['name']} ({c.get('command', '')}): "
                f"{tail or c.get('skip_reason', 'no output')}"
            )
        return "\n".join(lines)

    def requeue_dev_tasks(self, task: SdlcTask, result: dict) -> list:
        """Requeue DEV code tasks in the same epic for rework. Returns list of requeued IDs."""
        feedback = self.build_feedback_message(result)
        note = (
            f"DEVOPS deployment check failed: {result.get('summary', 'see role_feedback')} "
            "— DEV rework requested"
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
            except Exception as exc:
                logger.warning(f"[devops] could not requeue {dev_task.id}: {exc}")
        return requeued

    # ─── Artifact saving ──────────────────────────────────────────────────────

    def save_execution_artifact(
        self,
        task: SdlcTask,
        output_dir: str,
        result: dict,
        project_name: str = "",
    ) -> None:
        """Write devops_execution_result.json and deployment_readiness_report.md."""
        try:
            os.makedirs(output_dir, exist_ok=True)

            result_path = os.path.join(output_dir, "devops_execution_result.json")
            with open(result_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, ensure_ascii=False)

            report_md = build_deployment_report(result, task.id, project_name)
            report_path = os.path.join(output_dir, "deployment_readiness_report.md")
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(report_md)

        except Exception as exc:
            logger.warning(f"[devops] could not save execution artifacts for {task.id}: {exc}")
