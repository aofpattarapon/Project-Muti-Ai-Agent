"""
Test Runner — runs quality checks on a project directory.

Commands are selected from an allowlist only — never from LLM output.
Returns a structured result dict; missing tools or absent directories
produce "skipped" results rather than crashes.
"""

import json
import os
import shutil
import subprocess
import time
from typing import Optional

# Tail length for captured output per check (chars)
_OUTPUT_TAIL_CHARS = 500


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _check_result(
    name: str,
    command: str,
    status: str,
    exit_code: Optional[int] = None,
    duration_seconds: float = 0.0,
    stdout_tail: str = "",
    stderr_tail: str = "",
    skip_reason: str = "",
) -> dict:
    return {
        "name": name,
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": round(duration_seconds, 2),
        "stdout_tail": stdout_tail[-_OUTPUT_TAIL_CHARS:] if stdout_tail else "",
        "stderr_tail": stderr_tail[-_OUTPUT_TAIL_CHARS:] if stderr_tail else "",
        "skip_reason": skip_reason,
    }


def _build_result(checks: list) -> dict:
    failed   = [c for c in checks if c["status"] == "failed"]
    passed   = [c for c in checks if c["status"] == "passed"]
    skipped  = [c for c in checks if c["status"] in ("skipped", "error")]
    timed_out = [
        c for c in failed
        if "timed out" in (c.get("skip_reason") or "")
    ]

    if not checks:
        overall = "skipped"
    elif failed:
        # All failures are timeouts → blocked; otherwise failed
        overall = "blocked" if len(timed_out) == len(failed) else "failed"
    elif passed:
        overall = "passed"
    else:
        overall = "skipped"

    parts = []
    if passed:
        parts.append(f"{len(passed)} passed")
    if failed:
        parts.append(f"{len(failed)} failed")
    if skipped:
        parts.append(f"{len(skipped)} skipped")
    summary = ", ".join(parts) if parts else "no checks ran"

    return {
        "status": overall,
        "checks": checks,
        "summary": summary,
        "failed_count": len(failed),
        "passed_count": len(passed),
        "skipped_count": len(skipped),
    }


def _run_cmd(name: str, cmd: list, cwd: str, timeout: int) -> dict:
    """Run an allowlisted command and return a check result dict."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - t0
        status = "passed" if proc.returncode == 0 else "failed"
        return _check_result(
            name=name,
            command=" ".join(cmd),
            status=status,
            exit_code=proc.returncode,
            duration_seconds=duration,
            stdout_tail=proc.stdout,
            stderr_tail=proc.stderr,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return _check_result(
            name=name,
            command=" ".join(cmd),
            status="failed",
            exit_code=None,
            duration_seconds=duration,
            skip_reason=f"timed out after {timeout}s",
        )
    except FileNotFoundError:
        return _check_result(
            name=name,
            command=" ".join(cmd),
            status="skipped",
            skip_reason=f"command not found: {cmd[0]}",
        )
    except Exception as exc:
        return _check_result(
            name=name,
            command=" ".join(cmd),
            status="error",
            skip_reason=str(exc),
        )


# ─── Profile detection ────────────────────────────────────────────────────────

def _detect_profile(project_path: str) -> Optional[str]:
    """Infer project type from directory contents."""
    if not os.path.isdir(project_path):
        return None
    top_files = set(os.listdir(project_path))
    if "package.json" in top_files:
        return "node"
    # Any .py file in the tree → python
    for _root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        if any(f.endswith(".py") for f in files):
            return "python"
    if "docker-compose.yml" in top_files or "docker-compose.yaml" in top_files:
        return "docker"
    return None


def _read_package_scripts(project_path: str) -> set:
    pkg = os.path.join(project_path, "package.json")
    try:
        with open(pkg, encoding="utf-8") as fh:
            return set(json.load(fh).get("scripts", {}).keys())
    except Exception:
        return set()


def _find_python_files(project_path: str, max_files: int = 50) -> list:
    result = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
                if len(result) >= max_files:
                    return result
    return result


# ─── Profile runners ──────────────────────────────────────────────────────────

def _run_python_checks(project_path: str, timeout: int) -> list:
    checks = []

    # Check 1: syntax via py_compile
    py_files = _find_python_files(project_path)
    if not py_files:
        checks.append(_check_result(
            name="python:py_compile",
            command="python3 -m py_compile",
            status="skipped",
            skip_reason="no .py files found in project_path",
        ))
    else:
        checks.append(_run_cmd(
            "python:py_compile",
            ["python3", "-m", "py_compile"] + py_files,
            project_path,
            timeout,
        ))

    # Check 2: pytest (only if installed)
    probe = subprocess.run(
        ["python3", "-m", "pytest", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    if probe.returncode != 0:
        checks.append(_check_result(
            name="python:pytest",
            command="python3 -m pytest",
            status="skipped",
            skip_reason="pytest not installed (python3 -m pytest --version failed)",
        ))
    else:
        checks.append(_run_cmd(
            "python:pytest",
            ["python3", "-m", "pytest", "--tb=short", "-q"],
            project_path,
            timeout,
        ))

    return checks


def _run_node_checks(project_path: str, timeout: int) -> list:
    if not shutil.which("npm"):
        return [_check_result(
            name="node:npm",
            command="npm",
            status="skipped",
            skip_reason="npm not found in PATH",
        )]

    scripts = _read_package_scripts(project_path)
    checks = []
    for script_name in ("test", "build", "lint"):
        if script_name not in scripts:
            checks.append(_check_result(
                name=f"node:{script_name}",
                command=f"npm run {script_name}",
                status="skipped",
                skip_reason=f"'{script_name}' script not defined in package.json",
            ))
        else:
            # --if-present is belt-and-suspenders; we already checked above
            checks.append(_run_cmd(
                f"node:{script_name}",
                ["npm", "run", script_name, "--if-present"],
                project_path,
                timeout,
            ))
    return checks


def _run_docker_checks(project_path: str, timeout: int) -> list:
    compose_file = next(
        (f for f in ("docker-compose.yml", "docker-compose.yaml")
         if os.path.exists(os.path.join(project_path, f))),
        None,
    )
    if not compose_file:
        return [_check_result(
            name="docker:compose_config",
            command="docker compose config",
            status="skipped",
            skip_reason="no docker-compose.yml/yaml found",
        )]

    # Prefer docker compose v2; fall back to docker-compose v1
    if shutil.which("docker"):
        result = _run_cmd(
            "docker:compose_config",
            ["docker", "compose", "config"],
            project_path,
            timeout,
        )
        # v2 reports "not a docker command" in stderr when plugin is absent
        if "not a docker command" not in (result.get("stderr_tail") or ""):
            return [result]

    if shutil.which("docker-compose"):
        return [_run_cmd(
            "docker:compose_config",
            ["docker-compose", "config"],
            project_path,
            timeout,
        )]

    return [_check_result(
        name="docker:compose_config",
        command="docker compose config",
        status="skipped",
        skip_reason="docker / docker-compose not found in PATH",
    )]


# ─── Public API ───────────────────────────────────────────────────────────────

def run_quality_checks(
    project_path: str,
    profile: Optional[str] = None,
    timeout_seconds: int = 120,
) -> dict:
    """
    Run quality checks on project_path.

    profile: "python" | "node" | "docker" | None (auto-detect)
    timeout_seconds: budget shared across all checks (each check gets 1/3)

    Returns:
    {
        "status": "passed" | "failed" | "skipped" | "blocked",
        "checks": [
            {
                "name": str, "command": str, "status": str,
                "exit_code": int|None, "duration_seconds": float,
                "stdout_tail": str, "stderr_tail": str, "skip_reason": str,
            },
            ...
        ],
        "summary": str,
        "failed_count": int,
        "passed_count": int,
        "skipped_count": int,
    }
    """
    if not project_path:
        return _build_result([_check_result(
            name="setup",
            command="",
            status="skipped",
            skip_reason="no project_path provided",
        )])

    if not os.path.isdir(project_path):
        return _build_result([_check_result(
            name="setup",
            command="",
            status="skipped",
            skip_reason=f"project_path does not exist or is not a directory: {project_path!r}",
        )])

    resolved_profile = profile or _detect_profile(project_path)
    if resolved_profile is None:
        return _build_result([_check_result(
            name="setup",
            command="",
            status="skipped",
            skip_reason=(
                "could not detect project type — "
                "no .py files, package.json, or docker-compose.yml found"
            ),
        )])

    per_check_timeout = max(10, timeout_seconds // 3)

    if resolved_profile == "python":
        checks = _run_python_checks(project_path, per_check_timeout)
    elif resolved_profile == "node":
        checks = _run_node_checks(project_path, per_check_timeout)
    elif resolved_profile == "docker":
        checks = _run_docker_checks(project_path, per_check_timeout)
    else:
        checks = [_check_result(
            name="setup",
            command="",
            status="skipped",
            skip_reason=f"unknown profile: {resolved_profile!r}",
        )]

    return _build_result(checks)


def format_execution_result(result: dict) -> str:
    """Format a run_quality_checks result as a human-readable string for prompts/messages."""
    if not result:
        return "ไม่มีผล execution"
    status = result.get("status", "unknown").upper()
    summary = result.get("summary", "")
    lines = [f"**Execution Status:** {status} — {summary}", ""]
    icons = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "⚠️", "blocked": "🔒"}
    for check in result.get("checks", []):
        icon = icons.get(check["status"], "?")
        cmd = check.get("command") or check.get("name", "")
        lines.append(f"{icon} **{check['name']}**" + (f" (`{cmd}`)" if cmd else ""))
        if check.get("skip_reason"):
            lines.append(f"   ↳ {check['skip_reason']}")
        if check["status"] in ("failed", "error"):
            tail = (check.get("stderr_tail") or check.get("stdout_tail") or "")[-200:]
            if tail:
                lines.append(f"   ↳ {tail.strip()}")
    return "\n".join(lines)
