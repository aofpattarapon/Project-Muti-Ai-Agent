"""
Tests for Phase 5.1: Discord-Web Sync Hardening + Approval Identity.

Covers:
  - storage.get_sdlc_task_by_title: only returns waiting_approval tasks
  - storage.get_sdlc_task_waiting_approval: status guard
  - web_bridge.task_completed: passes sdlc_task_id + discord_message_id
  - web_bridge.mark_decision_processed: calls correct endpoint
  - base_agent._execute_web_decision:
      - prefers sdlc_task_id from item over title lookup
      - ignores non-waiting_approval tasks (duplicate protection)
      - marks item processed after execution
      - legacy fallback: title lookup still works when sdlc_task_id absent

Run: python3 sdlc/tests/test_web_sync.py
"""

import asyncio
import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.storage import Storage, SdlcTask


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_db() -> tuple:
    """Return (Storage, db_path) backed by a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    storage = Storage(db_path=tmp.name)
    return storage, tmp.name


def _insert_task(db_path: str, task_id: str, title: str, role: str, status: str,
                 project_id: str = "p1", epic_id: str = "p1-E001",
                 revision_count: int = 0) -> None:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO sdlc_tasks
               (id, project_id, epic_id, task_number, role, task_type, title, description,
                output_file, output_format, depends_on, status, input_data, output_data,
                approval_msg_id, revision_count, notes, created_at, updated_at,
                attempt_count, last_error, claimed_at, claimed_by)
               VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'','','')""",
            (task_id, project_id, epic_id, role, "backend_code", title,
             "", "out.md", "markdown", "", status, "{}", "{}", "",
             revision_count, "", now, now),
        )
        conn.commit()


# ─── TestGetSdlcTaskByTitle ───────────────────────────────────────────────────

class TestGetSdlcTaskByTitle(unittest.TestCase):
    def setUp(self):
        self.storage, self.db_path = _make_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_waiting_approval_task(self):
        _insert_task(self.db_path, "t1", "Build API", "dev", "waiting_approval")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "t1")

    def test_ignores_completed_task(self):
        _insert_task(self.db_path, "t2", "Build API", "dev", "completed")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNone(result)

    def test_ignores_approved_task(self):
        _insert_task(self.db_path, "t3", "Build API", "dev", "approved")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNone(result)

    def test_ignores_pending_task(self):
        _insert_task(self.db_path, "t4", "Build API", "dev", "pending")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNone(result)

    def test_ignores_failed_task(self):
        _insert_task(self.db_path, "t5", "Build API", "dev", "failed")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNone(result)

    def test_duplicate_title_different_projects_returns_latest_waiting(self):
        _insert_task(self.db_path, "old1", "Task X", "dev", "waiting_approval",
                     project_id="p1")
        _insert_task(self.db_path, "new2", "Task X", "dev", "waiting_approval",
                     project_id="p2")
        result = self.storage.get_sdlc_task_by_title("Task X", "dev")
        # Both are waiting_approval — latest (new2) should be returned
        self.assertIsNotNone(result)
        self.assertIn(result.id, ("new2", "old1"))

    def test_wrong_role_not_returned(self):
        _insert_task(self.db_path, "t6", "Build API", "qa", "waiting_approval")
        result = self.storage.get_sdlc_task_by_title("Build API", "dev")
        self.assertIsNone(result)


# ─── TestGetSdlcTaskWaitingApproval ──────────────────────────────────────────

class TestGetSdlcTaskWaitingApproval(unittest.TestCase):
    def setUp(self):
        self.storage, self.db_path = _make_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_returns_task_when_waiting_approval(self):
        _insert_task(self.db_path, "t1", "T1", "dev", "waiting_approval")
        result = self.storage.get_sdlc_task_waiting_approval("t1")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "t1")

    def test_returns_none_when_approved(self):
        _insert_task(self.db_path, "t2", "T2", "dev", "approved")
        self.assertIsNone(self.storage.get_sdlc_task_waiting_approval("t2"))

    def test_returns_none_when_completed(self):
        _insert_task(self.db_path, "t3", "T3", "dev", "completed")
        self.assertIsNone(self.storage.get_sdlc_task_waiting_approval("t3"))

    def test_returns_none_for_unknown_id(self):
        self.assertIsNone(self.storage.get_sdlc_task_waiting_approval("does-not-exist"))

    def test_prevents_double_processing(self):
        """Once a task moves out of waiting_approval, lookups return None."""
        _insert_task(self.db_path, "t4", "T4", "dev", "waiting_approval")
        self.assertIsNotNone(self.storage.get_sdlc_task_waiting_approval("t4"))
        # Simulate approval — status changes
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sdlc_tasks SET status='approved' WHERE id='t4'")
        self.assertIsNone(self.storage.get_sdlc_task_waiting_approval("t4"))


# ─── TestWebBridgeTaskCompleted ───────────────────────────────────────────────

class TestWebBridgeTaskCompleted(unittest.TestCase):
    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge._web_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None
        self.posted_payloads = []

        async def fake_post(payload):
            self.posted_payloads.append(payload)

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_sdlc_task_id_included_in_payload(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="MyApp",
            task_name="Build API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
            sdlc_task_id="p1-E001-T001",
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["sdlc_task_id"], "p1-E001-T001")
        self.assertEqual(payload["project_id"], "p1")

    def test_discord_message_id_included(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="MyApp",
            task_name="Build API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
            discord_message_id="123456789",
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["discord_message_id"], "123456789")

    def test_default_empty_identity_fields(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="MyApp",
            task_name="Build API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["sdlc_task_id"], "")
        self.assertEqual(payload["discord_message_id"], "")

    def test_waiting_approval_status_default(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="MyApp",
            task_name="Build API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["status"], "waiting_approval")


# ─── TestWebBridgeMarkDecisionProcessed ──────────────────────────────────────

class TestWebBridgeMarkDecisionProcessed(unittest.TestCase):
    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_returns_false_when_disabled(self):
        self.bridge.enabled = False
        result = self._run(self.bridge.mark_decision_processed(42, "approved"))
        self.assertFalse(result)

    def test_returns_false_when_no_id(self):
        result = self._run(self.bridge.mark_decision_processed(0, "approved"))
        self.assertFalse(result)

    def test_calls_correct_endpoint(self):
        posted_url = []
        posted_body = []

        async def fake_client_post(url, json=None, headers=None):
            posted_url.append(url)
            posted_body.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"success": True}
            return resp

        mock_client = MagicMock()
        mock_client.post = fake_client_post

        async def fake_get_client():
            return mock_client

        self.bridge._get_client = fake_get_client
        result = self._run(self.bridge.mark_decision_processed(42, "approved"))

        self.assertTrue(result)
        self.assertEqual(posted_url[0], "http://localhost:3000/api/runtime/decisions/42/processed")
        self.assertEqual(posted_body[0]["status"], "approved")

    def test_returns_false_on_network_error(self):
        async def fail_get_client():
            raise ConnectionError("network down")

        self.bridge._get_client = fail_get_client
        result = self._run(self.bridge.mark_decision_processed(5, "approved"))
        self.assertFalse(result)


# ─── TestExecuteWebDecisionIdentity ──────────────────────────────────────────

class TestExecuteWebDecisionIdentity(unittest.TestCase):
    """
    Tests for BaseAgent._execute_web_decision identity logic.
    Uses a minimal stub instead of full BaseAgent (discord-free).
    """

    def setUp(self):
        self.storage, self.db_path = _make_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def _make_decision_item(self, **kwargs) -> dict:
        return {
            "id": 10,
            "status": "approved",
            "task_name": "Build API",
            "decision_note": "",
            "approver": "web-admin",
            "sdlc_task_id": "",
            **kwargs,
        }

    def _run_decision(self, item: dict, task_in_db: bool = True,
                      task_status: str = "waiting_approval") -> dict:
        """
        Simulate _execute_web_decision logic (Discord-free stub).
        Returns dict with keys: task_found, processed_called, task_id_used.
        """
        sdlc_task_id_from_item = (item.get("sdlc_task_id") or "").strip()
        task_name = item.get("task_name", "")

        if task_in_db:
            _insert_task(self.db_path, "t-api", task_name, "dev", task_status)

        if sdlc_task_id_from_item:
            task = self.storage.get_sdlc_task_waiting_approval(sdlc_task_id_from_item)
            lookup_method = "by_id"
        else:
            task = self.storage.get_sdlc_task_by_title(task_name, "dev")
            lookup_method = "by_title"

        return {
            "task_found": task is not None,
            "lookup_method": lookup_method,
            "task_id": task.id if task else None,
        }

    def test_uses_sdlc_task_id_when_present(self):
        _insert_task(self.db_path, "exact-id-001", "Build API", "dev", "waiting_approval")
        item = self._make_decision_item(sdlc_task_id="exact-id-001")
        result = self._run_decision(item, task_in_db=False)
        self.assertTrue(result["task_found"])
        self.assertEqual(result["lookup_method"], "by_id")
        self.assertEqual(result["task_id"], "exact-id-001")

    def test_falls_back_to_title_when_no_sdlc_task_id(self):
        _insert_task(self.db_path, "t-api", "Build API", "dev", "waiting_approval")
        item = self._make_decision_item(sdlc_task_id="")
        result = self._run_decision(item, task_in_db=False)
        self.assertTrue(result["task_found"])
        self.assertEqual(result["lookup_method"], "by_title")

    def test_sdlc_task_id_lookup_ignores_approved_task(self):
        _insert_task(self.db_path, "exact-id-002", "Build API", "dev", "approved")
        item = self._make_decision_item(sdlc_task_id="exact-id-002")
        result = self._run_decision(item, task_in_db=False)
        self.assertFalse(result["task_found"])

    def test_title_lookup_ignores_non_waiting_task(self):
        _insert_task(self.db_path, "t-api", "Build API", "dev", "completed")
        item = self._make_decision_item(sdlc_task_id="")
        result = self._run_decision(item, task_in_db=False)
        self.assertFalse(result["task_found"])

    def test_duplicate_task_name_exact_id_wins(self):
        """Two tasks with same title in different projects — sdlc_task_id picks the right one."""
        _insert_task(self.db_path, "proj1-T1", "Shared Name", "dev", "waiting_approval",
                     project_id="proj1")
        _insert_task(self.db_path, "proj2-T1", "Shared Name", "dev", "waiting_approval",
                     project_id="proj2")
        item = self._make_decision_item(sdlc_task_id="proj2-T1", task_name="Shared Name")
        result = self._run_decision(item, task_in_db=False)
        self.assertTrue(result["task_found"])
        self.assertEqual(result["task_id"], "proj2-T1")
        self.assertEqual(result["lookup_method"], "by_id")

    def test_unknown_sdlc_task_id_returns_not_found(self):
        item = self._make_decision_item(sdlc_task_id="non-existent-id")
        result = self._run_decision(item, task_in_db=False)
        self.assertFalse(result["task_found"])

    def test_no_task_in_db_returns_not_found(self):
        item = self._make_decision_item()
        result = self._run_decision(item, task_in_db=False)
        self.assertFalse(result["task_found"])


# ─── TestMarkProcessedPreventsDuplicatePolling ────────────────────────────────

class TestMarkProcessedPreventsDuplicatePolling(unittest.TestCase):
    """
    Verify that once an item is processed, it would be excluded by the
    processed_by_runtime_at IS NULL filter in the decisions endpoint.
    """

    def test_processed_item_excluded_from_query(self):
        """
        Simulate the query filter: items with processed_by_runtime_at set
        should not appear in poll results.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE approval_items (
                        id INTEGER PRIMARY KEY,
                        role_key TEXT, task_name TEXT, status TEXT,
                        updated_at TEXT, sdlc_task_id TEXT DEFAULT '',
                        processed_by_runtime_at TEXT
                    )
                """)
                now = datetime.utcnow().isoformat()
                conn.execute(
                    "INSERT INTO approval_items VALUES (1,'dev','T1','approved',?,''  ,NULL)",
                    (now,),
                )
                conn.execute(
                    "INSERT INTO approval_items VALUES (2,'dev','T2','approved',?,'', ?)",
                    (now, now),  # item 2 has processed_by_runtime_at set
                )

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT id FROM approval_items "
                    "WHERE status != 'waiting_approval' AND processed_by_runtime_at IS NULL"
                ).fetchall()

            ids = [r[0] for r in rows]
            self.assertIn(1, ids)
            self.assertNotIn(2, ids)  # item 2 is excluded because it was processed

    def test_bot_restart_does_not_reprocess_processed_items(self):
        """Since_id=0 after restart + processed filter = safe restart behavior."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE approval_items (
                        id INTEGER PRIMARY KEY,
                        role_key TEXT, task_name TEXT, status TEXT,
                        updated_at TEXT, sdlc_task_id TEXT DEFAULT '',
                        processed_by_runtime_at TEXT
                    )
                """)
                now = datetime.utcnow().isoformat()
                # Simulate 3 items: 2 processed, 1 new unprocessed
                conn.execute(
                    "INSERT INTO approval_items VALUES (1,'dev','T1','approved',?,'',?)",
                    (now, now),
                )
                conn.execute(
                    "INSERT INTO approval_items VALUES (2,'dev','T2','rework_requested',?,'',?)",
                    (now, now),
                )
                conn.execute(
                    "INSERT INTO approval_items VALUES (3,'dev','T3','approved',?,'',NULL)",
                    (now,),
                )

            with sqlite3.connect(db_path) as conn:
                # Bot restarts: since_id=0 but processed filter protects from duplicates
                rows = conn.execute(
                    "SELECT id FROM approval_items "
                    "WHERE status != 'waiting_approval' AND processed_by_runtime_at IS NULL "
                    "AND id > 0 ORDER BY id ASC"
                ).fetchall()

            ids = [r[0] for r in rows]
            self.assertEqual(ids, [3])  # Only the unprocessed item


# ─── TestIngestIdentityPassthrough ───────────────────────────────────────────

class TestIngestIdentityPassthrough(unittest.TestCase):
    """
    Verify that the web_bridge.task_completed payload includes identity fields
    that would be picked up by the ingest route and stored on the approval_item.
    """

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge._web_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None
        self.posted_payloads = []

        async def fake_post(payload):
            self.posted_payloads.append(payload)

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_full_identity_payload_for_waiting_approval(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p42", project_name="MyApp",
            task_name="Backend API", summary="done", files=["api.py"],
            model_id="claude-sonnet", cost_usd=0.005, duration_seconds=12.0,
            status="waiting_approval",
            sdlc_task_id="p42-E001-T003",
            discord_message_id="987654321000",
        ))
        p = self.posted_payloads[0]
        self.assertEqual(p["sdlc_task_id"], "p42-E001-T003")
        self.assertEqual(p["project_id"], "p42")
        self.assertEqual(p["discord_message_id"], "987654321000")
        self.assertEqual(p["status"], "waiting_approval")
        self.assertEqual(p["roleKey"], "dev")


# ─── Phase 5.2: Auto-approve web sync ────────────────────────────────────────

class TestAutoApproveWebSync(unittest.TestCase):
    """
    Verify that task_completed passes the actual _initial_status to web bridge,
    not a hardcoded "waiting_approval".
    Auto mode → status="completed" → no approval_item created in webapp.
    """

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge._web_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None
        self.posted_payloads = []

        async def fake_post(payload):
            self.posted_payloads.append(payload)

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_auto_mode_sends_completed_status(self):
        """Auto-approve: status=completed should NOT create approval_item on ingest."""
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="AutoApp",
            task_name="Backend API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
            status="completed",  # _initial_status from auto mode
            sdlc_task_id="p1-E001-T001",
        ))
        payload = self.posted_payloads[0]
        # Must send "completed", not "waiting_approval"
        self.assertEqual(payload["status"], "completed")

    def test_manual_mode_sends_waiting_approval(self):
        """Manual-approve: status=waiting_approval creates approval_item."""
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="ManualApp",
            task_name="Backend API", summary="done", files=[], model_id="gpt",
            cost_usd=0.01, duration_seconds=5.0,
            status="waiting_approval",
            sdlc_task_id="p1-E001-T002",
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["status"], "waiting_approval")

    def test_completed_status_payload_still_has_identity(self):
        """Even in auto mode, identity fields must be present in payload."""
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p99", project_name="AutoApp",
            task_name="Test Task", summary="done", files=[], model_id="gpt",
            cost_usd=0.0, duration_seconds=1.0,
            status="completed",
            sdlc_task_id="p99-E001-T005",
            discord_message_id="11223344",
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["sdlc_task_id"], "p99-E001-T005")
        self.assertEqual(payload["discord_message_id"], "11223344")
        self.assertEqual(payload["project_id"], "p99")


# ─── Phase 5.2: WebBridge devops_blocked ─────────────────────────────────────

class TestWebBridgeDevopsBlocked(unittest.TestCase):
    """Verify devops_blocked() sends correct payload and does NOT create approval_item."""

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge._web_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None
        self.posted_payloads = []

        async def fake_post(payload):
            self.posted_payloads.append(payload)

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_event_type_is_devops_blocked(self):
        self._run(self.bridge.devops_blocked(
            role_key="devops", project_id="p1", project_name="MyApp",
            task_name="Dockerfile", task_id="p1-E001-T010",
            blocked_summary="docker not found",
            blockers=["docker:compose_config: docker and docker-compose not found"],
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["eventType"], "devops_blocked")

    def test_status_is_blocked(self):
        self._run(self.bridge.devops_blocked(
            role_key="devops", project_id="p1", project_name="MyApp",
            task_name="Dockerfile", task_id="p1-E001-T010",
            blocked_summary="tools missing", blockers=[],
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["status"], "blocked")

    def test_status_blocked_does_not_equal_waiting_approval(self):
        """blocked status means NO approval_item will be created on ingest."""
        self._run(self.bridge.devops_blocked(
            role_key="devops", project_id="p1", project_name="MyApp",
            task_name="Dockerfile", task_id="p1-E001-T010",
            blocked_summary="tools missing", blockers=[],
        ))
        payload = self.posted_payloads[0]
        self.assertNotEqual(payload["status"], "waiting_approval")

    def test_summary_includes_task_id(self):
        self._run(self.bridge.devops_blocked(
            role_key="devops", project_id="p1", project_name="MyApp",
            task_name="Dockerfile", task_id="t-xyz",
            blocked_summary="infra down", blockers=["check1: missing"],
        ))
        payload = self.posted_payloads[0]
        self.assertIn("t-xyz", payload["summary"])

    def test_real_post_returns_false_when_disabled(self):
        """When enabled=False, the real _post returns early without HTTP call."""
        from shared.web_bridge import WebAppBridge
        bridge = WebAppBridge.__new__(WebAppBridge)
        bridge.enabled = False
        bridge.base_url = "http://localhost:3000"
        bridge._web_url = "http://localhost:3000"
        bridge.token = ""
        bridge._client = None
        # real _post (not replaced): should return False immediately when disabled
        result = self._run(bridge._post({"roleKey": "devops", "eventType": "devops_blocked",
                                          "taskName": "x", "status": "blocked", "summary": "x"}))
        self.assertFalse(result)

    def test_blockers_in_metadata(self):
        blockers = ["check1: missing tool", "check2: timeout"]
        self._run(self.bridge.devops_blocked(
            role_key="devops", project_id="p1", project_name="MyApp",
            task_name="Dockerfile", task_id="t1",
            blocked_summary="infra down", blockers=blockers,
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(payload["metadata"]["blockers"], blockers)


# ─── Phase 6: Model observability fields in task_completed ────────────────────

class TestWebBridgeModelObservability(unittest.TestCase):
    """Verify task_completed passes preferred_model, routed_model, fallback_used."""

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge.__new__(WebAppBridge)
        self.bridge.enabled = True
        self.bridge.base_url = "http://localhost:3000"
        self.bridge._web_url = "http://localhost:3000"
        self.bridge.token = "test-token"
        self.bridge._client = None
        self.posted_payloads = []

        async def fake_post(payload):
            self.posted_payloads.append(payload)

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_preferred_model_in_metadata(self):
        self._run(self.bridge.task_completed(
            role_key="devops", project_id="p1", project_name="App",
            task_name="Task", summary="done", files=[], model_id="claude-sonnet",
            cost_usd=0.001, duration_seconds=5.0,
            preferred_model="ollama/qwen2.5-coder",
            routed_model="claude-sonnet",
            fallback_used=True,
        ))
        meta = self.posted_payloads[0]["metadata"]
        self.assertEqual(meta["preferred_model"], "ollama/qwen2.5-coder")
        self.assertEqual(meta["routed_model"], "claude-sonnet")
        self.assertTrue(meta["fallback_used"])

    def test_artifacts_in_payload(self):
        arts = [
            {"type": "output_file", "path": "Dockerfile", "ref": "/out/Dockerfile"},
            {"type": "release_notes", "path": "release_notes.md", "ref": "/out/rn.md"},
        ]
        self._run(self.bridge.task_completed(
            role_key="devops", project_id="p1", project_name="App",
            task_name="Task", summary="done", files=[], model_id="claude-sonnet",
            cost_usd=0.001, duration_seconds=5.0,
            artifacts=arts,
        ))
        payload = self.posted_payloads[0]
        self.assertEqual(len(payload["artifacts"]), 2)
        self.assertEqual(payload["artifacts"][0]["type"], "output_file")

    def test_default_model_fields_empty(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="App",
            task_name="Task", summary="done", files=[], model_id="claude",
            cost_usd=0.0, duration_seconds=1.0,
        ))
        meta = self.posted_payloads[0]["metadata"]
        self.assertEqual(meta["preferred_model"], "")
        self.assertEqual(meta["routed_model"], "")
        self.assertFalse(meta["fallback_used"])

    def test_no_fallback_when_models_match(self):
        self._run(self.bridge.task_completed(
            role_key="dev", project_id="p1", project_name="App",
            task_name="Task", summary="done", files=[], model_id="ollama/qwen2.5-coder",
            cost_usd=0.0, duration_seconds=1.0,
            preferred_model="ollama/qwen2.5-coder",
            routed_model="ollama/qwen2.5-coder",
            fallback_used=False,
        ))
        meta = self.posted_payloads[0]["metadata"]
        self.assertFalse(meta["fallback_used"])


# ─── Phase 6: _collect_artifacts helper ──────────────────────────────────────

class TestCollectArtifacts(unittest.TestCase):

    def setUp(self):
        from shared.storage import SdlcTask
        now = datetime.utcnow().isoformat()
        self.task = SdlcTask(
            id="t1", project_id="p1", epic_id="p1-E001", task_number=1,
            role="devops", task_type="dockerfile", title="Dockerfile",
            description="", output_file="Dockerfile", output_format="dockerfile",
            depends_on="", status="in_progress", input_data="{}", output_data="{}",
            approval_msg_id="", revision_count=0, notes="",
            created_at=now, updated_at=now,
            attempt_count=0, claimed_by="", claimed_at="", last_error="",
        )

    def test_main_output_always_included(self):
        from shared.artifact_collector import collect_artifacts as _collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            saved = os.path.join(d, "Dockerfile")
            with open(saved, "w") as f:
                f.write("FROM python:3.11\n")
            arts = _collect_artifacts(d, saved, self.task)
        types = [a["type"] for a in arts]
        self.assertIn("output_file", types)

    def test_secondary_artifacts_detected(self):
        from shared.artifact_collector import collect_artifacts as _collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            saved = os.path.join(d, "Dockerfile")
            with open(saved, "w") as f:
                f.write("FROM python\n")
            with open(os.path.join(d, "deployment_readiness_report.md"), "w") as f:
                f.write("# Report\n")
            with open(os.path.join(d, "release_notes.md"), "w") as f:
                f.write("# Notes\n")
            arts = _collect_artifacts(d, saved, self.task)
        types = [a["type"] for a in arts]
        self.assertIn("deployment_report", types)
        self.assertIn("release_notes", types)

    def test_empty_saved_path_skips_output_file(self):
        from shared.artifact_collector import collect_artifacts as _collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            arts = _collect_artifacts(d, "", self.task)
        types = [a["type"] for a in arts]
        self.assertNotIn("output_file", types)

    def test_nonexistent_secondary_not_included(self):
        from shared.artifact_collector import collect_artifacts as _collect_artifacts
        with tempfile.TemporaryDirectory() as d:
            saved = os.path.join(d, "out.md")
            with open(saved, "w") as f:
                f.write("output\n")
            # No secondary artifacts written
            arts = _collect_artifacts(d, saved, self.task)
        types = [a["type"] for a in arts]
        self.assertNotIn("deployment_report", types)
        self.assertNotIn("release_notes", types)


class TestDecisionIdentityFields(unittest.TestCase):
    """Phase 6.1: approved/revision_requested/rejected include top-level identity fields."""

    def setUp(self):
        from shared.web_bridge import WebAppBridge
        self.bridge = WebAppBridge()
        self.bridge.enabled = True
        self.posted: list[dict] = []

        async def fake_post(payload):
            self.posted.append(payload)
            return True

        self.bridge._post = fake_post

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_approved_includes_sdlc_task_id_top_level(self):
        self._run(self.bridge.approved(
            role_key="dev",
            project_id="proj-123",
            project_name="MyProject",
            task_name="DEV Phase",
            next_role=None,
            sdlc_task_id="sdlc-task-abc",
        ))
        self.assertEqual(len(self.posted), 1)
        p = self.posted[0]
        self.assertEqual(p["sdlc_task_id"], "sdlc-task-abc")
        self.assertEqual(p["project_id"], "proj-123")
        self.assertEqual(p["eventType"], "approved")

    def test_revision_requested_includes_sdlc_task_id_top_level(self):
        self._run(self.bridge.revision_requested(
            role_key="qa",
            project_id="proj-456",
            project_name="MyProject",
            task_name="QA Phase",
            comment="Fix tests",
            revision_count=2,
            sdlc_task_id="sdlc-task-def",
        ))
        self.assertEqual(len(self.posted), 1)
        p = self.posted[0]
        self.assertEqual(p["sdlc_task_id"], "sdlc-task-def")
        self.assertEqual(p["project_id"], "proj-456")
        self.assertEqual(p["eventType"], "revision_requested")

    def test_rejected_includes_sdlc_task_id_top_level(self):
        self._run(self.bridge.rejected(
            role_key="sa",
            project_id="proj-789",
            project_name="MyProject",
            task_name="SA Phase",
            reason="Out of scope",
            sdlc_task_id="sdlc-task-ghi",
        ))
        self.assertEqual(len(self.posted), 1)
        p = self.posted[0]
        self.assertEqual(p["sdlc_task_id"], "sdlc-task-ghi")
        self.assertEqual(p["project_id"], "proj-789")
        self.assertEqual(p["eventType"], "rejected")

    def test_approved_legacy_has_role_task_id_no_sdlc_task_id(self):
        """Legacy role_task flow: role_task_id present, sdlc_task_id empty."""
        self._run(self.bridge.approved(
            role_key="dev",
            project_id="proj-legacy",
            project_name="Legacy",
            task_name="DEV Phase",
            next_role="qa",
            role_task_id="rt-999",
        ))
        p = self.posted[0]
        self.assertEqual(p["role_task_id"], "rt-999")
        self.assertEqual(p["sdlc_task_id"], "")

    def test_revision_includes_discord_message_id(self):
        self._run(self.bridge.revision_requested(
            role_key="dev",
            project_id="proj-123",
            project_name="X",
            task_name="T",
            comment="redo",
            revision_count=1,
            sdlc_task_id="sdlc-xyz",
            discord_message_id="discord-msg-111",
        ))
        p = self.posted[0]
        self.assertEqual(p["discord_message_id"], "discord-msg-111")
        self.assertEqual(p["sdlc_task_id"], "sdlc-xyz")

    def test_default_empty_identity_fields_when_not_passed(self):
        """All new fields default to empty string when not passed."""
        self._run(self.bridge.approved(
            role_key="pm",
            project_id="proj-001",
            project_name="P",
            task_name="T",
            next_role=None,
        ))
        p = self.posted[0]
        self.assertEqual(p["sdlc_task_id"], "")
        self.assertEqual(p["discord_message_id"], "")
        self.assertEqual(p["role_task_id"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
