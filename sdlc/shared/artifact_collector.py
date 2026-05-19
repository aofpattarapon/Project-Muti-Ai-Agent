"""
artifact_collector — build artifact list for web bridge task_completed payloads.
Discord-free module; importable in tests without discord.py.
"""

import os

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


def collect_artifacts(output_dir: str, saved_path: str, task) -> list:
    """Build artifact list for web bridge: main output + known secondary files in output_dir."""
    artifacts = []
    if saved_path:
        artifacts.append({"type": "output_file", "path": task.output_file, "ref": saved_path})
    for fname, atype in _SECONDARY_ARTIFACT_TYPES.items():
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath):
            artifacts.append({"type": atype, "path": fname, "ref": fpath})
    return artifacts
