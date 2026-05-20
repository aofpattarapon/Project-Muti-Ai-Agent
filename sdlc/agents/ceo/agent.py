"""
CEO Agent - รับ Requirement จากมนุษย์ และส่งต่อ PM
"""

import os
import re
import uuid
import json
import discord
import logging
from discord.ext import commands
from datetime import datetime, date

from shared.base_agent import BaseAgent
from typing import Optional, List
from shared.storage import Project, TaskStatus, SdlcTask, Epic
from shared.task_catalog import build_project_tasks
from agents.ceo.prompts import CEO_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class CEOAgent(BaseAgent):
    """
    CEO Agent: ประตูแรก รับงานจากมนุษย์ผ่าน Discord
    """

    def __init__(self):
        super().__init__()
        self.role_name = "ceo"

    @property
    def system_prompt(self) -> str:
        return CEO_SYSTEM_PROMPT

    def setup_bot(self):
        bot = super().setup_bot()
        self._register_ceo_commands(bot)
        return bot

    def _register_ceo_commands(self, bot: commands.Bot):

        @bot.command(name="project")
        async def project_cmd(ctx, action: str = "help", *args):
            """CEO Project Commands"""
            if action == "start":
                await self._interactive_project_start(ctx)
            elif action == "status":
                projects = self.storage.list_active_projects()
                if not projects:
                    await ctx.send("📭 ไม่มี Active Projects")
                    return
                embed = discord.Embed(title="📊 Active Projects", color=0xFFD700)
                for p in projects:
                    embed.add_field(
                        name=f"🔖 {p.name}",
                        value=f"ID: `{p.id}`\nStatus: {p.status}\nCurrent: **{p.current_role.upper()}**",
                        inline=False,
                    )
                await ctx.send(embed=embed)
            elif action == "help":
                await ctx.send(
                    "**CEO Agent Commands:**\n"
                    "`!project start` - เริ่ม Project ใหม่\n"
                    "`!project status` - ดู Active Projects\n"
                    "`!status [project_id]` - ดูสถานะ Project"
                )

        @bot.command(name="new")
        async def new_project(ctx, *, requirements: str = None):
            """สร้าง Project ใหม่ด้วย single command (รองรับ attachment .txt/.md/.csv/.xlsx)"""
            from shared.attachment_intake import gather_intake, SUPPORTED_EXTS
            combined, warnings = await gather_intake(ctx.message, requirements or "")
            if not combined.strip():
                await ctx.send(
                    "❌ กรุณาใส่ Requirement:\n"
                    "`!new [ชื่อโปรเจค] | [คำอธิบาย] | [เป้าหมาย]`\n\n"
                    "หรือแนบไฟล์ พร้อม `!new` "
                    f"(รองรับ: {', '.join(sorted(SUPPORTED_EXTS))})\n\n"
                    "ตัวอย่าง:\n"
                    "`!new Trading Bot AI | ระบบ AI วิเคราะห์ตลาด crypto | เพิ่ม ROI 20%`"
                )
                return
            for w in warnings:
                await ctx.send(w)
            await self._start_project_from_text(ctx, combined)


    async def _interactive_project_start(self, ctx):
        """Interactive Project Setup"""
        await ctx.send(
            "🚀 **เริ่ม Project ใหม่**\n\n"
            "กรุณาตอบคำถามต่อไปนี้ใน message เดียว format:\n"
            "```\n"
            "Project Name: [ชื่อโปรเจค]\n"
            "Description: [คำอธิบายโดยละเอียด]\n"
            "Goals: [เป้าหมายทางธุรกิจ]\n"
            "Constraints: [ข้อจำกัด เช่น deadline, tech]\n"
            "Priority: [High/Medium/Low]\n"
            "```"
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            response = await ctx.bot.wait_for("message", check=check, timeout=300)
            from shared.attachment_intake import gather_intake
            combined, warnings = await gather_intake(response, response.content)
            for w in warnings:
                await ctx.send(w)
            await self._start_project_from_text(ctx, combined)
        except Exception:
            await ctx.send("⏰ Timeout - กรุณาลองใหม่")

    async def _start_project_from_text(self, ctx, requirements_text: str):
        """สร้าง Project จาก text requirements"""
        # B2: Hard cap — prevent DB bloat + LLM context overflow
        # Raised to 25k to accommodate attachment intake (gather_intake already enforces this limit)
        _MAX_REQ_CHARS = 25_000
        if len(requirements_text) > _MAX_REQ_CHARS:
            await ctx.send(
                f"⚠️ Requirements text ยาวเกินไป ({len(requirements_text):,} chars)\n"
                f"ระบบจะใช้แค่ {_MAX_REQ_CHARS:,} chars แรก"
            )
            requirements_text = requirements_text[:_MAX_REQ_CHARS]

        # Parse approval mode — "approval:auto" or "approval:manual" (default: manual)
        import re as _re
        _approval_match = _re.search(r'approval\s*:\s*(auto|manual)', requirements_text, _re.I)
        approval_mode = _approval_match.group(1).lower() if _approval_match else "manual"
        # Strip approval directive from requirements text so LLM doesn't see it
        if _approval_match:
            requirements_text = _re.sub(r'approval\s*:\s*(auto|manual)\s*', '', requirements_text, flags=_re.I).strip()

        # Parse project name — strip attachment headers and Discord command prefixes first,
        # then look for "Name | description" pipe format or "project name:" key.
        _CMD_PREFIX = re.compile(r'^![\w]+\s*', re.IGNORECASE)
        project_name = "Project"
        for _line in requirements_text.split("\n"):
            _line = _line.strip()
            if not _line or _line.startswith("## Attachment:") or _line.startswith("### "):
                continue
            _line = _CMD_PREFIX.sub("", _line).strip()
            if not _line:
                continue
            if "|" in _line:
                project_name = _line.split("|")[0].strip() or "Project"
                break
            if "project name:" in _line.lower() or "name:" in _line.lower():
                project_name = _line.split(":", 1)[1].strip() or "Project"
                break

        # สร้าง Project
        project_id = str(uuid.uuid4())[:8].upper()
        project = Project(
            id=project_id,
            name=project_name,
            description=requirements_text[:500],
            created_at=datetime.utcnow().isoformat(),
            current_role="ceo",
            status="in_progress",
            discord_guild_id=str(ctx.guild.id),
            approval_channel_id=os.getenv("DISCORD_APPROVAL_CHANNEL_ID", ""),
            metadata={"channel_id": str(ctx.channel.id), "approval_mode": approval_mode},
        )
        self.storage.create_project(project)

        _mode_label = "✅ Auto-approve" if approval_mode == "auto" else "👤 Manual approve"
        await ctx.send(
            f"✅ สร้าง Project สำเร็จ!\n"
            f"**Project ID:** `{project_id}`\n"
            f"**Name:** {project_name}\n"
            f"**Approval Mode:** {_mode_label}\n\n"
            f"CEO Agent กำลังวิเคราะห์ Requirement... ⏳"
        )

        # Hot cache: update web dashboard "Current Project" widget immediately
        from shared.web_bridge import get_bridge
        _req_preview = requirements_text[:120].replace("\n", " ")
        await get_bridge().hot_cache_update(
            role_key="ceo",
            project_id=project_id,
            project_name=project_name,
            summary=f"Project started — {_req_preview}",
            status="in_progress",
        )

        # สร้าง CEO sdlc_tasks (project_brief + epics)
        self._create_ceo_sdlc_tasks(project_id, project_name, requirements_text)

        await ctx.send(
            f"📋 CEO tasks สร้างแล้ว — `project_brief` และ `epics`\n"
            f"Bot จะเริ่มทำงานในไม่กี่วินาที..."
        )

    def _create_ceo_sdlc_tasks(self, project_id: str, project_name: str, requirements: str):
        """สร้าง CEO sdlc_tasks สำหรับ project ใหม่"""
        from shared.task_catalog import TASK_CATALOG
        now = datetime.utcnow().isoformat()
        project_epic_id = f"{project_id}-PROJECT"
        today = date.today().strftime("%d/%m/%Y")
        prev_id = None
        for i, tdef in enumerate(TASK_CATALOG["ceo"], start=1):
            tid = f"{project_epic_id}-CEO{i:02d}"
            input_data = json.dumps({
                "requirements": requirements,
                "project_name": project_name,
                "today": today,
                "project_brief_content": "",  # filled by previous task hook
            })
            task = SdlcTask(
                id=tid, project_id=project_id, epic_id=project_epic_id,
                task_number=i, role="ceo", task_type=tdef["task_type"],
                title=tdef["title"], description="",
                output_file=tdef["output_file"], output_format=tdef["output_format"],
                depends_on=prev_id or "", status="pending",
                input_data=input_data, output_data="",
                approval_msg_id="", revision_count=0, notes="",
                created_at=now, updated_at=now,
            )
            self.storage.create_sdlc_task(task)
            prev_id = tid

    async def _on_sdlc_task_completed(self, task: SdlcTask, content: str):
        """CEO post-completion hooks"""
        await super()._on_sdlc_task_completed(task, content)  # G4 epic completion check
        if task.task_type == "project_brief":
            self._inject_brief_into_epics_task(task.project_id, content)
            return
        if task.task_type != "epics":
            return
        try:
            project = self.storage.get_project(task.project_id)
            project_name = project.name if project else task.project_id

            epics = self._parse_epics_markdown(content, task.project_id)
            logger.info(f"[CEO] parsed {len(epics)} epics from task {task.id}")

            # ─── G3: Notify on epic parse failure ────────────────
            if not epics:
                logger.error(f"[CEO] epic parse returned 0 epics for {task.id}")
                guilds = self.bot.guilds
                if guilds:
                    from shared.channel_config import ROLE_CHANNELS, get_guild_channel
                    role_ch = ROLE_CHANNELS.get("ceo")
                    if role_ch:
                        out_ch = await get_guild_channel(guilds[0], role_ch.output)
                        if out_ch:
                            await out_ch.send(
                                f"❌ **[CEO] Epic Parse Failed** — project `{task.project_id}`\n"
                                f"ไม่พบ Epic structure ใน `epics.md` — LLM ต้องตอบด้วย pattern:\n"
                                f"```\n## EPIC-001: Epic Title\n**Priority:** P0\n**เป้าหมาย:** ...\n```\n"
                                f"Reply `!revise` ต่อ message นี้เพื่อ regenerate epics task `{task.id}`\n"
                                f"หรือ `!sdlc_retry {task.id}` เพื่อ re-run"
                            )
                return

            for epic in epics:
                try:
                    self.storage.create_epic(epic)
                except Exception:
                    pass  # may already exist on retry

            # สร้าง tasks สำหรับทุก role ยกเว้น ceo
            epic_dicts = [{"id": e.id, "title": e.title, "goal": e.goal,
                           "priority": e.priority, "user_stories": []} for e in epics]
            all_tasks = build_project_tasks(
                task.project_id, epic_dicts,
                include_roles=["pm", "ba", "sa", "uxui", "dev", "qa", "devops"],
            )

            # Inject shared context into every task's input_data
            brief_task = self._get_completed_ceo_task(task.project_id, "project_brief")
            brief_content = brief_task.output_data if brief_task else ""
            today = date.today().strftime("%d/%m/%Y")
            # Pull full requirements from CEO task input_data (never truncated)
            _ceo_inp = json.loads(task.input_data or "{}")
            full_requirements = _ceo_inp.get("requirements", "")

            created = 0
            for tdef in all_tasks:
                try:
                    inp = json.loads(tdef.get("input_data", "{}") or "{}")
                    inp["project_brief"] = brief_content
                    inp["epics_content"] = content
                    inp["project_name"] = project_name
                    inp["today"] = today
                    inp["requirements"] = full_requirements
                    tdef["input_data"] = json.dumps(inp)
                    self.storage.create_sdlc_task(SdlcTask(**tdef))
                    created += 1
                except Exception as e:
                    logger.warning(f"[CEO] skip task {tdef.get('id')}: {e}")

            logger.info(f"[CEO] created {created}/{len(all_tasks)} sdlc_tasks for project {task.project_id}")
        except Exception as e:
            logger.error(f"[CEO] epic parse/create error: {e}", exc_info=True)

    def _inject_brief_into_epics_task(self, project_id: str, brief_content: str):
        """อัปเดต input_data ของ epics task ให้มี project_brief_content"""
        project_epic_id = f"{project_id}-PROJECT"
        epics_task_id = f"{project_epic_id}-CEO02"
        epics_task = self.storage.get_sdlc_task(epics_task_id)
        if not epics_task:
            return
        try:
            inp = json.loads(epics_task.input_data or "{}")
            inp["project_brief_content"] = brief_content
            with __import__("sqlite3").connect(self.storage.db_path) as conn:
                conn.execute(
                    "UPDATE sdlc_tasks SET input_data=? WHERE id=?",
                    (json.dumps(inp), epics_task_id),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"[CEO] inject_brief error: {e}")

    def _get_completed_ceo_task(self, project_id: str, task_type: str) -> Optional[SdlcTask]:
        for t in self.storage.list_sdlc_tasks(project_id=project_id, role="ceo"):
            if t.task_type == task_type and t.status == "completed":
                return t
        return None

    def _parse_epics_markdown(self, content: str, project_id: str) -> List[Epic]:
        """แปลง epics.md markdown → list of Epic objects"""
        epics = []
        seen_nums: set = set()   # E1: dedup — LLM บางครั้ง output EPIC-001 ซ้ำ
        now = datetime.utcnow().isoformat()

        for m in re.finditer(r'##\s+EPIC-(\d+):\s*(.+?)(?:\n|\Z)', content):
            epic_num = int(m.group(1))

            # E1: skip out-of-range or duplicate epic numbers
            if epic_num < 1 or epic_num > 99:
                logger.warning(f"[CEO] skipping EPIC-{epic_num:03d}: out of range (1-99)")
                continue
            if epic_num in seen_nums:
                logger.warning(f"[CEO] skipping duplicate EPIC-{epic_num:03d}")
                continue
            seen_nums.add(epic_num)

            title = m.group(2).strip()
            epic_id = f"{project_id}-E{epic_num:03d}"

            # หา goal — บรรทัด **เป้าหมาย:** ถัด header
            goal_m = re.search(
                rf'EPIC-{epic_num:03d}[^\n]*\n.*?\*\*เป้าหมาย:\*\*\s*(.+?)(?:\n|$)',
                content, re.DOTALL,
            )
            goal = goal_m.group(1).strip() if goal_m else title

            # หา priority
            priority_m = re.search(
                rf'EPIC-{epic_num:03d}[^\n]*\n.*?\*\*Priority:\*\*\s*(P\d)',
                content, re.DOTALL,
            )
            priority = priority_m.group(1) if priority_m else "P1"

            # หา effort
            effort_m = re.search(
                rf'EPIC-{epic_num:03d}[^\n]*\n.*?\*\*Effort:\*\*\s*(\w+)',
                content, re.DOTALL,
            )
            effort = effort_m.group(1) if effort_m else "M"

            epics.append(Epic(
                id=epic_id, project_id=project_id, epic_number=epic_num,
                title=title, goal=goal, priority=priority, effort=effort,
                user_stories="[]", status="pending", created_at=now,
            ))

        return epics

    def _get_role_metrics(self, output_data: dict) -> dict:
        questions = output_data.get("questions", [])
        files     = output_data.get("files", {})
        return {
            "📄 Documents": str(len(files)),
            "❓ Questions": str(len(questions)) if questions else "0",
        }


def main():
    token = os.getenv("CEO_DISCORD_TOKEN")
    if not token:
        raise ValueError("CEO_DISCORD_TOKEN not set in .env")
    agent = CEOAgent()
    agent.run(token)


if __name__ == "__main__":
    main()
