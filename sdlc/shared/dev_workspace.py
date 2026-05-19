"""
DEV Workspace — safe file writer for DEV code task outputs.

Key guarantees:
  - Only relative paths accepted; absolute paths rejected
  - Path traversal (../) rejected
  - Writes to .git, node_modules, .env*, secrets rejected
  - Binary/secret file extensions rejected
  - All writes are text-only (UTF-8)
  - Returns a per-file manifest with sha256 before/after
  - Diff generation uses difflib (no subprocess)
"""

import difflib
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Safety constants ─────────────────────────────────────────────────────────

# Directory/file component names that must never be written to
_BLOCKED_COMPONENTS = frozenset([
    ".git", "node_modules", "secrets", ".secrets",
])

# Extensions that are binary, secret-material, or unsafe to write as text
_BLOCKED_EXTENSIONS = frozenset([
    ".key", ".pem", ".pfx", ".p12", ".cer", ".crt", ".der",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyo",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".webp", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".mp3", ".mp4", ".avi", ".mov",
])

# Valid write modes
_VALID_MODES = frozenset(["overwrite", "create", "append"])


# ─── Exceptions ───────────────────────────────────────────────────────────────

class WorkspacePathError(ValueError):
    """Raised when a file path violates workspace safety rules."""


class WorkspaceWriteError(RuntimeError):
    """Raised when workspace file writes fail; signals the task must be re-queued.

    already_recorded: if True the raising code already called
    storage.record_sdlc_task_error, so the BaseAgent poll loop must skip its own
    record call to avoid incrementing attempt_count twice.
    """
    def __init__(self, message: str, already_recorded: bool = False):
        super().__init__(message)
        self.already_recorded = already_recorded


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sha256_of_file(path: str) -> Optional[str]:
    """Return hex sha256 of file contents, or None if file does not exist."""
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_of_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_env_file(name: str) -> bool:
    """Return True for .env, .env.local, .env.production, etc."""
    return name == ".env" or name.startswith(".env.")


def _read_text(path: str) -> str:
    """Read file as UTF-8, return '' on error."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


# ─── Workspace resolver ───────────────────────────────────────────────────────

def resolve_workspace(
    project_id: str,
    epic_id: str,
    input_data: dict,
    output_base: str = "",
) -> str:
    """
    Determine the workspace root path.
    Priority:
      1. input_data["workspace_path"] if present — validated against allowed base
      2. output_base/projects/{project_id}/{epic_id}/workspace

    Allowed base for explicit paths:
      DEV_WORKSPACE_BASE env var  (if set)
      otherwise: output_base or OUTPUT_BASE_PATH env var

    Raises WorkspacePathError if an explicit workspace_path escapes the allowed base.
    """
    base = output_base or os.getenv("OUTPUT_BASE_PATH", "/app/outputs")
    if "workspace_path" in input_data:
        explicit = input_data["workspace_path"]
        # Resolve allowed base: prefer dedicated env var, fall back to output base
        allowed = os.path.realpath(os.getenv("DEV_WORKSPACE_BASE", "") or base)
        resolved = os.path.realpath(explicit)
        if resolved != allowed and not resolved.startswith(allowed + os.sep):
            raise WorkspacePathError(
                f"workspace_path {explicit!r} resolves to {resolved!r} "
                f"which is outside the allowed base {allowed!r}"
            )
        return resolved
    return os.path.join(base, "projects", project_id, epic_id, "workspace")


# ─── WorkspaceWriter ─────────────────────────────────────────────────────────

class WorkspaceWriter:
    """
    Writes text files into a controlled workspace directory.

    All writes are sandboxed: the resolved absolute path must remain under
    self.root. Any path that tries to escape is rejected immediately.
    """

    def __init__(self, workspace_root: str):
        # Resolve symlinks so realpath comparisons are reliable
        self.root = os.path.realpath(workspace_root)

    def validate_path(self, rel_path: str) -> str:
        """
        Validate a relative file path and return its absolute path.
        Raises WorkspacePathError on any safety violation.
        """
        if not rel_path or not rel_path.strip():
            raise WorkspacePathError("empty path not allowed")

        if os.path.isabs(rel_path):
            raise WorkspacePathError(
                f"absolute paths are not allowed (received {rel_path!r})"
            )

        # Normalise — os.path.normpath resolves .. components
        norm = os.path.normpath(rel_path)
        if norm.startswith(".."):
            raise WorkspacePathError(
                f"path traversal not allowed: {rel_path!r}"
            )

        # Inspect every path component
        parts = norm.replace("\\", "/").split("/")
        for part in parts:
            if not part or part == ".":
                continue
            if part in _BLOCKED_COMPONENTS:
                raise WorkspacePathError(
                    f"writes to '{part}' are not allowed: {rel_path!r}"
                )
            if _is_env_file(part):
                raise WorkspacePathError(
                    f"writes to env files are not allowed: {rel_path!r}"
                )

        # Check file extension
        _, ext = os.path.splitext(norm)
        if ext.lower() in _BLOCKED_EXTENSIONS:
            raise WorkspacePathError(
                f"writes to {ext!r} files are not allowed: {rel_path!r}"
            )

        # Build absolute path and confirm it remains inside workspace root
        abs_path = os.path.realpath(os.path.join(self.root, norm))
        if abs_path != self.root and not abs_path.startswith(self.root + os.sep):
            raise WorkspacePathError(
                f"resolved path escapes workspace root: {rel_path!r}"
            )

        return abs_path

    def write_file(
        self,
        rel_path: str,
        content: str,
        mode: str = "overwrite",
    ) -> dict:
        """
        Write a single file.

        mode:
          "overwrite" — create or replace the file
          "create"    — create only; error if file already exists
          "append"    — append to existing file (create if absent)

        Returns a result dict with path, action, bytes_written, sha256_before, sha256_after, error.
        """
        if mode not in _VALID_MODES:
            return _make_result(rel_path, "error", 0, None, None,
                                f"unknown mode {mode!r} — must be one of {sorted(_VALID_MODES)}")

        try:
            abs_path = self.validate_path(rel_path)
        except WorkspacePathError as exc:
            return _make_result(rel_path, "error", 0, None, None, str(exc))

        sha_before = _sha256_of_file(abs_path)
        exists = os.path.isfile(abs_path)

        if mode == "create" and exists:
            return _make_result(rel_path, "skipped", 0, sha_before, sha_before,
                                "file already exists (mode=create)")

        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            if mode == "append" and exists:
                with open(abs_path, "a", encoding="utf-8") as fh:
                    fh.write(content)
                action = "appended"
            else:
                with open(abs_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                action = "written"
        except OSError as exc:
            return _make_result(rel_path, "error", 0, sha_before, None, str(exc))

        sha_after = _sha256_of_file(abs_path)
        return _make_result(rel_path, action,
                            len(content.encode("utf-8")),
                            sha_before, sha_after, None)

    def write_files(self, files: list) -> list:
        """
        Write multiple files.
        Each entry: {"path": str, "content": str, "mode": str (optional, default "overwrite")}
        Returns list of result dicts.
        """
        results = []
        for f in files:
            path    = str(f.get("path", ""))
            content = str(f.get("content", ""))
            mode    = str(f.get("mode", "overwrite"))
            results.append(self.write_file(path, content, mode))
        return results


def _make_result(
    path: str,
    action: str,
    bytes_written: int,
    sha256_before: Optional[str],
    sha256_after: Optional[str],
    error: Optional[str],
) -> dict:
    return {
        "path": path,
        "action": action,
        "bytes_written": bytes_written,
        "sha256_before": sha256_before,
        "sha256_after": sha256_after,
        "error": error,
    }


# ─── Manifest builder ─────────────────────────────────────────────────────────

def build_manifest(
    workspace_root: str,
    task_id: str,
    results: list,
) -> dict:
    failed = [r for r in results if r["action"] == "error"]
    written = [r for r in results if r["action"] in ("written", "appended", "created")]
    return {
        "workspace_root": workspace_root,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "files": results,
        "total_files": len(results),
        "written_count": len(written),
        "failed_count": len(failed),
        "skipped_count": len(results) - len(written) - len(failed),
    }


# ─── Diff generator ───────────────────────────────────────────────────────────

def generate_diff(
    before: dict,
    after: dict,
) -> str:
    """
    Generate a unified diff string from before/after file content maps.
    Keys are relative paths; values are file contents (str).
    """
    lines = []
    for path in sorted(set(before) | set(after)):
        a_lines = (before.get(path) or "").splitlines(keepends=True)
        b_lines = (after.get(path) or "").splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            a_lines, b_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        ))
        lines.extend(diff)
    return "".join(lines)


# ─── LLM output parser ────────────────────────────────────────────────────────

def parse_code_output(content: str) -> list:
    """
    Parse LLM output into a list of {"path": str, "content": str, "mode": str}.

    Accepts two formats:
    1. JSON:       {"files": [{"path": "...", "content": "...", "mode": "overwrite"}]}
    2. code_multi: === FILE: relative/path.ext ===\\n<content>\\n=== FILE: ...
    """
    stripped = content.strip()

    # Strip outer markdown code fence if present
    fence_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', stripped)
    json_str = fence_match.group(1).strip() if fence_match else stripped

    # Try JSON format first
    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and "files" in data:
            files = data["files"]
            if isinstance(files, list):
                result = []
                for f in files:
                    if isinstance(f, dict) and "path" in f and "content" in f:
                        result.append({
                            "path": str(f["path"]),
                            "content": str(f["content"]),
                            "mode": str(f.get("mode", "overwrite")),
                        })
                if result:
                    return result
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fall back to code_multi format
    marker_re = re.compile(r'^=== FILE: (.+?) ===$', re.MULTILINE)
    matches = list(marker_re.finditer(stripped))
    if not matches:
        return []

    result = []
    for i, match in enumerate(matches):
        path = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stripped)
        file_content = stripped[start:end].strip("\n")
        result.append({"path": path, "content": file_content, "mode": "overwrite"})

    return result
