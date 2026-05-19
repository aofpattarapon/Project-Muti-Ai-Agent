"""
Artifact Validator — validates LLM output before it is saved or sent for approval.

Each validator returns (is_valid: bool, error_message: str).
error_message is "" when valid, a human-readable explanation when invalid.

The validation is intentionally lenient: it catches clearly broken output
(empty, wrong structure, missing required markers) but does not attempt full
semantic review. Human approval covers the rest.
"""

import re
import json
from typing import Tuple

# ─── Helpers ────────────────────────────────────────────────────────────────

_MIN_CONTENT_LENGTH = 80   # chars — output shorter than this is likely a stub

# Common placeholder strings that indicate the LLM didn't fill in the content
_PLACEHOLDER_RE = re.compile(
    r'\[(?:insert|add|placeholder|your\s+\w+|fill[- ]in|TBD|N/A)[^\]]*\]'
    r'|<(?:placeholder|fill[- ]in|insert)[^>]*>',
    re.IGNORECASE,
)

# Mermaid diagram type keywords — first token on a line after stripping fences
_MERMAID_TYPES = frozenset([
    "graph", "flowchart", "sequencediagram", "classdiagram",
    "statediagram", "statediagram-v2", "erdiagram", "gantt", "pie",
    "gitgraph", "mindmap", "timeline", "journey", "quadrantchart",
    "requirementdiagram", "c4context", "block-beta", "xychart-beta",
])

# SQL keywords that must appear at least once
_SQL_KEYWORDS_RE = re.compile(
    r'\b(CREATE|ALTER|INSERT|SELECT|DROP|UPDATE|DELETE|WITH|MERGE)\b',
    re.IGNORECASE,
)


def validate_artifact(content: str, output_format: str) -> Tuple[bool, str]:
    """Return (is_valid, error_message) for the given content and output format."""
    if not content or not content.strip():
        return False, "Output is empty — LLM returned no usable content"

    fmt = output_format.lower().strip()

    if fmt in ("markdown", "word"):
        return _validate_markdown(content)
    if fmt == "excel":
        return _validate_excel(content)
    if fmt == "mermaid":
        return _validate_mermaid(content)
    if fmt == "yaml":
        return _validate_yaml(content)
    if fmt == "sql":
        return _validate_sql(content)
    if fmt == "dockerfile":
        return _validate_dockerfile(content)
    if fmt == "code_multi":
        return _validate_code_multi(content)
    if fmt == "html":
        return _validate_html(content)

    # Unknown format — pass through; at least it's non-empty
    return True, ""


# ─── Per-format validators ───────────────────────────────────────────────────

def _validate_markdown(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if len(stripped) < _MIN_CONTENT_LENGTH:
        return False, (
            f"Markdown output too short ({len(stripped)} chars < {_MIN_CONTENT_LENGTH}). "
            "Likely a stub or incomplete response."
        )
    placeholder_matches = _PLACEHOLDER_RE.findall(stripped)
    if len(placeholder_matches) >= 5:
        return False, (
            f"Output contains {len(placeholder_matches)} unfilled placeholders "
            f"(e.g. {placeholder_matches[:2]}). LLM did not complete the document."
        )
    # Must have at least one heading OR two non-empty paragraphs
    has_heading = bool(re.search(r'^#{1,6}\s+\S', stripped, re.MULTILINE))
    paragraphs = [p for p in stripped.split('\n\n') if p.strip()]
    if not has_heading and len(paragraphs) < 2:
        return False, (
            "Markdown output has no headings and fewer than 2 paragraphs. "
            "Content appears to be incomplete."
        )
    return True, ""


def _validate_excel(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if len(stripped) < 20:
        return False, "Excel/table output is empty or too short"

    # Option 1: valid JSON with "sheets" key
    # Strip markdown code fence if present
    json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', stripped)
    json_str = json_match.group(1) if json_match else stripped
    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and "sheets" in data:
            sheets = data["sheets"]
            if isinstance(sheets, list) and len(sheets) > 0:
                return True, ""
        # Valid JSON but unexpected structure — still accept, warn in error
        return True, ""
    except (json.JSONDecodeError, ValueError):
        pass

    # Option 2: markdown table (has pipe separators)
    if re.search(r'\|.*\|.*\|', stripped):
        return True, ""

    return False, (
        "Excel output could not be parsed as JSON with 'sheets' key, "
        "and contains no markdown table structure. "
        "Expected: {\"sheets\":[{\"name\":\"...\",\"headers\":[...],\"rows\":[[...]]}]}"
    )


def _validate_mermaid(content: str) -> Tuple[bool, str]:
    # Strip ```mermaid fences if present
    fence_match = re.search(r'```mermaid\s*([\s\S]+?)\s*```', content, re.IGNORECASE)
    raw = fence_match.group(1).strip() if fence_match else content.strip()

    if not raw:
        return False, "Mermaid output is empty after stripping fences"

    # First meaningful line should declare a diagram type
    first_line = ""
    for line in raw.splitlines():
        stripped_line = line.strip()
        if stripped_line and not stripped_line.startswith("%%"):
            first_line = stripped_line.lower()
            break

    if not first_line:
        return False, "Mermaid output has no diagram content (only comments or blank)"

    first_token = re.split(r'[\s\-{(]', first_line)[0].strip()
    if first_token not in _MERMAID_TYPES:
        return False, (
            f"Mermaid diagram type '{first_token}' is not recognized. "
            f"Expected one of: {', '.join(sorted(_MERMAID_TYPES)[:8])}..."
        )

    # Must have at least 2 lines of actual diagram content
    content_lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("%%")]
    if len(content_lines) < 2:
        return False, "Mermaid diagram appears to be empty (only type declaration, no nodes/edges)"

    return True, ""


def _validate_yaml(content: str) -> Tuple[bool, str]:
    # Strip markdown fences if present
    fence_match = re.search(r'```(?:yaml|yml)?\s*([\s\S]+?)\s*```', content, re.IGNORECASE)
    raw = fence_match.group(1).strip() if fence_match else content.strip()

    if not raw:
        return False, "YAML output is empty"

    try:
        import yaml
        parsed = yaml.safe_load(raw)
        if parsed is None:
            return False, "YAML parses to null — output is likely empty or only comments"
        return True, ""
    except ImportError:
        pass  # Fall through to basic syntax check
    except Exception as e:
        return False, f"YAML parse error: {e}"

    # Basic syntax check without yaml module: must have key: value pairs
    kv_lines = [l for l in raw.splitlines() if re.match(r'^\s*\w[\w\s.-]*\s*:', l)]
    if len(kv_lines) == 0:
        return False, "No key: value pairs found — content does not appear to be valid YAML"
    return True, ""


def _validate_sql(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if len(stripped) < 20:
        return False, "SQL output is empty or too short"

    # Strip markdown fences
    fence_match = re.search(r'```(?:sql)?\s*([\s\S]+?)\s*```', stripped, re.IGNORECASE)
    raw = fence_match.group(1).strip() if fence_match else stripped

    if not _SQL_KEYWORDS_RE.search(raw):
        return False, (
            "SQL output contains no SQL statements "
            "(CREATE, ALTER, INSERT, SELECT, DROP, UPDATE, DELETE). "
            "Expected DDL/DML statements."
        )
    return True, ""


def _validate_dockerfile(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if not stripped:
        return False, "Dockerfile output is empty"

    # Strip markdown fences
    fence_match = re.search(r'```(?:dockerfile|docker)?\s*([\s\S]+?)\s*```', stripped, re.IGNORECASE)
    raw = fence_match.group(1).strip() if fence_match else stripped

    if not re.search(r'^\s*FROM\s+\S', raw, re.IGNORECASE | re.MULTILINE):
        return False, "Dockerfile must contain at least one FROM instruction"

    return True, ""


def _validate_code_multi(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if not stripped:
        return False, "code_multi output is empty"

    marker_pattern = re.compile(r'^=== FILE: (.+?) ===$', re.MULTILINE)
    matches = marker_pattern.findall(stripped)

    if not matches:
        return False, (
            "code_multi output contains no '=== FILE: path ===' markers. "
            "Expected format:\n=== FILE: src/main.py ===\n[content]"
        )

    # Check for path traversal attempts
    bad_paths = []
    for path in matches:
        normalized = path.strip().replace("\\", "/")
        if ".." in normalized.split("/"):
            bad_paths.append(path.strip())

    if bad_paths:
        return False, (
            f"code_multi contains path traversal in file markers: {bad_paths}. "
            "Paths must not contain '..' components."
        )

    # At least one file must have non-empty content
    parts = marker_pattern.split(stripped)
    # parts: [preamble, path1, content1, path2, content2, ...]
    file_contents = parts[2::2]
    non_empty = [c for c in file_contents if c.strip()]
    if not non_empty:
        return False, "code_multi has file markers but all file contents are empty"

    return True, ""


def _validate_html(content: str) -> Tuple[bool, str]:
    stripped = content.strip()
    if len(stripped) < 20:
        return False, "HTML output is empty or too short"

    # Strip markdown fences
    fence_match = re.search(r'```(?:html)?\s*([\s\S]+?)\s*```', stripped, re.IGNORECASE)
    raw = fence_match.group(1).strip() if fence_match else stripped

    has_markup = bool(re.search(
        r'<(?:html|body|div|section|article|main|header|footer|p|h[1-6]|!DOCTYPE)',
        raw, re.IGNORECASE,
    ))
    if not has_markup:
        return False, (
            "HTML output contains no meaningful HTML tags "
            "(<html>, <body>, <div>, <section>, etc.)"
        )
    return True, ""
