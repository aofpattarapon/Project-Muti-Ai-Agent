"""
artifact_collector — build artifact list for web bridge task_completed payloads.
Discord-free module; importable in tests without discord.py.
"""

import os
from typing import Optional

_SECONDARY_ARTIFACT_TYPES = {
    "deployment_readiness_report.md":   "deployment_report",
    "devops_execution_result.json":     "devops_execution_result",
    "release_notes.md":                 "release_notes",
    "qa_execution_result.json":         "qa_execution_result",
    "test_execution_result.json":       "test_execution_result",
    "workspace_manifest.json":          "workspace_manifest",
    "diff.patch":                       "workspace_diff",
    "artifact_validation_report.json":  "validation_report",
}


def collect_artifacts(
    output_dir: str,
    saved_path: str,
    task,
    attempt_started_at: Optional[float] = None,
) -> list:
    """Build artifact list for web bridge: main output + secondary files in output_dir.

    When attempt_started_at is provided (wall-clock time.time()), secondary files are only
    included if mtime >= attempt_started_at. This prevents stale files left by a prior failed
    attempt from being treated as produced by the current attempt.

    The main output_file (saved_path) is always included — it was just written this attempt.
    """
    artifacts = []
    if saved_path:
        artifacts.append({"type": "output_file", "path": task.output_file, "ref": saved_path})
    for fname, atype in _SECONDARY_ARTIFACT_TYPES.items():
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath):
            if attempt_started_at is None or os.path.getmtime(fpath) >= attempt_started_at:
                artifacts.append({"type": atype, "path": fname, "ref": fpath})
    return artifacts
