"""
Tests for agents/devops/execution_helper.py and agents/devops/task_prompts.py (Phase 5).

Run: python3 sdlc/tests/test_devops_execution.py
  or: python3 -m pytest sdlc/tests/test_devops_execution.py -v

No discord.py dependency — all DEVOPS business logic is tested via Discord-free helpers.

Safety properties tested:
  - Commands are hardcoded allowlist only (never from LLM output)
  - No actual deployment actions
  - .env values are never read — only .env.example structure is inspected
  - workspace_path validated under OUTPUT_BASE_PATH/DEV_WORKSPACE_BASE
  - failed (code issues) → rework_dev
  - blocked (infra/tool/timeout) → blocked (no auto-DEV requeue)
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.devops.execution_helper import (
    DEVOPSExecutionHelper,
    _DEVOPS_CHECK_TASK_TYPES,
    _DEV_REWORK_TASK_TYPES,
    _check_result,
    _build_result,
    _detect_stack,
    _run_cmd,
    _validate_dockerfile_static,
    _check_env_file,
    _run_python_checks,
    _run_node_checks,
    _run_docker_compose_check,
    run_deployment_checks,
    format_execution_result,
    build_deployment_report,
    generate_release_notes,
)
from shared.storage import Storage, SdlcTask
from shared.dev_workspace import WorkspacePathError


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write(path: str, content: str = "") -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_task(
    task_id: str = "t1",
    role: str = "devops",
    task_type: str = "dockerfile",
    project_id: str = "proj1",
    epic_id: str = "proj1-E001",
    status: str = "in_progress",
    input_data: str = "{}",
    revision_count: int = 0,
    attempt_count: int = 0,
) -> SdlcTask:
    now = datetime.utcnow().isoformat()
    return SdlcTask(
        id=task_id, project_id=project_id, epic_id=epic_id, task_number=1,
        role=role, task_type=task_type, title=f"Task {task_id}", description="",
        output_file="out.md", output_format="markdown", depends_on="",
        status=status, input_data=input_data, output_data="{}",
        approval_msg_id="", revision_count=revision_count, notes="",
        created_at=now, updated_at=now,
        attempt_count=attempt_count, claimed_by="", claimed_at="",
        last_error="",
    )


def _mock_storage(tasks=None):
    s = MagicMock(spec=Storage)
    s.list_sdlc_tasks.return_value = tasks or []
    s.requeue_for_rework.return_value = True
    s.update_sdlc_task_input_data.return_value = None
    s.get_project.return_value = MagicMock(name="TestProject")
    return s


# ─── TestConstants ────────────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):
    def test_check_task_types(self):
        expected = {"dockerfile", "docker_compose", "github_actions", "deployment_guide"}
        self.assertEqual(_DEVOPS_CHECK_TASK_TYPES, expected)

    def test_dev_rework_types(self):
        expected = {"backend_code", "frontend_code", "unit_tests"}
        self.assertEqual(_DEV_REWORK_TASK_TYPES, expected)

    def test_types_are_frozenset(self):
        self.assertIsInstance(_DEVOPS_CHECK_TASK_TYPES, frozenset)
        self.assertIsInstance(_DEV_REWORK_TASK_TYPES, frozenset)


# ─── TestCheckResult ─────────────────────────────────────────────────────────

class TestCheckResult(unittest.TestCase):
    def test_basic_fields(self):
        r = _check_result("docker:build", "docker build", "passed", returncode=0, duration_seconds=1.5)
        self.assertEqual(r["name"], "docker:build")
        self.assertEqual(r["command"], "docker build")
        self.assertEqual(r["status"], "passed")
        self.assertEqual(r["returncode"], 0)
        self.assertAlmostEqual(r["duration_seconds"], 1.5, places=1)

    def test_stdout_tail_truncated(self):
        long_out = "x" * 1000
        r = _check_result("n", "c", "passed", stdout_tail=long_out)
        self.assertLessEqual(len(r["stdout_tail"]), 500)
        self.assertEqual(r["stdout_tail"], long_out[-500:])

    def test_stderr_tail_truncated(self):
        long_err = "e" * 1000
        r = _check_result("n", "c", "failed", stderr_tail=long_err)
        self.assertLessEqual(len(r["stderr_tail"]), 500)

    def test_skip_reason_preserved(self):
        r = _check_result("n", "c", "skipped", skip_reason="tool not found")
        self.assertEqual(r["skip_reason"], "tool not found")

    def test_empty_tail_defaults(self):
        r = _check_result("n", "c", "passed")
        self.assertEqual(r["stdout_tail"], "")
        self.assertEqual(r["stderr_tail"], "")
        self.assertEqual(r["skip_reason"], "")


# ─── TestBuildResult ─────────────────────────────────────────────────────────

class TestBuildResult(unittest.TestCase):
    def test_empty_checks_skipped(self):
        r = _build_result([])
        self.assertEqual(r["status"], "skipped")
        self.assertEqual(r["summary"], "no checks ran")

    def test_all_passed(self):
        checks = [_check_result("a", "c", "passed"), _check_result("b", "c", "passed")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "passed")
        self.assertIn("2 passed", r["summary"])
        self.assertEqual(r["passed_count"], 2)
        self.assertEqual(r["failed_count"], 0)

    def test_any_blocked_wins_over_failed(self):
        checks = [
            _check_result("a", "c", "failed"),
            _check_result("b", "c", "blocked", skip_reason="no docker"),
        ]
        r = _build_result(checks)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["blocked_count"], 1)
        self.assertEqual(r["failed_count"], 1)

    def test_failed_without_blocked(self):
        checks = [
            _check_result("a", "c", "passed"),
            _check_result("b", "c", "failed", stderr_tail="syntax error"),
        ]
        r = _build_result(checks)
        self.assertEqual(r["status"], "failed")

    def test_deployment_blockers_populated(self):
        checks = [
            _check_result("a", "c", "blocked", skip_reason="npm not found"),
            _check_result("b", "c", "failed", stderr_tail="ImportError"),
        ]
        r = _build_result(checks)
        self.assertEqual(len(r["deployment_blockers"]), 2)
        self.assertIn("a:", r["deployment_blockers"][0])
        self.assertIn("npm not found", r["deployment_blockers"][0])

    def test_all_skipped(self):
        checks = [_check_result("a", "c", "skipped", skip_reason="no stack")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "skipped")

    def test_result_keys(self):
        r = _build_result([])
        for key in ("status", "summary", "workspace_path", "detected_stack", "checks",
                    "deployment_blockers", "release_notes", "failed_count", "passed_count",
                    "blocked_count", "skipped_count"):
            self.assertIn(key, r)


# ─── TestDetectStack ─────────────────────────────────────────────────────────

class TestDetectStack(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_detect_stack(d), [])

    def test_node_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"test"}')
            stack = _detect_stack(d)
            self.assertIn("node", stack)

    def test_docker_detected_from_dockerfile(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "FROM alpine")
            stack = _detect_stack(d)
            self.assertIn("docker", stack)

    def test_docker_detected_from_compose(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "docker-compose.yml"), "version: '3'")
            stack = _detect_stack(d)
            self.assertIn("docker", stack)

    def test_python_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "print('hello')")
            stack = _detect_stack(d)
            self.assertIn("python", stack)

    def test_mixed_stack(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{}')
            _write(os.path.join(d, "Dockerfile"), "FROM node:20")
            _write(os.path.join(d, "app.py"), "x = 1")
            stack = _detect_stack(d)
            self.assertIn("node", stack)
            self.assertIn("docker", stack)
            self.assertIn("python", stack)

    def test_nonexistent_dir(self):
        self.assertEqual(_detect_stack("/nonexistent/path/xyz"), [])

    def test_skips_pycache(self):
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "__pycache__")
            os.makedirs(cache, exist_ok=True)
            _write(os.path.join(cache, "cached.py"), "x=1")
            stack = _detect_stack(d)
            self.assertNotIn("python", stack)


# ─── TestValidateDockerfileStatic ────────────────────────────────────────────

class TestValidateDockerfileStatic(unittest.TestCase):
    def test_no_dockerfile(self):
        with tempfile.TemporaryDirectory() as d:
            result = _validate_dockerfile_static(d)
            self.assertIsNone(result)

    def test_valid_dockerfile_with_from(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "FROM alpine:3.18\nRUN apk add curl\n")
            result = _validate_dockerfile_static(d)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "passed")
            self.assertIn("FROM", result["stdout_tail"])

    def test_dockerfile_missing_from(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "# comment only\nRUN echo hello\n")
            result = _validate_dockerfile_static(d)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "failed")
            self.assertIn("No FROM", result["stderr_tail"])

    def test_dockerfile_from_in_comment_only(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "# FROM alpine\nRUN echo hello")
            result = _validate_dockerfile_static(d)
            self.assertEqual(result["status"], "failed")

    def test_dockerfile_variant_name(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile.backend"), "FROM python:3.11\nCMD python app.py")
            result = _validate_dockerfile_static(d)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "passed")

    def test_nonexistent_dir(self):
        result = _validate_dockerfile_static("/nonexistent/path/xyz")
        self.assertIsNone(result)


# ─── TestCheckEnvFile ────────────────────────────────────────────────────────

class TestCheckEnvFile(unittest.TestCase):
    def test_no_env_example(self):
        with tempfile.TemporaryDirectory() as d:
            result = _check_env_file(d)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "skipped")
            self.assertIn(".env.example not found", result["skip_reason"])

    def test_env_example_present_no_dot_env(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, ".env.example"), "DB_URL=postgres://\nJWT_SECRET=\n")
            result = _check_env_file(d)
            self.assertEqual(result["status"], "skipped")
            self.assertIn("2 vars", result["stdout_tail"])
            self.assertIn("MISSING", result["stdout_tail"])

    def test_env_example_present_with_dot_env(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, ".env.example"), "DB_URL=postgres://\nJWT_SECRET=\n")
            _write(os.path.join(d, ".env"), "DB_URL=real\nJWT_SECRET=real\n")
            result = _check_env_file(d)
            self.assertEqual(result["status"], "passed")
            self.assertIn("present", result["stdout_tail"])

    def test_env_values_never_read(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, ".env.example"), "SECRET=placeholder\n")
            _write(os.path.join(d, ".env"), "SECRET=SUPER_REAL_PASSWORD_123\n")
            result = _check_env_file(d)
            # The actual secret value must never appear in the result
            self.assertNotIn("SUPER_REAL_PASSWORD_123", str(result))

    def test_env_example_comments_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            content = "# comment\nDB_URL=postgres://\n# another\nJWT_SECRET=\n"
            _write(os.path.join(d, ".env.example"), content)
            result = _check_env_file(d)
            self.assertIn("2 vars", result["stdout_tail"])


# ─── TestRunPythonChecks ──────────────────────────────────────────────────────

class TestRunPythonChecks(unittest.TestCase):
    def test_no_py_files(self):
        with tempfile.TemporaryDirectory() as d:
            results = _run_python_checks(d, timeout=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "skipped")
            self.assertIn("no .py files", results[0]["skip_reason"])

    def test_valid_python_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            results = _run_python_checks(d, timeout=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "passed")
            self.assertEqual(results[0]["returncode"], 0)

    def test_invalid_python_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "bad.py"), "def f(\n  pass\n")
            results = _run_python_checks(d, timeout=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "failed")
            self.assertNotEqual(results[0]["returncode"], 0)

    def test_skips_pycache(self):
        with tempfile.TemporaryDirectory() as d:
            cache = os.path.join(d, "__pycache__")
            os.makedirs(cache, exist_ok=True)
            _write(os.path.join(cache, "cached.py"), "def f(:\n  pass\n")
            _write(os.path.join(d, "good.py"), "x = 1\n")
            results = _run_python_checks(d, timeout=30)
            # Only good.py should be checked — bad cached.py is excluded
            self.assertEqual(results[0]["status"], "passed")


# ─── TestRunNodeChecks ────────────────────────────────────────────────────────

class TestRunNodeChecks(unittest.TestCase):
    def test_invalid_package_json_returns_failed(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), "{invalid json}")
            results = _run_node_checks(d, timeout=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "failed")
            self.assertIn("parse error", results[0]["stderr_tail"])

    def test_valid_package_json_no_npm(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"test","scripts":{}}')
            with patch("shutil.which", return_value=None):
                results = _run_node_checks(d, timeout=30)
        # package.json passes, npm blocked
        self.assertEqual(results[0]["status"], "passed")
        self.assertEqual(results[1]["status"], "blocked")
        self.assertIn("npm not found", results[1]["skip_reason"])

    def test_no_build_lint_scripts_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"test","scripts":{"test":"jest"}}')
            with patch("shutil.which", return_value="/usr/bin/npm"):
                results = _run_node_checks(d, timeout=30)
        skipped_names = [r["name"] for r in results if r["status"] == "skipped"]
        self.assertIn("node:build", skipped_names)
        self.assertIn("node:lint", skipped_names)


# ─── TestRunDockerComposeCheck ────────────────────────────────────────────────

class TestRunDockerComposeCheck(unittest.TestCase):
    def test_no_compose_file_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(_run_docker_compose_check(d, timeout=30))

    def test_no_docker_returns_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "docker-compose.yml"), "version: '3'\n")
            with patch("shutil.which", return_value=None):
                result = _run_docker_compose_check(d, timeout=30)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("not found", result["skip_reason"])

    def test_compose_yaml_extension_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "docker-compose.yaml"), "version: '3'\n")
            with patch("shutil.which", return_value=None):
                result = _run_docker_compose_check(d, timeout=30)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "blocked")


# ─── TestRunDeploymentChecks ─────────────────────────────────────────────────

class TestRunDeploymentChecks(unittest.TestCase):
    def test_nonexistent_path(self):
        result = run_deployment_checks("/nonexistent/workspace/xyz")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("not found", result["checks"][0]["skip_reason"])

    def test_empty_string_path(self):
        result = run_deployment_checks("")
        self.assertEqual(result["status"], "skipped")

    def test_empty_dir_no_stack(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_deployment_checks(d)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("no recognized stack", result["checks"][0]["skip_reason"])

    def test_python_workspace_valid(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            result = run_deployment_checks(d)
        self.assertIn("python", result["detected_stack"])
        self.assertIn(result["status"], ("passed", "failed", "skipped"))
        self.assertTrue(any(c["name"] == "python:py_compile" for c in result["checks"]))

    def test_docker_workspace_no_docker_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "FROM alpine\n")
            _write(os.path.join(d, "docker-compose.yml"), "version: '3'\n")
            with patch("shutil.which", return_value=None):
                result = run_deployment_checks(d)
        self.assertIn("docker", result["detected_stack"])
        blocked = [c for c in result["checks"] if c["status"] == "blocked"]
        self.assertTrue(len(blocked) > 0)
        self.assertEqual(result["status"], "blocked")

    def test_env_check_included(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            _write(os.path.join(d, ".env.example"), "DB_URL=\n")
            result = run_deployment_checks(d)
        check_names = [c["name"] for c in result["checks"]]
        self.assertIn("env:env_example", check_names)

    def test_result_schema_keys(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            result = run_deployment_checks(d)
        for key in ("status", "summary", "workspace_path", "detected_stack", "checks",
                    "deployment_blockers", "release_notes", "failed_count", "passed_count"):
            self.assertIn(key, result)

    def test_workspace_path_in_result(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            result = run_deployment_checks(d)
        self.assertEqual(result["workspace_path"], d)


# ─── TestFormatExecutionResult ────────────────────────────────────────────────

class TestFormatExecutionResult(unittest.TestCase):
    def test_empty_result(self):
        text = format_execution_result({})
        self.assertIn("ไม่มีข้อมูล", text)

    def test_none_result(self):
        text = format_execution_result(None)
        self.assertIn("ไม่มีข้อมูล", text)

    def test_passed_result(self):
        result = _build_result([_check_result("a", "c", "passed")])
        text = format_execution_result(result)
        self.assertIn("PASSED", text)
        self.assertIn("✅", text)

    def test_failed_includes_blockers(self):
        checks = [_check_result("docker:build", "docker", "failed", stderr_tail="error XYZ")]
        result = _build_result(checks)
        text = format_execution_result(result)
        self.assertIn("FAILED", text)

    def test_blocked_icon(self):
        checks = [_check_result("node:npm", "npm", "blocked", skip_reason="npm not found")]
        result = _build_result(checks)
        text = format_execution_result(result)
        self.assertIn("🚫", text)
        self.assertIn("npm not found", text)

    def test_stack_included(self):
        result = _build_result([_check_result("a", "c", "passed")], detected_stack=["python", "docker"])
        text = format_execution_result(result)
        self.assertIn("python", text)
        self.assertIn("docker", text)


# ─── TestBuildDeploymentReport ────────────────────────────────────────────────

class TestBuildDeploymentReport(unittest.TestCase):
    def test_passed_report(self):
        result = _build_result([_check_result("a", "c", "passed")],
                               workspace_path="/ws", detected_stack=["python"])
        md = build_deployment_report(result, "task-001", "MyApp")
        self.assertIn("MyApp", md)
        self.assertIn("task-001", md)
        self.assertIn("PASSED", md)
        self.assertIn("All checks passed", md)

    def test_failed_report_includes_rework_hint(self):
        checks = [_check_result("py:compile", "py_compile", "failed", stderr_tail="SyntaxError")]
        result = _build_result(checks, workspace_path="/ws")
        md = build_deployment_report(result, "t1", "App")
        self.assertIn("Route to DEV", md)

    def test_blocked_report_no_auto_dev(self):
        checks = [_check_result("docker:compose", "docker compose", "blocked", skip_reason="no docker")]
        result = _build_result(checks, workspace_path="/ws")
        md = build_deployment_report(result, "t1", "App")
        self.assertIn("Do not route to DEV automatically", md)

    def test_markdown_table_included(self):
        result = _build_result([_check_result("a", "c", "passed")])
        md = build_deployment_report(result, "t1")
        self.assertIn("| Check |", md)
        self.assertIn("| a |", md)

    def test_deployment_blockers_section(self):
        checks = [_check_result("a", "c", "failed", stderr_tail="ImportError: no module")]
        result = _build_result(checks)
        md = build_deployment_report(result, "t1")
        self.assertIn("Deployment Blockers", md)


# ─── TestDEVOPSExecutionHelperResolveWorkspace ────────────────────────────────

class TestDEVOPSExecutionHelperResolveWorkspace(unittest.TestCase):
    def _make_helper(self, output_base: str = "") -> DEVOPSExecutionHelper:
        return DEVOPSExecutionHelper(_mock_storage(), output_base=output_base)

    def test_default_workspace_epic_missing(self):
        with tempfile.TemporaryDirectory() as base:
            h = self._make_helper(output_base=base)
            task = _make_task(project_id="proj1", epic_id="E001")
            ws = h.resolve_workspace(task, {})
            # Epic dir doesn't exist → falls back to project workspace
            self.assertEqual(ws, os.path.join(base, "projects", "proj1", "workspace"))

    def test_default_workspace_epic_exists(self):
        with tempfile.TemporaryDirectory() as base:
            epic_ws = os.path.join(base, "projects", "proj1", "E001", "workspace")
            os.makedirs(epic_ws)
            h = self._make_helper(output_base=base)
            task = _make_task(project_id="proj1", epic_id="E001")
            ws = h.resolve_workspace(task, {})
            self.assertEqual(ws, epic_ws)

    def test_explicit_workspace_path_valid(self):
        with tempfile.TemporaryDirectory() as base:
            explicit = os.path.join(base, "projects", "custom")
            os.makedirs(explicit)
            h = self._make_helper(output_base=base)
            task = _make_task()
            ws = h.resolve_workspace(task, {"workspace_path": explicit})
            self.assertEqual(os.path.realpath(ws), os.path.realpath(explicit))

    def test_explicit_workspace_path_outside_base_raises(self):
        with tempfile.TemporaryDirectory() as base:
            outside = tempfile.mkdtemp()
            try:
                h = self._make_helper(output_base=base)
                task = _make_task()
                with self.assertRaises(WorkspacePathError):
                    h.resolve_workspace(task, {"workspace_path": outside})
            finally:
                os.rmdir(outside)


# ─── TestDecideRouting ────────────────────────────────────────────────────────

class TestDecideRouting(unittest.TestCase):
    def _h(self) -> DEVOPSExecutionHelper:
        return DEVOPSExecutionHelper(_mock_storage())

    def test_passed_returns_normal(self):
        result = _build_result([_check_result("a", "c", "passed")])
        self.assertEqual(self._h().decide_routing(result), "normal")

    def test_skipped_returns_normal(self):
        result = _build_result([_check_result("a", "c", "skipped", skip_reason="no stack")])
        self.assertEqual(self._h().decide_routing(result), "normal")

    def test_failed_code_returns_rework_dev(self):
        checks = [
            _check_result("a", "c", "passed"),
            _check_result("b", "c", "failed"),
        ]
        result = _build_result(checks)
        self.assertEqual(self._h().decide_routing(result), "rework_dev")

    def test_blocked_returns_blocked(self):
        checks = [_check_result("a", "c", "blocked", skip_reason="no docker")]
        result = _build_result(checks)
        self.assertEqual(self._h().decide_routing(result), "blocked")

    def test_failed_with_blocked_check_returns_blocked(self):
        # Mixed: failed overall status but a check is blocked — treat as blocked (not rework_dev)
        checks = [
            _check_result("a", "c", "failed"),
            _check_result("b", "c", "blocked", skip_reason="tool missing"),
        ]
        result = _build_result(checks)
        # status will be "blocked" (blocked wins), so routing should be "blocked"
        self.assertEqual(self._h().decide_routing(result), "blocked")


# ─── TestBuildFeedbackMessage ─────────────────────────────────────────────────

class TestBuildFeedbackMessage(unittest.TestCase):
    def _h(self) -> DEVOPSExecutionHelper:
        return DEVOPSExecutionHelper(_mock_storage())

    def test_no_failed_checks(self):
        result = _build_result([_check_result("a", "c", "passed")])
        msg = self._h().build_feedback_message(result)
        self.assertIn("[devops-execution]", msg)

    def test_failed_checks_included(self):
        checks = [
            _check_result("python:py_compile", "py_compile", "failed", stderr_tail="SyntaxError: invalid syntax"),
        ]
        result = _build_result(checks)
        msg = self._h().build_feedback_message(result)
        self.assertIn("python:py_compile", msg)
        self.assertIn("SyntaxError", msg)

    def test_max_5_failed(self):
        checks = [_check_result(f"check{i}", "cmd", "failed", stderr_tail=f"err{i}") for i in range(8)]
        result = _build_result(checks)
        msg = self._h().build_feedback_message(result)
        # At most 5 failures should be included
        count = msg.count("err")
        self.assertLessEqual(count, 5)


# ─── TestRequeueDevTasks ─────────────────────────────────────────────────────

class TestRequeueDevTasks(unittest.TestCase):
    def _make_dev_task(self, task_type: str, epic_id: str = "E001") -> SdlcTask:
        return _make_task(
            task_id=f"dev-{task_type}", role="dev", task_type=task_type,
            project_id="proj1", epic_id=epic_id,
        )

    def test_requeues_eligible_dev_tasks(self):
        dev_tasks = [
            self._make_dev_task("backend_code"),
            self._make_dev_task("frontend_code"),
            self._make_dev_task("unit_tests"),
        ]
        storage = _mock_storage(tasks=dev_tasks)
        h = DEVOPSExecutionHelper(storage)
        task = _make_task(project_id="proj1", epic_id="E001")
        result = _build_result([_check_result("a", "c", "failed")])
        requeued = h.requeue_dev_tasks(task, result)
        self.assertEqual(len(requeued), 3)

    def test_skips_different_epic(self):
        dev_tasks = [
            self._make_dev_task("backend_code", epic_id="OTHER-E"),
        ]
        storage = _mock_storage(tasks=dev_tasks)
        h = DEVOPSExecutionHelper(storage)
        task = _make_task(project_id="proj1", epic_id="E001")
        result = _build_result([_check_result("a", "c", "failed")])
        requeued = h.requeue_dev_tasks(task, result)
        self.assertEqual(len(requeued), 0)

    def test_skips_ineligible_task_types(self):
        dev_tasks = [
            self._make_dev_task("project_structure"),
            self._make_dev_task("documentation"),
        ]
        storage = _mock_storage(tasks=dev_tasks)
        h = DEVOPSExecutionHelper(storage)
        task = _make_task(project_id="proj1", epic_id="E001")
        result = _build_result([_check_result("a", "c", "failed")])
        requeued = h.requeue_dev_tasks(task, result)
        self.assertEqual(len(requeued), 0)

    def test_storage_error_does_not_raise(self):
        storage = _mock_storage()
        storage.requeue_for_rework.side_effect = RuntimeError("DB error")
        h = DEVOPSExecutionHelper(storage)
        dev_task = self._make_dev_task("backend_code")
        storage.list_sdlc_tasks.return_value = [dev_task]
        task = _make_task(project_id="proj1", epic_id="E001")
        result = _build_result([_check_result("a", "c", "failed")])
        # Should not raise despite storage error
        requeued = h.requeue_dev_tasks(task, result)
        self.assertEqual(len(requeued), 0)

    def test_feedback_message_injected(self):
        dev_task = self._make_dev_task("backend_code")
        storage = _mock_storage(tasks=[dev_task])
        h = DEVOPSExecutionHelper(storage)
        task = _make_task(project_id="proj1", epic_id="E001")
        checks = [_check_result("python:py_compile", "py_compile", "failed", stderr_tail="err")]
        result = _build_result(checks)
        h.requeue_dev_tasks(task, result)
        storage.update_sdlc_task_input_data.assert_called_once()
        call_args = storage.update_sdlc_task_input_data.call_args
        feedback_data = call_args[0][1]
        self.assertIn("role_feedback", feedback_data)
        self.assertIn("[devops-execution]", feedback_data["role_feedback"])


# ─── TestSaveExecutionArtifact ────────────────────────────────────────────────

class TestSaveExecutionArtifact(unittest.TestCase):
    def test_saves_json_and_report(self):
        with tempfile.TemporaryDirectory() as out_dir:
            storage = _mock_storage()
            h = DEVOPSExecutionHelper(storage)
            task = _make_task()
            result = _build_result([_check_result("a", "c", "passed")],
                                   workspace_path="/ws", detected_stack=["python"])
            h.save_execution_artifact(task, out_dir, result, "TestProject")

            json_path = os.path.join(out_dir, "devops_execution_result.json")
            md_path = os.path.join(out_dir, "deployment_readiness_report.md")
            self.assertTrue(os.path.isfile(json_path))
            self.assertTrue(os.path.isfile(md_path))

    def test_json_content_valid(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result([_check_result("a", "c", "passed")])
            h.save_execution_artifact(task, out_dir, result)
            with open(os.path.join(out_dir, "devops_execution_result.json")) as f:
                data = json.load(f)
            self.assertIn("status", data)
            self.assertEqual(data["status"], "passed")

    def test_report_markdown_includes_project(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task(task_id="task-xyz")
            result = _build_result([_check_result("a", "c", "passed")])
            h.save_execution_artifact(task, out_dir, result, "CoolProject")
            with open(os.path.join(out_dir, "deployment_readiness_report.md")) as f:
                content = f.read()
            self.assertIn("CoolProject", content)
            self.assertIn("task-xyz", content)

    def test_mkdir_created(self):
        with tempfile.TemporaryDirectory() as base:
            out_dir = os.path.join(base, "new", "nested", "dir")
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result([])
            h.save_execution_artifact(task, out_dir, result)
            self.assertTrue(os.path.isdir(out_dir))

    def test_storage_error_does_not_raise(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result([])
            # Make out_dir read-only to force an I/O error
            os.chmod(out_dir, 0o444)
            try:
                h.save_execution_artifact(task, out_dir, result)
            except Exception:
                self.fail("save_execution_artifact should swallow exceptions")
            finally:
                os.chmod(out_dir, 0o755)


# ─── TestTaskPrompts ──────────────────────────────────────────────────────────

class TestDevopsTaskPrompts(unittest.TestCase):
    def setUp(self):
        from agents.devops.task_prompts import build_devops_task_prompt
        self.build = build_devops_task_prompt

    def test_dockerfile_prompt_no_context(self):
        prompt = self.build("dockerfile", {"project_name": "TestApp"})
        self.assertIn("Dockerfile", prompt)
        self.assertNotIn("{devops_execution_context}", prompt)

    def test_dockerfile_prompt_with_context(self):
        prompt = self.build("dockerfile", {
            "project_name": "TestApp",
            "devops_execution_context": "✅ Checks passed",
        })
        self.assertIn("Deployment Readiness Checks", prompt)
        self.assertIn("✅ Checks passed", prompt)

    def test_docker_compose_prompt(self):
        prompt = self.build("docker_compose", {
            "project_name": "TestApp",
            "devops_execution_context": "❌ Failed",
        })
        self.assertIn("Deployment Readiness", prompt)
        self.assertIn("docker-compose", prompt)

    def test_github_actions_prompt(self):
        prompt = self.build("github_actions", {
            "project_name": "TestApp",
            "devops_execution_context": "🚫 Blocked",
        })
        self.assertIn("Deployment Readiness", prompt)
        self.assertIn("GitHub Actions", prompt)

    def test_deployment_guide_prompt(self):
        prompt = self.build("deployment_guide", {
            "project_name": "TestApp",
            "github_actions_content": "# CI",
            "devops_execution_context": "✅ Passed",
        })
        self.assertIn("Deployment Readiness", prompt)
        self.assertIn("deployment_guide", prompt)

    def test_empty_context_no_section_injected(self):
        prompt = self.build("dockerfile", {"project_name": "TestApp", "devops_execution_context": ""})
        # Empty context → no "Deployment Readiness Checks" block injected
        self.assertNotIn("Deployment Readiness Checks", prompt)

    def test_pipeline_diagram_no_context_field(self):
        prompt = self.build("pipeline_diagram", {"project_name": "TestApp"})
        # pipeline_diagram doesn't use {devops_execution_context}
        self.assertNotIn("{devops_execution_context}", prompt)
        self.assertIn("Pipeline", prompt)

    def test_unknown_task_type_fallback(self):
        prompt = self.build("unknown_type", {"project_name": "TestApp"})
        self.assertIn("TestApp", prompt)

    def test_today_injected(self):
        from datetime import date
        prompt = self.build("docker_compose", {"project_name": "TestApp"})
        today = date.today().strftime("%Y-%m-%d")
        self.assertIn(today, prompt)


# ─── TestRunDeploymentChecksEndToEnd ─────────────────────────────────────────

class TestRunDeploymentChecksEndToEnd(unittest.TestCase):
    """Integration-style: real filesystem, real python3 invocation."""

    def test_all_valid_python_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "def hello(): return 1\n")
            _write(os.path.join(d, "utils.py"), "import os\n")
            _write(os.path.join(d, ".env.example"), "DB_URL=\nSECRET=\n")
            _write(os.path.join(d, ".env"), "DB_URL=x\nSECRET=y\n")
            result = run_deployment_checks(d)
        self.assertIn("python", result["detected_stack"])
        py_check = next((c for c in result["checks"] if c["name"] == "python:py_compile"), None)
        self.assertIsNotNone(py_check)
        self.assertEqual(py_check["status"], "passed")
        env_check = next((c for c in result["checks"] if c["name"] == "env:env_example"), None)
        self.assertIsNotNone(env_check)
        self.assertEqual(env_check["status"], "passed")

    def test_syntax_error_in_python(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "broken.py"), "def f(:\n  pass\n")
            result = run_deployment_checks(d)
        py_check = next((c for c in result["checks"] if c["name"] == "python:py_compile"), None)
        self.assertIsNotNone(py_check)
        self.assertEqual(py_check["status"], "failed")
        self.assertEqual(result["status"], "failed")

    def test_docker_static_validation(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "FROM python:3.11\nCMD python app.py\n")
            with patch("shutil.which", return_value=None):
                result = run_deployment_checks(d)
        df_check = next(
            (c for c in result["checks"] if c["name"] == "docker:dockerfile_syntax"), None
        )
        self.assertIsNotNone(df_check)
        self.assertEqual(df_check["status"], "passed")

    def test_missing_from_in_dockerfile_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "Dockerfile"), "# just a comment\nRUN echo hello\n")
            with patch("shutil.which", return_value=None):
                result = run_deployment_checks(d)
        df_check = next(
            (c for c in result["checks"] if c["name"] == "docker:dockerfile_syntax"), None
        )
        self.assertIsNotNone(df_check)
        self.assertEqual(df_check["status"], "failed")

    def test_no_llm_commands_executed(self):
        """Verify that LLM-supplied command strings are never executed — only allowlisted cmds."""
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "import subprocess; subprocess.run(['rm','-rf','/'])\n")
            # Even if a .py file contains dangerous code, only py_compile is run (syntax check)
            result = run_deployment_checks(d)
        # py_compile is a compile-time check, it does NOT execute the code
        self.assertIn("python:py_compile", [c["name"] for c in result["checks"]])
        # Result should be passed (syntax is valid Python, py_compile doesn't run it)
        py_check = next(c for c in result["checks"] if c["name"] == "python:py_compile")
        self.assertEqual(py_check["status"], "passed")


# ─── Phase 5.2: generate_release_notes ───────────────────────────────────────

class TestGenerateReleaseNotes(unittest.TestCase):

    def test_passed_result_generates_notes(self):
        result = _build_result(
            [_check_result("python:py_compile", "python3 -m py_compile", "passed")],
            workspace_path="/ws", detected_stack=["python"],
        )
        content, status = generate_release_notes(result, "t1", "TestApp")
        self.assertEqual(status, "generated")
        self.assertIn("release_notes_status:** generated", content)
        self.assertIn("TestApp", content)
        self.assertIn("t1", content)

    def test_blocked_result_skips_notes(self):
        result = _build_result(
            [_check_result("docker:compose_config", "docker compose config", "blocked",
                           skip_reason="docker not found")],
            workspace_path="/ws", detected_stack=["docker"],
        )
        content, status = generate_release_notes(result, "t2", "BlockedApp")
        self.assertEqual(status, "skipped")
        self.assertIn("release_notes_status:** skipped", content)
        self.assertIn("blocked", content.lower())

    def test_no_stack_skips_notes(self):
        result = _build_result([], workspace_path="/ws", detected_stack=[])
        content, status = generate_release_notes(result, "t3")
        self.assertEqual(status, "skipped")
        self.assertIn("release_notes_status:** skipped", content)
        self.assertIn("no recognized stack", content.lower())

    def test_failed_result_generates_issues_section(self):
        result = _build_result(
            [_check_result("python:py_compile", "py_compile", "failed",
                           stderr_tail="SyntaxError: bad syntax")],
            workspace_path="/ws", detected_stack=["python"],
        )
        content, status = generate_release_notes(result, "t4", "BrokenApp")
        self.assertEqual(status, "generated")
        self.assertIn("Issues Found", content)
        self.assertIn("SyntaxError", content)

    def test_passed_result_includes_checks_passed_section(self):
        result = _build_result(
            [_check_result("python:py_compile", "py_compile", "passed",
                           stdout_tail="All files OK")],
            workspace_path="/ws", detected_stack=["python"],
        )
        content, status = generate_release_notes(result, "t5")
        self.assertIn("Checks Passed", content)
        self.assertIn("All files OK", content)

    def test_manual_approval_required_note_always_present(self):
        result = _build_result(
            [_check_result("python:py_compile", "py_compile", "passed")],
            workspace_path="/ws", detected_stack=["python"],
        )
        content, _ = generate_release_notes(result, "t6")
        self.assertIn("Manual approval required", content)

    def test_blocked_note_lists_blockers(self):
        blockers = ["check1: missing tool", "check2: timeout"]
        result = _build_result(
            [_check_result("c1", "cmd", "blocked", skip_reason="missing tool"),
             _check_result("c2", "cmd", "blocked", skip_reason="timeout")],
            workspace_path="/ws", detected_stack=["python"],
        )
        content, status = generate_release_notes(result, "t7")
        self.assertEqual(status, "skipped")
        # blockers should appear in the skipped content
        self.assertIn("🚫", content)

    def test_project_name_fallback_when_empty(self):
        result = _build_result([], detected_stack=[])
        content, _ = generate_release_notes(result, "t8", "")
        self.assertIn("N/A", content)


# ─── Phase 5.2: save_execution_artifact writes release_notes.md ──────────────

class TestSaveExecutionArtifactReleaseNotes(unittest.TestCase):

    def test_release_notes_file_created(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result(
                [_check_result("python:py_compile", "py_compile", "passed")],
                workspace_path=out_dir, detected_stack=["python"],
            )
            h.save_execution_artifact(task, out_dir, result, "TestProject")
            notes_path = os.path.join(out_dir, "release_notes.md")
            self.assertTrue(os.path.isfile(notes_path))

    def test_release_notes_skipped_when_blocked(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result(
                [_check_result("docker:compose_config", "cmd", "blocked",
                               skip_reason="docker not found")],
                workspace_path=out_dir, detected_stack=["docker"],
            )
            h.save_execution_artifact(task, out_dir, result, "BlockedProject")
            notes_path = os.path.join(out_dir, "release_notes.md")
            self.assertTrue(os.path.isfile(notes_path))
            with open(notes_path) as f:
                content = f.read()
            self.assertIn("release_notes_status:** skipped", content)

    def test_release_notes_generated_when_passed(self):
        with tempfile.TemporaryDirectory() as out_dir:
            h = DEVOPSExecutionHelper(_mock_storage())
            task = _make_task()
            result = _build_result(
                [_check_result("python:py_compile", "py_compile", "passed",
                               stdout_tail="OK")],
                workspace_path=out_dir, detected_stack=["python"],
            )
            h.save_execution_artifact(task, out_dir, result, "PassProject")
            with open(os.path.join(out_dir, "release_notes.md")) as f:
                content = f.read()
            self.assertIn("release_notes_status:** generated", content)
            self.assertIn("PassProject", content)


# ─── Phase 5.2: Prompt hardening ─────────────────────────────────────────────

class TestDevopsPromptHardening(unittest.TestCase):
    def setUp(self):
        from agents.devops.task_prompts import build_devops_task_prompt
        self.build = build_devops_task_prompt

    def test_safety_rules_in_every_prompt(self):
        for task_type in ("dockerfile", "docker_compose", "github_actions", "deployment_guide"):
            with self.subTest(task_type=task_type):
                prompt = self.build(task_type, {
                    "project_name": "TestApp",
                    "github_actions_content": "# ci",
                })
                self.assertIn("Safety Rules", prompt)

    def test_no_real_deployment_claim_in_safety_rule(self):
        prompt = self.build("dockerfile", {"project_name": "TestApp"})
        # Must contain the "no deploy จริง" safety note
        self.assertIn("deployment successful", prompt.lower())
        # … but as a prohibition, not a claim
        self.assertIn("ห้าม", prompt)

    def test_blockers_injected_when_present(self):
        result_with_blockers = {
            "deployment_blockers": ["check1: docker not found", "check2: npm not found"],
        }
        prompt = self.build("dockerfile", {
            "project_name": "TestApp",
            "devops_execution_result": result_with_blockers,
        })
        self.assertIn("Deployment Blockers", prompt)
        self.assertIn("check1: docker not found", prompt)

    def test_no_blocker_block_when_no_blockers(self):
        result_clean = {"deployment_blockers": []}
        prompt = self.build("dockerfile", {
            "project_name": "TestApp",
            "devops_execution_result": result_clean,
        })
        # Blocker heading only injected when there are actual blockers
        self.assertNotIn("🚫 Deployment Blockers", prompt)

    def test_placeholder_hostname_note_present(self):
        prompt = self.build("deployment_guide", {
            "project_name": "TestApp",
            "github_actions_content": "# ci",
        })
        self.assertIn("placeholder", prompt.lower())

    def test_manual_approval_note_present(self):
        prompt = self.build("deployment_guide", {
            "project_name": "TestApp",
            "github_actions_content": "# ci",
        })
        self.assertIn("Manual approval", prompt)


# ─── Phase 5.2: Task catalog preferred_model ─────────────────────────────────

class TestTaskCatalogPreferredModel(unittest.TestCase):

    def setUp(self):
        from shared.task_catalog import TASK_CATALOG
        self.devops_tasks = {t["task_type"]: t for t in TASK_CATALOG.get("devops", [])}

    def test_dockerfile_uses_coder_model(self):
        t = self.devops_tasks.get("dockerfile", {})
        self.assertEqual(t.get("preferred_model"), "ollama/qwen2.5-coder")

    def test_docker_compose_uses_coder_model(self):
        t = self.devops_tasks.get("docker_compose", {})
        self.assertEqual(t.get("preferred_model"), "ollama/qwen2.5-coder")

    def test_github_actions_uses_coder_model(self):
        t = self.devops_tasks.get("github_actions", {})
        self.assertEqual(t.get("preferred_model"), "ollama/qwen2.5-coder")

    def test_deployment_guide_uses_reasoning_model(self):
        t = self.devops_tasks.get("deployment_guide", {})
        self.assertEqual(t.get("preferred_model"), "ollama/deepseek-r1")

    def test_pipeline_diagram_uses_reasoning_model(self):
        t = self.devops_tasks.get("pipeline_diagram", {})
        self.assertEqual(t.get("preferred_model"), "ollama/deepseek-r1")

    def test_all_devops_check_types_have_preferred_model(self):
        for ttype in ("dockerfile", "docker_compose", "github_actions", "deployment_guide"):
            with self.subTest(task_type=ttype):
                t = self.devops_tasks.get(ttype, {})
                self.assertIn("preferred_model", t,
                              f"{ttype} missing preferred_model in task_catalog")


if __name__ == "__main__":
    unittest.main(verbosity=2)
