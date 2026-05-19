"""
Tests for artifact_validator.py and its integration with storage.

Run: python3 sdlc/tests/test_artifact_validator.py
  or: python3 -m pytest sdlc/tests/test_artifact_validator.py -v
"""
import os
import sys
import json
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.artifact_validator import validate_artifact
from shared.storage import Storage, SdlcTask


# ─── Helpers ────────────────────────────────────────────────────────────────

def _ok(content, fmt):
    valid, err = validate_artifact(content, fmt)
    return valid, err


def _make_task(storage, task_id, fmt, status="in_progress"):
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id="p1", epic_id="p1-E001", task_number=1,
        role="ba", task_type="brd", title=f"T {task_id}", description="",
        output_file="out.md", output_format=fmt, depends_on="",
        status=status, input_data="{}", output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
        claimed_at=now, claimed_by="ba",
    )
    storage.create_sdlc_task(t)
    return t


# ─── Markdown / Word ─────────────────────────────────────────────────────────

class TestMarkdownValidator(unittest.TestCase):
    def test_valid_markdown_passes(self):
        content = "# Business Requirements Document\n\n" + "Some real content. " * 10
        ok, err = _ok(content, "markdown")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "markdown")
        self.assertFalse(ok)
        self.assertIn("empty", err.lower())

    def test_too_short_fails(self):
        ok, err = _ok("# Hi\n\nShort.", "markdown")
        self.assertFalse(ok)
        self.assertIn("short", err.lower())

    def test_many_placeholders_fails(self):
        content = "# Doc\n\n" + "[insert content] " * 6 + "Some filler text here today."
        ok, err = _ok(content, "markdown")
        self.assertFalse(ok)
        self.assertIn("placeholder", err.lower())

    def test_word_format_same_rules(self):
        content = "# Requirements\n\n" + "Content paragraph. " * 8
        ok, _ = _ok(content, "word")
        self.assertTrue(ok)

    def test_no_heading_but_two_paragraphs_passes(self):
        para = "This is a paragraph with enough text to be meaningful. " * 2
        content = para + "\n\n" + para
        ok, _ = _ok(content, "markdown")
        self.assertTrue(ok)


# ─── Excel ───────────────────────────────────────────────────────────────────

class TestExcelValidator(unittest.TestCase):
    def test_valid_json_sheets_passes(self):
        data = {"sheets": [{"name": "Matrix", "headers": ["A", "B"], "rows": [["1", "2"]]}]}
        ok, err = _ok(json.dumps(data), "excel")
        self.assertTrue(ok, err)

    def test_json_in_fence_passes(self):
        data = {"sheets": [{"name": "S", "headers": ["X"], "rows": [["v"]]}]}
        content = f"```json\n{json.dumps(data)}\n```"
        ok, err = _ok(content, "excel")
        self.assertTrue(ok, err)

    def test_markdown_table_passes(self):
        content = "| Role | Task | Status |\n|------|------|--------|\n| BA | BRD | Done |"
        ok, err = _ok(content, "excel")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "excel")
        self.assertFalse(ok)

    def test_plain_text_no_table_fails(self):
        ok, err = _ok("Just some random text with no structure at all.", "excel")
        self.assertFalse(ok)
        self.assertIn("json", err.lower())


# ─── Mermaid ─────────────────────────────────────────────────────────────────

class TestMermaidValidator(unittest.TestCase):
    def test_valid_flowchart_passes(self):
        content = "flowchart TD\n  A[Start] --> B[End]"
        ok, err = _ok(content, "mermaid")
        self.assertTrue(ok, err)

    def test_valid_fenced_passes(self):
        content = "```mermaid\nsequenceDiagram\n  A->>B: Hello\n  B-->>A: Hi\n```"
        ok, err = _ok(content, "mermaid")
        self.assertTrue(ok, err)

    def test_valid_er_diagram_passes(self):
        content = "erDiagram\n  USER ||--o{ ORDER : places\n  ORDER ||--|{ ITEM : contains"
        ok, err = _ok(content, "mermaid")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "mermaid")
        self.assertFalse(ok)

    def test_unknown_diagram_type_fails(self):
        content = "unknownDiagram\n  A --> B"
        ok, err = _ok(content, "mermaid")
        self.assertFalse(ok)
        self.assertIn("not recognized", err.lower())

    def test_only_declaration_no_content_fails(self):
        content = "flowchart TD"
        ok, err = _ok(content, "mermaid")
        self.assertFalse(ok)
        self.assertIn("empty", err.lower())

    def test_comments_only_fails(self):
        content = "%% just a comment\n%% another comment"
        ok, err = _ok(content, "mermaid")
        self.assertFalse(ok)


# ─── YAML ────────────────────────────────────────────────────────────────────

class TestYamlValidator(unittest.TestCase):
    def test_valid_yaml_passes(self):
        content = "name: my-service\nport: 8080\ndatabase:\n  host: localhost\n  port: 5432"
        ok, err = _ok(content, "yaml")
        self.assertTrue(ok, err)

    def test_valid_yaml_in_fence_passes(self):
        content = "```yaml\nkey: value\nlist:\n  - a\n  - b\n```"
        ok, err = _ok(content, "yaml")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "yaml")
        self.assertFalse(ok)

    def test_invalid_yaml_fails(self):
        content = "key: [unclosed bracket\n  bad indent\nkey: value: extra"
        ok, err = _ok(content, "yaml")
        self.assertFalse(ok)
        self.assertIn("yaml", err.lower())


# ─── SQL ─────────────────────────────────────────────────────────────────────

class TestSqlValidator(unittest.TestCase):
    def test_valid_ddl_passes(self):
        content = "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
        ok, err = _ok(content, "sql")
        self.assertTrue(ok, err)

    def test_select_passes(self):
        content = "SELECT * FROM users WHERE active = 1;"
        ok, err = _ok(content, "sql")
        self.assertTrue(ok, err)

    def test_sql_in_fence_passes(self):
        content = "```sql\nCREATE TABLE t (id INT);\n```"
        ok, err = _ok(content, "sql")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "sql")
        self.assertFalse(ok)

    def test_no_sql_statements_fails(self):
        content = "Here is the database schema description without any SQL statements."
        ok, err = _ok(content, "sql")
        self.assertFalse(ok)
        self.assertIn("sql", err.lower())


# ─── Dockerfile ──────────────────────────────────────────────────────────────

class TestDockerfileValidator(unittest.TestCase):
    def test_valid_dockerfile_passes(self):
        content = "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"main.py\"]"
        ok, err = _ok(content, "dockerfile")
        self.assertTrue(ok, err)

    def test_dockerfile_in_fence_passes(self):
        content = "```dockerfile\nFROM node:18\nWORKDIR /app\n```"
        ok, err = _ok(content, "dockerfile")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "dockerfile")
        self.assertFalse(ok)

    def test_no_from_fails(self):
        content = "WORKDIR /app\nCOPY . .\nRUN pip install flask\nCMD [\"python\", \"app.py\"]"
        ok, err = _ok(content, "dockerfile")
        self.assertFalse(ok)
        self.assertIn("FROM", err)


# ─── code_multi ──────────────────────────────────────────────────────────────

class TestCodeMultiValidator(unittest.TestCase):
    def test_valid_code_multi_passes(self):
        content = (
            "=== FILE: src/main.py ===\n"
            "def main():\n    print('hello')\n\n"
            "=== FILE: tests/test_main.py ===\n"
            "import pytest\n"
        )
        ok, err = _ok(content, "code_multi")
        self.assertTrue(ok, err)

    def test_no_marker_fails(self):
        content = "def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()"
        ok, err = _ok(content, "code_multi")
        self.assertFalse(ok)
        self.assertIn("marker", err.lower())

    def test_path_traversal_fails(self):
        content = "=== FILE: ../../etc/passwd ===\nroot:x:0:0:root:/root:/bin/bash"
        ok, err = _ok(content, "code_multi")
        self.assertFalse(ok)
        self.assertIn("traversal", err.lower())

    def test_normal_nested_path_passes(self):
        content = "=== FILE: src/utils/helpers.py ===\n# helpers\ndef noop(): pass\n"
        ok, err = _ok(content, "code_multi")
        self.assertTrue(ok, err)

    def test_empty_file_content_fails(self):
        content = "=== FILE: main.py ===\n   \n\n=== FILE: utils.py ===\n   \n"
        ok, err = _ok(content, "code_multi")
        self.assertFalse(ok)
        self.assertIn("empty", err.lower())

    def test_empty_input_fails(self):
        ok, err = _ok("", "code_multi")
        self.assertFalse(ok)


# ─── HTML ────────────────────────────────────────────────────────────────────

class TestHtmlValidator(unittest.TestCase):
    def test_valid_html_passes(self):
        content = "<!DOCTYPE html>\n<html>\n<body>\n<h1>Title</h1>\n<p>Content</p>\n</body>\n</html>"
        ok, err = _ok(content, "html")
        self.assertTrue(ok, err)

    def test_div_based_passes(self):
        content = "<div class='container'><section><p>Hello</p></section></div>"
        ok, err = _ok(content, "html")
        self.assertTrue(ok, err)

    def test_empty_fails(self):
        ok, err = _ok("", "html")
        self.assertFalse(ok)

    def test_plain_text_fails(self):
        content = "This is just plain text without any HTML markup whatsoever, quite long too."
        ok, err = _ok(content, "html")
        self.assertFalse(ok)
        self.assertIn("html", err.lower())


# ─── Unknown format passthrough ──────────────────────────────────────────────

class TestUnknownFormat(unittest.TestCase):
    def test_unknown_format_passes_if_nonempty(self):
        ok, err = _ok("some content", "pdf")
        self.assertTrue(ok, err)

    def test_unknown_format_fails_if_empty(self):
        ok, err = _ok("", "pdf")
        self.assertFalse(ok)


# ─── Integration: validation failure requeues + persists error ───────────────

class TestValidationIntegration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_validation_failure_requeues_task(self):
        """record_sdlc_task_error(requeue=True) puts task back to pending."""
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.record_sdlc_task_error(
            "T-001", "Validation failed: no FROM", attempt_count=1, requeue=True
        )
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "pending")
        self.assertEqual(t.attempt_count, 1)
        self.assertIn("Validation failed", t.last_error)

    def test_validation_failure_persists_last_error(self):
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.record_sdlc_task_error(
            "T-001", "Validation: dockerfile has no FROM", attempt_count=1, requeue=True
        )
        t = self.storage.get_sdlc_task("T-001")
        self.assertIn("FROM", t.last_error)

    def test_validation_failure_clears_claim_fields(self):
        """Requeue after validation failure must clear claimed_at/claimed_by."""
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.record_sdlc_task_error("T-001", "err", attempt_count=1, requeue=True)
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.claimed_at, "")
        self.assertEqual(t.claimed_by, "")

    def test_validation_failure_max_retries_marks_failed(self):
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.record_sdlc_task_error(
            "T-001", "Validation: no FROM", attempt_count=3, requeue=False
        )
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "failed")

    def test_revision_comment_injected_into_input_data(self):
        """update_sdlc_task_input_data merges revision_comment into input_data."""
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.update_sdlc_task_input_data(
            "T-001", {"revision_comment": "[auto-validation] no FROM instruction"}
        )
        t = self.storage.get_sdlc_task("T-001")
        inp = json.loads(t.input_data)
        self.assertIn("revision_comment", inp)
        self.assertIn("FROM", inp["revision_comment"])

    def test_revision_comment_merges_not_replaces(self):
        """Existing input_data keys must be preserved when injecting revision_comment."""
        now = datetime.utcnow().isoformat()
        existing = {"project_name": "MyApp", "brief": "test"}
        t = SdlcTask(
            id="T-002", project_id="p1", epic_id="p1-E001", task_number=2,
            role="ba", task_type="brd", title="T2", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="in_progress", input_data=json.dumps(existing), output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
        )
        self.storage.create_sdlc_task(t)
        self.storage.update_sdlc_task_input_data("T-002", {"revision_comment": "fix this"})
        updated = self.storage.get_sdlc_task("T-002")
        inp = json.loads(updated.input_data)
        self.assertEqual(inp["project_name"], "MyApp")
        self.assertEqual(inp["revision_comment"], "fix this")

    def test_requeued_task_can_be_reclaimed(self):
        """After requeue, a different process should be able to claim the task."""
        _make_task(self.storage, "T-001", "dockerfile")
        self.storage.record_sdlc_task_error("T-001", "err", attempt_count=1, requeue=True)
        # Should succeed since status=pending and claimed_at cleared
        result = self.storage.claim_sdlc_task("T-001", "ba")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
