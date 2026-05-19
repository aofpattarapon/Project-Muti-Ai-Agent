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


class TestClaimRoleCheck(unittest.TestCase):
    """claim_sdlc_task must reject if role doesn't match."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_role_mismatch_returns_false(self):
        _task(self.storage, "T-001", "pending")  # role="ba"
        result = self.storage.claim_sdlc_task("T-001", "dev")  # wrong role
        self.assertFalse(result, "Claim by wrong role must fail")

    def test_role_mismatch_leaves_status_pending(self):
        _task(self.storage, "T-001", "pending")
        self.storage.claim_sdlc_task("T-001", "dev")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "pending", "Status must stay pending after wrong-role claim")

    def test_correct_role_still_wins(self):
        _task(self.storage, "T-001", "pending")
        self.storage.claim_sdlc_task("T-001", "dev")  # wrong role — fails
        result = self.storage.claim_sdlc_task("T-001", "ba")  # correct role
        self.assertTrue(result)
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.claimed_by, "ba")


class TestStaleRecovery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def _claim_and_age(self, task_id: str, minutes_ago: int, attempt_count: int = 0):
        """Helper: create an in_progress task with a backdated claimed_at."""
        from datetime import timedelta
        old_ts = (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat()
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id=task_id, project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title=f"Task {task_id}", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="in_progress", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=attempt_count, claimed_at=old_ts, claimed_by="ba",
        )
        self.storage.create_sdlc_task(t)

    def test_stale_task_requeued(self):
        self._claim_and_age("T-001", minutes_ago=90)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=60)
        self.assertEqual(recovered, [("T-001", "pending")])
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "pending")
        self.assertEqual(t.claimed_at, "")
        self.assertEqual(t.claimed_by, "")

    def test_fresh_task_not_recovered(self):
        self._claim_and_age("T-001", minutes_ago=10)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=60)
        self.assertEqual(recovered, [])
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "in_progress")

    def test_stale_with_max_retries_fails_permanently(self):
        self._claim_and_age("T-001", minutes_ago=90, attempt_count=2)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=60, max_retries=2)
        self.assertEqual(recovered, [("T-001", "failed")])
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "failed")

    def test_no_claimed_at_skipped(self):
        """Tasks without claimed_at (pre-dating tracking) must not be touched."""
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="T-OLD", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="Old Task", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="in_progress", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=0, claimed_at="", claimed_by="",  # empty = pre-tracking
        )
        self.storage.create_sdlc_task(t)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=0)
        self.assertEqual(recovered, [], "Pre-tracking task must be skipped")

    def test_waiting_approval_not_recovered(self):
        now = datetime.utcnow().isoformat()
        old_ts = "2020-01-01T00:00:00"
        t = SdlcTask(
            id="T-WA", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="WA Task", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="waiting_approval", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=0, claimed_at=old_ts, claimed_by="ba",
        )
        self.storage.create_sdlc_task(t)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=0)
        self.assertEqual(recovered, [], "waiting_approval must never be recovered")

    def test_approved_not_recovered(self):
        now = datetime.utcnow().isoformat()
        old_ts = "2020-01-01T00:00:00"
        t = SdlcTask(
            id="T-AP", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="Approved Task", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="approved", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=0, claimed_at=old_ts, claimed_by="ba",
        )
        self.storage.create_sdlc_task(t)
        recovered = self.storage.recover_stale_sdlc_tasks("ba", max_age_minutes=0)
        self.assertEqual(recovered, [])

    def test_different_role_not_recovered(self):
        self._claim_and_age("T-DEV", minutes_ago=90)  # role="ba"
        recovered = self.storage.recover_stale_sdlc_tasks("dev", max_age_minutes=60)
        self.assertEqual(recovered, [], "Recovery must only affect tasks for the given role")


class TestManualRetry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.storage = Storage(db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_manual_retry_sets_pending(self):
        _task(self.storage, "T-001", "failed")
        self.storage.manual_retry_sdlc_task("T-001", "Manual retry by off")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.status, "pending")

    def test_manual_retry_clears_claim_fields(self):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="T-001", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="T", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="failed", input_data="{}", output_data="{}",
            approval_msg_id="msg-123", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=2, claimed_at="2024-01-01T00:00:00", claimed_by="ba",
        )
        self.storage.create_sdlc_task(t)
        self.storage.manual_retry_sdlc_task("T-001", "Manual retry by off")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.claimed_at, "")
        self.assertEqual(t.claimed_by, "")
        self.assertEqual(t.approval_msg_id, "")

    def test_manual_retry_preserves_attempt_count(self):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="T-001", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="T", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="failed", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=3, claimed_at="", claimed_by="",
        )
        self.storage.create_sdlc_task(t)
        self.storage.manual_retry_sdlc_task("T-001", "Manual retry by off")
        t = self.storage.get_sdlc_task("T-001")
        self.assertEqual(t.attempt_count, 3, "attempt_count must be preserved for audit")

    def test_manual_retry_notes_include_attempt_count(self):
        now = datetime.utcnow().isoformat()
        t = SdlcTask(
            id="T-001", project_id="proj-1", epic_id="proj-1-E001", task_number=1,
            role="ba", task_type="brd", title="T", description="",
            output_file="out.md", output_format="markdown", depends_on="",
            status="failed", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=2, claimed_at="", claimed_by="",
        )
        self.storage.create_sdlc_task(t)
        self.storage.manual_retry_sdlc_task("T-001", "Manual retry by off")
        t = self.storage.get_sdlc_task("T-001")
        self.assertIn("attempt_count=2", t.notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
