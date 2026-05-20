"""
Base Discord Bot Agent — unified execution layer + timelog + routing
ทุก Role Agent สืบทอด class นี้
"""

import os
import json
import uuid
import asyncio
import logging
import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

from shared.storage import Storage, Project, RoleTask, TaskStatus, SdlcTask
from shared.llm_client import LLMClient, create_client_for_role
from shared.output_formatter import save_task_output
from shared.model_router import CostTracker, ModelTier, TaskType, get_router, MODELS
from shared.timelog import TimeLogger
from shared.channel_config import (
    ROLE_CHANNELS, get_next_role, get_guild_channel, CONTROL_INPUT,
)
from shared.web_bridge import get_bridge
from shared.dna_bootstrap import get_dna_bootstrap
from shared.output_processor import OutputProcessor
from shared.role_schemas import ROLE_OUTPUT_SPECS, get_role_token_budget
from shared.obsidian_rag import build_rag_context
from shared.obsidian_client import get_obsidian
from shared.execution_contract import (
    DecisionAction,
    ExecutionContext,
    decision_help_text,
    parse_decision_message,
    resolve_execution_context,
    summarize_mode_label,
)


from shared.artifact_collector import collect_artifacts as _collect_artifacts


class BaseAgent(ABC):
    """Base class สำหรับทุก Role Agent — shared execution contract + dynamic routing"""

    def __init__(self):
        self.role_name: str = ""
        self.storage        = Storage()
        self.tracker        = CostTracker()
        self.timelog        = TimeLogger()
        self.bot: commands.Bot = None
        self._output_proc   = OutputProcessor()
        self._running_task_ids: set = set()    # in-process guard; DB claim is the authoritative lock
        self._task_fail_counts: dict = {}     # mirrors attempt_count in DB for the current process
        self._last_actual_model_key: str = "" # set after each call_llm; reflects fallback if used
        self._execution_contexts: dict[str, ExecutionContext] = {}
        # Default LLM: use claude CLI (no API key needed); falls back to anthropic
        _cli_model = MODELS.get("claude-cli/claude-sonnet-4-6")
        _ant_model  = MODELS.get("anthropic/claude-sonnet")
        _model = _cli_model or _ant_model or next(iter(MODELS.values()))
        _key   = "claude-cli/claude-sonnet-4-6" if _cli_model else "anthropic/claude-sonnet"
        self.llm = LLMClient(model_config=_model, model_key=_key)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        pass

    async def process_task(self, project: Project, input_data: dict) -> dict:
        """Legacy role-task pipeline (pre-SDLC). Override only if needed."""
        logger.warning(f"[{self.role_name}] process_task called on agent without implementation — returning stub")
        return {"summary": f"{self.role_name.upper()} stub (SDLC task flow active)", "files": {}}

    def format_discord_output(self, output_data: dict, project: Project) -> str:
        """Standard output-channel format (all roles).  Override _get_role_metrics for role-specific data."""
        role_emoji = {
            "ceo": "👔", "pm": "📋", "ba": "📝", "sa": "🏗️",
            "uxui": "🎨", "dev": "💻", "qa": "🧪", "devops": "🚀",
        }.get(self.role_name, "🤖")
        summary = output_data.get("summary", "")[:350]
        files   = list(output_data.get("files", {}).keys())
        metrics = self._get_role_metrics(output_data)
        lines = [
            f"**{role_emoji} {self.role_name.upper()} Agent — Complete**",
            f"**Project:** {project.name} (`{project.id}`)\n",
            f"**📋 Summary:**",
            summary, "",
        ]
        if metrics:
            lines.append("**📊 Metrics:**")
            lines.extend(f"• {k}: {v}" for k, v in metrics.items())
            lines.append("")
        if files:
            lines.append(f"**📄 Files ({len(files)}):**")
            lines.extend(f"• `{f}`" for f in files[:12])
            if len(files) > 12:
                lines.append(f"• … +{len(files)-12} more")
        for key, val in output_data.items():
            if key.endswith("_instructions") and val:
                next_role = key.replace("_instructions", "").upper()
                lines += [f"\n**📨 {next_role} Instructions:**", str(val)[:200]]
                break
        return "\n".join(lines)

    def _get_role_metrics(self, output_data: dict) -> dict:
        """Role-specific summary metrics shown in embed + output channel. Override per role."""
        return {}

    def _get_next_role_override(self, output_data: dict):
        """Override next role routing (e.g. QA→DEV bug loop). Return role str or None."""
        return None

    async def _pre_llm_hook(self, task: "SdlcTask", input_data: dict) -> dict:
        """Called in _execute_sdlc_task before the LLM prompt is built.
        Override in subclass to inject extra context keys (e.g. test execution results).
        Returned dict is merged into the context passed to _build_sdlc_prompt."""
        return {}

    async def _post_save_hook(self, task: "SdlcTask", output_dir: str, content: str = "") -> None:
        """Called in _execute_sdlc_task after the main artifact is saved.
        Override in subclass to write additional artifacts or inject feedback."""
        pass

    # ─── helper ให้ subclass เรียก LLM ────────────────────────────

    def _effective_system_prompt(self, is_free_model: bool = False) -> str:
        """
        Phase 4 token compression:
        - paid model  → use original system_prompt (full quality)
        - free model  → use DNA-compressed prompt if available (saves ~40-55% tokens)
        """
        if not is_free_model:
            return self.system_prompt
        try:
            dna = get_dna_bootstrap()
            if dna.has_dna(self.role_name):
                return dna.build_dna_system_prompt(self.role_name, self.system_prompt)
        except Exception:
            pass
        # Fallback: inject role output template into base prompt (still saves tokens vs re-explaining format)
        from shared.role_schemas import get_role_template
        template = get_role_template(self.role_name)
        return f"{self.system_prompt}\n\n{template}" if template else self.system_prompt

    async def call_llm(
        self,
        prompt: str,
        project_id: str = "",
        project_name: str = "",
        force_tier: Optional[ModelTier] = None,
        task_type: Optional[TaskType] = None,
        max_tokens: int = None,
        use_obsidian: bool = True,
        force_model_key: str = None,
    ) -> str:
        """
        เรียก LLM ผ่าน Dynamic Router พร้อม DNA injection + Obsidian RAG อัตโนมัติ

        task_type      — ระบุเพื่อ route ไป local model ที่เหมาะก่อน
        max_tokens     — ถ้าไม่ระบุ ใช้ role token budget จาก role_schemas
        use_obsidian   — inject Obsidian project context (default True)
        force_model_key — bypass router; use this exact model key from MODELS dict
        """
        if max_tokens is None:
            max_tokens = get_role_token_budget(self.role_name)

        if task_type is None and project_id and project_id in self._execution_contexts:
            task_type = self._execution_contexts[project_id].task_type

        if force_model_key:
            from shared.model_router import MODELS as _MODELS
            _pref_cfg = _MODELS.get(force_model_key)
            if _pref_cfg:
                from shared.llm_client import LLMClient as _LLC
                client = _LLC(model_config=_pref_cfg, model_key=force_model_key)
                complexity = 50  # mid-range; router not involved
                logger.info(f"[{self.role_name}] force_model_key override: {force_model_key}")
            else:
                logger.warning(f"[{self.role_name}] force_model_key '{force_model_key}' not in MODELS — falling back to router")
                client, complexity = create_client_for_role(
                    role=self.role_name,
                    prompt=prompt,
                    project_id=project_id,
                    force_tier=force_tier,
                    task_type=task_type,
                    system_prompt=self.system_prompt,
                )
        else:
            client, complexity = create_client_for_role(
                role=self.role_name,
                prompt=prompt,
                project_id=project_id,
                force_tier=force_tier,
                task_type=task_type,
                system_prompt=self.system_prompt,
            )

        is_free = client.config.tier.value == "free"
        effective_sys = self._effective_system_prompt(is_free_model=is_free)

        # Obsidian RAG: inject relevant vault notes into the prompt
        # Budget: 600 tokens for free models, 1200 for paid (they can handle more context)
        rag_budget = 600 if is_free else 1200
        if use_obsidian and (project_id or project_name or self.role_name):
            try:
                rag_ctx = build_rag_context(
                    role=self.role_name,
                    project_id=project_id,
                    project_name=project_name,
                    query=prompt[:200],
                    token_budget=rag_budget,
                )
                if rag_ctx:
                    prompt = rag_ctx + "\n\n" + prompt
                    logger.debug(f"[{self.role_name.upper()}] Obsidian RAG injected ({len(rag_ctx)} chars)")
            except Exception as _rag_err:
                logger.debug(f"[{self.role_name.upper()}] RAG skipped: {_rag_err}")

        result = await client.complete(
            system_prompt=effective_sys,
            user_message=prompt,
            max_tokens=max_tokens,
            role=self.role_name,
            project_id=project_id,
            complexity_score=complexity,
            use_dna=False,  # already handled above — don't double-inject
        )
        # Expose actual model used (may differ from initial plan if fallback fired)
        self._last_actual_model_key = client.model_key
        return result

    # ─── Bot Setup ─────────────────────────────────────────────────
    def setup_bot(self) -> commands.Bot:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True

        self.bot = commands.Bot(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            description=f"{self.role_name.upper()} Agent",
        )
        self._register_events()
        self._register_commands()
        return self.bot

    def _register_events(self):
        @self.bot.event
        async def on_ready():
            print(f"✅ [{self.role_name.upper()}] Bot online as {self.bot.user}")
            self.bot.loop.create_task(self._web_decision_poll_loop())
            self.bot.loop.create_task(self._task_poll_loop())
            self.bot.loop.create_task(self._sdlc_task_poll_loop())
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"SDLC | {self.role_name.upper()}"
                )
            )

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return
            content_preview = (message.content or "")[:60].replace("\n", " ")
            print(f"[{self.role_name.upper()}] msg #{message.channel.name} @{message.author.name}: {content_preview!r}", flush=True)
            if await self._handle_approval_message(message):
                return
            await self.bot.process_commands(message)

    def _register_commands(self):

        @self.bot.command(name="status")
        async def status_cmd(ctx, project_id: str = None):
            if project_id:
                project = self.storage.get_project(project_id)
                if project:
                    task = self.storage.get_task_by_project_role(project_id, self.role_name)
                    embed = self._create_status_embed(project, task)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"❌ ไม่พบ Project `{project_id}`")
            else:
                projects = self.storage.list_active_projects()
                if not projects:
                    await ctx.send("📭 ไม่มี Active Projects")
                    return
                embed = discord.Embed(title="📊 Active Projects", color=self._role_color())
                for p in projects[:10]:
                    embed.add_field(
                        name=f"🔖 {p.name}",
                        value=f"ID: `{p.id}` | Phase: **{p.current_role.upper()}**",
                        inline=False,
                    )
                await ctx.send(embed=embed)

        @self.bot.command(name="cost")
        async def cost_cmd(ctx):
            """ดู cost วันนี้"""
            summary = self.tracker.today_summary()
            budget  = summary["budget"]
            spent   = summary["total_spend"]
            remaining = max(0, budget - spent)
            pct = (spent / budget * 100) if budget > 0 else 0

            bar_len = 20
            filled  = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)

            embed = discord.Embed(
                title="💰 LLM Cost Today",
                color=0xff6b6b if pct > 80 else 0x51cf66,
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Budget", value=f"${budget:.2f}/day", inline=True)
            embed.add_field(name="Spent",  value=f"${spent:.4f}", inline=True)
            embed.add_field(name="Left",   value=f"${remaining:.4f}", inline=True)
            embed.add_field(name="Usage",  value=f"`{bar}` {pct:.1f}%", inline=False)

            if summary["breakdown"]:
                lines = []
                tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}
                for row in summary["breakdown"][:8]:
                    e = tier_emoji.get(row["tier"], "")
                    lines.append(
                        f"{e} `{row['model']}` — "
                        f"{row['calls']} calls, ${row['cost_usd']:.5f}"
                    )
                embed.add_field(name="Breakdown", value="\n".join(lines), inline=False)

            await ctx.send(embed=embed)

        @self.bot.command(name="model")
        async def model_cmd(ctx, *, prompt_preview: str = "test task"):
            """ดูว่า prompt นี้จะใช้ model อะไร + DNA status"""
            info = get_router().get_routing_summary(prompt_preview, self.role_name)
            tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(info["tier"], "")
            dna = get_dna_bootstrap()
            has_dna     = dna.has_dna(self.role_name)
            has_style   = dna.get_style_ref(self.role_name) is not None

            embed = discord.Embed(
                title=f"🔀 Model Routing — {self.role_name.upper()}",
                color=self._role_color(),
            )
            embed.add_field(name="Model",    value=f"`{info['model_id']}`",           inline=True)
            embed.add_field(name="Provider", value=info["provider"].upper(),           inline=True)
            embed.add_field(name="Tier",     value=f"{tier_emoji} {info['tier'].upper()}", inline=True)
            embed.add_field(name="Complexity",      value=f"{info['complexity_score']}/100", inline=True)
            embed.add_field(name="Est. Cost",       value=f"~${info['estimated_cost']:.5f}", inline=True)
            embed.add_field(name="Budget Left",     value=f"${info['budget_remaining']:.4f}", inline=True)
            embed.add_field(name="🧬 DNA Cached",   value="✅ Yes" if has_dna else "❌ No — run !bootstrap", inline=True)
            embed.add_field(name="🪞 Style Ref",    value="✅ Yes" if has_style else "⏳ Pending paid call", inline=True)
            await ctx.send(embed=embed)

        @self.bot.command(name="bootstrap")
        async def bootstrap_cmd(ctx, project_context: str = ""):
            """Bootstrap DNA for this role using paid model (one-time cost)"""
            await ctx.send(
                f"🧬 **Bootstrapping DNA** for **{self.role_name.upper()}**...\n"
                f"Using paid model to create optimized prompts + style DNA."
            )
            try:
                dna = await get_dna_bootstrap().bootstrap_role(
                    self.role_name,
                    project_context=project_context,
                    force_refresh=True,
                )
                embed = discord.Embed(
                    title=f"🧬 DNA Bootstrap Complete — {self.role_name.upper()}",
                    color=0x24e08a,
                )
                embed.add_field(
                    name="Compressed Prompt",
                    value=f"`{len(dna.get('compressed_system_prompt', ''))}` chars",
                    inline=True,
                )
                embed.add_field(
                    name="Format Rules",
                    value=str(len(dna.get("format_rules", []))),
                    inline=True,
                )
                embed.add_field(
                    name="Has Few-Shot",
                    value="✅" if dna.get("few_shot_snippet") else "❌",
                    inline=True,
                )
                embed.add_field(
                    name="Anti-patterns",
                    value=str(len(dna.get("anti_patterns", []))),
                    inline=True,
                )
                embed.set_footer(text="Free model calls will now use this DNA automatically")
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"❌ Bootstrap failed: `{e}`")

        @self.bot.command(name="dna_status")
        async def dna_status_cmd(ctx):
            """แสดง DNA cache status ทุก role"""
            entries = get_dna_bootstrap().list_cached_roles()
            if not entries:
                await ctx.send("🧬 No DNA cached yet. Run `!bootstrap` to create.")
                return
            embed = discord.Embed(title="🧬 DNA Cache Status", color=0x4f8cff)
            for e in entries:
                embed.add_field(
                    name=f"{e['role'].upper()} [{e['type']}]",
                    value=f"Model: `{e['model']}`\nUpdated: {e['updated_at'][:16]}",
                    inline=True,
                )
            await ctx.send(embed=embed)

        @self.bot.command(name="dashboard")
        async def dashboard_cmd(ctx, project_id: str = None):
            """SDLC Dashboard — แสดงภาพรวม project + sync link: !dashboard [project_id]"""
            import urllib.parse as _up
            web_url = os.getenv("WEB_APP_URL", "http://localhost:3001")

            projects = self.storage.list_active_projects()
            if not projects:
                await ctx.send("📭 ไม่มี active projects — ใช้ `!new <name> | <description>` เพื่อเริ่ม")
                return

            # If no project_id given, use most recent
            target = next((p for p in projects if p.id == project_id), None) or projects[0]
            all_tasks = self.storage.list_sdlc_tasks(project_id=target.id)

            # Stats per role
            roles = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
            role_emoji = {"ceo": "👑", "pm": "📋", "ba": "📊", "sa": "🏗️",
                          "uxui": "🎨", "dev": "💻", "qa": "🧪", "devops": "🚀"}
            status_icon = {"completed": "✅", "in_progress": "🔄", "pending": "⏳",
                           "waiting_approval": "🕐", "approved": "✅", "rejected": "❌",
                           "failed": "💥"}

            embed = discord.Embed(
                title=f"📊 SDLC Dashboard — {target.name}",
                description=(
                    f"**Project ID:** `{target.id}`\n"
                    f"**Status:** {target.status}\n"
                    f"🌐 [Web Dashboard]({web_url}/workboard) · "
                    f"[Approvals]({web_url}/approvals)"
                ),
                color=0x5865f2,
            )

            total = len(all_tasks)
            done  = sum(1 for t in all_tasks if t.status in ("completed", "approved"))
            pct   = int(done / total * 100) if total else 0
            bar_len = 15
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)

            embed.add_field(
                name="Overall Progress",
                value=f"`{bar}` **{pct}%** ({done}/{total} tasks)",
                inline=False,
            )

            # Per-role breakdown
            role_lines = []
            for role in roles:
                role_tasks = [t for t in all_tasks if t.role == role]
                if not role_tasks:
                    continue
                r_done = sum(1 for t in role_tasks if t.status in ("completed", "approved"))
                r_prog = sum(1 for t in role_tasks if t.status == "in_progress")
                r_wait = sum(1 for t in role_tasks if t.status == "waiting_approval")
                emoji = role_emoji.get(role, "🤖")
                status_str = f"{r_done}/{len(role_tasks)}"
                if r_prog:   status_str += f" 🔄{r_prog}"
                if r_wait:   status_str += f" 🕐{r_wait}"
                role_lines.append(f"{emoji} **{role.upper()}**: {status_str}")

            if role_lines:
                embed.add_field(
                    name="Role Breakdown",
                    value="\n".join(role_lines),
                    inline=False,
                )

            # Recent activity (last 5 completed)
            recent = sorted(
                [t for t in all_tasks if t.status in ("completed", "approved", "in_progress")],
                key=lambda t: t.updated_at,
                reverse=True,
            )[:5]
            if recent:
                activity = "\n".join(
                    f"{status_icon.get(t.status, '❓')} `{t.id}` {t.task_type}"
                    for t in recent
                )
                embed.add_field(name="Recent Activity", value=activity, inline=False)

            # Pending / in_progress
            pending = [t for t in all_tasks if t.status == "pending"]
            in_prog = [t for t in all_tasks if t.status == "in_progress"]
            embed.set_footer(
                text=f"⏳ {len(pending)} pending · 🔄 {len(in_prog)} running · "
                     f"Use !sdlc_status for role detail"
            )

            await ctx.send(embed=embed)

        @self.bot.command(name="sdlc_retry")
        async def sdlc_retry_cmd(ctx, task_id: str = None):
            """Re-queue ด้วย sdlc_task: !sdlc_retry <task_id>"""
            if not task_id:
                await ctx.send("❌ ใส่ task_id: `!sdlc_retry <task_id>`")
                return
            t = self.storage.get_sdlc_task(task_id)
            if not t:
                await ctx.send(f"❌ ไม่พบ task `{task_id}`")
                return
            if t.role != self.role_name:
                await ctx.send(f"❌ Task นี้เป็นของ role `{t.role}` ไม่ใช่ `{self.role_name}`")
                return
            self.storage.manual_retry_sdlc_task(task_id, f"Manual retry by {ctx.author}")
            await ctx.send(
                f"🔁 Re-queued `{task_id}` (`{t.task_type}`) → status=pending\n"
                f"Claim fields cleared. Bot จะรับไปทำใน poll loop ถัดไป (~15s)"
            )

        @self.bot.command(name="sdlc_status")
        async def sdlc_status_cmd(ctx, project_id: str = None):
            """ดู sdlc_tasks ทั้งหมดของ role นี้: !sdlc_status [project_id]"""
            if not project_id:
                # แสดง project ล่าสุดที่ active
                projects = self.storage.list_active_projects()
                if not projects:
                    await ctx.send("📭 ไม่มี active projects")
                    return
                project_id = projects[0].id
            tasks = self.storage.list_sdlc_tasks(project_id=project_id, role=self.role_name)
            if not tasks:
                await ctx.send(f"📭 ไม่มี sdlc_tasks สำหรับ `{self.role_name}` ใน project `{project_id}`")
                return
            embed = discord.Embed(
                title=f"📋 SDLC Tasks — {self.role_name.upper()} | {project_id}",
                color=self._role_color(),
            )
            status_icon = {
                "pending": "⏳", "in_progress": "🔄", "completed": "✅",
                "waiting_approval": "🕐", "approved": "✅", "rejected": "❌", "failed": "💥",
                "paused": "⏸️",
            }
            for t in tasks[:15]:
                icon = status_icon.get(t.status, "❓")
                rev = f" (rev#{t.revision_count})" if t.revision_count > 0 else ""
                embed.add_field(
                    name=f"{icon} `{t.id}`",
                    value=f"{t.task_type}{rev}\n`{t.status}`",
                    inline=True,
                )
            await ctx.send(embed=embed)

        @self.bot.command(name="sdlc_paused")
        async def sdlc_paused_cmd(ctx):
            """List all paused SDLC tasks across all roles: !sdlc_paused"""
            now = datetime.utcnow().isoformat()
            # Fetch both ready-to-resume and still-waiting paused tasks
            ready = self.storage.list_paused_sdlc_tasks(now)
            # All paused (no time filter) by querying directly
            import sqlite3 as _sqlite3
            with _sqlite3.connect(self.storage.db_path) as _conn:
                _all_rows = _conn.execute(
                    "SELECT * FROM sdlc_tasks WHERE status='paused' ORDER BY paused_at DESC LIMIT 20"
                ).fetchall()
            all_paused = [self.storage._row_to_sdlc_task(r) for r in _all_rows]
            if not all_paused:
                await ctx.send("✅ ไม่มี tasks ที่ถูก pause อยู่ตอนนี้")
                return
            ready_ids = {t.id for t in ready}
            embed = discord.Embed(
                title="⏸️ Paused SDLC Tasks",
                color=0xFFA500,
                description=f"Total: {len(all_paused)} paused task(s)",
            )
            for t in all_paused[:10]:
                status_line = "🟢 Ready to resume" if t.id in ready_ids else f"⏳ Retry after: {t.retry_after_at[:19] if t.retry_after_at else 'N/A'} UTC"
                policy = " ⚠️ MANUAL" if t.resume_policy == "manual_token_fix" else ""
                embed.add_field(
                    name=f"`{t.id}` [{t.role.upper()}]{policy}",
                    value=(
                        f"**Reason:** {t.pause_reason}\n"
                        f"**Provider:** {t.pause_provider or 'unknown'} / `{t.pause_model or 'unknown'}`\n"
                        f"{status_line}"
                    ),
                    inline=False,
                )
            embed.set_footer(text="Use !sdlc_resume <task_id> to manually resume a manual_token_fix task")
            await ctx.send(embed=embed)

        @self.bot.command(name="sdlc_resume")
        async def sdlc_resume_cmd(ctx, task_id: str = None):
            """Manually resume a paused task (use for manual_token_fix after rotating API key): !sdlc_resume <task_id>"""
            if not task_id:
                await ctx.send("❌ ใส่ task_id: `!sdlc_resume <task_id>`")
                return
            t = self.storage.get_sdlc_task(task_id)
            if not t:
                await ctx.send(f"❌ ไม่พบ task `{task_id}`")
                return
            if t.status != "paused":
                await ctx.send(f"❌ Task `{task_id}` ไม่ได้อยู่ใน status paused (ปัจจุบัน: `{t.status}`)")
                return
            self.storage.resume_paused_sdlc_task(task_id)
            policy_note = " (manual_token_fix — ตรวจสอบ API key แล้ว)" if t.resume_policy == "manual_token_fix" else ""
            await ctx.send(
                f"▶️ Resumed `{task_id}` (`{t.task_type}`){policy_note}\n"
                f"Status → `pending` — bot จะ pick up ใน poll loop ถัดไป (~15s)"
            )
            await get_bridge().post_event(
                role_key=self.role_name,
                event_type="agent.task.resumed.discord",
                task_name=t.task_type or task_id,
                status="pending",
                summary=f"Task {task_id} manually resumed via Discord.",
                sdlc_task_id=task_id,
                project_id=t.project_id if hasattr(t, "project_id") else "",
                actor=str(ctx.author),
            )

    # ─── Approval Handling ─────────────────────────────────────────

    async def _handle_approval_message(self, message: discord.Message) -> bool:
        content = message.content.strip()
        role_ch = ROLE_CHANNELS.get(self.role_name)
        if not role_ch:
            return False
        if message.channel.name not in {role_ch.approve, role_ch.output, role_ch.room}:
            return False
        if not message.reference:
            return False

        ref_msg_id = str(message.reference.message_id)

        # ─── Try role_task (legacy flow) ──────────────────────────
        task = self.storage.get_pending_approval_task(ref_msg_id)
        if task and task.role == self.role_name:
            intent = parse_decision_message(content)
            if not intent:
                return False
            if intent.action == DecisionAction.APPROVE:
                await self._handle_approve(message, task, intent.note)
            elif intent.action == DecisionAction.REWORK:
                await self._handle_revise(message, task, intent.note)
            elif intent.action == DecisionAction.REJECT:
                await self._handle_reject(message, task, intent.note)
            return True

        # ─── Try sdlc_task (new SDLC flow) ────────────────────────
        sdlc_task = self.storage.get_sdlc_task_by_approval_msg(ref_msg_id)
        if sdlc_task and sdlc_task.role == self.role_name:
            intent = parse_decision_message(content)
            if not intent:
                return False
            await self._handle_sdlc_decision(message, sdlc_task, intent)
            return True

        return False

    async def _handle_sdlc_decision(self, message: discord.Message, task: SdlcTask, intent):
        """Handle !approve / !revise / !reject for an sdlc_task reply."""
        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else task.project_id

        if intent.action == DecisionAction.APPROVE:
            self.storage.update_sdlc_task_status(task.id, "approved", f"Approved by {message.author}")
            await message.channel.send(
                f"✅ **SDLC Task Approved** — `{task.id}`\n"
                f"Task `{task.task_type}` marked approved — downstream tasks unblocked"
                + (f"\n📝 {intent.note}" if intent.note else "")
            )
            await get_bridge().approved(
                role_key=self.role_name,
                project_id=task.project_id,
                project_name=project_name,
                task_name=task.title,
                next_role=None,
                approver=str(message.author),
                sdlc_task_id=task.id,
            )
            try:
                _updated = self.storage.get_sdlc_task(task.id)
                await self._on_sdlc_task_completed(_updated or task, (_updated or task).output_data or "")
            except Exception as _hook_err:
                logger.warning(f"[{self.role_name}] post-discord-approve hook error: {_hook_err}")

        elif intent.action == DecisionAction.REWORK:
            note = intent.note or "Revision requested"
            revision_num = task.revision_count + 1
            self.storage.request_sdlc_task_revision(task.id, note)
            await message.channel.send(
                f"🔄 **SDLC Task Revision #{revision_num}** — `{task.id}`\n"
                f"Task `{task.task_type}` re-queued for revision\n"
                f"📝 Note: {note}"
            )
            await get_bridge().revision_requested(
                role_key=self.role_name,
                project_id=task.project_id,
                project_name=project_name,
                task_name=task.title,
                comment=note,
                revision_count=revision_num,
                approver=str(message.author),
                sdlc_task_id=task.id,
            )

        elif intent.action == DecisionAction.REJECT:
            reason = intent.note or "Rejected"
            self.storage.update_sdlc_task_status(task.id, "rejected", reason)
            await message.channel.send(
                f"❌ **SDLC Task Rejected** — `{task.id}`\n"
                f"Task `{task.task_type}` marked rejected\n"
                f"📝 Reason: {reason}"
            )
            await get_bridge().rejected(
                role_key=self.role_name,
                project_id=task.project_id,
                project_name=project_name,
                task_name=task.title,
                reason=reason,
                approver=str(message.author),
                sdlc_task_id=task.id,
            )

    async def _handle_approve(self, message: discord.Message, task: RoleTask, note: str = ""):
        output_data = {}
        try:
            output_data = json.loads(task.output_data or "{}")
        except Exception:
            pass

        # Check for role-specific routing override (e.g., QA→DEV bug loop)
        override_role = self._get_next_role_override(output_data)
        if override_role:
            self.storage.set_role_feedback(task.project_id, override_role, output_data)

        self.storage.update_task_status(task.id, TaskStatus.APPROVED, "Approved")
        project = self.storage.get_project(task.project_id)
        next_role = override_role or self.storage.get_next_role(self.role_name)

        # ─── Report to Web App ────────────────────────────────────
        await get_bridge().approved(
            role_key=self.role_name,
            project_id=project.id,
            project_name=project.name,
            task_name=f"{self.role_name.upper()} Phase",
            next_role=next_role,
            approver=str(message.author),
            role_task_id=task.id,
        )

        if next_role:
            self.storage.update_project_role(task.project_id, next_role, "in_progress")
            if override_role:
                await message.channel.send(
                    f"🔁 **{self.role_name.upper()} → {override_role.upper()}** (bugs found — returning for fixes)\n"
                    f"Project: `{task.project_id}`"
                )
            else:
                await message.channel.send(
                    f"✅ **Approved!** → ส่งต่อ **{next_role.upper()}** Agent\n"
                    f"Project: `{task.project_id}`"
                    + (f"\n📝 Note: {note}" if note else "")
                )
            await self._notify_next_role(message.guild, next_role, task)
        else:
            self.storage.update_project_role(task.project_id, "completed", "completed")
            total_cost = self.tracker.today_spend()
            await message.channel.send(
                f"🎉 **Project Complete!** `{task.project_id}` — {project.name}\n"
                f"💰 Total cost today: **${total_cost:.4f}**"
                + (f"\n📝 Note: {note}" if note else "")
            )

    async def _handle_revise(self, message: discord.Message, task: RoleTask, comment: str):
        self.storage.update_task_status(task.id, TaskStatus.REVISION_REQUESTED, comment)
        self.storage.increment_revision(task.id)
        project = self.storage.get_project(task.project_id)

        # ─── Report to Web App ────────────────────────────────────
        await get_bridge().revision_requested(
            role_key=self.role_name,
            project_id=project.id,
            project_name=project.name,
            task_name=f"{self.role_name.upper()} Phase",
            comment=comment,
            revision_count=task.revision_count + 1,
            approver=str(message.author),
        )

        await message.channel.send(
            f"🔄 **Revision** → **{task.role.upper()}** แก้ไขตาม: _{comment or 'ไม่มี comment'}_"
        )
        input_data = json.loads(task.input_data)
        input_data["revision_comment"] = comment
        input_data["revision_count"]   = task.revision_count
        await self._execute_and_post_approval(project, input_data, message.guild)

    async def _handle_reject(self, message: discord.Message, task: RoleTask, reason: str):
        self.storage.update_task_status(task.id, TaskStatus.REJECTED, reason)
        self.storage.update_project_role(task.project_id, "rejected", "rejected")
        project = self.storage.get_project(task.project_id)

        # ─── Report to Web App ────────────────────────────────────
        await get_bridge().rejected(
            role_key=self.role_name,
            project_id=project.id,
            project_name=project.name,
            task_name=f"{self.role_name.upper()} Phase",
            reason=reason,
            approver=str(message.author),
        )

        await message.channel.send(
            f"❌ **Rejected** at **{task.role.upper()}** — {reason or '(ไม่ระบุ)'}\n"
            f"Project: `{task.project_id}` หยุดทำงาน"
        )

    # ─── Execute Task ──────────────────────────────────────────────

    async def receive_task(self, project: Project, input_data: dict, guild: discord.Guild):
        """รับงานใหม่ — แจ้งใน room channel"""
        role_ch = ROLE_CHANNELS.get(self.role_name)
        room_ch = await get_guild_channel(guild, role_ch.room) if role_ch else None
        exec_ctx = resolve_execution_context(
            role=self.role_name,
            input_data=input_data,
            project_id=project.id,
            project_name=project.name,
        )
        if room_ch:
            await room_ch.send(
                f"📥 **{self.role_name.upper()} Agent** รับงาน\n"
                f"**Project:** `{project.id}` — {project.name}\n"
                f"🧭 Mode: **{summarize_mode_label(exec_ctx.workflow_mode)}**"
                f" | Task: **{exec_ctx.task_type.value}**\n"
                f"⏳ กำลังเริ่มทำงาน..."
            )
        await self._execute_and_post_approval(project, input_data, guild)

    async def _execute_and_post_approval(
        self, project: Project, input_data: dict, guild: discord.Guild
    ):
        """Execute task → timelog → post output + approval (once per task)"""
        role_ch     = ROLE_CHANNELS.get(self.role_name)
        inbox_ch    = await get_guild_channel(guild, role_ch.inbox)   if role_ch else None
        room_ch     = await get_guild_channel(guild, role_ch.room)    if role_ch else None
        approve_ch  = await get_guild_channel(guild, role_ch.approve) if role_ch else None
        output_ch   = await get_guild_channel(guild, role_ch.output)  if role_ch else None
        tlog_ch     = await get_guild_channel(guild, role_ch.timelog) if role_ch else None

        notify_ch = room_ch or inbox_ch or approve_ch

        try:
            task_id = str(uuid.uuid4())[:8]
            log_id  = f"{self.role_name}-{task_id}"
            exec_ctx = resolve_execution_context(
                role=self.role_name,
                input_data=input_data,
                project_id=project.id,
                project_name=project.name,
            )
            self._execution_contexts[project.id] = exec_ctx
            input_data = {**input_data, "_execution_context": exec_ctx.to_dict()}
            revision_count = exec_ctx.revision_count

            task = RoleTask(
                id=task_id, project_id=project.id, role=self.role_name,
                status=TaskStatus.IN_PROGRESS,
                input_data=json.dumps(input_data), output_data="{}",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                approval_message_id="", revision_count=revision_count, notes="",
            )
            self.storage.create_role_task(task)

            # ─── Start TimeLog ────────────────────────────────────
            task_type = "revision" if revision_count > 0 else "processing"
            log_entry = self.timelog.start(
                log_id=log_id,
                project_id=project.id,
                role=self.role_name,
                task_type=task_type,
                task_description=f"{project.name} — {self.role_name.upper()} phase",
                revision_count=revision_count,
            )
            if tlog_ch:
                start_embed = self.timelog.build_start_embed(log_entry, project.name)
                await tlog_ch.send(embed=start_embed)

            # ─── Model Routing info → room ───────────────────────
            prompt_preview = json.dumps(input_data)[:300]
            routing = get_router().get_routing_summary(
                prompt_preview, self.role_name,
                full_context=(self.system_prompt + "\n\n" + prompt_preview).strip(),
                task_type=exec_ctx.task_type,
            )
            tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(routing["tier"], "")
            if room_ch:
                task_type_label = getattr(routing.get("task_type", "generic"), "value", routing.get("task_type", "generic"))
                await room_ch.send(
                    f"🔀 **Model:** `{routing['model_id']}` {tier_emoji} "
                    f"| mode={summarize_mode_label(exec_ctx.workflow_mode)} "
                    f"| task={task_type_label} "
                    f"| complexity={routing['complexity_score']}/100 "
                    f"| tokens≈{routing.get('prompt_tokens', 0)}"
                )

            # ─── Report task_started → Web App ───────────────────
            start_time = datetime.utcnow()
            await get_bridge().task_started(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=f"{self.role_name.upper()} Phase",
                model_id=routing["model_id"],
                revision_count=revision_count,
            )

            # ─── Process Task ─────────────────────────────────────
            if room_ch:
                await room_ch.send(f"🤖 **{self.role_name.upper()}** กำลังประมวลผล...")
            output_data = await self.process_task(project, input_data)
            end_time = datetime.utcnow()
            duration_seconds = (end_time - start_time).total_seconds()

            # ─── Finish TimeLog ───────────────────────────────────
            output_files = list(output_data.get("files", {}).keys())
            finished = self.timelog.finish(
                log_id=log_id,
                model_used=routing["model_id"],
                cost_usd=routing.get("estimated_cost", 0.0),
                output_files=output_files,
                status="done",
            )
            if tlog_ch and finished:
                finish_embed = self.timelog.build_finish_embed(finished, project.name)
                await tlog_ch.send(embed=finish_embed)

            # ─── Save output files + DB ───────────────────────────
            self.storage.update_task_output(task_id, output_data)
            self.storage.update_task_status(task_id, TaskStatus.WAITING_APPROVAL)
            await self._save_output_files(project.id, output_data)

            # ─── Post output to shared room-output ───────────────
            if output_ch:
                formatted = self.format_discord_output(output_data, project)
                await self._send_long_message(output_ch, formatted)

            # ─── Report task_completed → Web App ─────────────────
            await get_bridge().task_completed(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=f"{self.role_name.upper()} Phase",
                summary=output_data.get("summary", ""),
                files=output_files,
                model_id=routing["model_id"],
                cost_usd=routing.get("estimated_cost", 0.0),
                duration_seconds=duration_seconds,
                revision_count=revision_count,
                artifact_ref=output_data.get("artifact_ref", ""),
            )

            # ─── Post to role-specific approve channel (once per task) ──
            if approve_ch and not task.approval_message_id:
                embed = self._create_approval_embed(project, output_data, task, routing, timelog_entry=finished)
                approval_msg = await approve_ch.send(
                    content=(
                        f"🔔 **Approval Required** — **{self.role_name.upper()}** | {project.name}\n"
                        f"↩️ {decision_help_text()}"
                    ),
                    embed=embed,
                )
                self.storage.set_approval_message(task_id, str(approval_msg.id))

        except Exception as e:
            import traceback
            err_msg = str(e) or type(e).__name__
            err_detail = traceback.format_exc()
            logger.error(f"[{self.role_name}] task error in {log_id}:\n{err_detail}")
            # Mark task as failed so poll loop can retry
            try:
                self.storage.update_task_status(task_id, "failed", err_msg)
            except Exception:
                pass
            self.timelog.finish(log_id, status="blocked")
            await get_bridge().error(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=f"{self.role_name.upper()} Phase",
                error_message=err_msg,
            )
            if notify_ch:
                await notify_ch.send(
                    f"❌ **{self.role_name.upper()} Error**: `{err_msg}`\n"
                    f"Log ID: `{log_id}` — retrying on next poll cycle..."
                )
            raise
        finally:
            self._execution_contexts.pop(project.id, None)

    async def _notify_next_role(self, guild: discord.Guild, next_role: str, current_task: RoleTask):
        """แจ้ง room ของ role ถัดไป"""
        project = self.storage.get_project(current_task.project_id)
        next_channels = ROLE_CHANNELS.get(next_role)
        if next_channels:
            room = await get_guild_channel(guild, next_channels.room)
            if room:
                await room.send(
                    f"📨 **งานใหม่จาก {self.role_name.upper()}**\n"
                    f"**Project:** `{current_task.project_id}` — {project.name}\n"
                    f"**Next:** {next_role.upper()} Agent จะเริ่มทำงาน..."
                )

    async def _save_output_files(self, project_id: str, output_data: dict):
        base_path = os.path.join(
            os.getenv("OUTPUT_BASE_PATH", "/app/outputs"),
            "projects", project_id, self.role_name
        )
        os.makedirs(base_path, exist_ok=True)

        # ── Save explicit files from output_data["files"] ────────────────
        for filename, content in output_data.get("files", {}).items():
            fpath = os.path.join(base_path, filename)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(fpath, mode, **({} if isinstance(content, bytes) else {"encoding": "utf-8"})) as f:
                f.write(content)

        # ── Auto-extract rich artifacts from raw LLM output ──────────────
        raw_llm = output_data.get("raw_llm_output") or output_data.get("summary", "")
        if raw_llm and len(raw_llm) > 100:
            try:
                artifacts = self._output_proc.process(
                    role=self.role_name,
                    raw_output=raw_llm,
                    base_filename=f"{self.role_name}_output",
                )
                saved = self._output_proc.save_to_disk(artifacts, base_path)
                # Merge saved file list back into output_data for Discord embed
                existing = output_data.get("files", {})
                for fname in saved:
                    if fname not in existing:
                        existing[fname] = f"[auto-extracted: {base_path}/{fname}]"
                output_data["files"] = existing
                logger.info(f"[{self.role_name}] OutputProcessor saved {len(saved)} artifacts to {base_path}")
            except Exception as e:
                logger.warning(f"[{self.role_name}] OutputProcessor error: {e}")

        # ── Sync output to Obsidian vault ─────────────────────────────────
        try:
            obs = get_obsidian()
            project_name = output_data.get("project_name", project_id)
            obs.save_project_note(
                project_id=project_id,
                project_name=project_name,
                role=self.role_name,
                content=raw_llm or output_data.get("summary", ""),
            )
        except Exception as _obs_err:
            logger.debug(f"[{self.role_name}] Obsidian sync skipped: {_obs_err}")

    # ─── Embed Builders ───────────────────────────────────────────

    def _create_approval_embed(
        self, project: Project, output_data: dict, task: RoleTask,
        routing: dict = None, timelog_entry: dict = None,
    ) -> discord.Embed:
        import urllib.parse
        role_emoji = {
            "ceo": "👔", "pm": "📋", "ba": "📝", "sa": "🏗️",
            "uxui": "🎨", "dev": "💻", "qa": "🧪", "devops": "🚀",
        }.get(self.role_name, "🤖")
        tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(
            routing.get("tier", "") if routing else "", ""
        )
        model_id  = routing.get("model_id", "?") if routing else "?"
        tier_label = routing.get("tier", "").upper() if routing else "?"
        summary   = output_data.get("summary", "")

        embed = discord.Embed(
            title=f"{role_emoji} {self.role_name.upper()} — {project.name}",
            description=summary[:450] if summary else "*(ไม่มี summary)*",
            color=self._role_color(),
            timestamp=datetime.utcnow(),
        )

        # ── Row 1: Model | Duration & Cost | Rev/Project (all inline) ──
        embed.add_field(
            name="🤖 Model",
            value=f"{tier_emoji} `{model_id}`\n{tier_label}",
            inline=True,
        )
        if timelog_entry:
            if isinstance(timelog_entry, dict):
                dur_s = int(timelog_entry.get("duration_seconds", 0) or 0)
                cost  = float(timelog_entry.get("cost_usd", 0.0) or 0.0)
            else:
                dur_s = int(getattr(timelog_entry, "duration_seconds", None) or 0)
                cost  = float(getattr(timelog_entry, "cost_usd", None) or 0.0)
            mn, s = divmod(dur_s, 60)
            h, mn = divmod(mn, 60)
            dur_str = f"{h}h {mn:02}m {s:02}s" if h else f"{mn}m {s:02}s"
            embed.add_field(
                name="⏱️ Duration & Cost",
                value=f"**{dur_str}**\n`${cost:.5f}`",
                inline=True,
            )
        embed.add_field(
            name="📌 Rev / Project",
            value=f"Rev **#{task.revision_count}**\n`{project.id}`",
            inline=True,
        )

        exec_ctx = self._execution_contexts.get(project.id)
        if exec_ctx:
            embed.add_field(
                name="🧭 Execution",
                value=f"Mode: **{summarize_mode_label(exec_ctx.workflow_mode)}**\nTask: **{exec_ctx.task_type.value}**",
                inline=True,
            )

        # ── Row 2: Role-specific metrics ──────────────────────────────
        metrics = self._get_role_metrics(output_data)
        if metrics:
            embed.add_field(
                name="📊 Metrics",
                value="\n".join(f"• {k}: **{v}**" for k, v in list(metrics.items())[:4]),
                inline=False,
            )

        # ── Row 3: Files with download links ──────────────────────────
        web_url = os.getenv("WEB_APP_URL", "http://localhost:3001")
        files = output_data.get("files", {})
        if files:
            file_links = []
            for fname in list(files.keys()):
                dl_url = (
                    f"{web_url}/api/project-logs/files/download"
                    f"?project={urllib.parse.quote(project.id)}"
                    f"&role={urllib.parse.quote(self.role_name)}"
                    f"&file={urllib.parse.quote(fname)}"
                )
                line = f"• [{fname}]({dl_url})"
                if len("\n".join(file_links + [line])) > 980:
                    file_links.append(f"• … +{len(files) - len(file_links)} more")
                    break
                file_links.append(line)
            embed.add_field(
                name=f"📄 Files ({len(files)})",
                value="\n".join(file_links),
                inline=False,
            )

        # ── Row 4: Next role instructions ─────────────────────────────
        for key, val in output_data.items():
            if key.endswith("_instructions") and val:
                next_role_name = key.replace("_instructions", "").upper()
                embed.add_field(
                    name=f"📨 {next_role_name} Instructions",
                    value=str(val)[:300],
                    inline=False,
                )
                break

        # ── Row 5: View / Export links ────────────────────────────────
        view_url   = f"{web_url}/project-logs?project={project.id}&role={self.role_name}"
        export_url = f"{web_url}/api/project-logs/files?project={project.id}&role={self.role_name}"
        embed.add_field(
            name="🔗 View / Export",
            value=f"[📱 Open in Web App]({view_url})  •  [📦 Export All JSON]({export_url})",
            inline=False,
        )

        embed.set_footer(text=decision_help_text())
        return embed

    def _create_status_embed(self, project: Project, task) -> discord.Embed:
        embed = discord.Embed(title=f"📊 {project.name}", color=self._role_color())
        embed.add_field(name="ID",      value=f"`{project.id}`",    inline=True)
        embed.add_field(name="Phase",   value=project.current_role.upper(), inline=True)
        embed.add_field(name="Status",  value=project.status,       inline=True)
        if task:
            embed.add_field(name="Task Status", value=task.status,  inline=True)
            embed.add_field(name="Revisions",   value=str(task.revision_count), inline=True)
        return embed

    def _role_color(self) -> int:
        return {
            "ceo": 0xFFD700, "pm": 0x4169E1, "ba": 0x32CD32,
            "sa": 0xFF8C00,  "uxui": 0xFF69B4, "dev": 0x9370DB,
            "qa": 0xFF4500,  "devops": 0x20B2AA,
        }.get(self.role_name, 0x808080)

    async def _send_long_message(self, channel: discord.TextChannel, content: str):
        max_len = 1900
        if len(content) <= max_len:
            await channel.send(content)
            return
        chunks = [content[i:i+max_len] for i in range(0, len(content), max_len)]
        for i, chunk in enumerate(chunks):
            await channel.send(f"**[{i+1}/{len(chunks)}]** {chunk}")

    # ─── Web Decision Polling ──────────────────────────────────────
    async def _web_decision_poll_loop(self):
        """
        ทุก 15 วิ: ดึง approval items ที่ถูก decide ผ่าน Web UI
        แล้ว execute ใน Discord เหมือนกับที่มนุษย์ reply !approve / !revise / !reject
        """
        await asyncio.sleep(10)  # รอให้ bot พร้อมก่อน
        last_id = 0
        while True:
            try:
                items = await get_bridge().fetch_web_decisions(self.role_name, since_id=last_id)
                for item in items:
                    item_id = item.get("id", 0)
                    if item_id > last_id:
                        last_id = item_id
                    await self._execute_web_decision(item)
            except Exception as e:
                logger.warning(f"[{self.role_name}] web decision poll error: {e}")
            await asyncio.sleep(15)

    async def _execute_web_decision(self, item: dict):
        """Execute a decision made via the web UI in Discord."""
        decision = item.get("status", "")
        task_name = item.get("task_name", "")
        note = item.get("decision_note", "") or ""
        approver = item.get("approver", "web-ui")
        item_id = item.get("id", 0)

        guilds = self.bot.guilds
        if not guilds:
            return
        guild = guilds[0]

        approval_ch_id = os.getenv("DISCORD_APPROVAL_CHANNEL_ID")
        approval_ch = guild.get_channel(int(approval_ch_id)) if approval_ch_id else None

        # ─── Prefer sdlc_task_id lookup (exact identity, status-guarded) ─────
        # Falls back to title lookup (legacy items that predate identity fields)
        sdlc_task_id_from_item = (item.get("sdlc_task_id") or "").strip()
        if sdlc_task_id_from_item:
            sdlc_task = self.storage.get_sdlc_task_waiting_approval(sdlc_task_id_from_item)
        else:
            sdlc_task = self.storage.get_sdlc_task_by_title(task_name, self.role_name)

        if sdlc_task:
            project = self.storage.get_project(sdlc_task.project_id)
            project_name = project.name if project else sdlc_task.project_id

            if approval_ch:
                await approval_ch.send(
                    f"🌐 **Web UI Decision (SDLC)** — `{approver}` marked `{self.role_name.upper()}` as **{decision.upper()}**\n"
                    f"**Task:** {task_name}\n"
                    + (f"**Note:** {note}" if note else "")
                )

            if decision == "approved":
                self.storage.update_sdlc_task_status(sdlc_task.id, "approved", f"Approved by {approver}")
                await get_bridge().approved(
                    role_key=self.role_name, project_id=sdlc_task.project_id,
                    project_name=project_name, task_name=task_name,
                    next_role=None, approver=approver,
                    sdlc_task_id=sdlc_task.id,
                )
                try:
                    _updated = self.storage.get_sdlc_task(sdlc_task.id)
                    await self._on_sdlc_task_completed(_updated or sdlc_task, (_updated or sdlc_task).output_data or "")
                except Exception as _hook_err:
                    logger.warning(f"[{self.role_name}] post-web-approve hook error: {_hook_err}")
            elif decision == "rework_requested":
                revision_num = sdlc_task.revision_count + 1
                self.storage.request_sdlc_task_revision(sdlc_task.id, note or "Web rework")
                await get_bridge().revision_requested(
                    role_key=self.role_name, project_id=sdlc_task.project_id,
                    project_name=project_name, task_name=task_name,
                    comment=note, revision_count=revision_num, approver=approver,
                    sdlc_task_id=sdlc_task.id,
                )
            elif decision == "rejected":
                self.storage.update_sdlc_task_status(sdlc_task.id, "rejected", note)
                await get_bridge().rejected(
                    role_key=self.role_name, project_id=sdlc_task.project_id,
                    project_name=project_name, task_name=task_name,
                    reason=note, approver=approver,
                    sdlc_task_id=sdlc_task.id,
                )
            # Mark the web approval item processed so it is excluded from future polls
            if item_id:
                await get_bridge().mark_decision_processed(item_id, decision)
            return

        # ─── Fallback: role_task (legacy flow) ───────────────────────────────
        task = self.storage.get_pending_approval_task_by_name(task_name, self.role_name)
        if not task:
            return  # ไม่ใช่ task ของ role นี้

        if approval_ch:
            await approval_ch.send(
                f"🌐 **Web UI Decision** — `{approver}` marked **{self.role_name.upper()}** task as **{decision.upper()}**\n"
                f"**Task:** {task_name}\n"
                f"{'**Note:** ' + note if note else ''}"
            )

        if decision == "approved":
            self.storage.update_task_status(task.id, TaskStatus.APPROVED, note or "Web approved")
            project = self.storage.get_project(task.project_id)
            next_role = self.storage.get_next_role(self.role_name)
            await get_bridge().approved(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=task_name,
                next_role=next_role,
                approver=approver,
                role_task_id=task.id,
            )
            if next_role and approval_ch:
                self.storage.update_project_role(task.project_id, next_role, "in_progress")
                await self._notify_next_role(guild, next_role, task)

        elif decision == "rework_requested":
            revision_count = task.revision_count + 1
            self.storage.update_task_status(task.id, TaskStatus.REVISION_REQUESTED, note)
            project = self.storage.get_project(task.project_id)
            await get_bridge().revision_requested(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=task_name,
                comment=note,
                revision_count=revision_count,
                approver=approver,
                role_task_id=task.id,
            )
            await self._execute_and_post_approval(
                project, {"revision_comment": note, "revision_count": revision_count}, guild
            )

        elif decision == "rejected":
            self.storage.update_task_status(task.id, TaskStatus.REJECTED, note)
            project = self.storage.get_project(task.project_id)
            await get_bridge().rejected(
                role_key=self.role_name,
                project_id=project.id,
                project_name=project.name,
                task_name=task_name,
                reason=note,
                approver=approver,
                role_task_id=task.id,
            )

        # Mark the web approval item processed so it is excluded from future polls
        if item_id:
            await get_bridge().mark_decision_processed(item_id, decision)

    # ─── Pipeline Auto-Trigger ─────────────────────────────────────
    async def _task_poll_loop(self):
        """Every 20s: check DB for projects where current_role = me and start if needed."""
        await asyncio.sleep(25)  # staggered start after web decision poller
        while True:
            try:
                await self._check_and_start_pending_task()
            except Exception as e:
                logger.warning(f"[{self.role_name}] task poll error: {e}")
            await asyncio.sleep(20)

    async def _check_and_start_pending_task(self):
        projects = self.storage.list_active_projects()
        for project in projects:
            if project.current_role != self.role_name:
                continue
            # G5: Skip old role_task pipeline if this project uses the new SDLC task flow
            if self.storage.list_sdlc_tasks(project_id=project.id, role=self.role_name):
                continue
            existing = self.storage.get_task_by_project_role(project.id, self.role_name)
            if existing and existing.status in ("in_progress", "waiting_approval", "approved"):
                continue
            input_data = self._build_input_from_previous_role(project)
            guilds = self.bot.guilds
            if guilds:
                logger.info(f"[{self.role_name}] auto-starting for project {project.id}")
                await self.receive_task(project, input_data, guilds[0])

    def _build_input_from_previous_role(self, project: Project) -> dict:
        from shared.channel_config import WORKFLOW_ORDER
        base = {"project_name": project.name, "requirements": project.description}
        try:
            idx = WORKFLOW_ORDER.index(self.role_name)
        except ValueError:
            return base
        if idx == 0:
            return base
        prev_role = WORKFLOW_ORDER[idx - 1]
        prev_task = self.storage.get_task_by_project_role(project.id, prev_role)
        if prev_task and prev_task.output_data and prev_task.output_data != "{}":
            input_data = {
                "previous_output": json.loads(prev_task.output_data),
                "project_name": project.name,
            }
        else:
            input_data = base
        # Inject cross-role feedback (e.g., QA bug report → DEV fix)
        feedback = self.storage.get_role_feedback(project.id, self.role_name)
        if feedback:
            input_data["role_feedback"] = feedback
            self.storage.clear_role_feedback(project.id, self.role_name)
        return input_data

    # ─── SDLC Task Poll Loop (Epic-based) ─────────────────────────

    async def _sdlc_task_poll_loop(self):
        """ทุก 15 วิ: ตรวจ sdlc_tasks ที่รอ (pending + deps satisfied) แล้วประมวลผล"""
        await asyncio.sleep(30)  # stagger after main poll loops
        while True:
            try:
                await self._check_and_start_sdlc_tasks()
            except Exception as e:
                logger.warning(f"[{self.role_name}] sdlc_task poll error: {e}")
            await asyncio.sleep(15)

    async def _check_and_start_sdlc_tasks(self):
        # Must have a guild to post Discord output — bail early so we never
        # claim a task that we can't execute (which would leave it stuck in_progress).
        guilds = self.bot.guilds
        if not guilds:
            logger.debug(f"[{self.role_name}] No guild connected — skipping sdlc task poll")
            return

        # Recover tasks that were claimed but never finished (e.g. bot crashed mid-task)
        for task_id, new_status in self.storage.recover_stale_sdlc_tasks(self.role_name):
            logger.warning(f"[{self.role_name}] Stale task recovered: {task_id} → {new_status}")

        tasks = self.storage.list_pending_sdlc_tasks(self.role_name)
        for task in tasks:
            if task.id in self._running_task_ids:
                continue
            # DB-level atomic claim (also verifies role match) — guards against
            # duplicate execution across restarts and multiple bot instances.
            if not self.storage.claim_sdlc_task(task.id, self.role_name):
                continue  # lost the race, or role mismatch
            self._running_task_ids.add(task.id)
            try:
                logger.info(f"[{self.role_name}] starting sdlc task {task.id} ({task.task_type})")
                await self._execute_sdlc_task(task, guilds[0])
            except Exception as e:
                _MAX_AUTO_RETRIES = 2
                # Prefer persisted attempt_count so restarts don't reset the counter
                _fresh = self.storage.get_sdlc_task(task.id)
                err_msg = str(e)[:300]
                # already_recorded=True means a hook already called record_sdlc_task_error;
                # use the DB count as-is (no +1) to avoid incrementing attempt_count twice.
                _already_recorded = getattr(e, "already_recorded", False)
                if _already_recorded:
                    fail_count = _fresh.attempt_count if _fresh else 1
                else:
                    fail_count = (_fresh.attempt_count if _fresh else 0) + 1
                self._task_fail_counts[task.id] = fail_count
                _exhausted = fail_count > _MAX_AUTO_RETRIES
                if not _already_recorded:
                    # Normal path: record the error here (single owner)
                    self.storage.record_sdlc_task_error(
                        task.id, err_msg, fail_count, requeue=not _exhausted
                    )
                elif _exhausted:
                    # Hook recorded with requeue=True but retries are exhausted — flip to failed
                    self.storage.record_sdlc_task_error(task.id, err_msg, fail_count, requeue=False)
                if _exhausted:
                    logger.error(f"[{self.role_name}] sdlc task {task.id} FAILED after {fail_count} attempts: {err_msg}")
                    self._task_fail_counts.pop(task.id, None)
                    role_ch = ROLE_CHANNELS.get(self.role_name)
                    if role_ch:
                        out_ch = await get_guild_channel(guilds[0], role_ch.output)
                        if out_ch:
                            await out_ch.send(
                                f"💥 **Task Failed** — `{task.id}` (`{task.task_type}`)\n"
                                f"Failed after {fail_count} attempts. Use `!sdlc_retry {task.id}` to re-queue.\n"
                                f"Error: `{err_msg}`"
                            )
                else:
                    logger.warning(
                        f"[{self.role_name}] sdlc task {task.id} failed "
                        f"(attempt {fail_count}/{_MAX_AUTO_RETRIES}): {err_msg}"
                    )
            finally:
                self._running_task_ids.discard(task.id)

    async def _execute_sdlc_task(self, task: SdlcTask, guild: discord.Guild):
        """Execute 1 sdlc_task → 1 file output"""
        from shared.channel_config import ROLE_CHANNELS, get_guild_channel

        role_ch   = ROLE_CHANNELS.get(self.role_name)
        output_ch = await get_guild_channel(guild, role_ch.output)  if role_ch else None
        tlog_ch   = await get_guild_channel(guild, role_ch.timelog) if role_ch else None

        # Status is already 'in_progress' — set by claim_sdlc_task() before entering here
        log_id = f"{self.role_name}-{task.id}"

        # ─── Build context for the prompt ───────────────────────────
        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else task.project_id
        input_data   = json.loads(task.input_data or "{}")

        context = self._build_sdlc_context(task, project_name, input_data)

        # ─── Role-specific pre-LLM hook ──────────────────────────────
        # Subclasses (e.g. QA) override this to inject extra context
        # (test execution results, etc.) before the prompt is built.
        try:
            _extra_ctx = await self._pre_llm_hook(task, input_data)
            if _extra_ctx:
                context.update(_extra_ctx)
        except Exception as _hook_err:
            logger.warning(f"[{self.role_name}] pre-llm hook error: {_hook_err}")

        # ─── Build prompt via role-specific builder ──────────────────
        prompt = self._build_sdlc_prompt(task.task_type, context)

        # ─── G1: Web bridge — task started ──────────────────────────
        await get_bridge().task_started(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            task_name=task.title,
            model_id="pending",
            revision_count=task.revision_count,
        )

        # ─── TimeLog start ───────────────────────────────────────────
        log_entry = self.timelog.start(
            log_id=log_id,
            project_id=task.project_id,
            role=self.role_name,
            task_type="sdlc_task",
            task_description=task.title,
            revision_count=task.revision_count,
        )
        if tlog_ch:
            await tlog_ch.send(embed=self.timelog.build_start_embed(log_entry, project_name))

        # ─── Preferred model override from task_catalog ──────────────
        # If task has a preferred_model key, temporarily swap the LLM client
        from shared.task_catalog import TASK_CATALOG as _TC
        _preferred_model_key = None
        for _tdef in _TC.get(self.role_name, []):
            if _tdef.get("task_type") == task.task_type:
                _preferred_model_key = _tdef.get("preferred_model")
                break

        # ─── Call LLM (G6: show typing indicator while waiting) ──────
        routing = get_router().get_routing_summary(prompt[:300], self.role_name)
        import time as _time
        _start_ts = _time.monotonic()
        _start_wall_ts = _time.time()  # wall-clock for mtime comparison in contract freshness check
        try:
            if output_ch:
                async with output_ch.typing():
                    content = await self.call_llm(
                        prompt=prompt,
                        project_id=task.project_id,
                        project_name=project_name,
                        force_model_key=_preferred_model_key,
                    )
            else:
                content = await self.call_llm(
                    prompt=prompt,
                    project_id=task.project_id,
                    project_name=project_name,
                    force_model_key=_preferred_model_key,
                )
        except Exception as _llm_exc:
            from shared.llm_error_classifier import classify_llm_error
            _err_info = classify_llm_error(_llm_exc)
            if _err_info.is_quota_error:
                # Pause task — do not consume retry budget for provider issues
                await self._pause_task_for_quota(
                    task=task,
                    project_name=project_name,
                    err_info=_err_info,
                    model_key=_preferred_model_key or routing.get("model_id", ""),
                    output_ch=output_ch,
                    log_id=log_id,
                    estimated_cost=routing.get("estimated_cost", 0.0),
                    actual_model=self._last_actual_model_key or routing.get("model_id", "unknown"),
                )
                return  # handled — do not propagate
            raise  # non-quota error: let poll loop handle normally
        _duration = _time.monotonic() - _start_ts
        # actual_model reflects fallback if the primary model failed mid-call
        _actual_model = self._last_actual_model_key or routing.get("model_id", "unknown")
        # Cost is a routing estimate — actual cost is accumulated in LLMClient.tracker
        # and accessible via /usage. Do not present as exact billing.
        _estimated_cost_usd = routing.get("estimated_cost", 0.0)

        # ─── Artifact Validation ─────────────────────────────────────
        # Validate before saving so invalid output never reaches disk/approval.
        _MAX_AUTO_RETRIES = 2
        from shared.artifact_validator import validate_artifact
        _val_ok, _val_error = validate_artifact(content, task.output_format)
        if not _val_ok:
            _fresh = self.storage.get_sdlc_task(task.id)
            _fail_count = ((_fresh.attempt_count if _fresh else 0) + 1)
            self._task_fail_counts[task.id] = _fail_count
            logger.warning(
                f"[{self.role_name}] Validation failed for {task.id} "
                f"(attempt {_fail_count}): {_val_error}"
            )
            # Inject the validation error into input_data so the next LLM call
            # knows exactly what to fix
            self.storage.update_sdlc_task_input_data(
                task.id,
                {"revision_comment": f"[auto-validation] {_val_error}"},
            )
            _requeue = _fail_count <= _MAX_AUTO_RETRIES
            self.storage.record_sdlc_task_error(
                task.id, f"Validation failed: {_val_error}", _fail_count, requeue=_requeue
            )
            # Finish timelog so it doesn't hang open
            self.timelog.finish(log_id=log_id, model_used=_actual_model,
                                cost_usd=_estimated_cost_usd,
                                output_files=[], status="validation_failed")
            if output_ch:
                _status_label = "🔁 will retry" if _requeue else "💥 max retries — marked failed"
                await output_ch.send(
                    f"⚠️ **Validation Failed** — `{task.id}` (`{task.task_type}`)\n"
                    f"**Error:** {_val_error[:200]}\n"
                    f"**Attempt:** {_fail_count}/{_MAX_AUTO_RETRIES + 1} — {_status_label}"
                )
            return

        # ─── Save output file ────────────────────────────────────────
        output_dir = os.path.join(
            os.getenv("OUTPUT_BASE_PATH", "/app/outputs"),
            "projects", task.project_id, task.epic_id, self.role_name,
        )
        saved_path = save_task_output(
            content=content,
            output_file=task.output_file,
            output_format=task.output_format,
            output_dir=output_dir,
        )

        # ─── Role-specific post-save hook ────────────────────────────
        # Subclasses (e.g. QA) override this to save extra artifacts
        # or inject feedback into other tasks after the main file is saved.
        try:
            await self._post_save_hook(task, output_dir, content)
        except Exception as _ph_err:
            # Re-raise so the poll loop handles failure (record error, requeue/fail).
            # Hooks that record errors in DB before raising prevent double-counting.
            logger.warning(f"[{self.role_name}] post-save hook failed: {_ph_err}")
            raise

        # ─── Role Artifact Contract Validation ───────────────────────
        # Collect with freshness filter: secondary files older than attempt start are
        # excluded so stale files from a prior failed attempt don't pass contract checks.
        _artifacts = _collect_artifacts(output_dir, saved_path, task, attempt_started_at=_start_wall_ts)
        _gen_names = {a["path"] for a in _artifacts if a.get("path")}

        from shared.artifact_contracts import validate_role_artifact_contract
        _contract = validate_role_artifact_contract(
            role=self.role_name,
            task_type=task.task_type,
            content=content,
            output_format=task.output_format,
            output_dir=output_dir,
            generated_artifacts=_artifacts,
            attempt_started_at=_start_wall_ts,
        )
        if _contract.status == "failed":
            # Read persisted attempt_count from DB so restart cannot lower the counter
            _fresh_for_contract = self.storage.get_sdlc_task(task.id)
            _fail_count = ((_fresh_for_contract.attempt_count if _fresh_for_contract else 0) + 1)
            self._task_fail_counts[task.id] = _fail_count
            _requeue = _fail_count <= _MAX_AUTO_RETRIES
            logger.warning(
                f"[{self.role_name}] Contract check failed for {task.id}: "
                f"{_contract.revision_comment}"
            )
            self.storage.update_sdlc_task_input_data(
                task.id, {"revision_comment": _contract.revision_comment},
            )
            self.storage.record_sdlc_task_error(
                task.id, _contract.revision_comment, _fail_count, requeue=_requeue,
            )
            self.timelog.finish(
                log_id=log_id, model_used=_actual_model,
                cost_usd=_estimated_cost_usd, output_files=[], status="contract_failed",
            )
            if output_ch:
                _label = "🔁 will retry" if _requeue else "💥 max retries — marked failed"
                await output_ch.send(
                    f"📋 **Contract Check Failed** — `{task.id}` (`{task.task_type}`)\n"
                    f"**Missing:** {_contract.revision_comment[:200]}\n"
                    f"**Attempt:** {_fail_count}/{_MAX_AUTO_RETRIES + 1} — {_label}"
                )
            await get_bridge().task_completed(
                role_key=self.role_name,
                project_id=task.project_id,
                project_name=project_name,
                task_name=task.title,
                summary=f"[contract-failed] {_contract.revision_comment[:300]}",
                files=[],
                model_id=_actual_model,
                cost_usd=_estimated_cost_usd,
                duration_seconds=round(_duration, 1),
                sdlc_task_id=task.id,
                status="blocked",
                error_info=_contract.revision_comment,
                contract_info={
                    "contract_status": "failed",
                    "contract_name": _contract.contract_name,
                    "missing_sections": _contract.missing_sections,
                    "missing_artifacts": _contract.missing_artifacts,
                },
            )
            return

        # ─── TimeLog finish ──────────────────────────────────────────
        finished = self.timelog.finish(
            log_id=log_id,
            model_used=_actual_model,
            cost_usd=_estimated_cost_usd,
            output_files=[task.output_file],
            status="done",
        )
        if tlog_ch and finished:
            await tlog_ch.send(embed=self.timelog.build_finish_embed(finished, project_name))

        # ─── Read approval_mode before setting DB status ─────────────
        _approval_mode = "manual"
        _project_obj = self.storage.get_project(task.project_id)
        if _project_obj:
            _approval_mode = (_project_obj.metadata or {}).get("approval_mode", "manual")

        # ─── Update DB ───────────────────────────────────────────────
        # auto  → "completed"        : downstream deps pass immediately
        # manual → "waiting_approval" : downstream blocked until human !approve
        _initial_status = "completed" if _approval_mode == "auto" else "waiting_approval"
        self.storage.update_sdlc_task_output(task.id, content)
        self.storage.update_sdlc_task_status(task.id, _initial_status)

        # ─── Post-completion hook (override per agent) ───────────────
        try:
            await self._on_sdlc_task_completed(task, content)
        except Exception as _hook_err:
            logger.warning(f"[{self.role_name}] post-task hook error: {_hook_err}")

        # ─── Post to output channel + store msg_id for G2 approval ──
        _discord_msg_id = ""
        if output_ch:
            import urllib.parse as _up
            tier_emoji = {"free": "🆓", "cheap": "💰", "smart": "🧠"}.get(routing["tier"], "")
            # Build download URL: file is relative to OUTPUT_BASE/projects/{project_id}/
            _web_url = os.getenv("WEB_APP_URL", "http://localhost:3001")
            _rel_file = f"{task.epic_id}/{self.role_name}/{task.output_file}"
            _dl_url = (
                f"{_web_url}/api/project-logs/files/download"
                f"?project={_up.quote(task.project_id)}"
                f"&file={_up.quote(_rel_file)}"
            )
            embed = discord.Embed(
                title=f"✅ {task.task_type} — {task.id}",
                color=0x24e08a,
            )
            embed.add_field(name="Epic", value=f"`{task.epic_id}`", inline=True)
            embed.add_field(name="Model", value=f"`{_actual_model}` {tier_emoji}", inline=True)
            embed.add_field(name="Duration", value=f"{round(_duration)}s", inline=True)
            embed.add_field(
                name="Output file",
                value=f"`{task.output_file}`\n[⬇ Download]({_dl_url})",
                inline=False,
            )
            if task.revision_count > 0:
                embed.set_footer(text=f"Revision #{task.revision_count}")
            embed.description = (
                "> Reply `!revise <note>` to request changes\n"
                "> Reply `!reject <reason>` to reject\n"
                "> React or use `!sdlc_status` to see all tasks"
            )
            msg = await output_ch.send(embed=embed)
            _discord_msg_id = str(msg.id)
            # G2: store message ID so !revise / !reject replies can find this task
            self.storage.set_sdlc_task_approval_msg(task.id, _discord_msg_id)

        # ─── G1: Web bridge — task completed ────────────────────────
        _routed_model = routing.get("model_id", "")
        _fallback_used = bool(
            _preferred_model_key and _actual_model != _preferred_model_key
        )
        # _artifacts already collected before contract validation above
        _contract_meta = {
            "contract_status": _contract.status,
            "contract_name": _contract.contract_name,
        } if _contract else {}
        await get_bridge().task_completed(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            task_name=task.title,
            summary=f"[{task.task_type}] {content[:300].replace(chr(10), ' ')}",
            files=[task.output_file],
            model_id=_actual_model,
            cost_usd=_estimated_cost_usd,
            duration_seconds=round(_duration, 1),
            revision_count=task.revision_count,
            artifact_ref=saved_path,
            status=_initial_status,  # auto→"completed" skips approval_item creation
            sdlc_task_id=task.id,
            discord_message_id=_discord_msg_id,
            preferred_model=_preferred_model_key or "",
            routed_model=_routed_model,
            fallback_used=_fallback_used,
            artifacts=_artifacts,
            contract_info=_contract_meta,
        )

        # ─── Auto-approve mode ────────────────────────────────────────
        if _approval_mode == "auto":
            # Notify approve channel (for audit trail) then auto-approve via web bridge
            approve_ch = await get_guild_channel(guild, role_ch.approve) if role_ch else None
            if approve_ch:
                await approve_ch.send(
                    f"✅ **Auto-approved** (approval:auto mode)\n"
                    f"Task: `{task.id}` — `{task.task_type}`\n"
                    f"File: `{task.output_file}`"
                )
            await get_bridge().approved(
                role_key=self.role_name,
                project_id=task.project_id,
                project_name=project_name,
                task_name=task.title,
                next_role=None,
                approver="auto",
                sdlc_task_id=task.id,
            )

        logger.info(f"[{self.role_name}] completed sdlc task {task.id} → {saved_path} (approval:{_approval_mode})")

    # ─── Phase 8: Quota/Provider Pause helper ──────────────────────────────

    async def _pause_task_for_quota(
        self,
        task,
        project_name: str,
        err_info,
        model_key: str,
        output_ch,
        log_id: str,
        estimated_cost: float,
        actual_model: str,
    ):
        """
        Pause an SDLC task when all LLM fallbacks fail due to quota/rate/provider issues.

        - Writes paused status + pause metadata to DB (clears claim so recovery can requeue)
        - Registers provider cooldown
        - Notifies Discord output channel
        - Sends Web App paused event (no approval_item created)
        - Closes the timelog entry
        """
        import time as _time
        from datetime import timedelta
        from shared.channel_config import ROLE_CHANNELS

        # Compute retry_after timestamp
        retry_s = err_info.retry_after_seconds or 3600
        retry_after_at = (
            datetime.utcnow() + timedelta(seconds=retry_s)
        ).isoformat()

        # Determine provider from model_key or err_info hint
        provider = err_info.provider_hint
        if not provider and "/" in model_key:
            provider = model_key.split("/")[0]

        # 1. Persist pause state
        self.storage.pause_sdlc_task_for_provider(
            task_id=task.id,
            reason=err_info.error_type,
            provider=provider,
            model=model_key,
            retry_after_at=retry_after_at,
            error=err_info.raw_message,
            resume_policy=err_info.resume_policy,
        )

        # 2. Register provider cooldown so router avoids it
        if provider:
            self.storage.set_provider_cooldown(
                provider=provider,
                model=model_key,
                reason=err_info.error_type,
                retry_after_at=retry_after_at,
            )

        # 3. Discord notification (no approval needed)
        if output_ch:
            _policy_note = " — **manual key rotation required**" if err_info.is_manual else ""
            await output_ch.send(
                f"⏸️ **Task Paused** — `{task.id}` (`{task.task_type}`)\n"
                f"**Reason:** {err_info.error_type} on `{model_key}`{_policy_note}\n"
                f"**Resume after:** {retry_after_at[:19]} UTC\n"
                f"**Error:** `{err_info.raw_message[:200]}`"
            )

        # 4. Web App notification (status=paused, no approval_item)
        await get_bridge().task_completed(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            task_name=task.title,
            summary=(
                f"⏸️ Task paused: {err_info.error_type} on {provider or model_key}. "
                f"Resume after {retry_after_at[:19]} UTC."
            ),
            files=[],
            model_id=actual_model,
            cost_usd=estimated_cost,
            duration_seconds=0.0,
            sdlc_task_id=task.id,
            status="paused",
            extra_metadata=dict(
                pause_reason=err_info.error_type,
                pause_provider=provider,
                pause_model=model_key,
                retry_after_at=retry_after_at,
                resume_policy=err_info.resume_policy,
                error=err_info.raw_message,
            ),
        )

        # 5. Audit trail — agent.task.paused (separate from task_completed above)
        await get_bridge().post_event(
            role_key=self.role_name,
            event_type="agent.task.paused",
            task_name=task.title or task.id,
            status="paused",
            summary=(
                f"Task {task.id} paused: {err_info.error_type} on "
                f"{provider or model_key}. Resume after {retry_after_at[:19]} UTC."
            ),
            sdlc_task_id=task.id,
            project_id=task.project_id,
            metadata=dict(
                pause_reason=err_info.error_type,
                pause_provider=provider,
                pause_model=model_key,
                retry_after_at=retry_after_at,
                resume_policy=err_info.resume_policy,
            ),
            actor="system",
        )

        # 6. Close timelog
        self.timelog.finish(
            log_id=log_id,
            model_used=actual_model,
            cost_usd=estimated_cost,
            output_files=[],
            status="paused",
        )

        logger.warning(
            f"[{self.role_name}] task {task.id} paused ({err_info.error_type}) "
            f"provider={provider} retry_after={retry_after_at[:19]}"
        )

    def _build_sdlc_context(self, task: SdlcTask, project_name: str, input_data: dict) -> dict:
        """รวบรวม context จาก dependency tasks + input_data สำหรับ prompt"""
        from datetime import date

        ctx: dict = {
            "project_name": project_name,
            "project_id": task.project_id,
            "epic_id": task.epic_id,
            "epic_title": input_data.get("epic_title", ""),
            "epic_goal": input_data.get("epic_goal", ""),
            "epic_priority": input_data.get("epic_priority", "P1"),
            "today": date.today().strftime("%d/%m/%Y"),
            "tech_stack": input_data.get("tech_stack", "ไม่ระบุ (ตัดสินใจตาม requirement)"),
            "role_feedback": input_data.get("role_feedback", "") or "",
            "revision_count": task.revision_count,
        }

        # Load project_brief if available
        project = self.storage.get_project(task.project_id)
        if project:
            ctx["project_brief"] = project.description or ""
            ctx["requirements"] = project.description or ""

        # Load outputs of dependency tasks
        if task.depends_on:
            for dep_id in task.depends_on.split(","):
                dep_id = dep_id.strip()
                if not dep_id:
                    continue
                dep_task = self.storage.get_sdlc_task(dep_id)
                if dep_task and dep_task.output_data:
                    # Map dep task_type → context key
                    key_map = {
                        # BA
                        "brd": "brd_content",
                        "srs": "srs_content",
                        "user_stories": "ba_user_stories",         # QA/SA expect ba_user_stories
                        "use_cases": "use_cases_content",
                        "data_dictionary": "ba_data_dictionary",
                        # SA
                        "system_purpose": "system_purpose_content",
                        "scope_definition": "scope_content",
                        "architecture": "architecture_content",
                        "sequence_diagram": "sequence_content",
                        "activity_workflow": "activity_content",
                        "service_decomposition": "service_content",
                        "integration_landscape": "integration_content",
                        "deployment_model": "deployment_model_content",
                        "database_schema": "sa_database_schema",   # DEV expects sa_database_schema
                        "api_spec": "sa_api_spec",
                        "sa_data_dictionary": "sa_data_dictionary_content",
                        # UXUI
                        "user_flow": "user_flow_content",
                        "wireframe": "uxui_wireframe",
                        "design_system": "design_system_content",
                        "ux_guidelines": "ux_guidelines_content",
                        # DEV
                        "frontend_structure": "frontend_structure_content",
                        "frontend_code": "frontend_code_content",
                        "backend_structure": "backend_structure_content",
                        "backend_code": "backend_code_content",
                        "unit_tests": "unit_tests_content",
                        "dev_readme": "dev_readme_content",
                        # QA
                        "qa_plan": "qa_plan_content",
                        "test_cases": "test_cases_content",
                        "test_scenarios": "test_scenarios_content",
                        "test_report": "test_report_content",
                        # DevOps
                        "pipeline_diagram": "pipeline_content",
                        "dockerfile": "dockerfile_content",
                        "docker_compose": "docker_compose_content",
                        "github_actions": "github_actions_content",
                        "deployment_guide": "deployment_guide_content",
                        # CEO / PM
                        "project_brief": "project_brief",
                        "epics": "epics_content",
                        "project_charter": "project_charter_content",
                        "project_management_plan": "pm_plan_content",
                        "raci_matrix": "raci_content",
                        "risk_register": "risk_register_content",
                        "communications_plan": "comms_content",
                        "project_status_report": "status_report_content",
                    }
                    ctx_key = key_map.get(dep_task.task_type, f"{dep_task.task_type}_content")
                    # Truncate large dep outputs to avoid 413 Payload Too Large on Groq
                    _dep_data = dep_task.output_data or ""
                    ctx[ctx_key] = _dep_data[:2000] if len(_dep_data) > 2000 else _dep_data

        # Fill missing keys with empty string so .format() doesn't fail
        for key in list(ctx.keys()):
            if ctx[key] is None:
                ctx[key] = ""

        return ctx

    def _build_sdlc_prompt(self, task_type: str, context: dict) -> str:
        """Route to role-specific prompt builder, then append artifact contract block."""
        builders = {
            "ceo":    self._get_ceo_prompt,
            "pm":     self._get_pm_prompt,
            "ba":     self._get_ba_prompt,
            "sa":     self._get_sa_prompt,
            "uxui":   self._get_uxui_prompt,
            "dev":    self._get_dev_prompt,
            "qa":     self._get_qa_prompt,
            "devops": self._get_devops_prompt,
        }
        builder = builders.get(self.role_name)
        prompt = builder(task_type, context) if builder else f"สร้าง {task_type} สำหรับ {context.get('project_name', '')}"
        try:
            from shared.artifact_contracts import build_contract_prompt_block
            block = build_contract_prompt_block(self.role_name, task_type)
            if block:
                prompt = prompt + block
        except Exception:
            pass
        return prompt

    async def _on_sdlc_task_completed(self, task: SdlcTask, content: str):
        """Hook: called after every sdlc_task completes. Override per agent for role-specific logic."""
        await self._check_epic_role_completion(task)
        await self._check_project_completion(task)
        await self._check_milestone_progress(task)

    async def _check_epic_role_completion(self, task: SdlcTask):
        """G4: When all sdlc_tasks for this role+epic are done, post a completion notice."""
        if task.epic_id.endswith("-PROJECT"):
            return  # project-level tasks don't trigger epic banners
        role_epic_tasks = [
            t for t in self.storage.list_sdlc_tasks(project_id=task.project_id, role=self.role_name)
            if t.epic_id == task.epic_id
        ]
        if not role_epic_tasks:
            return
        if any(t.status not in ("completed", "approved") for t in role_epic_tasks):
            return  # still tasks remaining

        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else task.project_id
        guilds = self.bot.guilds
        if not guilds:
            return
        role_ch = ROLE_CHANNELS.get(self.role_name)
        if not role_ch:
            return
        output_ch = await get_guild_channel(guilds[0], role_ch.output)
        if not output_ch:
            return

        task_list = " · ".join(f"`{t.task_type}`" for t in role_epic_tasks)
        embed = discord.Embed(
            title=f"🏁 {self.role_name.upper()} Epic Complete — {task.epic_id}",
            description=f"**Project:** {project_name}\nAll **{len(role_epic_tasks)}** tasks finished",
            color=0x24e08a,
        )
        embed.add_field(name="Tasks done", value=task_list, inline=False)
        await output_ch.send(embed=embed)
        await get_bridge().task_completed(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            task_name=f"{self.role_name.upper()} {task.epic_id} complete",
            summary=f"All {len(role_epic_tasks)} {self.role_name.upper()} tasks done for {task.epic_id}",
            files=[],
            model_id="",
            cost_usd=0.0,
            duration_seconds=0.0,
            status="completed",
        )

    async def _check_project_completion(self, task: SdlcTask):
        """Fire a 'project complete' notification when ALL sdlc_tasks across all roles are done."""
        terminal = {"completed", "approved", "rejected", "failed"}
        all_tasks = self.storage.list_sdlc_tasks(project_id=task.project_id)
        if not all_tasks:
            return
        if any(t.status not in terminal for t in all_tasks):
            return  # still work to do

        # Atomically transition project — only one agent wins the race
        if not self.storage.try_complete_project(task.project_id):
            return  # already marked completed by another agent

        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else task.project_id
        total = len(all_tasks)
        done = sum(1 for t in all_tasks if t.status in ("completed", "approved"))
        total_cost = self.tracker.today_spend()

        guilds = self.bot.guilds
        if guilds:
            role_ch = ROLE_CHANNELS.get(self.role_name)
            if role_ch:
                output_ch = await get_guild_channel(guilds[0], role_ch.output)
                if output_ch:
                    embed = discord.Embed(
                        title=f"🎉 PROJECT COMPLETE — {project_name}",
                        description=f"**All {total} SDLC tasks finished!**\n✅ {done} completed · ❌ {total - done} rejected/failed",
                        color=0xFFD700,
                    )
                    embed.add_field(name="Project ID", value=f"`{task.project_id}`", inline=True)
                    embed.add_field(name="Total Tasks", value=str(total), inline=True)
                    embed.add_field(name="Cost Today", value=f"${total_cost:.4f}", inline=True)
                    web_url = os.getenv("WEB_APP_URL", "http://localhost:3001")
                    embed.add_field(
                        name="🔗 Links",
                        value=f"[Workboard]({web_url}/workboard) · [Project Logs]({web_url}/project-logs?project={task.project_id})",
                        inline=False,
                    )
                    await output_ch.send(embed=embed)

        await get_bridge().task_completed(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            task_name=f"🎉 {project_name} — Project Complete",
            summary=f"All {total} SDLC tasks finished across all roles. Project complete!",
            files=[],
            model_id="",
            cost_usd=total_cost,
            duration_seconds=0.0,
            status="completed",
        )
        # Update hot cache so web dashboard "Current Project" widget reflects completion
        await get_bridge().hot_cache_update(
            role_key=self.role_name,
            project_id=task.project_id,
            project_name=project_name,
            summary=f"Project complete — {done}/{total} tasks done",
            status="completed",
        )

        logger.info(f"[{self.role_name}] PROJECT COMPLETE: {task.project_id} — {project_name} ({total} tasks)")

    async def _check_milestone_progress(self, task: SdlcTask):
        """Post a progress report to ceo-output at 25/50/75% task completion milestones."""
        all_tasks = self.storage.list_sdlc_tasks(project_id=task.project_id)
        if not all_tasks:
            return
        total = len(all_tasks)
        completed = sum(1 for t in all_tasks if t.status in ("completed", "approved"))

        # Calculate current and previous percentage (integer floor)
        cur_pct  = completed * 100 // total
        prev_pct = (completed - 1) * 100 // total if completed > 0 else 0

        milestone_hit = None
        for m in (25, 50, 75):
            if prev_pct < m <= cur_pct:
                milestone_hit = m
                break

        if not milestone_hit:
            return

        project = self.storage.get_project(task.project_id)
        project_name = project.name if project else task.project_id

        guilds = self.bot.guilds
        if not guilds:
            return

        from shared.channel_config import ROLE_CHANNELS as _RC, get_guild_channel as _GCH
        ceo_ch = _RC.get("ceo")
        if not ceo_ch:
            return
        report_ch = await _GCH(guilds[0], ceo_ch.output)
        if not report_ch:
            return

        # Count per-role completion
        roles = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
        role_lines = []
        for r in roles:
            r_tasks = [t for t in all_tasks if t.role == r]
            if not r_tasks:
                continue
            r_done = sum(1 for t in r_tasks if t.status in ("completed", "approved"))
            pct_r = r_done * 100 // len(r_tasks)
            bar = "█" * (pct_r // 10) + "░" * (10 - pct_r // 10)
            role_lines.append(f"`{r.upper():6}` {bar} {pct_r}% ({r_done}/{len(r_tasks)})")

        failed = sum(1 for t in all_tasks if t.status in ("failed", "rejected"))
        embed = discord.Embed(
            title=f"📊 Milestone {milestone_hit}% — {project_name}",
            description=f"**{completed}/{total} tasks complete** across all roles",
            color=0x6366f1 if milestone_hit < 75 else 0x22c55e,
        )
        embed.add_field(name="Project ID", value=f"`{task.project_id}`", inline=True)
        embed.add_field(name="Completed", value=f"{completed}", inline=True)
        embed.add_field(name="Failed/Rejected", value=str(failed), inline=True)
        if role_lines:
            embed.add_field(name="Per-Role Progress", value="\n".join(role_lines), inline=False)
        await report_ch.send(embed=embed)

        await get_bridge().hot_cache_update(
            role_key="ceo",
            project_id=task.project_id,
            project_name=project_name,
            summary=f"{milestone_hit}% milestone — {completed}/{total} tasks done",
            status="in_progress",
        )
        logger.info(f"[{self.role_name}] Milestone {milestone_hit}% reported for {task.project_id}")

    def _get_ceo_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.ceo.task_prompts import build_ceo_task_prompt
            return build_ceo_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_pm_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.pm.task_prompts import build_pm_task_prompt
            return build_pm_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_ba_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.ba.task_prompts import build_ba_task_prompt
            return build_ba_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_sa_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.sa.task_prompts import build_sa_task_prompt
            return build_sa_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_uxui_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.uxui.task_prompts import build_uxui_task_prompt
            return build_uxui_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_dev_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.dev.task_prompts import build_dev_task_prompt
            return build_dev_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_qa_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.qa.task_prompts import build_qa_task_prompt
            return build_qa_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def _get_devops_prompt(self, task_type: str, context: dict) -> str:
        try:
            from agents.devops.task_prompts import build_devops_task_prompt
            return build_devops_task_prompt(task_type, context)
        except ImportError:
            return f"สร้าง {task_type}"

    def run(self, token: str):
        bot = self.setup_bot()
        bot.run(token)
