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
    status: str          # pending / in_progress / waiting_approval / approved / failed
    input_data: str      # JSON
    output_data: str     # JSON {"content": "…"}
    approval_msg_id: str
    revision_count: int
    notes: str
    created_at: str
    updated_at: str


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
                "INSERT INTO sdlc_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task.id, task.project_id, task.epic_id, task.task_number, task.role,
                 task.task_type, task.title, task.description, task.output_file,
                 task.output_format, task.depends_on, task.status, task.input_data,
                 task.output_data, task.approval_msg_id, task.revision_count,
                 task.notes, task.created_at, task.updated_at),
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
        return SdlcTask(
            id=row[0], project_id=row[1], epic_id=row[2], task_number=row[3],
            role=row[4], task_type=row[5], title=row[6], description=row[7],
            output_file=row[8], output_format=row[9], depends_on=row[10],
            status=row[11], input_data=row[12], output_data=row[13],
            approval_msg_id=row[14], revision_count=row[15], notes=row[16],
            created_at=row[17], updated_at=row[18],
        )

    def get_sdlc_task_by_title(self, task_name: str, role: str) -> Optional[SdlcTask]:
        """หา sdlc_task โดย title (ใช้ใน web decision poll loop)"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sdlc_tasks WHERE role=? AND title=? ORDER BY created_at DESC LIMIT 1",
                (role, task_name),
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
