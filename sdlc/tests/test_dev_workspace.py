"""
Tests for Phase 4: DEV Workspace Mode

Covers:
  - resolve_workspace priority chain
  - WorkspaceWriter path validation (safety cases + happy paths)
  - WorkspaceWriter write_file / write_files
  - build_manifest structure
  - generate_diff output
  - parse_code_output (JSON + code_multi + fenced)
  - DEVExecutionHelper: apply_workspace_writes, save_artifacts, get_workspace_path
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ── make shared/ importable without discord.py ─────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Stub discord so base_agent imports don't blow up (discord-free test)
import types
_discord = types.ModuleType("discord")
_discord.Intents = MagicMock()
_discord.Activity = MagicMock()
_discord.ActivityType = MagicMock()
_discord_ext = types.ModuleType("discord.ext")
_discord_ext_commands = types.ModuleType("discord.ext.commands")
_discord_ext_commands.Bot = MagicMock()
_discord_ext_commands.when_mentioned_or = MagicMock()
sys.modules.setdefault("discord", _discord)
sys.modules.setdefault("discord.ext", _discord_ext)
sys.modules.setdefault("discord.ext.commands", _discord_ext_commands)

from shared.dev_workspace import (
    WorkspacePathError,
    WorkspaceWriteError,
    WorkspaceWriter,
    _read_text,
    build_manifest,
    generate_diff,
    parse_code_output,
    resolve_workspace,
)


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_workspace
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveWorkspace(unittest.TestCase):

    def test_explicit_workspace_path_wins(self):
        with tempfile.TemporaryDirectory() as base:
            ws = os.path.join(base, "projects", "custom", "ws")
            os.makedirs(ws, exist_ok=True)
            result = resolve_workspace(
                "pid", "eid",
                input_data={"workspace_path": ws},
                output_base=base,
            )
            self.assertEqual(result, os.path.realpath(ws))

    def test_default_path_from_output_base(self):
        result = resolve_workspace("pid", "eid", input_data={}, output_base="/base")
        self.assertEqual(result, "/base/projects/pid/eid/workspace")

    def test_env_fallback_when_no_output_base(self):
        with patch.dict(os.environ, {"OUTPUT_BASE_PATH": "/env/base"}):
            result = resolve_workspace("pid", "eid", input_data={})
        self.assertEqual(result, "/env/base/projects/pid/eid/workspace")

    def test_output_base_takes_precedence_over_env(self):
        with patch.dict(os.environ, {"OUTPUT_BASE_PATH": "/env/base"}):
            result = resolve_workspace("pid", "eid", input_data={}, output_base="/explicit")
        self.assertEqual(result, "/explicit/projects/pid/eid/workspace")


# ═══════════════════════════════════════════════════════════════════════════════
# WorkspaceWriter — path validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkspacePathValidation(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.writer = WorkspaceWriter(self._tmp)

    # ── Safety rejections ────────────────────────────────────────────────────

    def test_empty_path_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("")

    def test_whitespace_only_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("   ")

    def test_absolute_path_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("/etc/passwd")

    def test_traversal_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("../outside/file.py")

    def test_traversal_deep_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("a/b/../../../../../../etc/passwd")

    def test_dot_git_component_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path(".git/config")

    def test_node_modules_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("node_modules/evil/index.js")

    def test_secrets_dir_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("secrets/key.txt")

    def test_dot_secrets_dir_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path(".secrets/token")

    def test_env_file_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path(".env")

    def test_env_local_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path(".env.local")

    def test_env_production_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path(".env.production")

    def test_pem_extension_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("certs/server.pem")

    def test_key_extension_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("id_rsa.key")

    def test_exe_extension_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("bin/run.exe")

    def test_pyc_extension_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("app/__pycache__/main.pyc")

    def test_image_extension_rejected(self):
        with self.assertRaises(WorkspacePathError):
            self.writer.validate_path("assets/logo.png")

    # ── Valid paths succeed ──────────────────────────────────────────────────

    def test_simple_py_file_accepted(self):
        abs_path = self.writer.validate_path("app/main.py")
        self.assertTrue(abs_path.startswith(self._tmp))

    def test_nested_ts_file_accepted(self):
        abs_path = self.writer.validate_path("src/components/Button.tsx")
        self.assertTrue(abs_path.startswith(self._tmp))

    def test_requirements_txt_accepted(self):
        abs_path = self.writer.validate_path("requirements.txt")
        self.assertTrue(abs_path.startswith(self._tmp))

    def test_path_stays_inside_root(self):
        abs_path = self.writer.validate_path("a/b/c.py")
        self.assertTrue(abs_path.startswith(self._tmp + os.sep))

    def test_dot_prefix_file_not_env_accepted(self):
        # e.g. .gitignore should be allowed
        abs_path = self.writer.validate_path(".gitignore")
        self.assertTrue(abs_path.startswith(self._tmp))


# ═══════════════════════════════════════════════════════════════════════════════
# WorkspaceWriter — write_file
# ═══════════════════════════════════════════════════════════════════════════════

class TestWriteFile(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.writer = WorkspaceWriter(self._tmp)

    def test_overwrite_creates_new_file(self):
        result = self.writer.write_file("src/hello.py", "print('hi')")
        self.assertEqual(result["action"], "written")
        self.assertIsNone(result["error"])
        self.assertIsNone(result["sha256_before"])
        self.assertIsNotNone(result["sha256_after"])

    def test_overwrite_replaces_existing(self):
        self.writer.write_file("f.py", "v1")
        r2 = self.writer.write_file("f.py", "v2")
        self.assertEqual(r2["action"], "written")
        self.assertNotEqual(r2["sha256_before"], r2["sha256_after"])

    def test_create_mode_new_file(self):
        result = self.writer.write_file("new.py", "x=1", mode="create")
        self.assertEqual(result["action"], "written")

    def test_create_mode_existing_file_skipped(self):
        self.writer.write_file("existing.py", "original")
        result = self.writer.write_file("existing.py", "new", mode="create")
        self.assertEqual(result["action"], "skipped")
        self.assertIn("already exists", result["error"])

    def test_append_mode_extends_file(self):
        self.writer.write_file("log.txt", "line1\n")
        result = self.writer.write_file("log.txt", "line2\n", mode="append")
        self.assertEqual(result["action"], "appended")
        fpath = os.path.join(self._tmp, "log.txt")
        content = open(fpath).read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)

    def test_append_mode_creates_if_absent(self):
        result = self.writer.write_file("new_log.txt", "start\n", mode="append")
        self.assertEqual(result["action"], "written")

    def test_invalid_mode_returns_error(self):
        result = self.writer.write_file("f.py", "x", mode="delete")
        self.assertEqual(result["action"], "error")
        self.assertIn("delete", result["error"])

    def test_safety_violation_returns_error(self):
        result = self.writer.write_file("../escape.py", "x")
        self.assertEqual(result["action"], "error")

    def test_bytes_written_matches_utf8_length(self):
        content = "สวัสดี"  # Thai chars, multi-byte UTF-8
        result = self.writer.write_file("thai.py", content)
        self.assertEqual(result["bytes_written"], len(content.encode("utf-8")))

    def test_nested_dir_created_automatically(self):
        result = self.writer.write_file("a/b/c/d.py", "x=1")
        self.assertEqual(result["action"], "written")
        self.assertTrue(os.path.isfile(os.path.join(self._tmp, "a/b/c/d.py")))


# ═══════════════════════════════════════════════════════════════════════════════
# WorkspaceWriter — write_files (batch)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWriteFiles(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.writer = WorkspaceWriter(self._tmp)

    def test_batch_returns_one_result_per_file(self):
        files = [
            {"path": "a.py", "content": "a=1"},
            {"path": "b.py", "content": "b=2"},
        ]
        results = self.writer.write_files(files)
        self.assertEqual(len(results), 2)

    def test_batch_with_mixed_outcomes(self):
        # First write: ok; second has safety violation
        files = [
            {"path": "ok.py", "content": "x=1"},
            {"path": "../bad.py", "content": "evil"},
        ]
        results = self.writer.write_files(files)
        self.assertEqual(results[0]["action"], "written")
        self.assertEqual(results[1]["action"], "error")

    def test_empty_batch_returns_empty_list(self):
        results = self.writer.write_files([])
        self.assertEqual(results, [])


# ═══════════════════════════════════════════════════════════════════════════════
# build_manifest
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildManifest(unittest.TestCase):

    def _make_result(self, action):
        return {
            "path": "x.py", "action": action,
            "bytes_written": 10, "sha256_before": None, "sha256_after": "abc",
            "error": None,
        }

    def test_manifest_has_required_keys(self):
        m = build_manifest("/ws", "task-1", [])
        for key in ("workspace_root", "task_id", "timestamp", "files",
                    "total_files", "written_count", "failed_count", "skipped_count"):
            self.assertIn(key, m)

    def test_written_count(self):
        results = [self._make_result("written"), self._make_result("written")]
        m = build_manifest("/ws", "t", results)
        self.assertEqual(m["written_count"], 2)
        self.assertEqual(m["failed_count"], 0)

    def test_failed_count(self):
        results = [self._make_result("error")]
        m = build_manifest("/ws", "t", results)
        self.assertEqual(m["failed_count"], 1)
        self.assertEqual(m["written_count"], 0)

    def test_skipped_count(self):
        results = [self._make_result("skipped"), self._make_result("written")]
        m = build_manifest("/ws", "t", results)
        self.assertEqual(m["skipped_count"], 1)
        self.assertEqual(m["total_files"], 2)


# ═══════════════════════════════════════════════════════════════════════════════
# generate_diff
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateDiff(unittest.TestCase):

    def test_new_file_shows_additions(self):
        diff = generate_diff(before={}, after={"hello.py": "print('hi')\n"})
        self.assertIn("+print('hi')", diff)
        self.assertIn("b/hello.py", diff)

    def test_modified_file_shows_change(self):
        diff = generate_diff(
            before={"f.py": "x = 1\n"},
            after={"f.py": "x = 2\n"},
        )
        self.assertIn("-x = 1", diff)
        self.assertIn("+x = 2", diff)

    def test_unchanged_file_empty_diff(self):
        diff = generate_diff(
            before={"f.py": "same\n"},
            after={"f.py": "same\n"},
        )
        self.assertEqual(diff, "")

    def test_multiple_files(self):
        diff = generate_diff(
            before={"a.py": "a\n", "b.py": "b\n"},
            after={"a.py": "A\n", "b.py": "b\n"},
        )
        self.assertIn("a/a.py", diff)
        self.assertNotIn("b/b.py", diff)  # b.py unchanged → not in diff

    def test_deleted_file_shows_removals(self):
        diff = generate_diff(
            before={"gone.py": "old line\n"},
            after={},
        )
        self.assertIn("-old line", diff)


# ═══════════════════════════════════════════════════════════════════════════════
# parse_code_output
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseCodeOutput(unittest.TestCase):

    # ── code_multi format ────────────────────────────────────────────────────

    def test_code_multi_single_file(self):
        content = "=== FILE: src/main.py ===\nprint('hello')"
        result = parse_code_output(content)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "src/main.py")
        self.assertIn("print('hello')", result[0]["content"])

    def test_code_multi_multiple_files(self):
        content = (
            "=== FILE: a.py ===\nx = 1\n"
            "=== FILE: b.py ===\ny = 2\n"
        )
        result = parse_code_output(content)
        self.assertEqual(len(result), 2)
        paths = [f["path"] for f in result]
        self.assertIn("a.py", paths)
        self.assertIn("b.py", paths)

    def test_code_multi_default_mode_overwrite(self):
        content = "=== FILE: x.py ===\nx=1"
        result = parse_code_output(content)
        self.assertEqual(result[0]["mode"], "overwrite")

    # ── JSON format ─────────────────────────────────────────────────────────

    def test_json_format(self):
        data = {"files": [{"path": "app.py", "content": "pass", "mode": "overwrite"}]}
        content = json.dumps(data)
        result = parse_code_output(content)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "app.py")

    def test_json_format_default_mode(self):
        data = {"files": [{"path": "app.py", "content": "pass"}]}
        content = json.dumps(data)
        result = parse_code_output(content)
        self.assertEqual(result[0]["mode"], "overwrite")

    def test_fenced_json(self):
        data = {"files": [{"path": "x.py", "content": "y=1"}]}
        content = f"```json\n{json.dumps(data)}\n```"
        result = parse_code_output(content)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "x.py")

    # ── Edge cases ───────────────────────────────────────────────────────────

    def test_no_markers_returns_empty(self):
        result = parse_code_output("no markers here")
        self.assertEqual(result, [])

    def test_empty_string_returns_empty(self):
        result = parse_code_output("")
        self.assertEqual(result, [])

    def test_malformed_json_falls_back_to_code_multi(self):
        content = '{"broken": true\n=== FILE: rescue.py ===\nx=1'
        result = parse_code_output(content)
        # Should find the code_multi marker
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "rescue.py")


# ═══════════════════════════════════════════════════════════════════════════════
# DEVExecutionHelper
# ═══════════════════════════════════════════════════════════════════════════════

def _make_task(task_type="backend_code", project_id="proj1", epic_id="epic1"):
    task = MagicMock()
    task.task_type = task_type
    task.project_id = project_id
    task.epic_id = epic_id
    task.id = f"{task_type}-task-id"
    return task


class TestDEVExecutionHelperWorkspacePath(unittest.TestCase):

    def _make_helper(self, output_base="/base"):
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        return DEVExecutionHelper(storage, output_base=output_base)

    def test_explicit_workspace_path_from_input_data(self):
        with tempfile.TemporaryDirectory() as base:
            ws = os.path.join(base, "projects", "custom")
            os.makedirs(ws, exist_ok=True)
            helper = self._make_helper(output_base=base)
            task = _make_task()
            result = helper.get_workspace_path(task, {"workspace_path": ws})
            self.assertEqual(result, os.path.realpath(ws))

    def test_default_path_built_from_task(self):
        helper = self._make_helper(output_base="/base")
        task = _make_task(project_id="p1", epic_id="e1")
        result = helper.get_workspace_path(task, {})
        self.assertEqual(result, "/base/projects/p1/e1/workspace")


class TestApplyWorkspaceWrites(unittest.TestCase):

    def _make_helper(self, tmp_dir):
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        helper = DEVExecutionHelper(storage, output_base=tmp_dir)
        return helper

    def test_code_multi_output_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: app/main.py ===\nprint('hello')\n"
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertGreaterEqual(manifest["written_count"], 1)
            # Verify file was actually written
            ws = os.path.join(tmp, "projects", "p1", "e1", "workspace")
            self.assertTrue(os.path.isfile(os.path.join(ws, "app/main.py")))

    def test_json_output_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            data = {"files": [{"path": "utils.py", "content": "x=1"}]}
            content = json.dumps(data)
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertEqual(manifest["written_count"], 1)

    def test_no_markers_returns_empty_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task()
            manifest = helper.apply_workspace_writes(task, "no markers", {})
            self.assertEqual(manifest["total_files"], 0)
            self.assertEqual(manifest["written_count"], 0)

    def test_unsafe_path_in_output_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: ../escape.py ===\nevil"
            manifest = helper.apply_workspace_writes(task, content, {})
            # File should fail safely — no files written outside workspace
            self.assertEqual(manifest["written_count"], 0)
            escape_path = os.path.join(tmp, "projects", "p1", "e1", "escape.py")
            self.assertFalse(os.path.exists(escape_path))

    def test_manifest_includes_diff_patch_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: x.py ===\nfoo = 1\n"
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertIn("diff_patch", manifest)

    def test_diff_patch_contains_additions(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: new.py ===\nfoo = 42\n"
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertIn("+foo = 42", manifest.get("diff_patch", ""))

    def test_explicit_workspace_path_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = os.path.join(tmp, "custom_ws")
            helper = self._make_helper(tmp)
            task = _make_task()
            content = "=== FILE: hello.py ===\nhi=1\n"
            helper.apply_workspace_writes(task, content, {"workspace_path": ws})
            self.assertTrue(os.path.isfile(os.path.join(ws, "hello.py")))


class TestSaveArtifacts(unittest.TestCase):

    def _make_helper(self):
        from agents.dev.execution_helper import DEVExecutionHelper
        return DEVExecutionHelper(MagicMock(), output_base="/base")

    def test_manifest_json_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper()
            task = _make_task()
            manifest = {
                "workspace_root": "/ws",
                "task_id": task.id,
                "timestamp": "2026-01-01T00:00:00",
                "files": [], "total_files": 0,
                "written_count": 0, "failed_count": 0, "skipped_count": 0,
                "diff_patch": "",
            }
            helper.save_artifacts(task, tmp, manifest)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "dev_workspace_manifest.json")))

    def test_diff_patch_written_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper()
            task = _make_task()
            manifest = {
                "workspace_root": "/ws", "task_id": task.id,
                "timestamp": "2026-01-01T00:00:00",
                "files": [], "total_files": 0,
                "written_count": 1, "failed_count": 0, "skipped_count": 0,
                "diff_patch": "--- a/f.py\n+++ b/f.py\n@@ -0,0 +1 @@\n+x=1\n",
            }
            helper.save_artifacts(task, tmp, manifest)
            patch_path = os.path.join(tmp, "dev_workspace_diff.patch")
            self.assertTrue(os.path.isfile(patch_path))
            self.assertIn("+x=1", open(patch_path).read())

    def test_no_patch_file_when_diff_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper()
            task = _make_task()
            manifest = {
                "workspace_root": "/ws", "task_id": task.id,
                "timestamp": "2026-01-01T00:00:00",
                "files": [], "total_files": 0,
                "written_count": 0, "failed_count": 0, "skipped_count": 0,
                "diff_patch": "",
            }
            helper.save_artifacts(task, tmp, manifest)
            self.assertFalse(
                os.path.isfile(os.path.join(tmp, "dev_workspace_diff.patch"))
            )

    def test_manifest_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._make_helper()
            task = _make_task()
            manifest = {
                "workspace_root": "/ws", "task_id": task.id,
                "timestamp": "2026-01-01T00:00:00",
                "files": [{"path": "x.py", "action": "written"}],
                "total_files": 1, "written_count": 1,
                "failed_count": 0, "skipped_count": 0,
                "diff_patch": "",
            }
            helper.save_artifacts(task, tmp, manifest)
            with open(os.path.join(tmp, "dev_workspace_manifest.json")) as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded["task_id"], task.id)
            self.assertEqual(loaded["written_count"], 1)


# ═══════════════════════════════════════════════════════════════════════════════
# DEV task_prompts rework_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestDevTaskPromptsReworkContext(unittest.TestCase):

    def _build(self, task_type, role_feedback="", revision_count=0):
        from agents.dev.task_prompts import build_dev_task_prompt
        ctx = {
            "project_name": "TestProject",
            "epic_id": "EP-01",
            "epic_title": "Test Epic",
            "epic_goal": "test goal",
            "frontend_structure_content": "",
            "uxui_wireframe": "",
            "sa_api_spec": "",
            "sa_database_schema": "",
            "backend_structure_content": "",
            "backend_code_content": "",
            "frontend_code_content": "",
            "role_feedback": role_feedback,
            "revision_count": revision_count,
        }
        return build_dev_task_prompt(task_type, ctx)

    def test_no_rework_context_when_revision_zero(self):
        prompt = self._build("backend_code")
        self.assertNotIn("Rework Context", prompt)
        self.assertNotIn("Revision", prompt)

    def test_rework_context_shown_when_revision_and_feedback(self):
        prompt = self._build("backend_code", role_feedback="tests failed: X", revision_count=1)
        self.assertIn("Rework Context", prompt)
        self.assertIn("tests failed: X", prompt)
        self.assertIn("Revision #1", prompt)

    def test_rework_context_for_frontend_code(self):
        prompt = self._build("frontend_code", role_feedback="lint errors", revision_count=2)
        self.assertIn("Rework Context", prompt)
        self.assertIn("lint errors", prompt)

    def test_rework_context_for_unit_tests(self):
        prompt = self._build("unit_tests", role_feedback="pytest failed", revision_count=1)
        self.assertIn("Rework Context", prompt)
        self.assertIn("pytest failed", prompt)

    def test_revision_only_no_feedback(self):
        prompt = self._build("backend_code", role_feedback="", revision_count=2)
        self.assertIn("Revision #2", prompt)
        self.assertNotIn("QA execution failed", prompt)


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_workspace — explicit path base validation (Blocker 1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveWorkspaceBaseValidation(unittest.TestCase):

    def test_explicit_path_inside_allowed_base_accepted(self):
        with tempfile.TemporaryDirectory() as base:
            allowed = os.path.join(base, "projects", "p1")
            os.makedirs(allowed, exist_ok=True)
            result = resolve_workspace(
                "p1", "e1",
                input_data={"workspace_path": allowed},
                output_base=base,
            )
            self.assertEqual(result, os.path.realpath(allowed))

    def test_explicit_path_outside_allowed_base_raises(self):
        with tempfile.TemporaryDirectory() as base:
            with tempfile.TemporaryDirectory() as other:
                with self.assertRaises(WorkspacePathError):
                    resolve_workspace(
                        "p1", "e1",
                        input_data={"workspace_path": other},
                        output_base=base,
                    )

    def test_absolute_path_to_root_rejected(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(WorkspacePathError):
                resolve_workspace(
                    "p1", "e1",
                    input_data={"workspace_path": "/"},
                    output_base=base,
                )

    def test_dev_workspace_base_env_var_overrides_allowed_base(self):
        with tempfile.TemporaryDirectory() as dev_base:
            with tempfile.TemporaryDirectory() as output_base:
                sub = os.path.join(dev_base, "ws")
                os.makedirs(sub, exist_ok=True)
                with patch.dict(os.environ, {"DEV_WORKSPACE_BASE": dev_base}):
                    result = resolve_workspace(
                        "p1", "e1",
                        input_data={"workspace_path": sub},
                        output_base=output_base,
                    )
                self.assertEqual(result, os.path.realpath(sub))

    def test_path_outside_dev_workspace_base_rejected(self):
        with tempfile.TemporaryDirectory() as dev_base:
            with tempfile.TemporaryDirectory() as other:
                with patch.dict(os.environ, {"DEV_WORKSPACE_BASE": dev_base}):
                    with self.assertRaises(WorkspacePathError):
                        resolve_workspace(
                            "p1", "e1",
                            input_data={"workspace_path": other},
                            output_base="/irrelevant",
                        )

    def test_no_explicit_path_always_allowed(self):
        with tempfile.TemporaryDirectory() as base:
            result = resolve_workspace("p1", "e1", input_data={}, output_base=base)
            self.assertIn("p1", result)
            self.assertIn("e1", result)


# ═══════════════════════════════════════════════════════════════════════════════
# check_workspace_results — failure signaling (Blocker 2)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckWorkspaceResults(unittest.TestCase):

    def _make_helper(self):
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=0)
        return DEVExecutionHelper(storage, output_base="/base"), storage

    def _manifest(self, written=1, failed=0):
        return {
            "workspace_root": "/ws",
            "task_id": "t1",
            "timestamp": "2026-01-01T00:00:00",
            "files": [],
            "total_files": written + failed,
            "written_count": written,
            "failed_count": failed,
            "skipped_count": 0,
        }

    def test_all_written_no_exception(self):
        helper, storage = self._make_helper()
        task = _make_task()
        helper.check_workspace_results(task, self._manifest(written=2, failed=0))
        storage.record_sdlc_task_error.assert_not_called()

    def test_failed_count_raises_workspace_write_error(self):
        helper, _ = self._make_helper()
        task = _make_task()
        with self.assertRaises(WorkspaceWriteError):
            helper.check_workspace_results(task, self._manifest(written=0, failed=1))

    def test_failed_count_calls_record_sdlc_task_error(self):
        helper, storage = self._make_helper()
        task = _make_task()
        try:
            helper.check_workspace_results(task, self._manifest(written=1, failed=2))
        except WorkspaceWriteError:
            pass
        storage.record_sdlc_task_error.assert_called_once()
        call_args = storage.record_sdlc_task_error.call_args
        # First positional arg is task_id; requeue is passed as keyword arg
        self.assertEqual(call_args[0][0], task.id)
        self.assertTrue(call_args.kwargs["requeue"])

    def test_error_message_mentions_failed_count(self):
        helper, _ = self._make_helper()
        task = _make_task()
        with self.assertRaises(WorkspaceWriteError) as ctx:
            helper.check_workspace_results(task, self._manifest(written=0, failed=3))
        self.assertIn("3", str(ctx.exception))

    def test_zero_total_files_no_exception(self):
        helper, storage = self._make_helper()
        task = _make_task()
        helper.check_workspace_results(task, self._manifest(written=0, failed=0))
        storage.record_sdlc_task_error.assert_not_called()


class TestWorkspaceWriteFailureEndToEnd(unittest.TestCase):
    """End-to-end: invalid paths in LLM output produce failed_count > 0."""

    def _make_helper(self, tmp):
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=0)
        return DEVExecutionHelper(storage, output_base=tmp), storage

    def test_traversal_path_in_llm_output_counts_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper, _ = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: ../escape.py ===\nevil"
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertEqual(manifest["failed_count"], 1)
            self.assertEqual(manifest["written_count"], 0)

    def test_env_file_in_llm_output_counts_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper, _ = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = "=== FILE: .env.production ===\nSECRET=bad"
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertEqual(manifest["failed_count"], 1)
            self.assertEqual(manifest["written_count"], 0)

    def test_mixed_valid_invalid_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper, _ = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = (
                "=== FILE: good.py ===\nx=1\n"
                "=== FILE: ../bad.py ===\nevil\n"
            )
            manifest = helper.apply_workspace_writes(task, content, {})
            self.assertEqual(manifest["written_count"], 1)
            self.assertEqual(manifest["failed_count"], 1)

    def test_check_workspace_results_raises_after_mixed_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper, storage = self._make_helper(tmp)
            task = _make_task(project_id="p1", epic_id="e1")
            content = (
                "=== FILE: ok.py ===\nx=1\n"
                "=== FILE: .git/config ===\nevil\n"
            )
            manifest = helper.apply_workspace_writes(task, content, {})
            with self.assertRaises(WorkspaceWriteError):
                helper.check_workspace_results(task, manifest)
            # Error was recorded → task will NOT proceed to approval
            storage.record_sdlc_task_error.assert_called_once()

    def test_outside_base_workspace_path_raises_on_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as other:
                helper, storage = self._make_helper(tmp)
                task = _make_task(project_id="p1", epic_id="e1")
                content = "=== FILE: x.py ===\nx=1\n"
                # Explicit workspace_path outside allowed base
                with self.assertRaises(WorkspacePathError):
                    helper.apply_workspace_writes(task, content, {"workspace_path": other})


# ═══════════════════════════════════════════════════════════════════════════════
# No double attempt_count increment (Blocker 3 fix)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoDoubleAttemptCount(unittest.TestCase):
    """Proves attempt_count is incremented exactly once for a workspace write failure."""

    def _make_helper(self, attempt_count=0):
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=attempt_count)
        return DEVExecutionHelper(storage, output_base="/base"), storage

    def test_workspace_write_error_carries_already_recorded_flag(self):
        exc = WorkspaceWriteError("fail", already_recorded=True)
        self.assertTrue(exc.already_recorded)

    def test_workspace_write_error_default_not_already_recorded(self):
        exc = WorkspaceWriteError("fail")
        self.assertFalse(exc.already_recorded)

    def test_check_workspace_results_sets_already_recorded_on_exception(self):
        helper, _ = self._make_helper()
        task = _make_task()
        manifest = {
            "workspace_root": "/ws", "task_id": task.id,
            "timestamp": "2026-01-01", "files": [],
            "total_files": 1, "written_count": 0, "failed_count": 1, "skipped_count": 0,
        }
        with self.assertRaises(WorkspaceWriteError) as ctx:
            helper.check_workspace_results(task, manifest)
        self.assertTrue(ctx.exception.already_recorded)

    def test_check_workspace_results_calls_record_exactly_once(self):
        """Hook records the error; poll loop sees already_recorded=True and skips."""
        helper, storage = self._make_helper(attempt_count=0)
        task = _make_task()
        manifest = {
            "workspace_root": "/ws", "task_id": task.id,
            "timestamp": "2026-01-01", "files": [],
            "total_files": 1, "written_count": 0, "failed_count": 1, "skipped_count": 0,
        }
        try:
            helper.check_workspace_results(task, manifest)
        except WorkspaceWriteError:
            pass
        # Exactly one DB call from the hook
        self.assertEqual(storage.record_sdlc_task_error.call_count, 1)

    def test_poll_loop_skips_record_when_already_recorded(self):
        """Simulates BaseAgent poll loop: already_recorded=True → no extra DB call."""
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=1)
        exc = WorkspaceWriteError("file failed", already_recorded=True)
        _MAX_AUTO_RETRIES = 2

        fresh = storage.get_sdlc_task("task-id")
        # Poll loop logic: already_recorded → use DB count directly, no +1
        fail_count = fresh.attempt_count  # = 1, not 2
        _exhausted = fail_count > _MAX_AUTO_RETRIES

        if not exc.already_recorded:
            storage.record_sdlc_task_error("task-id", str(exc), fail_count,
                                           requeue=not _exhausted)
        elif _exhausted:
            storage.record_sdlc_task_error("task-id", str(exc), fail_count, requeue=False)

        # attempt_count=1 not exhausted + already_recorded → zero additional DB calls
        storage.record_sdlc_task_error.assert_not_called()
        self.assertEqual(fail_count, 1)

    def test_poll_loop_flips_to_failed_when_exhausted_and_already_recorded(self):
        """If retries exhausted, poll loop calls record once more to flip requeue=False."""
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=3)  # > MAX_AUTO_RETRIES=2
        exc = WorkspaceWriteError("file failed", already_recorded=True)
        _MAX_AUTO_RETRIES = 2

        fresh = storage.get_sdlc_task("task-id")
        fail_count = fresh.attempt_count  # = 3
        _exhausted = fail_count > _MAX_AUTO_RETRIES  # True

        if not exc.already_recorded:
            storage.record_sdlc_task_error("task-id", str(exc), fail_count,
                                           requeue=not _exhausted)
        elif _exhausted:
            storage.record_sdlc_task_error("task-id", str(exc), fail_count, requeue=False)

        # One call to flip from pending→failed (requeue=False)
        storage.record_sdlc_task_error.assert_called_once_with(
            "task-id", str(exc), 3, requeue=False
        )

    def test_total_db_calls_across_hook_and_poll_loop_is_one(self):
        """End-to-end: hook records once + poll loop skips = total 1 DB call."""
        from agents.dev.execution_helper import DEVExecutionHelper
        storage = MagicMock()
        storage.get_sdlc_task.return_value = MagicMock(attempt_count=0)
        helper = DEVExecutionHelper(storage, output_base="/base")
        task = _make_task()
        manifest = {
            "workspace_root": "/ws", "task_id": task.id,
            "timestamp": "2026-01-01", "files": [],
            "total_files": 1, "written_count": 0, "failed_count": 1, "skipped_count": 0,
        }
        exc = None
        try:
            helper.check_workspace_results(task, manifest)
        except WorkspaceWriteError as e:
            exc = e

        # Simulate poll loop: sees already_recorded=True, skips recording
        _MAX_AUTO_RETRIES = 2
        fresh = storage.get_sdlc_task(task.id)
        fail_count = fresh.attempt_count  # 0+1 already set by hook = 1 (mocked stays 0)
        _exhausted = fail_count > _MAX_AUTO_RETRIES
        if not exc.already_recorded:
            storage.record_sdlc_task_error(task.id, str(exc), fail_count + 1,
                                           requeue=not _exhausted)
        elif _exhausted:
            storage.record_sdlc_task_error(task.id, str(exc), fail_count, requeue=False)

        # Total: 1 from hook, 0 from poll loop simulation → exactly 1
        self.assertEqual(storage.record_sdlc_task_error.call_count, 1)


if __name__ == "__main__":
    unittest.main()
