"""
Output Processor — converts LLM text output into real files
Extracts code blocks, tables, mermaid diagrams and saves as:
  .py, .ts, .tsx, .yaml, .sql, .sh, .json, .xlsx, .docx, .md, .mmd
"""

import os
import re
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OutputArtifact:
    filename: str
    content: bytes
    mime_type: str
    runnable: bool = False  # True = file can be executed directly


# ─── Language → filename mapping ─────────────────────────────────────────────

_LANG_EXT: dict[str, str] = {
    "python":     ".py",
    "py":         ".py",
    "typescript": ".ts",
    "ts":         ".ts",
    "tsx":        ".tsx",
    "javascript": ".js",
    "js":         ".js",
    "yaml":       ".yaml",
    "yml":        ".yaml",
    "sql":        ".sql",
    "bash":       ".sh",
    "sh":         ".sh",
    "shell":      ".sh",
    "json":       ".json",
    "dockerfile": "Dockerfile",
    "docker":     "Dockerfile",
    "mermaid":    ".mmd",
    "mmd":        ".mmd",
    "html":       ".html",
    "css":        ".css",
    "env":        ".env.example",
    "toml":       ".toml",
    "ini":        ".ini",
    "xml":        ".xml",
}

_RUNNABLE_EXTS = {".py", ".sh", ".sql"}


class OutputProcessor:
    """
    Parses raw LLM output and extracts structured artifacts.

    Usage:
        processor = OutputProcessor()
        artifacts = processor.process(role="dev", raw_output=llm_text)
        # artifacts: list[OutputArtifact]
    """

    def process(
        self,
        role: str,
        raw_output: str,
        base_filename: str = "output",
    ) -> list[OutputArtifact]:
        """
        Extract all artifacts from raw LLM output.
        Returns list of OutputArtifact (filename, bytes, mime_type).
        """
        artifacts: list[OutputArtifact] = []

        # 1. Extract named code blocks (```language\n// filename: ...\n```)
        named = self._extract_named_blocks(raw_output)
        artifacts.extend(named)

        already_seen_langs: set[str] = {a.filename.rsplit(".", 1)[-1] for a in artifacts}

        # 2. Extract unnamed code blocks by language tag
        unnamed = self._extract_unnamed_blocks(raw_output, role, already_seen_langs)
        artifacts.extend(unnamed)

        # 3. Extract markdown tables → xlsx
        xlsx = self._tables_to_xlsx(raw_output, base_filename)
        if xlsx:
            artifacts.append(xlsx)

        # 4. Extract mermaid diagrams → individual .mmd files
        mermaid = self._extract_mermaid(raw_output)
        artifacts.extend(mermaid)

        # 5. Convert full output → .docx
        docx = self._to_docx(raw_output, base_filename)
        if docx:
            artifacts.append(docx)

        # 6. Always save raw LLM output as .md
        artifacts.append(OutputArtifact(
            filename=f"{base_filename}.md",
            content=raw_output.encode("utf-8"),
            mime_type="text/markdown",
        ))

        return artifacts

    # ─── Extraction helpers ───────────────────────────────────────────────────

    def _extract_named_blocks(self, text: str) -> list[OutputArtifact]:
        """
        Extracts blocks with explicit filename comment on first line:
          ```python
          # filename: backend/routes.py
          <code>
          ```
        """
        artifacts = []
        pattern = re.compile(
            r"```(\w+)\n"                  # language tag
            r"(?:#|//|--|<!--|;)\s*"        # comment prefix
            r"(?:filename|file|path):\s*"  # keyword
            r"([^\n]+)\n"                  # filename
            r"(.*?)```",                   # content
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            lang, fname, code = m.group(1), m.group(2).strip(), m.group(3)
            artifacts.append(OutputArtifact(
                filename=fname,
                content=code.encode("utf-8"),
                mime_type=_mime(fname),
                runnable=_is_runnable(fname),
            ))
        return artifacts

    def _extract_unnamed_blocks(
        self, text: str, role: str, skip_exts: set[str]
    ) -> list[OutputArtifact]:
        """
        Extracts code blocks by language tag, deduplicating by extension.
        Names them by role convention (e.g. api_spec.yaml for yaml).
        """
        artifacts = []
        seen: dict[str, int] = {}  # ext → count
        pattern = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)

        for m in pattern.finditer(text):
            lang = m.group(1).lower()
            code = m.group(2).strip()
            if not code or lang in ("mermaid", "mmd"):
                continue

            ext = _LANG_EXT.get(lang)
            if not ext or ext in skip_exts:
                continue

            # Build filename
            if ext == "Dockerfile":
                fname = "Dockerfile"
            else:
                base = _role_file_base(role, lang)
                idx = seen.get(ext, 0)
                suffix = f"_{idx}" if idx > 0 else ""
                fname = f"{base}{suffix}{ext}"

            seen[ext] = seen.get(ext, 0) + 1
            artifacts.append(OutputArtifact(
                filename=fname,
                content=code.encode("utf-8"),
                mime_type=_mime(fname),
                runnable=_is_runnable(fname),
            ))

        return artifacts

    def _tables_to_xlsx(self, text: str, base_filename: str) -> Optional[OutputArtifact]:
        """Extract all markdown tables and write to a single xlsx workbook."""
        try:
            import openpyxl
        except ImportError:
            logger.warning("[OutputProcessor] openpyxl not installed — skipping xlsx")
            return None

        table_pattern = re.compile(
            r"###\s+([^\n]+)\n"           # heading before table (optional)
            r"(?:[^\n]*\n)?"              # optional text line
            r"(\|[^\n]+\|\n"             # header row
            r"\|[-| :]+\|\n"             # separator row
            r"(?:\|[^\n]+\|\n)+)",       # data rows
            re.MULTILINE,
        )

        tables = []
        for m in table_pattern.finditer(text):
            heading = m.group(1).strip() if m.group(1) else "Sheet"
            table_text = m.group(2)
            rows = _parse_md_table(table_text)
            if rows:
                tables.append((heading[:31], rows))  # xlsx sheet name max 31 chars

        # Also find tables without headings
        bare_pattern = re.compile(
            r"(\|[^\n]+\|\n\|[-| :]+\|\n(?:\|[^\n]+\|\n)+)",
            re.MULTILINE,
        )
        if not tables:
            for i, m in enumerate(bare_pattern.finditer(text)):
                rows = _parse_md_table(m.group(1))
                if rows:
                    tables.append((f"Sheet{i+1}", rows))

        if not tables:
            return None

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        from openpyxl.styles import Font, PatternFill, Alignment
        header_font  = Font(bold=True, color="FFFFFF")
        header_fill  = PatternFill("solid", fgColor="1F3864")
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for sheet_name, rows in tables:
            ws = wb.create_sheet(title=sheet_name)
            for r_idx, row in enumerate(rows):
                for c_idx, cell_val in enumerate(row):
                    cell = ws.cell(row=r_idx + 1, column=c_idx + 1, value=cell_val)
                    if r_idx == 0:
                        cell.font  = header_font
                        cell.fill  = header_fill
                        cell.alignment = center_align
                    else:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
            # Auto-fit column width
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

        buf = io.BytesIO()
        wb.save(buf)
        return OutputArtifact(
            filename=f"{base_filename}.xlsx",
            content=buf.getvalue(),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _extract_mermaid(self, text: str) -> list[OutputArtifact]:
        """Extract mermaid blocks → individual .mmd files."""
        artifacts = []
        pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
        counters: dict[str, int] = {}

        for m in pattern.finditer(text):
            diagram = m.group(1).strip()
            diag_type = diagram.split("\n")[0].strip().split()[0].lower()
            idx = counters.get(diag_type, 0)
            suffix = f"_{idx}" if idx > 0 else ""
            fname = f"{diag_type}{suffix}.mmd"
            counters[diag_type] = idx + 1

            artifacts.append(OutputArtifact(
                filename=fname,
                content=diagram.encode("utf-8"),
                mime_type="text/plain",
            ))

        return artifacts

    def _to_docx(self, text: str, base_filename: str) -> Optional[OutputArtifact]:
        """Convert full markdown output to .docx."""
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            logger.warning("[OutputProcessor] python-docx not installed — skipping docx")
            return None

        doc = Document()
        # Narrow margins
        for section in doc.sections:
            section.top_margin    = section.top_margin.__class__(914400 // 2)    # 0.5in
            section.bottom_margin = section.bottom_margin.__class__(914400 // 2)
            section.left_margin   = section.left_margin.__class__(914400)        # 1in
            section.right_margin  = section.right_margin.__class__(914400)

        _md_to_docx(doc, text)

        buf = io.BytesIO()
        doc.save(buf)
        return OutputArtifact(
            filename=f"{base_filename}.docx",
            content=buf.getvalue(),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def save_to_disk(
        self,
        artifacts: list[OutputArtifact],
        base_dir: str,
    ) -> dict[str, str]:
        """
        Save all artifacts to disk.
        Returns dict of {filename: absolute_path}.
        """
        saved = {}
        for artifact in artifacts:
            full_path = os.path.join(base_dir, artifact.filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            mode = "wb" if isinstance(artifact.content, bytes) else "w"
            with open(full_path, mode) as f:
                f.write(artifact.content)
            saved[artifact.filename] = full_path
            logger.info(f"[OutputProcessor] saved {artifact.filename} ({len(artifact.content)} bytes)")
        return saved


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _parse_md_table(text: str) -> list[list[str]]:
    """Parse markdown table into list of rows (list of str)."""
    rows = []
    for line in text.strip().splitlines():
        if re.match(r"^\|[-| :]+\|$", line.strip()):
            continue  # separator row
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells:
            rows.append(cells)
    return rows


def _mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "py":   "text/x-python",
        "ts":   "text/typescript",
        "tsx":  "text/typescript",
        "yaml": "text/yaml",
        "yml":  "text/yaml",
        "sql":  "text/plain",
        "sh":   "text/x-shellscript",
        "json": "application/json",
        "md":   "text/markdown",
        "mmd":  "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "text/plain")


def _is_runnable(filename: str) -> bool:
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    return ext in _RUNNABLE_EXTS or filename == "Dockerfile"


def _role_file_base(role: str, lang: str) -> str:
    """Return a sensible base filename for a role + language combination."""
    _role_lang_map: dict[tuple[str, str], str] = {
        ("dev", "yaml"):      "api_spec",
        ("dev", "yml"):       "api_spec",
        ("dev", "sql"):       "schema",
        ("dev", "python"):    "backend/app",
        ("dev", "py"):        "backend/app",
        ("dev", "typescript"):"frontend/app",
        ("dev", "ts"):        "frontend/app",
        ("dev", "tsx"):       "frontend/App",
        ("sa",  "yaml"):      "api_spec",
        ("sa",  "sql"):       "schema",
        ("qa",  "python"):    "tests/test_suite",
        ("qa",  "py"):        "tests/test_suite",
        ("devops", "yaml"):   "docker-compose",
        ("devops", "yml"):    "docker-compose",
        ("devops", "bash"):   "scripts/deploy",
        ("devops", "sh"):     "scripts/deploy",
    }
    return _role_lang_map.get((role, lang), f"{role}_{lang}")


def _md_to_docx(doc, text: str):
    """Convert markdown text to Word document paragraphs (best-effort)."""
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    import lxml.etree as etree

    lines = text.splitlines()
    in_code_block = False
    code_lines = []
    code_lang = ""

    for line in lines:
        # Code block toggle
        if line.startswith("```"):
            if in_code_block:
                # Close code block
                code_text = "\n".join(code_lines)
                para = doc.add_paragraph(style="No Spacing")
                run = para.add_run(code_text)
                run.font.name = "Courier New"
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
                # Light gray background via XML shading
                try:
                    pPr = para._p.get_or_add_pPr()
                    shd = etree.SubElement(pPr, qn("w:shd"))
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), "F5F5F5")
                except Exception:
                    pass
                in_code_block = False
                code_lines = []
                code_lang = ""
            else:
                in_code_block = True
                code_lang = line[3:].strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Headings
        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        # Table rows
        elif line.startswith("|") and line.endswith("|"):
            # Tables are not natively handled here — skip (already in xlsx)
            pass
        # Bullet list
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif re.match(r"^\d+\.\s", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s", "", line), style="List Number")
        # Horizontal rule
        elif line.strip() in ("---", "***", "___"):
            doc.add_paragraph()
        # Empty line
        elif not line.strip():
            doc.add_paragraph()
        # Normal paragraph — handle inline bold/italic
        else:
            para = doc.add_paragraph()
            _add_inline_runs(para, line)


def _add_inline_runs(para, text: str):
    """Add runs with bold/italic/code handling to a paragraph."""
    from docx.shared import Pt, RGBColor

    parts = re.split(r"(\*\*.*?\*\*|`[^`]+`|\*[^*]+\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`"):
            run = para.add_run(part[1:-1])
            run.font.name = "Courier New"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0xC7, 0x25, 0x4F)
        elif part.startswith("*") and part.endswith("*"):
            run = para.add_run(part[1:-1])
            run.italic = True
        else:
            para.add_run(part)
