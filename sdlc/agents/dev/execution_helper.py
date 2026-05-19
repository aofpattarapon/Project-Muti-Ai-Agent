"""
DEVExecutionHelper — workspace writes and artifact generation for DEV tasks.
Discord-free so it can be unit-tested without discord.py installed.
"""

import json
import logging
import os
from typing import Optional

from shared.storage import Storage, SdlcTask
from shared.dev_workspace import (
    WorkspaceWriteError,
    WorkspaceWriter,
    _read_text,
    build_manifest,
    generate_diff,
    parse_code_output,
    resolve_workspace,
)

logger = logging.getLogger(__name__)

# Only these task types trigger workspace writes — docs/structure tasks are excluded.
_WORKSPACE_TASK_TYPES = frozenset(["backend_code", "frontend_code", "unit_tests"])


class DEVExecutionHelper:
    """
    Encapsulates DEV workspace write logic: parse → write → diff → manifest.
    Never executes commands from LLM output — only writes text files.
    """

    def __init__(self, storage: Storage, output_base: str = ""):
        self.storage = storage
        self.output_base = output_base or os.getenv("OUTPUT_BASE_PATH", "/app/outputs")

    # ─── Workspace resolution ──────────────────────────────────────────────────

    def get_workspace_path(self, task: SdlcTask, input_data: dict) -> str:
        """Return the workspace root path for this task."""
        return resolve_workspace(
            project_id=task.project_id,
            epic_id=task.epic_id,
            input_data=input_data,
            output_base=self.output_base,
        )

    # ─── Write ────────────────────────────────────────────────────────────────

    def apply_workspace_writes(
        self, task: SdlcTask, content: str, input_data: dict
    ) -> dict:
        """
        Parse LLM output, write files to workspace, return manifest dict.

        Accepts code_multi (=== FILE: path ===) or JSON {"files": [...]} format.
        Returns a build_manifest dict extended with a "diff_patch" key.
        Never executes any commands — purely file writes.
        """
        workspace = self.get_workspace_path(task, input_data)
        writer = WorkspaceWriter(workspace)

        files_to_write = parse_code_output(content)
        if not files_to_write:
            logger.info(f"[dev] no file markers found in LLM output for task {task.id}")
            return build_manifest(workspace, task.id, [])

        # Snapshot before-state for diff generation
        before: dict = {}
        for f in files_to_write:
            rel_path = f.get("path", "")
            if not rel_path:
                continue
            try:
                abs_path = writer.validate_path(rel_path)
                before[rel_path] = _read_text(abs_path)
            except Exception:
                before[rel_path] = ""

        results = writer.write_files(files_to_write)

        # Snapshot after-state
        after: dict = {}
        for f in files_to_write:
            rel_path = f.get("path", "")
            if not rel_path:
                continue
            try:
                abs_path = writer.validate_path(rel_path)
                after[rel_path] = _read_text(abs_path)
            except Exception:
                after[rel_path] = ""

        manifest = build_manifest(workspace, task.id, results)
        manifest["diff_patch"] = generate_diff(before, after)
        return manifest

    # ─── Artifact saving ──────────────────────────────────────────────────────

    def check_workspace_results(self, task: SdlcTask, manifest: dict) -> None:
        """
        Raise WorkspaceWriteError if any files failed to write.
        Caller must already have persisted the manifest for audit before calling this.
        Records the error in storage so the task is re-queued, not silently approved.
        """
        failed_count = manifest.get("failed_count", 0)
        if failed_count <= 0:
            return
        written_count = manifest.get("written_count", 0)
        err_msg = (
            f"workspace write: {failed_count} file(s) failed "
            f"({written_count} succeeded) — see dev_workspace_manifest.json"
        )
        fresh = self.storage.get_sdlc_task(task.id)
        attempt = (fresh.attempt_count if fresh else 0) + 1
        self.storage.record_sdlc_task_error(task.id, err_msg, attempt, requeue=True)
        raise WorkspaceWriteError(err_msg, already_recorded=True)

    def save_artifacts(
        self, task: SdlcTask, output_dir: str, manifest: dict
    ) -> None:
        """Write dev_workspace_manifest.json and dev_workspace_diff.patch to output_dir."""
        try:
            os.makedirs(output_dir, exist_ok=True)

            diff_patch = manifest.pop("diff_patch", "")

            manifest_path = os.path.join(output_dir, "dev_workspace_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2, ensure_ascii=False)

            if diff_patch:
                patch_path = os.path.join(output_dir, "dev_workspace_diff.patch")
                with open(patch_path, "w", encoding="utf-8") as fh:
                    fh.write(diff_patch)

        except Exception as exc:
            logger.warning(f"[dev] could not save workspace artifacts for {task.id}: {exc}")
