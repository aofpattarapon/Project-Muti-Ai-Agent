"""
Tests for test_runner.py and QA agent SDLC hooks.

Run: python3 sdlc/tests/test_test_runner.py
  or: python3 -m pytest sdlc/tests/test_test_runner.py -v
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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_task(storage, task_id, role="qa", task_type="test_report",
               project_id="p1", epic_id="p1-E001", status="in_progress"):
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id=project_id, epic_id=epic_id, task_number=1,
        role=role, task_type=task_type, title=f"T {task_id}", description="",
        output_file="out.md", output_format="markdown", depends_on="",
        status=status, input_data="{}", output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
        claimed_at=now, claimed_by=role,
    )
    storage.create_sdlc_task(t)
    return t


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
            # No .py files, no package.json
            self.assertEqual(_detect_profile(d), "docker")

    def test_node_wins_over_python_when_both_present(self):
        """package.json takes priority over .py files."""
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
            # No .py, no package.json, no docker-compose
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
        """If pytest is not installed, the pytest check is skipped — not crashed."""
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "app.py"), "x = 1\n")
            # Patch the probe call to simulate pytest not installed
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
                # npm not in PATH is also acceptable
                self.assertIn("not found", check.get("skip_reason", ""))

    def test_missing_test_script_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "package.json"), '{"name":"x","scripts":{"build":"tsc"}}')
            r = run_quality_checks(d, profile="node", timeout_seconds=30)
        test_check = next((c for c in r["checks"] if c["name"] == "node:test"), None)
        # Either skipped (script missing) or skipped (npm not found)
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
            # _run_cmd must have been called for test and build (not lint)
            called_names = [call.args[0] for call in mock_run_cmd.call_args_list]
            self.assertIn("node:test", called_names)
            self.assertIn("node:build", called_names)
            self.assertNotIn("node:lint", called_names)
            # lint check should appear as skipped in results
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
        """run_quality_checks must not accept a 'command' or 'commands' parameter."""
        import inspect
        sig = inspect.signature(run_quality_checks)
        self.assertNotIn("command", sig.parameters)
        self.assertNotIn("commands", sig.parameters)

    def test_profile_param_is_not_executed_as_command(self):
        """Passing a shell string as profile must not execute it."""
        r = run_quality_checks("/tmp", profile="rm -rf /")
        # Should just skip with 'unknown profile' error, not execute rm
        self.assertEqual(r["status"], "skipped")
        self.assertIn("unknown profile", r["checks"][0]["skip_reason"])

    def test_project_path_with_shell_injection_is_safe(self):
        """Path containing shell metacharacters must be passed literally."""
        r = run_quality_checks("/tmp/$(echo evil)")
        # Path won't exist → skipped, no command executed
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


# ─── Integration: QA hooks ────────────────────────────────────────────────────

class TestQAIntegration(unittest.TestCase):
    def setUp(self):
        import tempfile as _tf
        self._tmp = _tf.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        import os as _os
        _os.unlink(self._tmp.name)

    def _make_dev_task(self, task_id="DEV-001", epic_id="p1-E001"):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id=task_id, project_id="p1", epic_id=epic_id, task_number=1,
            role="dev", task_type="unit_tests", title=f"T {task_id}", description="",
            output_file="unit_tests.py", output_format="code_multi", depends_on="",
            status="approved", input_data='{"project_name":"TestApp"}',
            output_data="{}", approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
        )
        self.storage.create_sdlc_task(t)
        return t

    def test_dev_feedback_injected_when_execution_fails(self):
        """When QA execution fails, role_feedback is injected into DEV tasks."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent.storage = self.storage

        # Create a DEV task in the same epic
        dev_task = self._make_dev_task()

        # Set up a failed execution result
        failed_result = _build_result([
            _check_result("python:pytest", "pytest", "failed", stderr_tail="AssertionError")
        ])
        agent._last_execution_result = failed_result

        # Create QA test_report task
        qa_task = _make_task(self.storage, "QA-001", role="qa",
                              task_type="test_report", project_id="p1", epic_id="p1-E001")

        # Call inject directly
        agent._inject_dev_feedback(qa_task)

        updated = self.storage.get_sdlc_task(dev_task.id)
        inp = json.loads(updated.input_data)
        self.assertIn("role_feedback", inp)
        self.assertIn("qa-execution", inp["role_feedback"])

    def test_dev_feedback_not_injected_for_different_epic(self):
        """DEV tasks from a different epic must not receive feedback."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent.storage = self.storage

        dev_task = self._make_dev_task(epic_id="p1-E002")  # different epic

        failed_result = _build_result([
            _check_result("python:pytest", "pytest", "failed", stderr_tail="err")
        ])
        agent._last_execution_result = failed_result

        qa_task = _make_task(self.storage, "QA-001", role="qa",
                              task_type="test_report", project_id="p1", epic_id="p1-E001")
        agent._inject_dev_feedback(qa_task)

        updated = self.storage.get_sdlc_task(dev_task.id)
        inp = json.loads(updated.input_data)
        self.assertNotIn("role_feedback", inp)

    def test_no_feedback_injected_when_execution_passes(self):
        """Passing execution must not inject feedback into DEV tasks."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent.storage = self.storage

        dev_task = self._make_dev_task()

        passed_result = _build_result([
            _check_result("python:py_compile", "python3 -m py_compile", "passed")
        ])
        agent._last_execution_result = passed_result

        qa_task = _make_task(self.storage, "QA-001", role="qa",
                              task_type="test_report", project_id="p1", epic_id="p1-E001")
        agent._inject_dev_feedback(qa_task)

        updated = self.storage.get_sdlc_task(dev_task.id)
        inp = json.loads(updated.input_data)
        self.assertNotIn("role_feedback", inp)

    def test_get_next_role_override_returns_dev_on_execution_failure(self):
        """_get_next_role_override must return 'dev' when execution result is failed."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        failed_result = _build_result([
            _check_result("python:pytest", "pytest", "failed")
        ])
        agent._last_execution_result = failed_result
        override = agent._get_next_role_override({})
        self.assertEqual(override, "dev")

    def test_get_next_role_override_none_when_execution_passes(self):
        """No override when execution passes and no critical bugs."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        passed_result = _build_result([
            _check_result("python:py_compile", "python3 -m py_compile", "passed")
        ])
        agent._last_execution_result = passed_result
        override = agent._get_next_role_override({"bugs_found": 0})
        self.assertIsNone(override)

    def test_get_next_role_override_still_works_for_critical_bugs(self):
        """Original bug-severity routing still works when no execution result."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent._last_execution_result = None
        output_data = {
            "bugs_found": 3,
            "severity_breakdown": {"critical": 2, "high": 1},
        }
        override = agent._get_next_role_override(output_data)
        self.assertEqual(override, "dev")

    def test_resolve_project_path_uses_input_data_override(self):
        """Explicit project_path in input_data takes priority."""
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        qa_task = _make_task(self.storage, "QA-001")
        agent.storage = self.storage
        path = agent._resolve_project_path(qa_task, {"project_path": "/custom/path"})
        self.assertEqual(path, "/custom/path")

    def test_post_save_hook_saves_json_artifact(self):
        """_post_save_hook writes qa_execution_result.json when execution result is set."""
        import asyncio
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent.storage = self.storage

        qa_task = _make_task(self.storage, "QA-001", task_type="test_report")
        agent._last_execution_result = _build_result([
            _check_result("python:py_compile", "python3 -m py_compile", "passed")
        ])

        with tempfile.TemporaryDirectory() as out_dir:
            asyncio.run(agent._post_save_hook(qa_task, out_dir))
            json_path = os.path.join(out_dir, "qa_execution_result.json")
            self.assertTrue(os.path.exists(json_path))
            with open(json_path) as fh:
                data = json.load(fh)
            self.assertIn("status", data)
            self.assertIn("checks", data)

    def test_post_save_hook_noop_for_non_test_report_task(self):
        """_post_save_hook does nothing for tasks other than test_report."""
        import asyncio
        from agents.qa.agent import QAAgent
        agent = QAAgent()
        agent.storage = self.storage
        agent._last_execution_result = _build_result([
            _check_result("python:py_compile", "python3 -m py_compile", "passed")
        ])
        qa_task = _make_task(self.storage, "QA-001", task_type="qa_plan")

        with tempfile.TemporaryDirectory() as out_dir:
            asyncio.run(agent._post_save_hook(qa_task, out_dir))
            self.assertFalse(
                os.path.exists(os.path.join(out_dir, "qa_execution_result.json"))
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
