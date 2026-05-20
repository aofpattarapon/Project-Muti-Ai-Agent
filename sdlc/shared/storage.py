"""
Storage Layer - SQLite สำหรับเก็บ State ของแต่ละ Project และ Task
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    COMPLETED = "completed"


# ─── Epic + SdlcTask Models ─────────────────────────────────────────────────

@dataclass
class Epic:
    id: str              # "{project_id}-E001"
    project_id: str
    epic_number: int     # 1, 2, 3 …
    title: str
    goal: str
    priority: str        # P0 / P1 / P2
    effort: str          # XS / S / M / L / XL
    user_stories: str    # JSON array string
    status: str          # pending / in_progress / completed
    created_at: str


@dataclass
class SdlcTask:
    id: str              # "{project_id}-E001-T001"
    project_id: str
    epic_id: str         # Epic ID or "{project_id}-PROJECT" for project-level tasks
    task_number: int     # running number within epic
    role: str            # "ba", "sa", "dev" …
    task_type: str       # "brd", "architecture", "setup" …
    title: str
    description: str
    output_file: str     # "BRD.md", "raci_matrix.xlsx" …
    output_format: str   # markdown / excel / mermaid / html / sql / yaml / dockerfile
    depends_on: str      # comma-separated SdlcTask IDs (empty = no deps)
    status: str          # pending / in_progress / waiting_approval / approved / failed / paused
    input_data: str      # JSON
    output_data: str     # JSON {"content": "…"}
    approval_msg_id: str
    revision_count: int
    notes: str
    created_at: str
    updated_at: str
    # Execution tracking (added via migration — safe to omit on insert)
    attempt_count: int = 0   # incremented on each auto-retry; persists across restarts
    last_error: str = ""     # last failure message
    claimed_at: str = ""     # ISO timestamp when task was claimed for execution
    claimed_by: str = ""     # role name that claimed this task
    # Quota/provider pause fields (added via migration)
    pause_reason: str = ""   # quota_exceeded | rate_limited | context_limit_exceeded | …
    pause_provider: str = "" # "anthropic" | "openai" | "groq" | "ollama"
    pause_model: str = ""    # model_key that triggered the pause
    retry_after_at: str = "" # ISO timestamp — earliest time recovery worker may requeue
    paused_at: str = ""      # ISO timestamp when task entered paused state
    resume_policy: str = ""  # "auto" | "manual_token_fix"


class RoleType(str, Enum):
    CEO = "ceo"
    PM = "pm"
    BA = "ba"
    SA = "sa"
    UXUI = "uxui"
    DEV = "dev"
    QA = "qa"
    DEVOPS = "devops"


# SDLC Workflow Order
ROLE_ORDER = [
    RoleType.CEO,
    RoleType.PM,
    RoleType.BA,
    RoleType.SA,
    RoleType.UXUI,
    RoleType.DEV,
    RoleType.QA,
    RoleType.DEVOPS,
]


@dataclass
class Project:
    id: str
    name: str
    description: str
    created_at: str
    current_role: str
    status: str
    discord_guild_id: str
    approval_channel_id: str
    metadata: Dict = None

    def to_dict(self):
        d = asdict(self)
        if d["metadata"] is None:
            d["metadata"] = {}
        return d


@dataclass
class RoleTask:
    id: str
    project_id: str
    role: str
    status: str
    input_data: str         # JSON string
    output_data: str        # JSON string (documents, files, etc.)
    created_at: str
    updated_at: str
    approval_message_id: str  # Discord message ID for approval
    revision_count: int
    notes: str              # Human notes from approval/revision


class Storage:
    """SQLite-backed storage สำหรับ project state"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DB_PATH", "/app/data/sdlc.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT,
                    current_role TEXT,
                    status TEXT,
                    discord_guild_id TEXT,
                    approval_channel_id TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    role TEXT,
                    status TEXT,
                    input_data TEXT,
                    output_data TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    approval_message_id TEXT,
                    revision_count INTEGER DEFAULT 0,
                    notes TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epics (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    epic_number INTEGER NOT NULL,
                    title TEXT,
                    goal TEXT,
                    priority TEXT DEFAULT 'P1',
                    effort TEXT DEFAULT 'M',
                    user_stories TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sdlc_tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    epic_id TEXT NOT NULL,
                    task_number INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    title TEXT,
                    description TEXT DEFAULT '',
                    output_file TEXT NOT NULL,
                    output_format TEXT DEFAULT 'markdown',
                    depends_on TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    input_data TEXT DEFAULT '{}',
                    output_data TEXT DEFAULT '{}',
                    approval_msg_id TEXT DEFAULT '',
                    revision_count INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            # Migration: add execution-tracking columns if they don't exist yet
            _sdlc_cols = {r[1] for r in conn.execute("PRAGMA table_info(sdlc_tasks)").fetchall()}
            for _col, _defn in [
                ("attempt_count",  "INTEGER DEFAULT 0"),
                ("last_error",     "TEXT DEFAULT ''"),
                ("claimed_at",     "TEXT DEFAULT ''"),
                ("claimed_by",     "TEXT DEFAULT ''"),
                # Phase 8 pause fields
                ("pause_reason",   "TEXT DEFAULT ''"),
                ("pause_provider", "TEXT DEFAULT ''"),
                ("pause_model",    "TEXT DEFAULT ''"),
                ("retry_after_at", "TEXT DEFAULT ''"),
                ("paused_at",      "TEXT DEFAULT ''"),
                ("resume_policy",  "TEXT DEFAULT ''"),
            ]:
                if _col not in _sdlc_cols:
                    conn.execute(f"ALTER TABLE sdlc_tasks ADD COLUMN {_col} {_defn}")

            # Phase 8: provider cooldown tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    reason TEXT DEFAULT '',
                    retry_after_at TEXT NOT NULL,
                    created_at TEXT
                )
            """)
            conn.commit()

    # ─── Project CRUD ───────────────────────────────────────────────────────────

    def create_project(self, project: Project) -> Project:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    project.id, project.name, project.description,
                    project.created_at, project.current_role, project.status,
                    project.discord_guild_id, project.approval_channel_id,
                    json.dumps(project.metadata or {}),
                ),
            )
            conn.commit()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return Project(
            id=row[0], name=row[1], description=row[2], created_at=row[3],
            current_role=row[4], status=row[5], discord_guild_id=row[6],
            approval_channel_id=row[7], metadata=json.loads(row[8] or "{}"),
        )

    def update_project_role(self, project_id: str, role: str, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE projects SET current_role=?, status=? WHERE id=?",
                (role, status, project_id),
            )
            conn.commit()

    def list_active_projects(self) -> List[Project]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status != 'completed' AND status != 'rejected'"
            ).fetchall()
        return [
            Project(id=r[0], name=r[1], description=r[2], created_at=r[3],
                    current_role=r[4], status=r[5], discord_guild_id=r[6],
                    approval_channel_id=r[7], metadata=json.loads(r[8] or "{}"))
            for r in rows
        ]

    # ─── RoleTask CRUD ──────────────────────────────────────────────────────────

    def create_role_task(self, task: RoleTask) -> RoleTask:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO role_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task.id, task.project_id, task.role, task.status,
                    task.input_data, task.output_data, task.created_at,
                    task.updated_at, task.approval_message_id,
                    task.revision_count, task.notes,
                ),
            )
            conn.commit()
        return task

    def get_role_task(self, task_id: str) -> Optional[RoleTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM role_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def get_task_by_project_role(self, project_id: str, role: str) -> Optional[RoleTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM role_tasks WHERE project_id=? AND role=? ORDER BY created_at DESC LIMIT 1",
                (project_id, role),
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def get_pending_approval_task_by_name(self, task_name: str, role: str) -> Optional[RoleTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM role_tasks WHERE role=? AND status IN ('waiting_approval','in_progress') ORDER BY created_at DESC LIMIT 1",
                (role,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def get_pending_approval_task(self, message_id: str) -> Optional[RoleTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM role_tasks WHERE approval_message_id=?", (message_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def update_task_status(self, task_id: str, status: str, notes: str = None):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if notes:
                conn.execute(
                    "UPDATE role_tasks SET status=?, updated_at=?, notes=? WHERE id=?",
                    (status, now, notes, task_id),
                )
            else:
                conn.execute(
                    "UPDATE role_tasks SET status=?, updated_at=? WHERE id=?",
                    (status, now, task_id),
                )
            conn.commit()

    def update_task_output(self, task_id: str, output_data: dict):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE role_tasks SET output_data=?, updated_at=? WHERE id=?",
                (json.dumps(output_data), now, task_id),
            )
            conn.commit()

    def set_approval_message(self, task_id: str, message_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE role_tasks SET approval_message_id=? WHERE id=?",
                (message_id, task_id),
            )
            conn.commit()

    def increment_revision(self, task_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE role_tasks SET revision_count = revision_count + 1 WHERE id=?",
                (task_id,),
            )
            conn.commit()

    def _row_to_task(self, row) -> RoleTask:
        return RoleTask(
            id=row[0], project_id=row[1], role=row[2], status=row[3],
            input_data=row[4], output_data=row[5], created_at=row[6],
            updated_at=row[7], approval_message_id=row[8],
            revision_count=row[9], notes=row[10],
        )

    # ─── Cross-role feedback (e.g., QA → DEV bug report) ───────────────────────

    def set_role_feedback(self, project_id: str, target_role: str, feedback: dict):
        """Store output feedback for a target role to consume on next task start."""
        project = self.get_project(project_id)
        metadata = project.metadata or {} if project else {}
        if "role_feedback" not in metadata:
            metadata["role_feedback"] = {}
        metadata["role_feedback"][target_role] = feedback
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE projects SET metadata=? WHERE id=?",
                (json.dumps(metadata), project_id),
            )
            conn.commit()

    def get_role_feedback(self, project_id: str, role: str) -> Optional[dict]:
        project = self.get_project(project_id)
        if not project or not project.metadata:
            return None
        return project.metadata.get("role_feedback", {}).get(role)

    def clear_role_feedback(self, project_id: str, role: str):
        project = self.get_project(project_id)
        if not project or not project.metadata:
            return
        metadata = project.metadata
        if "role_feedback" in metadata and role in metadata["role_feedback"]:
            del metadata["role_feedback"][role]
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE projects SET metadata=? WHERE id=?",
                    (json.dumps(metadata), project_id),
                )
                conn.commit()

    # ─── Epic CRUD ──────────────────────────────────────────────────────────────

    def create_epic(self, epic: Epic) -> Epic:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epics VALUES (?,?,?,?,?,?,?,?,?,?)",
                (epic.id, epic.project_id, epic.epic_number, epic.title, epic.goal,
                 epic.priority, epic.effort, epic.user_stories, epic.status, epic.created_at),
            )
            conn.commit()
        return epic

    def get_epic(self, epic_id: str) -> Optional[Epic]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM epics WHERE id=?", (epic_id,)).fetchone()
        return self._row_to_epic(row) if row else None

    def list_epics(self, project_id: str) -> List[Epic]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM epics WHERE project_id=? ORDER BY epic_number", (project_id,)
            ).fetchall()
        return [self._row_to_epic(r) for r in rows]

    def update_epic_status(self, epic_id: str, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE epics SET status=? WHERE id=?", (status, epic_id))
            conn.commit()

    def _row_to_epic(self, row) -> Epic:
        return Epic(id=row[0], project_id=row[1], epic_number=row[2], title=row[3],
                    goal=row[4], priority=row[5], effort=row[6], user_stories=row[7],
                    status=row[8], created_at=row[9])

    # ─── SdlcTask CRUD ──────────────────────────────────────────────────────────

    def create_sdlc_task(self, task: SdlcTask) -> SdlcTask:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO sdlc_tasks
                   (id, project_id, epic_id, task_number, role, task_type, title,
                    description, output_file, output_format, depends_on, status,
                    input_data, output_data, approval_msg_id, revision_count, notes,
                    created_at, updated_at, attempt_count, last_error, claimed_at, claimed_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task.id, task.project_id, task.epic_id, task.task_number, task.role,
                 task.task_type, task.title, task.description, task.output_file,
                 task.output_format, task.depends_on, task.status, task.input_data,
                 task.output_data, task.approval_msg_id, task.revision_count,
                 task.notes, task.created_at, task.updated_at,
                 task.attempt_count, task.last_error, task.claimed_at, task.claimed_by),
            )
            conn.commit()
        return task

    def get_sdlc_task(self, task_id: str) -> Optional[SdlcTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM sdlc_tasks WHERE id=?", (task_id,)).fetchone()
        return self._row_to_sdlc_task(row) if row else None

    def get_sdlc_task_by_approval_msg(self, msg_id: str) -> Optional[SdlcTask]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sdlc_tasks WHERE approval_msg_id=?", (msg_id,)
            ).fetchone()
        return self._row_to_sdlc_task(row) if row else None

    def list_pending_sdlc_tasks(self, role: str) -> List[SdlcTask]:
        """คืน tasks ที่ pending และ depends_on ทั้งหมด approved แล้ว"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sdlc_tasks WHERE role=? AND status='pending' ORDER BY created_at",
                (role,),
            ).fetchall()
        tasks = [self._row_to_sdlc_task(r) for r in rows]
        return [t for t in tasks if self._deps_satisfied(t, conn=None)]

    def _deps_satisfied(self, task: SdlcTask, conn=None) -> bool:
        if not task.depends_on:
            return True
        dep_ids = [d.strip() for d in task.depends_on.split(",") if d.strip()]
        with sqlite3.connect(self.db_path) as c:
            for dep_id in dep_ids:
                row = c.execute(
                    "SELECT status FROM sdlc_tasks WHERE id=?", (dep_id,)
                ).fetchone()
                if not row or row[0] not in ("approved", "completed"):
                    return False
        return True

    def update_sdlc_task_status(self, task_id: str, status: str, notes: str = None):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if notes:
                conn.execute(
                    "UPDATE sdlc_tasks SET status=?, updated_at=?, notes=? WHERE id=?",
                    (status, now, notes, task_id),
                )
            else:
                conn.execute(
                    "UPDATE sdlc_tasks SET status=?, updated_at=? WHERE id=?",
                    (status, now, task_id),
                )
            conn.commit()

    def claim_sdlc_task(self, task_id: str, role: str) -> bool:
        """Atomically claim a pending task for execution.

        Returns True only when this call wins the race (rowcount == 1).
        Callers that get False must skip the task — it was already claimed by
        another process or a previous loop iteration.
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE sdlc_tasks SET status='in_progress', claimed_by=?, claimed_at=?, updated_at=? "
                "WHERE id=? AND role=? AND status='pending'",
                (role, now, now, task_id, role),
            )
            conn.commit()
        return cursor.rowcount == 1

    def record_sdlc_task_error(self, task_id: str, error: str, attempt_count: int, requeue: bool = True):
        """Persist retry state after a task failure.

        requeue=True  → reset status to 'pending', clear claim fields so it can
                        be re-claimed cleanly on the next poll cycle
        requeue=False → set status to 'failed' (max retries exhausted)
        """
        now = datetime.utcnow().isoformat()
        status = "pending" if requeue else "failed"
        notes = f"Auto-retry {attempt_count}: {error[:300]}" if requeue else error[:300]
        if requeue:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE sdlc_tasks SET status=?, attempt_count=?, last_error=?, notes=?, "
                    "claimed_at='', claimed_by='', updated_at=? WHERE id=?",
                    (status, attempt_count, error[:500], notes, now, task_id),
                )
                conn.commit()
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE sdlc_tasks SET status=?, attempt_count=?, last_error=?, notes=?, updated_at=? WHERE id=?",
                    (status, attempt_count, error[:500], notes, now, task_id),
                )
                conn.commit()

    def update_sdlc_task_input_data(self, task_id: str, input_data: dict):
        """Merge new key/values into a task's input_data JSON (used to inject revision_comment)."""
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT input_data FROM sdlc_tasks WHERE id=?", (task_id,)).fetchone()
            try:
                existing = json.loads(row[0] or "{}") if row else {}
            except Exception:
                existing = {}
            existing.update(input_data)
            conn.execute(
                "UPDATE sdlc_tasks SET input_data=?, updated_at=? WHERE id=?",
                (json.dumps(existing), now, task_id),
            )
            conn.commit()

    def recover_stale_sdlc_tasks(self, role: str, max_age_minutes: int = 60, max_retries: int = 2) -> list:
        """Re-queue or permanently fail tasks stuck in in_progress too long.

        Only touches tasks for the given role that have a non-empty claimed_at
        (tasks without claimed_at pre-date tracking and are left alone).
        Returns list of (task_id, new_status) tuples so the caller can log them.
        """
        from datetime import timedelta
        now = datetime.utcnow()
        cutoff = (now - timedelta(minutes=max_age_minutes)).isoformat()
        recovered = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, attempt_count FROM sdlc_tasks "
                "WHERE role=? AND status='in_progress' AND claimed_at != '' AND claimed_at < ?",
                (role, cutoff),
            ).fetchall()
            for task_id, attempt_count in rows:
                note = (
                    f"Stale recovery at {now.isoformat()[:19]} "
                    f"(stuck in_progress > {max_age_minutes}m)"
                )
                if (attempt_count or 0) < max_retries:
                    conn.execute(
                        "UPDATE sdlc_tasks SET status='pending', claimed_at='', claimed_by='', "
                        "notes=?, updated_at=? WHERE id=?",
                        (note, now.isoformat(), task_id),
                    )
                    recovered.append((task_id, "pending"))
                else:
                    conn.execute(
                        "UPDATE sdlc_tasks SET status='failed', "
                        "notes=?, updated_at=? WHERE id=?",
                        (note + " — max retries exhausted", now.isoformat(), task_id),
                    )
                    recovered.append((task_id, "failed"))
            if recovered:
                conn.commit()
        return recovered

    def manual_retry_sdlc_task(self, task_id: str, notes: str = "Manual retry"):
        """Re-queue a task for manual retry.

        Clears claim fields and approval_msg_id so it can be re-claimed cleanly.
        Preserves attempt_count for audit; appends the current count to notes.
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT attempt_count FROM sdlc_tasks WHERE id=?", (task_id,)
            ).fetchone()
            count_note = f" [attempt_count={row[0] if row else 0}]" if row else ""
            conn.execute(
                "UPDATE sdlc_tasks SET status='pending', claimed_at='', claimed_by='', "
                "approval_msg_id='', notes=?, updated_at=? WHERE id=?",
                (notes + count_note, now, task_id),
            )
            conn.commit()

    def update_sdlc_task_output(self, task_id: str, output_data):
        """Store raw string or dict as output_data"""
        now = datetime.utcnow().isoformat()
        stored = output_data if isinstance(output_data, str) else json.dumps(output_data)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sdlc_tasks SET output_data=?, updated_at=? WHERE id=?",
                (stored, now, task_id),
            )
            conn.commit()

    def set_sdlc_task_approval_msg(self, task_id: str, msg_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sdlc_tasks SET approval_msg_id=? WHERE id=?", (msg_id, task_id)
            )
            conn.commit()

    def increment_sdlc_task_revision(self, task_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sdlc_tasks SET revision_count = revision_count + 1 WHERE id=?",
                (task_id,),
            )
            conn.commit()

    def requeue_for_rework(self, task_id: str, notes_suffix: str = "") -> bool:
        """Re-queue a task for QA-triggered rework.

        Unlike manual_retry_sdlc_task (which preserves attempt_count and is
        human-initiated), this increments revision_count and clears claim fields.
        Only applies to tasks in terminal/approval states — never touches tasks
        that are already pending or in_progress to avoid double-requeueing.
        Returns True if the task was actually updated.
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE sdlc_tasks
                   SET status='pending',
                       revision_count=revision_count+1,
                       claimed_at='', claimed_by='', approval_msg_id='',
                       notes=CASE WHEN notes='' OR notes IS NULL
                                  THEN ? ELSE notes||'; '||? END,
                       updated_at=?
                   WHERE id=?
                     AND status IN ('approved','completed','waiting_approval','failed')""",
                (notes_suffix, notes_suffix, now, task_id),
            )
            conn.commit()
        return cursor.rowcount == 1

    def request_sdlc_task_revision(self, task_id: str, note: str):
        """Re-queue an sdlc_task for revision: status=pending, increment revision, inject note."""
        import logging as _logging
        _log = _logging.getLogger(__name__)
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT input_data, revision_count FROM sdlc_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                # C2: log ให้ชัดเมื่อหา task ไม่เจอ แทนที่จะ return เงียบๆ
                _log.warning(f"[Storage] request_sdlc_task_revision: task '{task_id}' not found — revision skipped")
                return
            try:
                inp = json.loads(row[0] or "{}")
            except Exception:
                inp = {}
            inp["revision_comment"] = note
            inp["revision_count"] = (row[1] or 0) + 1
            conn.execute(
                "UPDATE sdlc_tasks SET status='pending', revision_count=revision_count+1, "
                "input_data=?, notes=?, approval_msg_id='', updated_at=? WHERE id=?",
                (json.dumps(inp), note, now, task_id),
            )
            conn.commit()

    def list_sdlc_tasks(self, project_id: str, role: str = None) -> List[SdlcTask]:
        with sqlite3.connect(self.db_path) as conn:
            if role:
                rows = conn.execute(
                    "SELECT * FROM sdlc_tasks WHERE project_id=? AND role=? ORDER BY epic_id, task_number",
                    (project_id, role),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sdlc_tasks WHERE project_id=? ORDER BY epic_id, task_number",
                    (project_id,),
                ).fetchall()
        return [self._row_to_sdlc_task(r) for r in rows]

    def _row_to_sdlc_task(self, row) -> SdlcTask:
        def _s(i: int) -> str:
            return row[i] if len(row) > i and row[i] is not None else ""
        def _i(i: int) -> int:
            return row[i] if len(row) > i and row[i] is not None else 0
        return SdlcTask(
            id=row[0], project_id=row[1], epic_id=row[2], task_number=row[3],
            role=row[4], task_type=row[5], title=row[6], description=row[7],
            output_file=row[8], output_format=row[9], depends_on=row[10],
            status=row[11], input_data=row[12], output_data=row[13],
            approval_msg_id=row[14], revision_count=_i(15), notes=_s(16),
            created_at=_s(17), updated_at=_s(18),
            attempt_count=_i(19),
            last_error=_s(20),
            claimed_at=_s(21),
            claimed_by=_s(22),
            # Phase 8 pause fields
            pause_reason=_s(23),
            pause_provider=_s(24),
            pause_model=_s(25),
            retry_after_at=_s(26),
            paused_at=_s(27),
            resume_policy=_s(28),
        )

    def get_sdlc_task_by_title(self, task_name: str, role: str) -> Optional[SdlcTask]:
        """หา sdlc_task โดย title — only returns tasks in waiting_approval status."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sdlc_tasks WHERE role=? AND title=? AND status='waiting_approval' "
                "ORDER BY created_at DESC LIMIT 1",
                (role, task_name),
            ).fetchone()
        return self._row_to_sdlc_task(row) if row else None

    def get_sdlc_task_waiting_approval(self, task_id: str) -> Optional[SdlcTask]:
        """Return task by ID only if currently in waiting_approval status."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sdlc_tasks WHERE id=? AND status='waiting_approval' LIMIT 1",
                (task_id,),
            ).fetchone()
        return self._row_to_sdlc_task(row) if row else None

    def try_complete_project(self, project_id: str) -> bool:
        """
        Atomically mark project as completed only if it's currently in_progress.
        Returns True if this call did the transition (i.e., first agent to detect completion).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE projects SET status='completed', current_role='completed' "
                "WHERE id=? AND status='in_progress'",
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ─── Phase 8: Quota/Provider Pause ─────────────────────────────────────────

    def pause_sdlc_task_for_provider(
        self,
        task_id: str,
        reason: str,
        provider: str,
        model: str,
        retry_after_at: str,
        error: str = "",
        resume_policy: str = "auto",
    ):
        """
        Move task to status='paused' and record all pause metadata.

        Clears claimed_at/claimed_by so the recovery worker can safely requeue it
        without racing against an active agent claim.
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE sdlc_tasks
                   SET status='paused',
                       pause_reason=?, pause_provider=?, pause_model=?,
                       retry_after_at=?, paused_at=?, resume_policy=?,
                       last_error=?,
                       claimed_at='', claimed_by='',
                       updated_at=?
                   WHERE id=?""",
                (reason, provider, model, retry_after_at, now,
                 resume_policy, error[:500], now, task_id),
            )
            conn.commit()

    def list_paused_sdlc_tasks(self, now_iso: str = "") -> list:
        """
        Return paused tasks whose retry_after_at <= now_iso (ready to resume).
        If now_iso is empty, return ALL paused tasks regardless of retry_after_at.
        Never returns tasks with resume_policy='manual_token_fix'.
        """
        now_iso = now_iso or datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sdlc_tasks "
                "WHERE status='paused' "
                "  AND (resume_policy IS NULL OR resume_policy != 'manual_token_fix') "
                "  AND (retry_after_at = '' OR retry_after_at <= ?) "
                "ORDER BY retry_after_at",
                (now_iso,),
            ).fetchall()
        return [self._row_to_sdlc_task(r) for r in rows]

    def resume_paused_sdlc_task(self, task_id: str):
        """
        Clear pause fields and requeue task to pending.
        Only acts on tasks currently in status='paused'.
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE sdlc_tasks
                   SET status='pending',
                       pause_reason='', pause_provider='', pause_model='',
                       retry_after_at='', paused_at='', resume_policy='',
                       claimed_at='', claimed_by='',
                       updated_at=?
                   WHERE id=? AND status='paused'""",
                (now, task_id),
            )
            conn.commit()

    # ── Provider cooldown ────────────────────────────────────────────────────

    def set_provider_cooldown(
        self,
        provider: str,
        model: str,
        reason: str,
        retry_after_at: str,
    ):
        """
        Upsert a cooldown record for a provider+model combination.
        Replaces any existing cooldown for the same (provider, model) pair
        if the new retry_after_at is later (more restrictive).
        """
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id, retry_after_at FROM provider_cooldowns "
                "WHERE provider=? AND model=?",
                (provider, model),
            ).fetchone()
            if existing:
                # Only update if new deadline is later
                if retry_after_at >= existing[1]:
                    conn.execute(
                        "UPDATE provider_cooldowns "
                        "SET reason=?, retry_after_at=?, created_at=? "
                        "WHERE id=?",
                        (reason, retry_after_at, now, existing[0]),
                    )
            else:
                conn.execute(
                    "INSERT INTO provider_cooldowns (provider, model, reason, retry_after_at, created_at) "
                    "VALUES (?,?,?,?,?)",
                    (provider, model, reason, retry_after_at, now),
                )
            conn.commit()

    def get_active_provider_cooldowns(self, now_iso: str = "") -> list:
        """
        Return list of dicts for cooldowns still active (retry_after_at > now).
        Each dict has: provider, model, reason, retry_after_at.
        """
        now_iso = now_iso or datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT provider, model, reason, retry_after_at FROM provider_cooldowns "
                "WHERE retry_after_at > ? ORDER BY retry_after_at",
                (now_iso,),
            ).fetchall()
        return [
            {"provider": r[0], "model": r[1], "reason": r[2], "retry_after_at": r[3]}
            for r in rows
        ]

    def get_expired_provider_cooldowns(self, now_iso: str = "") -> list:
        """
        Return cooldowns whose retry_after_at has passed.
        The recovery worker uses this to clean up old cooldown rows.
        """
        now_iso = now_iso or datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT provider, model, reason, retry_after_at FROM provider_cooldowns "
                "WHERE retry_after_at <= ? ORDER BY retry_after_at",
                (now_iso,),
            ).fetchall()
        return [
            {"provider": r[0], "model": r[1], "reason": r[2], "retry_after_at": r[3]}
            for r in rows
        ]

    def clear_provider_cooldown(self, provider: str, model: str = ""):
        """Remove the cooldown record for the given provider (and optionally model)."""
        with sqlite3.connect(self.db_path) as conn:
            if model:
                conn.execute(
                    "DELETE FROM provider_cooldowns WHERE provider=? AND model=?",
                    (provider, model),
                )
            else:
                conn.execute(
                    "DELETE FROM provider_cooldowns WHERE provider=?", (provider,)
                )
            conn.commit()

    def update_task_retry_after(self, task_id: str, new_retry_after_at: str):
        """Push back retry_after_at for a paused task without changing other pause fields."""
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sdlc_tasks SET retry_after_at=?, updated_at=? WHERE id=? AND status='paused'",
                (new_retry_after_at, now, task_id),
            )
            conn.commit()

    def prune_expired_cooldowns(self, now_iso: str = "") -> int:
        """Delete provider_cooldown rows whose retry_after_at has passed. Returns count deleted."""
        now_iso = now_iso or datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM provider_cooldowns WHERE retry_after_at <= ?", (now_iso,)
            )
            conn.commit()
            return cursor.rowcount

    def get_next_role(self, current_role: str) -> Optional[str]:
        """ส่งคืน Role ถัดไปใน SDLC Workflow (ใช้ channel_config)"""
        try:
            from shared.channel_config import get_next_role as _get_next
            return _get_next(current_role)
        except ImportError:
            # fallback: old workflow without frontend/backend split
            role_names = [r.value for r in ROLE_ORDER]
            try:
                idx = role_names.index(current_role)
                return role_names[idx + 1] if idx + 1 < len(role_names) else None
            except ValueError:
                return None
