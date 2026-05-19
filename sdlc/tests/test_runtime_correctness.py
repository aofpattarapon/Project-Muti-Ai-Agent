"""
Runtime correctness tests for SDLC storage layer.

Tests cover the behaviors Codex flagged as critical:
- dependency gate: waiting_approval blocks downstream, approved unblocks
- claim_sdlc_task: atomic, only first caller wins
- record_sdlc_task_error: persists attempt_count and last_error correctly
- web/Discord approval path: update_sdlc_task_status sets 'approved' in DB

Run: python3 -m pytest sdlc/tests/test_runtime_correctness.py -v
  or: python3 sdlc/tests/test_runtime_correctness.py
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, SdlcTask


def _task(storage: Storage, task_id: str, status: str, depends_on: str = "") -> SdlcTask:
    now = datetime.utcnow().isoformat()
    t = SdlcTask(
        id=task_id, project_id="proj-1", epic_id="proj-1-E001", task_number=1,
        role="ba", task_type="brd", title=f"Task {task_id}", description="",
        output_file="out.md", output_format="markdown", depends_on=depends_on,
        status=status, input_data="{}", output_data="{}",
        approval_msg_id="", revision_count=0, notes="",
        created_at=now, updated_at=now,
    )
    storage.create_sdlc_task(t)
    return t


class TestDependencyGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_waiting_approval_blocks_downstream(self):
        """Upstream in waiting_approval must block downstream from appearing in pending list."""
        upstream = _task(self.storage, "T-001", "waiting_approval")
        _task(self.storage, "T-002", "pending", depends_on="T-001")

        pending = self.storage.list_pending_sdlc_tasks("ba")
        ids = [t.id for t in pending]
        self.assertNotIn("T-002", ids, "Downstream must be blocked while upstream is waiting_approval")

    def test_approved_unblocks_downstream(self):
        """Upstream approved must let downstream appear in pending list."""
        _task(self.storage, "T-001", "approved")
        _task(self.storage, "T-002", "pending", depends_on="T-001")

        pending = self.storage.list_pending_sdlc_tasks("ba")
        ids = [t.id for t in pending]
        self.assertIn("T-002", ids, "Downstream must be unblocked once upstream is approved")

    def test_completed_unblocks_downstream(self):
        """Upstream completed (auto-approve mode) must also unblock downstream."""
        _task(self.storage, "T-001", "completed")
        _task(self.storage, "T-002", "pending", depends_on="T-001")

        pending = self.storage.list_pending_sdlc_tasks("ba")
        ids = [t.id for t in pending]
        self.assertIn("T-002", ids)

    def test_multiple_deps_all_must_pass(self):
        """Both upstream tasks must be approved/completed for downstream to unlock."""
        _task(self.storage, "T-001", "approved")
        _task(self.storage, "T-002", "waiting_approval")
        _task(self.storage, "T-003", "pending", depends_on="T-001,T-002")

        pending = self.storage.list_pending_sdlc_tasks("ba")
        self.assertEqual([], [t.id for t in pending if t.id == "T-003"])

        # Now approve T-002
        self.storage.update_sdlc_task_status("T-002", "approved")
        pending = self.storage.list_pending_sdlc_tasks("ba")
        ids = [t.id for t in pending]
        self.assertIn("T-003", ids)


class TestClaimSdlcTask(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_first_claim_wins(self):
        _task(self.storage, "T-001", "pending")
        result = self.storage.claim_sdlc_task("T-001", "ba")
        self.assertTrue(result, "First claim must succeed")

    def test_second_claim_loses(self):
        _task(self.storage, "T-001", "pending")
        self.storage.claim_sdlc_task("T-001", "ba")
        result = self.storage.claim_sdlc_task("T-001", "ba")
        self.assertFalse(result, "Second claim on same task must fail")

    def test_claim_sets_status_in_progress(self):
        _task(self.storage, "T-001", "pending")
        self.storage.claim_sdlc_task("T-001", "ba")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "in_progress")

    def test_claim_sets_claimed_by(self):
        _task(self.storage, "T-001", "pending")
        self.storage.claim_sdlc_task("T-001", "ba")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.claimed_by, "ba")

    def test_claim_not_pending_fails(self):
        _task(self.storage, "T-001", "in_progress")
        result = self.storage.claim_sdlc_task("T-001", "ba")
        self.assertFalse(result, "Cannot claim a task that is not pending")


class TestRecordSdlcTaskError(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_requeue_sets_pending_and_persists_count(self):
        _task(self.storage, "T-001", "in_progress")
        self.storage.record_sdlc_task_error("T-001", "timeout", attempt_count=1, requeue=True)
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "pending")
        self.assertEqual(t.attempt_count, 1)
        self.assertEqual(t.last_error, "timeout")

    def test_no_requeue_sets_failed(self):
        _task(self.storage, "T-001", "in_progress")
        self.storage.record_sdlc_task_error("T-001", "max retries", attempt_count=3, requeue=False)
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "failed")
        self.assertEqual(t.attempt_count, 3)

    def test_attempt_count_survives_restart(self):
        """Simulate restart: re-open DB and verify attempt_count is still there."""
        _task(self.storage, "T-001", "in_progress")
        self.storage.record_sdlc_task_error("T-001", "err", attempt_count=2, requeue=True)

        fresh_storage = Storage(db_path=self._tmp.name)
        t = fresh_storage.get_sdlc_task("T-001")
        self.assertEqual(t.attempt_count, 2, "attempt_count must persist across restarts")

    def test_failed_task_not_in_pending_list(self):
        _task(self.storage, "T-001", "in_progress")
        self.storage.record_sdlc_task_error("T-001", "fatal", attempt_count=3, requeue=False)
        pending = self.storage.list_pending_sdlc_tasks("ba")
        self.assertNotIn("T-001", [t.id for t in pending])


class TestApprovalStatusUpdate(unittest.TestCase):
    """Verify that the approval path (Discord + Web) writes 'approved' to DB."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_update_status_to_approved_unblocks_downstream(self):
        _task(self.storage, "T-001", "waiting_approval")
        _task(self.storage, "T-002", "pending", depends_on="T-001")

        # Simulate what _handle_sdlc_decision and _execute_web_decision now do:
        self.storage.update_sdlc_task_status("T-001", "approved", "Approved by test")

        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "approved")

        pending = self.storage.list_pending_sdlc_tasks("ba")
        self.assertIn("T-002", [t.id for t in pending])

    def test_update_status_preserves_notes(self):
        _task(self.storage, "T-001", "waiting_approval")
        self.storage.update_sdlc_task_status("T-001", "approved", "Approved by web-ui")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.notes, "Approved by web-ui")


if __name__ == "__main__":
    unittest.main(verbosity=2)
