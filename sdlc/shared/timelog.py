"""
TimeLog System — Jira-style Time Tracking
บันทึก start/end time, duration, task description ต่อ Agent
โพสต์อัตโนมัติใน #{role}-timelog channel
"""

import os
import sqlite3
import asyncio
import discord
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class TimeEntry:
    id: str
    project_id: str
    role: str
    task_type: str          # "processing" | "revision" | "review"
    task_description: str
    started_at: str         # ISO format
    ended_at: Optional[str]
    duration_seconds: Optional[int]
    status: str             # "in_progress" | "done" | "blocked"
    model_used: str
    cost_usd: float
    revision_count: int
    output_files: str       # comma-separated filenames


class TimeLogger:
    """
    บันทึก Time Log ของแต่ละ Agent แบบ Jira
    """

    # Role → emoji mapping
    ROLE_EMOJI = {
        "ceo": "👑", "pm": "📊", "ba": "📝",
        "sa": "🏛️", "uxui": "🎨",
        "frontend": "💻", "backend": "⚙️",
        "qa": "🧪", "devops": "🔧",
    }

    # Task type → label
    TASK_LABELS = {
        "processing":  "🔨 Processing",
        "revision":    "🔄 Revision",
        "review":      "👀 Review",
        "research":    "🔍 Research",
        "deployment":  "🚀 Deploy",
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DB_PATH", "/app/data/sdlc.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_logs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    role TEXT,
                    task_type TEXT,
                    task_description TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    duration_seconds INTEGER,
                    status TEXT DEFAULT 'in_progress',
                    model_used TEXT,
                    cost_usd REAL DEFAULT 0,
                    revision_count INTEGER DEFAULT 0,
                    output_files TEXT DEFAULT '',
                    discord_message_id TEXT DEFAULT ''
                )
            """)
            conn.commit()

    def start(
        self,
        log_id: str,
        project_id: str,
        role: str,
        task_type: str,
        task_description: str,
        revision_count: int = 0,
    ) -> "TimeEntry":
        entry = TimeEntry(
            id=log_id,
            project_id=project_id,
            role=role,
            task_type=task_type,
            task_description=task_description,
            started_at=datetime.utcnow().isoformat(),
            ended_at=None,
            duration_seconds=None,
            status="in_progress",
            model_used="",
            cost_usd=0.0,
            revision_count=revision_count,
            output_files="",
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO time_logs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    entry.id, entry.project_id, entry.role,
                    entry.task_type, entry.task_description,
                    entry.started_at, None, None,
                    entry.status, "", 0, revision_count, "", "",
                ),
            )
            conn.commit()
        return entry

    def finish(
        self,
        log_id: str,
        model_used: str = "",
        cost_usd: float = 0.0,
        output_files: list = None,
        status: str = "done",
    ) -> Optional[TimeEntry]:
        ended_at = datetime.utcnow()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT started_at FROM time_logs WHERE id=?", (log_id,)
            ).fetchone()
            if not row:
                return None

            started_at = datetime.fromisoformat(row[0])
            duration   = int((ended_at - started_at).total_seconds())
            files_str  = ",".join(output_files or [])

            conn.execute(
                """UPDATE time_logs SET ended_at=?, duration_seconds=?,
                   status=?, model_used=?, cost_usd=?, output_files=?
                   WHERE id=?""",
                (ended_at.isoformat(), duration, status, model_used,
                 cost_usd, files_str, log_id),
            )
            conn.commit()

            row2 = conn.execute("SELECT * FROM time_logs WHERE id=?", (log_id,)).fetchone()
        return self._row_to_entry(row2) if row2 else None

    def get_entry(self, log_id: str) -> Optional[TimeEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM time_logs WHERE id=?", (log_id,)).fetchone()
        return self._row_to_entry(row) if row else None

    def get_project_logs(self, project_id: str) -> list[TimeEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM time_logs WHERE project_id=? ORDER BY started_at",
                (project_id,)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def set_discord_message(self, log_id: str, message_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE time_logs SET discord_message_id=? WHERE id=?",
                (message_id, log_id)
            )
            conn.commit()

    def _row_to_entry(self, row) -> TimeEntry:
        return TimeEntry(
            id=row[0], project_id=row[1], role=row[2],
            task_type=row[3], task_description=row[4],
            started_at=row[5], ended_at=row[6],
            duration_seconds=row[7], status=row[8],
            model_used=row[9], cost_usd=row[10],
            revision_count=row[11], output_files=row[12],
        )

    def get_task_count(self, project_id: str, role: str) -> int:
        """นับจำนวน tasks ที่เสร็จแล้ว (done/blocked) สำหรับ project+role คู่นี้"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM time_logs WHERE project_id=? AND role=? AND status IN ('done','blocked')",
                (project_id, role),
            ).fetchone()
        return (row[0] if row else 0) + 1  # +1 เพราะ task ปัจจุบันยังไม่ถูกนับ

    @staticmethod
    def _to_thai_time(dt: datetime) -> datetime:
        """แปลง UTC → Thai time (UTC+7)"""
        return dt + timedelta(hours=7)

    # ─── Discord Embed Builders ─────────────────────────────────────

    def build_start_embed(self, entry: TimeEntry, project_name: str) -> discord.Embed:
        """Embed สำหรับแจ้งเริ่มงาน"""
        emoji = self.ROLE_EMOJI.get(entry.role, "🤖")
        task_label = self.TASK_LABELS.get(entry.task_type, entry.task_type)

        started_utc = datetime.fromisoformat(entry.started_at)
        started_th  = self._to_thai_time(started_utc)

        task_count = self.get_task_count(entry.project_id, entry.role)

        embed = discord.Embed(
            title=f"⏱️ {emoji} {entry.role.upper()} — เริ่มทำงาน",
            color=0xfbbf24,  # amber
            timestamp=started_utc,
        )
        embed.add_field(name="📋 Project", value=f"`{entry.project_id}` {project_name}", inline=False)
        embed.add_field(name="🔖 Task Type", value=task_label, inline=True)
        embed.add_field(name="🔄 Revision #", value=str(entry.revision_count), inline=True)
        embed.add_field(name="🕐 เริ่ม (Thai)", value=started_th.strftime("%d/%m/%Y %H:%M:%S"), inline=True)
        embed.add_field(name="📊 Task #", value=f"#{task_count} สำหรับ project นี้", inline=True)
        embed.add_field(name="📝 Description", value=entry.task_description[:300], inline=False)
        embed.set_footer(text=f"Log ID: {entry.id}")
        return embed

    def build_finish_embed(self, entry: TimeEntry, project_name: str) -> discord.Embed:
        """Embed สำหรับแจ้งจบงาน"""
        emoji = self.ROLE_EMOJI.get(entry.role, "🤖")

        started_utc = datetime.fromisoformat(entry.started_at)
        ended_utc   = datetime.fromisoformat(entry.ended_at) if entry.ended_at else datetime.utcnow()
        started_th  = self._to_thai_time(started_utc)
        ended_th    = self._to_thai_time(ended_utc)
        duration    = timedelta(seconds=entry.duration_seconds or 0)

        # Format duration
        mins, secs = divmod(int(duration.total_seconds()), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            dur_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            dur_str = f"{mins}m {secs}s"
        else:
            dur_str = f"{secs}s"

        status_emoji = {"done": "✅", "blocked": "🚫", "in_progress": "⏳"}.get(entry.status, "✅")

        tier_info = ""
        if entry.model_used:
            if "ollama" in entry.model_used or "groq" in entry.model_used:
                tier_info = f"🆓 `{entry.model_used}`"
            elif "haiku" in entry.model_used or "mini" in entry.model_used:
                tier_info = f"💰 `{entry.model_used}`"
            else:
                tier_info = f"🧠 `{entry.model_used}`"

        task_count = self.get_task_count(entry.project_id, entry.role)

        embed = discord.Embed(
            title=f"{status_emoji} {emoji} {entry.role.upper()} — งานเสร็จ  ⏱️ {dur_str}",
            color=0x22c55e if entry.status == "done" else 0xef4444,
            timestamp=ended_utc,
        )
        embed.add_field(name="📋 Project",      value=f"`{entry.project_id}` {project_name}", inline=False)
        embed.add_field(name="🕐 เริ่ม (Thai)",  value=started_th.strftime("%d/%m/%Y %H:%M:%S"), inline=True)
        embed.add_field(name="🕑 เสร็จ (Thai)",  value=ended_th.strftime("%d/%m/%Y %H:%M:%S"),   inline=True)
        embed.add_field(name="⏱️ ใช้เวลา",       value=f"**{dur_str}**",                          inline=True)
        embed.add_field(name="📊 Task #",         value=f"#{task_count} สำหรับ project นี้",       inline=True)

        if tier_info:
            embed.add_field(name="🤖 Model", value=tier_info, inline=True)
        if entry.cost_usd > 0:
            cost_thb = entry.cost_usd * 35
            embed.add_field(
                name="💰 Cost",
                value=f"${entry.cost_usd:.5f} (≈฿{cost_thb:.4f})",
                inline=True,
            )

        files = [f for f in entry.output_files.split(",") if f]
        if files:
            embed.add_field(
                name=f"📄 Output ({len(files)} ไฟล์)",
                value="\n".join(f"• `{f}`" for f in files[:8]),
                inline=False,
            )

        embed.set_footer(text=f"Log ID: {entry.id} | {entry.task_description[:80]}")
        return embed

    def build_project_summary_embed(self, project_id: str, project_name: str) -> discord.Embed:
        """สรุป time log ทั้ง project"""
        logs = self.get_project_logs(project_id)

        embed = discord.Embed(
            title=f"📊 Time Log Summary — {project_name}",
            color=0x6366f1,
        )

        total_seconds = sum(e.duration_seconds or 0 for e in logs)
        total_cost    = sum(e.cost_usd for e in logs)
        mins, secs    = divmod(total_seconds, 60)
        hours, mins   = divmod(mins, 60)

        embed.add_field(name="⏱️ Total Time", value=f"{hours}h {mins}m {secs}s", inline=True)
        embed.add_field(name="💰 Total Cost", value=f"${total_cost:.4f}",          inline=True)
        embed.add_field(name="📝 Log Entries", value=str(len(logs)),               inline=True)

        rows = []
        for e in logs:
            emoji = self.ROLE_EMOJI.get(e.role, "🤖")
            dur   = timedelta(seconds=e.duration_seconds or 0)
            m, s  = divmod(int(dur.total_seconds()), 60)
            h, m  = divmod(m, 60)
            dur_str = f"{h}h{m}m" if h else f"{m}m{s}s"
            status_e = {"done": "✅", "blocked": "🚫"}.get(e.status, "⏳")
            rows.append(f"{status_e} `{e.role:8}` {emoji} {dur_str}")

        if rows:
            embed.add_field(name="📋 Per Role", value="\n".join(rows), inline=False)

        return embed
