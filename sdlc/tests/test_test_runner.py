"""
Tests for test_runner.py, execution_helper.py, and storage.requeue_for_rework.

Run: python3 sdlc/tests/test_test_runner.py
  or: python3 -m pytest sdlc/tests/test_test_runner.py -v

No discord.py dependency — QA business logic is tested via QAExecutionHelper directly.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.test_runner import (
    run_quality_checks,
    format_execution_result,
    _check_result,
    _build_result,
    _read_package_scripts,
    _find_python_files,
    _detect_profile,
    _OUTPUT_TAIL_CHARS,
)
from shared.storage import Storage, SdlcTask

# QAExecutionHelper is Discord-free — safe to import without discord.py installed
from agents.qa.execution_helper import QAExecutionHelper, _DEV_REWORK_TASK_TYPES


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_task(
    storage: Storage,
    task_id: str,
    role: str = "qa",
    task_type: str = "test_report",
    project_id: str = "p1",
    epic_id: str = "p1-E001",
    status: str = "in_progress",
    input_data: str = "{}",
) -> SdlcTask:
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id=project_id, epic_id=epic_id, task_number=1,
        role=role, task_type=task_type, title=f"T {task_id}", description="",
        output_file="out.md", output_format="markdown", depends_on="",
        status=status, input_data=input_data, output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
        claimed_at=now, claimed_by=role,
    )
    storage.create_sdlc_task(t)
    return t


def _make_dev_task(
    storage: Storage,
    task_id: str,
    task_type: str = "backend_code",
    epic_id: str = "p1-E001",
    status: str = "approved",
) -> SdlcTask:
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id="p1", epic_id=epic_id, task_number=1,
        role="dev", task_type=task_type, title=f"T {task_id}", description="",
        output_file="code.py", output_format="code_multi", depends_on="",
        status=status, input_data='{"project_name":"TestApp"}', output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
    )
    storage.create_sdlc_task(t)
    return t


class _DBFixture(unittest.TestCase):
    """Mixin that provides a fresh SQLite DB per test."""

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        self.storage = Storage(db_path=self._tmpfile.name)

    def tearDown(self):
        os.unlink(self._tmpfile.name)


# ─── _build_result helpers ────────────────────────────────────────────────────

class TestBuildResult(unittest.TestCase):
    def test_all_passed(self):
        checks = [_check_result("a", "x", "passed"), _check_result("b", "y", "passed")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "passed")
        self.assertEqual(r["passed_count"], 2)
        self.assertEqual(r["failed_count"], 0)

    def test_one_failed(self):
        checks = [_check_result("a", "x", "passed"), _check_result("b", "y", "failed")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["failed_count"], 1)

    def test_all_skipped(self):
        checks = [_check_result("a", "x", "skipped")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "skipped")

    def test_empty_checks(self):
        r = _build_result([])
        self.assertEqual(r["status"], "skipped")

    def test_timeout_only_gives_blocked(self):
        checks = [_check_result("a", "x", "failed", skip_reason="timed out after 30s")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "blocked")

    def test_mixed_timeout_and_real_failure_gives_failed(self):
        checks = [
            _check_result("a", "x", "failed", skip_reason="timed out after 30s"),
            _check_result("b", "y", "failed"),
        ]
        r = _build_result(checks)
        self.assertEqual(r["status"], "failed")

    def test_summary_counts(self):
        checks = [
            _check_result("a", "x", "passed"),
            _check_result("b", "y", "failed"),
            _check_result("c", "z", "skipped"),
        ]
        r = _build_result(checks)
        self.assertIn("1 passed", r["summary"])
        self.assertIn("1 failed", r["summary"])
        self.assertIn("1 skipped", r["summary"])


# ─── Output truncation ────────────────────────────────────────────────────────

class TestOutputTruncation(unittest.TestCase):
    def test_stdout_tail_truncated(self):
        long_out = "x" * 2000
        c = _check_result("a", "cmd", "passed", stdout_tail=long_out)
        self.assertLessEqual(len(c["stdout_tail"]), _OUTPUT_TAIL_CHARS)

    def test_stderr_tail_truncated(self):
        long_err = "e" * 2000
        c = _check_result("a", "cmd", "failed", stderr_tail=long_err)
        self.assertLessEqual(len(c["stderr_tail"]), _OUTPUT_TAIL_CHARS)

    def test_tail_is_last_chars(self):
        """Truncation keeps the END of the output (most relevant for error messages)."""
        out = "START" + "x" * 1000 + "END"
        c = _check_result("a", "cmd", "passed", stdout_tail=out)
        self.assertTrue(c["stdout_tail"].endswith("END"))


# ─── Profile detection ────────────────────────────────────────────────────────

class TestDetectProfile(unittest.TestCase):
    def test_node_from_package_json(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x"}')
            self.assertEqual(_detect_profile(d), "node")

    def test_python_from_py_file(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "print('hi')")
            self.assertEqual(_detect_profile(d), "python")

    def test_docker_from_compose_yml(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "docker-compose.yml"), "version: '3'")
            self.assertEqual(_detect_profile(d), "docker")

    def test_node_wins_over_python_when_both_present(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x"}')
            _write(os.path.join(d, "app.py"), "print('hi')")
            self.assertEqual(_detect_profile(d), "node")

    def test_empty_directory_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(_detect_profile(d))

    def test_nonexistent_path_returns_none(self):
        self.assertIsNone(_detect_profile("/nonexistent/path/xyz"))


# ─── run_quality_checks — missing/empty path ─────────────────────────────────

class TestRunQualityChecksSetup(unittest.TestCase):
    def test_empty_path_string_skipped(self):
        r = run_quality_checks("")
        self.assertEqual(r["status"], "skipped")
        self.assertIn("no project_path", r["checks"][0]["skip_reason"])

    def test_nonexistent_path_skipped(self):
        r = run_quality_checks("/nonexistent/qa/test/path")
        self.assertEqual(r["status"], "skipped")
        self.assertIn("does not exist", r["checks"][0]["skip_reason"])

    def test_undetectable_profile_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_quality_checks(d)
        self.assertEqual(r["status"], "skipped")
        self.assertIn("could not detect", r["checks"][0]["skip_reason"])

    def test_unknown_explicit_profile_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_quality_checks(d, profile="cobol")
        self.assertEqual(r["status"], "skipped")
        self.assertIn("unknown profile", r["checks"][0]["skip_reason"])


# ─── Python profile ───────────────────────────────────────────────────────────

class TestPythonProfile(unittest.TestCase):
    def test_valid_python_py_compile_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "main.py"), "def main():\n    pass\n")
            r = run_quality_checks(d, profile="python", timeout_seconds=30)
        compile_check = next(c for c in r["checks"] if "py_compile" in c["name"])
        self.assertEqual(compile_check["status"], "passed")

    def test_syntax_error_py_compile_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "bad.py"), "def bad(\n    x y\n")
            r = run_quality_checks(d, profile="python", timeout_seconds=30)
        compile_check = next(c for c in r["checks"] if "py_compile" in c["name"])
        self.assertEqual(compile_check["status"], "failed")
        self.assertEqual(r["status"], "failed")

    def test_no_py_files_compile_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "readme.txt"), "hello")
            r = run_quality_checks(d, profile="python", timeout_seconds=30)
        compile_check = next(c for c in r["checks"] if "py_compile" in c["name"])
        self.assertEqual(compile_check["status"], "skipped")
        self.assertIn("no .py files", compile_check["skip_reason"])

    def test_pytest_missing_gives_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            with patch("shared.test_runner.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
                r = run_quality_checks(d, profile="python", timeout_seconds=30)
        pytest_check = next((c for c in r["checks"] if "pytest" in c["name"]), None)
        self.assertIsNotNone(pytest_check)
        self.assertEqual(pytest_check["status"], "skipped")
        self.assertIn("not installed", pytest_check["skip_reason"])

    def test_failed_check_makes_overall_failed(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "bad.py"), "def bad(\n    x y\n")
            r = run_quality_checks(d, profile="python", timeout_seconds=30)
        self.assertEqual(r["status"], "failed")
        self.assertGreater(r["failed_count"], 0)


# ─── Node profile ─────────────────────────────────────────────────────────────

class TestNodeProfile(unittest.TestCase):
    def test_no_scripts_all_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x","scripts":{}}')
            r = run_quality_checks(d, profile="node", timeout_seconds=30)
        for check in r["checks"]:
            if check["status"] != "skipped":
                self.assertIn("not found", check.get("skip_reason", ""))

    def test_missing_test_script_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x","scripts":{"build":"tsc"}}')
            r = run_quality_checks(d, profile="node", timeout_seconds=30)
        test_check = next((c for c in r["checks"] if c["name"] == "node:test"), None)
        self.assertIsNotNone(test_check)
        if test_check["status"] == "skipped":
            reason = test_check.get("skip_reason", "")
            self.assertTrue(
                "'test' script not defined" in reason or "npm not found" in reason,
                f"Unexpected skip reason: {reason}",
            )

    def test_defined_script_selected_for_execution(self):
        """Scripts present in package.json must be passed to _run_cmd; absent ones skipped."""
        with tempfile.TemporaryDirectory() as d:
            pkg = {"name": "x", "scripts": {"test": "echo ok", "build": "echo built"}}
            _write(os.path.join(d, "package.json"), json.dumps(pkg))
            with patch("shared.test_runner.shutil.which") as mock_which:
                mock_which.return_value = "/usr/bin/npm"
                with patch("shared.test_runner._run_cmd") as mock_run_cmd:
                    mock_run_cmd.side_effect = lambda name, cmd, cwd, timeout: \
                        _check_result(name, " ".join(cmd), "passed")
                    r = run_quality_checks(d, profile="node", timeout_seconds=30)
            called_names = [call.args[0] for call in mock_run_cmd.call_args_list]
            self.assertIn("node:test", called_names)
            self.assertIn("node:build", called_names)
            self.assertNotIn("node:lint", called_names)
            lint_check = next(c for c in r["checks"] if c["name"] == "node:lint")
            self.assertEqual(lint_check["status"], "skipped")
            self.assertIn("not defined", lint_check["skip_reason"])

    def test_read_package_scripts(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = {"scripts": {"test": "jest", "build": "tsc", "start": "node index.js"}}
            _write(os.path.join(d, "package.json"), json.dumps(pkg))
            scripts = _read_package_scripts(d)
        self.assertIn("test", scripts)
        self.assertIn("build", scripts)
        self.assertIn("start", scripts)

    def test_malformed_package_json_returns_empty_set(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), "{broken json")
            scripts = _read_package_scripts(d)
        self.assertEqual(scripts, set())

    def test_npm_not_in_path_gives_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x","scripts":{"test":"jest"}}')
            with patch("shared.test_runner.shutil.which", return_value=None):
                r = run_quality_checks(d, profile="node", timeout_seconds=30)
        self.assertEqual(r["status"], "skipped")
        self.assertIn("npm not found", r["checks"][0]["skip_reason"])


# ─── Command timeout ──────────────────────────────────────────────────────────

class TestCommandTimeout(unittest.TestCase):
    def test_timeout_produces_failed_status(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "slow.py"), "import time; time.sleep(999)\n")
            with patch("shared.test_runner.subprocess.run") as mock_run:
                import subprocess
                mock_run.side_effect = subprocess.TimeoutExpired(["python3"], 1)
                from shared.test_runner import _run_cmd
                check = _run_cmd("test", ["python3", "slow.py"], d, 1)
        self.assertEqual(check["status"], "failed")
        self.assertIn("timed out", check["skip_reason"])

    def test_timeout_gives_blocked_overall(self):
        checks = [_check_result("a", "x", "failed", skip_reason="timed out after 5s")]
        r = _build_result(checks)
        self.assertEqual(r["status"], "blocked")


# ─── No arbitrary command execution ──────────────────────────────────────────

class TestNoArbitraryCommands(unittest.TestCase):
    def test_run_quality_checks_has_no_command_param(self):
        import inspect
        sig = inspect.signature(run_quality_checks)
        self.assertNotIn("command", sig.parameters)
        self.assertNotIn("commands", sig.parameters)

    def test_profile_param_is_not_executed_as_command(self):
        r = run_quality_checks("/tmp", profile="rm -rf /")
        self.assertEqual(r["status"], "skipped")
        self.assertIn("unknown profile", r["checks"][0]["skip_reason"])

    def test_project_path_with_shell_injection_is_safe(self):
        r = run_quality_checks("/tmp/$(echo evil)")
        self.assertEqual(r["status"], "skipped")


# ─── format_execution_result ─────────────────────────────────────────────────

class TestFormatExecutionResult(unittest.TestCase):
    def test_empty_result(self):
        out = format_execution_result({})
        self.assertIn("execution", out.lower())

    def test_passed_result_shows_status(self):
        r = _build_result([_check_result("python:py_compile", "python3 -m py_compile", "passed")])
        out = format_execution_result(r)
        self.assertIn("PASSED", out)

    def test_failed_result_shows_check_name(self):
        r = _build_result([_check_result("python:pytest", "pytest", "failed", stderr_tail="FAILED")])
        out = format_execution_result(r)
        self.assertIn("python:pytest", out)

    def test_skipped_check_shown(self):
        r = _build_result([_check_result("python:pytest", "pytest", "skipped",
                                         skip_reason="not installed")])
        out = format_execution_result(r)
        self.assertIn("not installed", out)


# ─── Storage: requeue_for_rework ─────────────────────────────────────────────

class TestRequeueForRework(_DBFixture):
    def test_approved_task_requeued(self):
        dev = _make_dev_task(self.storage, "DEV-001", status="approved")
        result = self.storage.requeue_for_rework(dev.id, "QA failed")
        self.assertTrue(result)
        updated = self.storage.get_sdlc_task(dev.id)
        self.assertEqual(updated.status, "pending")
        self.assertEqual(updated.revision_count, 1)
        self.assertEqual(updated.claimed_at, "")
        self.assertEqual(updated.claimed_by, "")

    def test_completed_task_requeued(self):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="DEV-002", project_id="p1", epic_id="p1-E001", task_number=2,
            role="dev", task_type="unit_tests", title="T", description="",
            output_file="t.py", output_format="code_multi", depends_on="",
            status="completed", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
        )
        self.storage.create_sdlc_task(t)
        result = self.storage.requeue_for_rework(t.id, "QA rework")
        self.assertTrue(result)
        updated = self.storage.get_sdlc_task(t.id)
        self.assertEqual(updated.status, "pending")
        self.assertEqual(updated.revision_count, 1)

    def test_pending_task_not_double_requeued(self):
        """Tasks already pending must not be touched — prevents double-requeue."""
        dev = _make_dev_task(self.storage, "DEV-001", status="approved")
        self.storage.requeue_for_rework(dev.id, "first")
        # Now it's pending — second call should not update
        result = self.storage.requeue_for_rework(dev.id, "second")
        self.assertFalse(result)
        updated = self.storage.get_sdlc_task(dev.id)
        # revision_count should still be 1 (not 2)
        self.assertEqual(updated.revision_count, 1)

    def test_in_progress_task_not_requeued(self):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="DEV-003", project_id="p1", epic_id="p1-E001", task_number=3,
            role="dev", task_type="backend_code", title="T", description="",
            output_file="c.py", output_format="code_multi", depends_on="",
            status="in_progress", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
        )
        self.storage.create_sdlc_task(t)
        result = self.storage.requeue_for_rework(t.id, "QA rework")
        self.assertFalse(result)
        updated = self.storage.get_sdlc_task(t.id)
        self.assertEqual(updated.status, "in_progress")

    def test_nonexistent_task_returns_false(self):
        result = self.storage.requeue_for_rework("NONEXISTENT", "note")
        self.assertFalse(result)

    def test_notes_appended(self):
        dev = _make_dev_task(self.storage, "DEV-001", status="approved")
        self.storage.requeue_for_rework(dev.id, "QA failed: 1 failed")
        updated = self.storage.get_sdlc_task(dev.id)
        self.assertIn("QA failed", updated.notes)


# ─── QAExecutionHelper — routing decisions ────────────────────────────────────

class TestQAExecutionHelperRouting(_DBFixture):
    def _helper(self):
        return QAExecutionHelper(self.storage)

    def test_decide_action_failed(self):
        result = _build_result([_check_result("a", "x", "failed")])
        self.assertEqual(self._helper().decide_action(result), "rework")

    def test_decide_action_blocked(self):
        result = _build_result([_check_result("a", "x", "failed", skip_reason="timed out after 30s")])
        self.assertEqual(self._helper().decide_action(result), "blocked")

    def test_decide_action_passed(self):
        result = _build_result([_check_result("a", "x", "passed")])
        self.assertEqual(self._helper().decide_action(result), "passed")

    def test_decide_action_skipped(self):
        result = _build_result([_check_result("a", "x", "skipped")])
        self.assertEqual(self._helper().decide_action(result), "skipped")

    def test_get_role_override_failed_returns_dev(self):
        result = _build_result([_check_result("python:pytest", "pytest", "failed")])
        override = self._helper().get_role_override({}, result)
        self.assertEqual(override, "dev")

    def test_get_role_override_blocked_returns_none(self):
        """Blocked (infrastructure/timeout) must NOT auto-route to DEV."""
        result = _build_result([_check_result("a", "x", "failed", skip_reason="timed out after 30s")])
        override = self._helper().get_role_override({}, result)
        self.assertIsNone(override)

    def test_get_role_override_passed_returns_none(self):
        result = _build_result([_check_result("a", "x", "passed")])
        override = self._helper().get_role_override({"bugs_found": 0}, result)
        self.assertIsNone(override)

    def test_get_role_override_skipped_returns_none(self):
        result = _build_result([_check_result("a", "x", "skipped")])
        override = self._helper().get_role_override({}, result)
        self.assertIsNone(override)

    def test_get_role_override_critical_bugs_returns_dev(self):
        """Legacy bug-severity routing still works when no execution result."""
        output_data = {"bugs_found": 3, "severity_breakdown": {"critical": 2, "high": 1}}
        override = self._helper().get_role_override(output_data, None)
        self.assertEqual(override, "dev")

    def test_get_role_override_no_execution_result_no_bugs(self):
        override = self._helper().get_role_override({"bugs_found": 0}, None)
        self.assertIsNone(override)


# ─── QAExecutionHelper — DEV rework ──────────────────────────────────────────

class TestQAExecutionHelperRework(_DBFixture):
    def _helper(self):
        return QAExecutionHelper(self.storage)

    def _qa_task(self, epic_id="p1-E001"):
        return _make_task(self.storage, "QA-001", role="qa",
                          task_type="test_report", epic_id=epic_id)

    def test_failed_execution_requeues_backend_code(self):
        dev = _make_dev_task(self.storage, "DEV-001", task_type="backend_code", status="approved")
        qa_task = self._qa_task()
        result = _build_result([_check_result("python:pytest", "pytest", "failed")])
        requeued = self._helper().requeue_dev_tasks(qa_task, result)
        self.assertIn(dev.id, requeued)
        updated = self.storage.get_sdlc_task(dev.id)
        self.assertEqual(updated.status, "pending")
        self.assertEqual(updated.revision_count, 1)

    def test_failed_execution_requeues_unit_tests(self):
        dev = _make_dev_task(self.storage, "DEV-002", task_type="unit_tests", status="approved")
        qa_task = self._qa_task()
        result = _build_result([_check_result("python:pytest", "pytest", "failed")])
        requeued = self._helper().requeue_dev_tasks(qa_task, result)
        self.assertIn(dev.id, requeued)

    def test_failed_execution_requeues_frontend_code(self):
        dev = _make_dev_task(self.storage, "DEV-003", task_type="frontend_code", status="approved")
        qa_task = self._qa_task()
        result = _build_result([_check_result("node:test", "npm run test", "failed")])
        requeued = self._helper().requeue_dev_tasks(qa_task, result)
        self.assertIn(dev.id, requeued)

    def test_non_code_dev_tasks_not_requeued(self):
        """dev_readme and backend_structure are not code tasks — must be left alone."""
        readme = _make_dev_task(self.storage, "DEV-004", task_type="dev_readme", status="approved")
        struct = _make_dev_task(self.storage, "DEV-005", task_type="backend_structure", status="approved")
        qa_task = self._qa_task()
        result = _build_result([_check_result("python:pytest", "pytest", "failed")])
        requeued = self._helper().requeue_dev_tasks(qa_task, result)
        self.assertNotIn(readme.id, requeued)
        self.assertNotIn(struct.id, requeued)

    def test_different_epic_tasks_not_requeued(self):
        dev = _make_dev_task(self.storage, "DEV-001", task_type="backend_code",
                              epic_id="p1-E002", status="approved")
        qa_task = self._qa_task(epic_id="p1-E001")
        result = _build_result([_check_result("python:pytest", "pytest", "failed")])
        requeued = self._helper().requeue_dev_tasks(qa_task, result)
        self.assertNotIn(dev.id, requeued)

    def test_role_feedback_injected_into_requeued_task(self):
        dev = _make_dev_task(self.storage, "DEV-001", task_type="backend_code", status="approved")
        qa_task = self._qa_task()
        result = _build_result([_check_result("python:pytest", "pytest", "failed",
                                              stderr_tail="AssertionError")])
        self._helper().requeue_dev_tasks(qa_task, result)
        updated = self.storage.get_sdlc_task(dev.id)
        inp = json.loads(updated.input_data)
        self.assertIn("role_feedback", inp)
        self.assertIn("qa-execution", inp["role_feedback"])

    def test_blocked_execution_does_not_requeue(self):
        """Blocked (timeout/infra) must not requeue DEV — human review needed."""
        dev = _make_dev_task(self.storage, "DEV-001", task_type="backend_code", status="approved")
        qa_task = self._qa_task()
        blocked_result = _build_result([
            _check_result("python:pytest", "pytest", "failed", skip_reason="timed out after 30s")
        ])
        self.assertEqual(blocked_result["status"], "blocked")
        action = self._helper().decide_action(blocked_result)
        self.assertEqual(action, "blocked")
        # decide_action returns "blocked", so caller (agent) does NOT call requeue_dev_tasks
        # Verify helper.requeue_dev_tasks is NOT called for blocked — simulate agent logic
        if action == "rework":
            self._helper().requeue_dev_tasks(qa_task, blocked_result)
        updated = self.storage.get_sdlc_task(dev.id)
        self.assertEqual(updated.status, "approved")  # unchanged

    def test_passed_execution_does_not_requeue(self):
        dev = _make_dev_task(self.storage, "DEV-001", task_type="backend_code", status="approved")
        qa_task = self._qa_task()
        passed_result = _build_result([_check_result("python:py_compile", "python3 -m py_compile", "passed")])
        action = self._helper().decide_action(passed_result)
        if action == "rework":
            self._helper().requeue_dev_tasks(qa_task, passed_result)
        updated = self.storage.get_sdlc_task(dev.id)
        self.assertEqual(updated.status, "approved")  # unchanged


# ─── QAExecutionHelper — artifact saving and path resolution ─────────────────

class TestQAExecutionHelperArtifacts(_DBFixture):
    def test_save_execution_artifact_writes_json(self):
        qa_task = _make_task(self.storage, "QA-001", task_type="test_report")
        result = _build_result([_check_result("python:py_compile", "python3 -m py_compile", "passed")])
        helper = QAExecutionHelper(self.storage)
        with tempfile.TemporaryDirectory() as out_dir:
            helper.save_execution_artifact(qa_task, out_dir, result)
            json_path = os.path.join(out_dir, "qa_execution_result.json")
            self.assertTrue(os.path.exists(json_path))
            with open(json_path) as fh:
                data = json.load(fh)
            self.assertIn("status", data)
            self.assertIn("checks", data)

    def test_resolve_project_path_uses_input_data_override(self):
        qa_task = _make_task(self.storage, "QA-001")
        helper = QAExecutionHelper(self.storage)
        path = helper.resolve_project_path(qa_task, {"project_path": "/custom/path"})
        self.assertEqual(path, "/custom/path")

    def test_resolve_project_path_falls_back_to_project_dir(self):
        qa_task = _make_task(self.storage, "QA-001",
                              project_id="p1", epic_id="p1-E001")
        helper = QAExecutionHelper(self.storage, output_base="/app/outputs")
        path = helper.resolve_project_path(qa_task, {})
        # DEV dir doesn't exist so it falls through to project dir
        self.assertIn("p1", path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
