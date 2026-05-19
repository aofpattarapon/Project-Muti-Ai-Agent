#!/usr/bin/env python3
"""
Discord Live Full-Loop Test — Autonomous End-to-End Pipeline on Real Discord
============================================================================
Run: python3 scripts/discord_live_test.py

What this does:
  1. Creates 2 real projects and runs them through all 8 agent roles
  2. Posts EVERY output to real Discord channels (as each role's bot)
  3. Auto-approves each stage (acting as human approver)
  4. Scenario A  — Happy path with 1 BA revision
  5. Scenario B  — Forced token exhaustion → visible fallback chain in Discord
  6. Posts periodic heartbeat updates to #project-dashboard
  7. Writes full log to outputs/discord_test_YYYYMMDD.log
"""

import os, sys, json, uuid, asyncio, time, traceback, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DB_PATH",          str(ROOT / "data" / "sdlc.db"))
os.environ.setdefault("OUTPUT_BASE_PATH", str(ROOT / "outputs"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx

# ── Channel map ───────────────────────────────────────────────
CHANNELS = {
    "ceo-input":          "1504863027692966010",
    "ceo-output":         "1504863038195372083",
    "ceo-approve":        "1504876404951744623",
    "pm-output":          "1504863046693158924",
    "pm-approve":         "1504876410077184232",
    "ba-output":          "1504863054251425852",
    "ba-approve":         "1504876413336031346",
    "sa-output":          "1504863061423423600",
    "sa-approve":         "1504876415344971827",
    "uxui-output":        "1504863068952334376",
    "uxui-approve":       "1504876417245253857",
    "dev-output":         "1504863075977658473",
    "dev-approve":        "1504876419107393567",
    "qa-output":          "1504863083548512368",
    "qa-approve":         "1504876420814344333",
    "devops-output":      "1504863091060637746",
    "devops-approve":     "1504876422492323841",
    "project-dashboard":  "1504863032205906110",
    "log":                "1505239589026005134",
}

# ── Bot tokens per role ────────────────────────────────────────
BOT_TOKENS = {
    "ceo":    os.getenv("CEO_DISCORD_TOKEN"),
    "pm":     os.getenv("PM_DISCORD_TOKEN"),
    "ba":     os.getenv("BA_DISCORD_TOKEN"),
    "sa":     os.getenv("SA_DISCORD_TOKEN"),
    "uxui":   os.getenv("UXUI_DISCORD_TOKEN"),
    "dev":    os.getenv("FRONTEND_DISCORD_TOKEN"),
    "qa":     os.getenv("QA_DISCORD_TOKEN"),
    "devops": os.getenv("DEVOPS_DISCORD_TOKEN"),
    "system": os.getenv("CEO_DISCORD_TOKEN"),  # system messages use CEO token
}

ROLE_EMOJI = {
    "ceo":"👔","pm":"📋","ba":"📝","sa":"🏗️",
    "uxui":"🎨","dev":"💻","qa":"🧪","devops":"⚙️",
}
ROLE_COLOR = {
    "ceo":0x5865F2,"pm":0x57F287,"ba":0xFEE75C,"sa":0xEB459E,
    "uxui":0xFF73FA,"dev":0x1ABC9C,"qa":0xF1C40F,"devops":0xE67E22,
}
WORKFLOW = ["ceo","pm","ba","sa","uxui","dev","qa","devops"]

# ── Logging ────────────────────────────────────────────────────
LOG_FILE = ROOT / "outputs" / f"discord_test_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_log_fh = open(LOG_FILE, "w", encoding="utf-8")

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    _log_fh.write(line + "\n")
    _log_fh.flush()


# ── Discord REST helpers ───────────────────────────────────────

async def discord_post(channel_key: str, token: str, content: str = None,
                        embed: dict = None, reply_to: str = None) -> dict:
    channel_id = CHANNELS.get(channel_key, channel_key)
    payload = {}
    if content:
        payload["content"] = content[:2000]
    if embed:
        payload["embeds"] = [embed]
    if reply_to:
        payload["message_reference"] = {"message_id": reply_to}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
                    json=payload,
                )
                if r.status_code == 429:  # rate limit
                    retry_after = r.json().get("retry_after", 2)
                    log(f"  [rate limit] sleeping {retry_after:.1f}s")
                    await asyncio.sleep(retry_after + 0.5)
                    continue
                if r.status_code in (200, 201):
                    return r.json()
                log(f"  [discord warn] {r.status_code}: {r.text[:120]}")
                return {}
        except Exception as e:
            log(f"  [discord err attempt {attempt+1}] {e}")
            await asyncio.sleep(2)
    return {}


async def dashboard_update(title: str, description: str, color: int = 0x5865F2, fields: list = None):
    embed = {"title": title, "description": description, "color": color,
             "timestamp": datetime.utcnow().isoformat(), "fields": fields or []}
    await discord_post("project-dashboard", BOT_TOKENS["system"], embed=embed)
    await asyncio.sleep(0.5)


async def log_channel(msg: str):
    token = BOT_TOKENS["system"]
    await discord_post("log", token, content=msg)
    await asyncio.sleep(0.3)


# ── Agent runner ───────────────────────────────────────────────

async def run_agent(role: str, project, input_data: dict, force_billing_error: bool = False) -> dict:
    import importlib
    mod = importlib.import_module(f"agents.{role}.agent")
    agent_class = next(
        (getattr(mod, n) for n in dir(mod)
         if isinstance(getattr(mod, n), type)
         and n.lower() != "baseagent"
         and hasattr(getattr(mod, n), "process_task")),
        None
    )
    if not agent_class:
        raise RuntimeError(f"No agent class in agents.{role}.agent")

    agent = agent_class()

    if force_billing_error:
        # Save real key, inject fake one to trigger 401
        real_key = os.environ.get("ANTHROPIC_API_KEY", "")
        real_claude_cli = os.environ.get("PATH", "")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-FAKE-KEY-TO-FORCE-BILLING-ERROR"
        # Also hide claude CLI temporarily
        os.environ["PATH"] = ""
        log(f"  [SCENARIO B] Forced billing error for {role.upper()} — will trigger fallback chain")

    try:
        result = await agent.process_task(project, input_data)
    finally:
        if force_billing_error:
            os.environ["ANTHROPIC_API_KEY"] = real_key
            os.environ["PATH"] = real_claude_cli

    return result


# ── Post role output to Discord ────────────────────────────────

async def post_role_output(role: str, project, output: dict, elapsed: float,
                            revision_count: int = 0, is_fallback: bool = False):
    token = BOT_TOKENS[role]
    emoji = ROLE_EMOJI.get(role, "")
    color = ROLE_COLOR.get(role, 0x95A5A6)
    model_used = output.get("_model_used", "unknown")

    summary = output.get("summary", "")
    if not summary:
        summary = str(output)[:200]
    summary = summary[:500]

    rev_note = f" | Revision #{revision_count}" if revision_count > 0 else ""
    fallback_note = " ⚠️ **FALLBACK MODEL**" if is_fallback else ""

    # Files produced
    files_list = list(output.get("files", {}).keys())
    files_str = "\n".join(f"• `{f}`" for f in files_list[:8]) or "N/A"

    embed = {
        "title": f"{emoji} {role.upper()} Agent — Task Complete{rev_note}",
        "description": summary[:400],
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "Project",  "value": f"`{project.id}` — {project.name}", "inline": True},
            {"name": "Time",     "value": f"{elapsed:.1f}s", "inline": True},
            {"name": "Model",    "value": f"`{model_used[:40]}`{fallback_note}", "inline": False},
            {"name": "Files",    "value": files_str, "inline": False},
        ],
        "footer": {"text": "↩️ Reply: !approve | !revise [comment] | !reject [reason]"},
    }

    # Post to output channel
    await discord_post(f"{role}-output", token, embed=embed)
    await asyncio.sleep(0.5)

    # Post approval prompt to approve channel
    approval_embed = {
        "title": f"✋ Awaiting Approval — {role.upper()}",
        "description": (
            f"**Project:** `{project.id}` — {project.name}\n\n"
            f"{summary[:300]}"
        ),
        "color": 0xFEE75C,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "Model used",   "value": f"`{model_used[:50]}`{fallback_note}", "inline": True},
            {"name": "Elapsed",      "value": f"{elapsed:.1f}s", "inline": True},
        ],
        "footer": {"text": "🤖 Auto-Approver will respond in 5s..."},
    }
    msg = await discord_post(f"{role}-approve", token, embed=approval_embed)
    return msg.get("id")  # message ID for approval reply


async def post_auto_approve(role: str, project_id: str, approval_msg_id: str,
                             next_role: str = None):
    token = BOT_TOKENS[role]
    if next_role:
        content = (
            f"✅ **[AUTO-APPROVED]** — `{project_id}`\n"
            f"→ Passing to **{ROLE_EMOJI.get(next_role,'')}{next_role.upper()}** Agent"
        )
    else:
        content = f"🎉 **[AUTO-APPROVED]** — `{project_id}` — **PIPELINE COMPLETE!**"

    await discord_post(f"{role}-approve", token, content=content,
                        reply_to=approval_msg_id)
    await asyncio.sleep(0.5)


async def post_revision_request(role: str, project_id: str, approval_msg_id: str, comment: str):
    token = BOT_TOKENS[role]
    content = (
        f"🔄 **[AUTO-REVISE]** — `{project_id}`\n"
        f"Comment: _{comment}_"
    )
    await discord_post(f"{role}-approve", token, content=content,
                        reply_to=approval_msg_id)
    await asyncio.sleep(0.5)


# ── Pipeline runner ────────────────────────────────────────────

async def run_pipeline(
    scenario_name: str,
    project_name: str,
    description: str,
    roles: list,
    revision_at: dict = None,    # {role: comment} — request revision at this role
    force_billing_at: str = None, # role name to force billing error
) -> dict:
    """
    Run full pipeline for one project, auto-approving each stage.
    Posts all results to Discord in real-time.
    revision_at: e.g. {"ba": "เพิ่ม offline mode user story"}  (first time → revise, second → approve)
    force_billing_at: role to inject fake API key (tests fallback chain)
    """
    from shared.storage import Storage, Project, TaskStatus
    from shared.output_processor import OutputProcessor
    from shared.obsidian_client import get_obsidian

    pid = f"{scenario_name[:6].upper()}-{uuid.uuid4().hex[:5].upper()}"
    storage = Storage()
    proc    = OutputProcessor()

    project = Project(
        id=pid, name=project_name, description=description,
        created_at=datetime.utcnow().isoformat(),
        current_role=roles[0], status="active",
        discord_guild_id=os.getenv("DISCORD_GUILD_ID",""),
        approval_channel_id=CHANNELS.get("project-dashboard",""),
    )
    storage.create_project(project)

    log(f"\n{'='*60}")
    log(f"SCENARIO: {scenario_name}")
    log(f"Project:  {pid} — {project_name}")
    log(f"Roles:    {' → '.join(r.upper() for r in roles)}")
    log(f"{'='*60}")

    # Dashboard announcement
    await dashboard_update(
        f"🚀 {scenario_name} — Project Started",
        f"**{project_name}**\n`{pid}`\n\n{description[:200]}",
        color=0x5865F2,
        fields=[{"name": "Pipeline", "value": " → ".join(r.upper() for r in roles), "inline": False}],
    )

    pipeline_log = []
    current_output: dict = {}
    revised_roles: set = set()  # track roles already revised

    for i, role in enumerate(roles):
        next_role = roles[i+1] if i+1 < len(roles) else None
        revision_comment = revision_at.get(role) if revision_at else None
        is_revision_run  = role in revised_roles
        # Only revise first time; second pass → approve
        do_revise = (revision_comment and not is_revision_run)

        log(f"\n  [{role.upper()}] Starting...")
        t0 = time.time()

        # Build input
        input_data = {
            "project_description": description,
            "project_name":        project_name,
            "previous_output":     current_output,
            "revision_comment":    "",
            "revision_count":      0,
        }

        # ── Run agent ────────────────────────────────────────────
        force_billing = (role == force_billing_at and not is_revision_run)
        try:
            output = await run_agent(role, project, input_data, force_billing_error=force_billing)
            # Detect if fallback was used (look at last model in tracker)
            from shared.model_router import CostTracker
            last_calls = CostTracker().today_summary().get("breakdown", [])
            is_fallback = (
                force_billing or
                any("fallback" in str(c.get("model","")).lower() for c in last_calls[-3:])
            )
        except Exception as e:
            log(f"  [{role.upper()}] ERROR: {e}")
            traceback.print_exc()
            pipeline_log.append({"role": role, "status": "error", "error": str(e)})
            await dashboard_update(
                f"❌ {scenario_name} — {role.upper()} Failed",
                f"`{pid}` — {role.upper()} error: {str(e)[:200]}",
                color=0xED4245,
            )
            continue

        elapsed = time.time() - t0
        log(f"  [{role.upper()}] Done in {elapsed:.1f}s | fallback={is_fallback}")

        # ── Save artifacts ────────────────────────────────────────
        base_path = str(ROOT / "outputs" / "projects" / pid / role)
        Path(base_path).mkdir(parents=True, exist_ok=True)
        raw_llm = output.get("raw_llm_output") or output.get("summary","")
        artifacts = []
        if raw_llm and len(raw_llm) > 50:
            artifacts = proc.process(role, raw_llm, f"{role}_output")
            proc.save_to_disk(artifacts, base_path)
        try:
            get_obsidian().save_project_note(pid, project_name, role, raw_llm)
        except Exception:
            pass

        # ── Post to Discord ───────────────────────────────────────
        rev_count = 1 if is_revision_run else 0
        approval_msg_id = await post_role_output(
            role, project, output, elapsed, rev_count, is_fallback
        )
        await asyncio.sleep(3)  # pause so user can see output

        # ── Approve or Revise ─────────────────────────────────────
        if do_revise:
            # Request revision
            await post_revision_request(role, pid, approval_msg_id, revision_comment)
            log(f"  [{role.upper()}] REVISION REQUESTED: {revision_comment}")

            revised_roles.add(role)
            pipeline_log.append({
                "role": role, "status": "revision", "elapsed": elapsed,
                "comment": revision_comment,
            })

            # Re-run with revision
            await asyncio.sleep(2)
            log(f"  [{role.upper()}] Re-running with revision comment...")
            t0 = time.time()
            rev_input = dict(input_data)
            rev_input["revision_comment"] = revision_comment
            rev_input["revision_count"]   = 1

            try:
                output = await run_agent(role, project, rev_input)
                elapsed2 = time.time() - t0
                log(f"  [{role.upper()}] Revision done in {elapsed2:.1f}s")
            except Exception as e:
                log(f"  [{role.upper()}] Revision ERROR: {e}")
                continue

            # Post revised output
            approval_msg_id = await post_role_output(
                role, project, output, elapsed2, revision_count=1
            )
            await asyncio.sleep(3)

            # Auto-approve revised output
            await post_auto_approve(role, pid, approval_msg_id, next_role)
            elapsed = elapsed + elapsed2

        else:
            # Straight approve
            await post_auto_approve(role, pid, approval_msg_id, next_role)

        # ── DB: advance pipeline ──────────────────────────────────
        task_id = str(uuid.uuid4())
        import sqlite3
        with sqlite3.connect(os.getenv("DB_PATH","data/sdlc.db")) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO role_tasks
                   (id,project_id,role,status,input_data,output_data,
                    created_at,updated_at,approval_message_id,revision_count,notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id, pid, role, TaskStatus.APPROVED,
                 json.dumps(input_data), json.dumps(output),
                 datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                 approval_msg_id or "auto", 0,
                 "Auto-approved by discord_live_test.py"),
            )
        storage.update_project_role(
            pid, next_role or "completed",
            "active" if next_role else "completed"
        )

        pipeline_log.append({
            "role": role, "status": "approved", "elapsed": elapsed,
            "artifacts": [a.filename for a in artifacts],
            "is_fallback": is_fallback,
        })
        current_output = output

        # Dashboard update every role
        emoji = ROLE_EMOJI.get(role,"")
        remaining = " → ".join(r.upper() for r in roles[i+1:]) if next_role else "—"
        await dashboard_update(
            f"{emoji} {role.upper()} ✅ — {scenario_name}",
            f"`{pid}` — {project_name}\n\n✅ {role.upper()} approved!\n{'⚠️ Fallback model used' if is_fallback else ''}",
            color=0x57F287,
            fields=[
                {"name": "Elapsed", "value": f"{elapsed:.0f}s", "inline": True},
                {"name": "Artifacts", "value": str(len(artifacts)), "inline": True},
                {"name": "Remaining", "value": remaining or "COMPLETE!", "inline": False},
            ],
        )

        log(f"  [{role.upper()}] ✅ APPROVED → {(next_role or 'COMPLETE').upper()}")
        await asyncio.sleep(1)

    # ── Final summary ──────────────────────────────────────────
    passed = sum(1 for s in pipeline_log if s["status"] == "approved")
    total_elapsed = sum(s.get("elapsed",0) for s in pipeline_log)
    fallbacks = [s["role"] for s in pipeline_log if s.get("is_fallback")]

    summary_lines = [f"`{pid}` — **{project_name}**\n"]
    for step in pipeline_log:
        icon = "✅" if step["status"]=="approved" else "🔄" if step["status"]=="revision" else "❌"
        fb_note = " *(fallback)*" if step.get("is_fallback") else ""
        summary_lines.append(f"{icon} **{step['role'].upper()}** {step.get('elapsed',0):.0f}s{fb_note}")

    await dashboard_update(
        f"🏁 {scenario_name} — PIPELINE {'COMPLETE' if passed==len(roles) else 'PARTIAL'}",
        "\n".join(summary_lines),
        color=0x57F287 if passed==len(roles) else 0xFEE75C,
        fields=[
            {"name": "Roles passed", "value": f"{passed}/{len(roles)}", "inline": True},
            {"name": "Total time",   "value": f"{total_elapsed:.0f}s ({total_elapsed/60:.1f}m)", "inline": True},
            {"name": "Fallback used","value": ", ".join(fallbacks) or "None", "inline": True},
        ],
    )

    return {"project_id": pid, "project_name": project_name,
            "pipeline": pipeline_log, "passed": passed, "total": len(roles)}


# ══════════════════════════════════════════════════════════════
# MAIN — Run both scenarios
# ══════════════════════════════════════════════════════════════

async def main():
    log("=" * 65)
    log("  Discord Live Full-Loop Test — Autonomous")
    log(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 65)

    # ── Announce to Discord ──────────────────────────────────────
    await discord_post("project-dashboard", BOT_TOKENS["system"],
        content=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 **Autonomous Full-Loop Test Starting**\n"
            f"Time: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
            "**Scenario A** — HealthTrack Mobile App (full 8-role + revision)\n"
            "**Scenario B** — Token exhaustion → fallback chain visible here\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    )
    await asyncio.sleep(2)

    results = {}

    # ══════════════════════════════════════════════════════════
    # SCENARIO A — Full pipeline + BA revision
    # ══════════════════════════════════════════════════════════
    log("\n\n" + "█"*60)
    log("  SCENARIO A — HealthTrack Mobile App (Full Pipeline + Revision)")
    log("█"*60)

    await discord_post("ceo-input", BOT_TOKENS["ceo"],
        content=(
            "🤖 **[AUTO-TEST SCENARIO A]**\n"
            "`!new HealthTrack Mobile App | ระบบติดตามสุขภาพบน mobile สำหรับ Thai users | "
            "ฟีเจอร์: heart rate monitoring, sleep tracking, step counter, "
            "doctor dashboard, offline mode, LINE notification, health history chart`"
        )
    )
    await asyncio.sleep(1)

    try:
        result_a = await run_pipeline(
            scenario_name   = "Scenario A",
            project_name    = "HealthTrack Mobile App",
            description     = (
                "ระบบติดตามสุขภาพบน mobile สำหรับ Thai users\n"
                "Features:\n"
                "- Heart rate monitoring (BLE sensor integration)\n"
                "- Sleep tracking with AI analysis\n"
                "- Step counter + calories\n"
                "- Doctor dashboard (view patient data)\n"
                "- Offline mode with background sync\n"
                "- LINE Notify integration\n"
                "- Health history chart (30/90/180 days)\n"
                "Tech: React Native + TypeScript, FastAPI, PostgreSQL, Redis, Docker"
            ),
            roles           = WORKFLOW,
            revision_at     = {"ba": "เพิ่ม user story สำหรับ doctor dashboard ที่มี realtime patient monitoring และ alert เมื่อ heart rate ผิดปกติ"},
        )
        results["scenario_a"] = result_a
        log(f"\n  Scenario A DONE: {result_a['passed']}/{result_a['total']} roles")
    except Exception as e:
        log(f"\n  Scenario A FAILED: {e}")
        traceback.print_exc()
        results["scenario_a"] = {"error": str(e)}

    await asyncio.sleep(5)

    # ══════════════════════════════════════════════════════════
    # SCENARIO B — Force billing error at SA → show fallback
    # ══════════════════════════════════════════════════════════
    log("\n\n" + "█"*60)
    log("  SCENARIO B — TaskFlow (Token Exhaustion + Fallback Chain)")
    log("█"*60)

    await discord_post("project-dashboard", BOT_TOKENS["system"],
        content=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **SCENARIO B — Forcing Token Exhaustion**\n"
            "Injecting invalid API key for **SA** role...\n"
            "Watch the fallback chain: `claude-cli` → `groq/qwen3-32b` → `ollama/deepseek-r1`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    )
    await asyncio.sleep(2)

    try:
        result_b = await run_pipeline(
            scenario_name    = "Scenario B",
            project_name     = "TaskFlow Project Manager",
            description      = (
                "ระบบบริหารโปรเจกต์สำหรับทีม remote\n"
                "Features:\n"
                "- Task board (Kanban + Scrum)\n"
                "- Time tracking per task\n"
                "- Team chat with threads\n"
                "- AI daily standup summarizer\n"
                "- GitHub/Jira integration\n"
                "Tech: Next.js 14, tRPC, Prisma, MySQL, WebSocket"
            ),
            roles            = ["ba", "sa", "dev"],   # partial pipeline for speed
            force_billing_at = "sa",                   # force 401 → fallback at SA
        )
        results["scenario_b"] = result_b
        log(f"\n  Scenario B DONE: {result_b['passed']}/{result_b['total']} roles")
    except Exception as e:
        log(f"\n  Scenario B FAILED: {e}")
        traceback.print_exc()
        results["scenario_b"] = {"error": str(e)}

    # ══════════════════════════════════════════════════════════
    # FINAL REPORT
    # ══════════════════════════════════════════════════════════
    log("\n" + "="*65)
    log("  FINAL TEST REPORT")
    log("="*65)

    from shared.model_router import CostTracker
    cost_summary = CostTracker().today_summary()

    # Compile report
    report_lines = ["# Discord Live Test Report\n"]
    total_pass = 0
    total_roles = 0

    for key, res in results.items():
        if "error" in res:
            report_lines.append(f"## ❌ {key}: ERROR — {res['error'][:100]}\n")
            continue
        passed = res["passed"]
        total  = res["total"]
        total_pass  += passed
        total_roles += total
        report_lines.append(f"## {key}: {passed}/{total} roles passed\n")
        for step in res.get("pipeline", []):
            icon = "✅" if step["status"]=="approved" else "🔄" if step["status"]=="revision" else "❌"
            fb   = " *(fallback model)*" if step.get("is_fallback") else ""
            report_lines.append(f"- {icon} {step['role'].upper():8} {step.get('elapsed',0):.0f}s{fb}")
        report_lines.append("")

    report_lines += [
        f"\n## Cost Summary",
        f"- Total calls: {cost_summary.get('total_calls',0)}",
        f"- Total spend: ${cost_summary.get('total_spend',0):.4f}",
        f"- Models used:",
    ]
    for row in cost_summary.get("breakdown", []):
        tier_e = {"free":"🆓","cheap":"💰","smart":"🧠"}.get(row.get("tier",""),"")
        report_lines.append(f"  {tier_e} {row['model']:40} {row['calls']} calls")

    report_md = "\n".join(report_lines)
    report_path = ROOT / "outputs" / f"discord_test_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    report_path.write_text(report_md, encoding="utf-8")
    log(f"\nReport saved: {report_path}")

    for line in report_lines[:30]:
        log(line)

    # Final Discord post
    breakdown_lines = []
    for row in cost_summary.get("breakdown", [])[:6]:
        tier_e = {"free":"🆓","cheap":"💰","smart":"🧠"}.get(row.get("tier",""),"")
        breakdown_lines.append(f"{tier_e} `{row['model'][:35]}` — {row['calls']} calls")

    await discord_post("project-dashboard", BOT_TOKENS["system"],
        content=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **Full-Loop Test Complete!**\n\n"
            f"**Scenario A (HealthTrack):** {results.get('scenario_a',{}).get('passed','?')}/8 roles\n"
            f"**Scenario B (Fallback test):** {results.get('scenario_b',{}).get('passed','?')}/3 roles\n\n"
            f"**Cost:** `${cost_summary.get('total_spend',0):.4f}` ({cost_summary.get('total_calls',0)} LLM calls)\n"
            f"**Models used:**\n" + "\n".join(breakdown_lines) + "\n"
            f"📄 Report: `{report_path.name}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    )
    await asyncio.sleep(1)

    log(f"\nLog file: {LOG_FILE}")
    log("DONE.")
    _log_fh.close()

    return results


if __name__ == "__main__":
    asyncio.run(main())
