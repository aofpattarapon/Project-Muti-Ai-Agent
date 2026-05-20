"""
Tests for shared/attachment_intake.py

Covers:
  - Text-only inline (no attachments): works unchanged
  - .txt attachment becomes requirements
  - Inline text + .txt attachment: merged with section header
  - .md attachment: parsed as plain text
  - .csv attachment: decoded, pipe-delimited rows
  - .xlsx attachment: parsed via mocked openpyxl
  - Unsupported extension: rejected with clear message
  - .xls: rejected with conversion hint
  - Oversized raw file (> MAX_SINGLE_BYTES): skipped with warning
  - Oversized content (> MAX_ATTACHMENT_CHARS): truncated with warning
  - Combined cap (> MAX_TOTAL_CHARS): combined text truncated with warning
  - Empty message + no attachments: returns empty string, no warnings

Run: python3 sdlc/tests/test_attachment_intake.py
"""

import asyncio
import io
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.attachment_intake import (
    MAX_ATTACHMENT_CHARS,
    MAX_SINGLE_BYTES,
    MAX_TOTAL_CHARS,
    AttachmentResult,
    gather_intake,
    parse_bytes,
)


def _run(coro):
    return asyncio.run(coro)


def _fake_attachment(filename: str, data: bytes) -> MagicMock:
    att = MagicMock()
    att.filename = filename
    att.size = len(data)
    att.read = AsyncMock(return_value=data)
    return att


def _fake_message(inline: str = "", attachments=None) -> MagicMock:
    msg = MagicMock()
    msg.content = inline
    msg.attachments = attachments or []
    return msg


# ─── parse_bytes (synchronous) ───────────────────────────────────────────────

class TestParseBytesText(unittest.TestCase):

    def test_txt_utf8(self):
        r = parse_bytes(b"Hello world", "reqs.txt")
        self.assertEqual(r.text, "Hello world")
        self.assertFalse(r.error)
        self.assertFalse(r.truncated)

    def test_md_utf8(self):
        r = parse_bytes(b"# Title\ncontent", "brief.md")
        self.assertIn("Title", r.text)
        self.assertFalse(r.error)

    def test_txt_latin1_fallback(self):
        data = "Caf\xe9 au lait".encode("latin-1")
        r = parse_bytes(data, "notes.txt")
        self.assertIn("Caf", r.text)
        self.assertFalse(r.error)

    def test_txt_truncated_at_limit(self):
        data = ("x" * (MAX_ATTACHMENT_CHARS + 100)).encode()
        r = parse_bytes(data, "big.txt")
        self.assertEqual(len(r.text), MAX_ATTACHMENT_CHARS)
        self.assertTrue(r.truncated)

    def test_txt_within_limit_not_truncated(self):
        data = ("y" * 100).encode()
        r = parse_bytes(data, "small.txt")
        self.assertFalse(r.truncated)


class TestParseBytesCSV(unittest.TestCase):

    def test_csv_basic(self):
        data = b"Name,Age,Role\nAlice,30,PM\nBob,25,Dev"
        r = parse_bytes(data, "team.csv")
        self.assertIn("Name | Age | Role", r.text)
        self.assertIn("Alice | 30 | PM", r.text)
        self.assertFalse(r.error)

    def test_csv_truncated(self):
        row = "col1,col2,col3\n"
        data = (row * ((MAX_ATTACHMENT_CHARS // len(row)) + 10)).encode()
        r = parse_bytes(data, "huge.csv")
        self.assertTrue(r.truncated)
        self.assertEqual(len(r.text), MAX_ATTACHMENT_CHARS)


class TestParseBytesXlsx(unittest.TestCase):

    def _make_mock_wb(self):
        """Build a fake openpyxl workbook that returns deterministic rows."""
        ws = MagicMock()
        ws.iter_rows = MagicMock(return_value=[
            ("Project Name", "ACME App"),
            ("Budget",       "100k USD"),
            (None,           None),        # empty row — should be skipped
        ])
        wb = MagicMock()
        wb.sheetnames = ["Sheet1"]
        wb.__getitem__ = MagicMock(return_value=ws)
        return wb

    def test_xlsx_parsed_with_mocked_openpyxl(self):
        mock_wb = self._make_mock_wb()
        with patch.dict("sys.modules", {"openpyxl": MagicMock(load_workbook=MagicMock(return_value=mock_wb))}):
            r = parse_bytes(b"fake-xlsx-bytes", "spec.xlsx")
        self.assertFalse(r.error, r.error)
        self.assertIn("Sheet1", r.text)
        self.assertIn("Project Name | ACME App", r.text)
        self.assertNotIn("None | None", r.text)  # empty row skipped

    def test_xlsx_openpyxl_missing(self):
        original = sys.modules.pop("openpyxl", None)
        try:
            # Force ImportError when openpyxl is imported inside parse_bytes
            with patch.dict("sys.modules", {"openpyxl": None}):
                r = parse_bytes(b"bytes", "data.xlsx")
            self.assertIn("openpyxl", r.error)
            self.assertEqual(r.text, "")
        finally:
            if original is not None:
                sys.modules["openpyxl"] = original

    def test_xls_rejected_with_hint(self):
        r = parse_bytes(b"bytes", "legacy.xls")
        self.assertIn(".xls", r.error)
        self.assertIn(".xlsx", r.error)
        self.assertEqual(r.text, "")


class TestParseBytesUnsupported(unittest.TestCase):

    def test_pdf_rejected(self):
        r = parse_bytes(b"%PDF-1.4", "spec.pdf")
        self.assertIn(".pdf", r.error)
        self.assertEqual(r.text, "")

    def test_png_rejected(self):
        r = parse_bytes(b"\x89PNG", "screenshot.png")
        self.assertIn(".png", r.error)
        self.assertIn("Supported:", r.error)

    def test_zip_rejected(self):
        r = parse_bytes(b"PK\x03\x04", "archive.zip")
        self.assertIn("Unsupported", r.error)


# ─── gather_intake (async) ────────────────────────────────────────────────────

class TestGatherIntake(unittest.TestCase):

    def test_inline_only_no_attachments(self):
        msg = _fake_message("Build a trading bot", attachments=[])
        combined, warnings = _run(gather_intake(msg, "Build a trading bot"))
        self.assertEqual(combined, "Build a trading bot")
        self.assertEqual(warnings, [])

    def test_empty_message_no_attachments(self):
        msg = _fake_message("", attachments=[])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertEqual(combined, "")
        self.assertEqual(warnings, [])

    def test_txt_attachment_becomes_requirements(self):
        data = b"Requirement: build a crypto dashboard"
        att = _fake_attachment("reqs.txt", data)
        msg = _fake_message(attachments=[att])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertIn("## Attachment: reqs.txt", combined)
        self.assertIn("crypto dashboard", combined)
        self.assertEqual(warnings, [])

    def test_inline_plus_attachment_merged(self):
        inline = "Project: ACME App"
        data = b"Feature list:\n- Login\n- Dashboard"
        att = _fake_attachment("features.txt", data)
        msg = _fake_message(inline, attachments=[att])
        combined, warnings = _run(gather_intake(msg, inline))
        self.assertTrue(combined.startswith("Project: ACME App"))
        self.assertIn("## Attachment: features.txt", combined)
        self.assertIn("Feature list:", combined)

    def test_attachment_header_label_uses_filename(self):
        att = _fake_attachment("product_spec.md", b"# Spec\ncontent here")
        msg = _fake_message(attachments=[att])
        combined, _ = _run(gather_intake(msg, ""))
        self.assertIn("## Attachment: product_spec.md", combined)

    def test_csv_attachment_parsed(self):
        data = b"Epic,Priority\nUser Auth,P0\nDashboard,P1"
        att = _fake_attachment("epics.csv", data)
        msg = _fake_message(attachments=[att])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertIn("Epic | Priority", combined)
        self.assertIn("User Auth | P0", combined)
        self.assertEqual(warnings, [])

    def test_unsupported_type_rejected_with_warning(self):
        att = _fake_attachment("design.pdf", b"%PDF")
        msg = _fake_message(attachments=[att])
        combined, warnings = _run(gather_intake(msg, "inline text"))
        self.assertEqual(combined, "inline text")
        self.assertEqual(len(warnings), 1)
        self.assertIn("design.pdf", warnings[0])

    def test_oversized_file_skipped_with_warning(self):
        att = _fake_attachment("huge.txt", b"x")
        att.size = MAX_SINGLE_BYTES + 1
        msg = _fake_message(attachments=[att])
        combined, warnings = _run(gather_intake(msg, "base text"))
        self.assertEqual(combined, "base text")
        self.assertEqual(len(warnings), 1)
        self.assertIn("huge.txt", warnings[0])
        self.assertIn("limit", warnings[0])

    def test_truncated_attachment_warns(self):
        data = ("A" * (MAX_ATTACHMENT_CHARS + 500)).encode()
        att = _fake_attachment("big.txt", data)
        msg = _fake_message(attachments=[att])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertTrue(any("truncated" in w for w in warnings))
        self.assertIn("## Attachment: big.txt", combined)

    def test_combined_cap_applied(self):
        # Two large attachments that together exceed MAX_TOTAL_CHARS
        half = MAX_TOTAL_CHARS // 2 + 1000
        att1 = _fake_attachment("a.txt", ("A" * half).encode())
        att2 = _fake_attachment("b.txt", ("B" * half).encode())
        msg = _fake_message(attachments=[att1, att2])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertLessEqual(len(combined), MAX_TOTAL_CHARS)
        self.assertTrue(any("truncated" in w for w in warnings))

    def test_multiple_attachments_all_included(self):
        att1 = _fake_attachment("part1.txt", b"Part 1 content")
        att2 = _fake_attachment("part2.md", b"Part 2 content")
        msg = _fake_message(attachments=[att1, att2])
        combined, warnings = _run(gather_intake(msg, ""))
        self.assertIn("## Attachment: part1.txt", combined)
        self.assertIn("## Attachment: part2.md", combined)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
