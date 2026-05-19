#!/usr/bin/env python3
"""
Auto Run Full Pipeline
1. Insert project ตรงเข้า DB (ไม่ผ่าน Discord command — บอทไม่ตอบสนองข้อความของตัวเอง)
2. Watch DB ทุก 5s — เมื่อ task ถึง waiting_approval + มี approval_message_id
3. POST reply "!approve" ไปยัง {role}-approve channel ผ่าน Discord REST API
4. บอทรับ reply → update DB → แจ้ง role ถัดไป → _task_poll_loop ของ role นั้น pick up

Run: venv/bin/python scripts/auto_run_project.py
"""
import os, sys, asyncio, sqlite3, json, uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

import httpx

# ─── Config ───────────────────────────────────────────────────────────────────
GUILD_ID    = os.getenv("DISCORD_GUILD_ID", "")
CEO_TOKEN   = os.getenv("CEO_DISCORD_TOKEN", "")
DB_PATH     = os.getenv("DB_PATH", "data/sdlc.db")
API_BASE    = "https://discord.com/api/v10"
OUTPUT_BASE = os.getenv("OUTPUT_BASE_PATH", "outputs")

ROLE_ORDER         = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
MAX_WAIT_PER_ROLE  = 3600   # 60 min per role
POLL_INTERVAL      = 5      # seconds

PROJECT_NAME = "HealthTrack Mobile App"
PROJECT_DESC = """HealthTrack Mobile App | แอปติดตามสุขภาพสำหรับผู้สูงอายุไทย

แอปพลิเคชัน mobile (iOS + Android) สำหรับผู้สูงอายุและผู้ดูแล
ช่วยติดตามสุขภาพประจำวัน ลดภาระผู้ดูแล และส่งข้อมูลให้แพทย์ได้

ฟีเจอร์หลัก:
- บันทึกยาและแจ้งเตือนเวลากินยา
- วัดและบันทึกความดันโลหิต / ระดับน้ำตาล
- บันทึกอาหารประจำวัน (photo + manual)
- Pedometer นับก้าวเดิน
- แจ้งเตือน Emergency ส่ง location ให้ผู้ดูแล
- Dashboard สรุปสุขภาพรายสัปดาห์
- Export รายงานสุขภาพ PDF ส่งแพทย์
- Chat กับ AI ผู้ช่วยสุขภาพ (RAG จากฐานข้อมูลยา)

Tech Stack: React Native + FastAPI + PostgreSQL + Docker + AWS
Timeline: 4 เดือน | Priority: High"""

# ─── Colors ───────────────────────────────────────────────────────────────────
G="\033[92m"; Y="\033[93m"; R="\033[91m"; B="\033[94m"; C="\033[96m"
W="\033[97m"; D="\033[90m"; RS="\033[0m"; BOLD="\033[1m"

def ts(): return datetime.now().strftime("%H:%M:%S")
def log(msg, color=W): print(f"{D}{ts()}{RS} {color}{msg}{RS}", flush=True)

# ─── Discord REST ─────────────────────────────────────────────────────────────

def dheaders():
    return {"Authorization": f"Bot {CEO_TOKEN}", "Content-Type": "application/json"}


def get_channels() -> dict:
    r = httpx.get(f"{API_BASE}/guilds/{GUILD_ID}/channels", headers=dheaders(), timeout=15)
    r.raise_for_status()
    return {ch["name"]: ch["id"] for ch in r.json() if ch.get("type") == 0}


def post_reply(channel_id: str, content: str, reference_msg_id: str) -> dict:
    """POST reply ไปยัง approval message"""
    r = httpx.post(
        f"{API_BASE}/channels/{channel_id}/messages",
        headers=dheaders(),
        json={
            "content": content,
            "message_reference": {"message_id": reference_msg_id},
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ─── DB helpers ───────────────────────────────────────────────────────────────

def db_row(sql, params=()):
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute(sql, params).fetchone()
    return dict(row) if row else None


def db_rows(sql, params=()):
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, params).fetchall()]


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main(resume_project_id: str = None):
    print(f"\n{BOLD}{C}{'━'*62}{RS}")
    print(f"{BOLD}{W}  Auto Full Pipeline — {PROJECT_NAME}{RS}")
    print(f"{D}  {ts()}{RS}")
    print(f"{C}{'━'*62}{RS}\n")

    # ── 1. Get already-approved roles (for resume) ──────────────────────────
    approved_roles = []

    # ── 2. Create or resume project ─────────────────────────────────────────
    if resume_project_id:
        project_id = resume_project_id
        proj = db_row("SELECT * FROM projects WHERE id=?", (project_id,))
        if not proj:
            log(f"❌ Project {project_id} not found in DB", R); return
        log(f"Resuming project {BOLD}{project_id}{RS} — {proj['name']}", Y)
        log(f"  Current role: {proj['current_role'].upper()}", D)
        # Mark already-completed roles as approved
        done_tasks = db_rows(
            "SELECT role FROM role_tasks WHERE project_id=? AND status='approved'",
            (project_id,),
        )
        approved_roles = [t["role"] for t in done_tasks]
        if approved_roles:
            log(f"  Already approved: {', '.join(r.upper() for r in approved_roles)}", D)
    else:
        project_id = f"HT-{str(uuid.uuid4())[:6].upper()}"
        log(f"Creating project: {BOLD}{project_id}{RS}", G)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    project_id, PROJECT_NAME, PROJECT_DESC,
                    datetime.now(timezone.utc).isoformat(), "ceo", "in_progress",
                    GUILD_ID, "", "{}",
                ),
            )
            conn.commit()
        log(f"✅ Project created — CEO agent will pick up within 20s\n", G)

    log(f"  Watching: {' → '.join(r.upper() for r in ROLE_ORDER)}", D)
    log(f"  Max wait per role: {MAX_WAIT_PER_ROLE//60} min\n", D)

    # ── 3. Watch loop ───────────────────────────────────────────────────────
    wait_seconds    = 0
    last_log_at     = 0

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        wait_seconds += POLL_INTERVAL

        proj = db_row("SELECT * FROM projects WHERE id=?", (project_id,))
        if not proj:
            log("❌ Project missing from DB!", R); break

        current_role = proj.get("current_role", "")
        status       = proj.get("status", "")

        # Finished?
        if current_role in ("completed", "done") or status in ("completed", "done"):
            log(f"\n{BOLD}{G}🎉 PROJECT COMPLETE!{RS}", G)
            break

        # Don't re-approve
        if current_role in approved_roles:
            continue

        # Check task status
        task = db_row(
            """SELECT * FROM role_tasks WHERE project_id=? AND role=?
               AND status='waiting_approval' ORDER BY created_at DESC LIMIT 1""",
            (project_id, current_role),
        )

        if task:
            wait_seconds = 0  # reset per-role timeout
            log(f"\n{'─'*55}", D)
            log(f"✅ {BOLD}{current_role.upper()}{RS} done — auto-approving via DB", G)
            log(f"   task: {task['id']}  |  approval_msg: {task.get('approval_message_id') or '(none)'}", D)
            _db_approve(project_id, current_role, task["id"])
            approved_roles.append(current_role)
            log(f"   ⏩ Next role will start within 20s...\n", C)
            await asyncio.sleep(5)
        else:
            # Task not done yet
            if wait_seconds - last_log_at > 60:
                log(f"⏳ {current_role.upper()} processing... ({wait_seconds}s elapsed)", D)
                last_log_at = wait_seconds
            if wait_seconds > MAX_WAIT_PER_ROLE:
                log(f"⚠️  {current_role.upper()} timeout after {MAX_WAIT_PER_ROLE}s", Y)
                break

    # ── 4. Show summary ─────────────────────────────────────────────────────
    await asyncio.sleep(3)
    show_results(project_id)


def _db_approve(project_id: str, role: str, task_id: str):
    """Approve via direct DB update — supports QA→DEV bug loop"""
    from shared.storage import Storage, TaskStatus
    s = Storage()

    # QA bug loop: if critical/high bugs found → send back to DEV
    if role == "qa":
        task = s.get_role_task(task_id)
        if task:
            try:
                od = json.loads(task.output_data or "{}")
                bugs     = int(od.get("bugs_found", 0) or 0)
                severity = od.get("severity_breakdown", {})
                critical = int(severity.get("critical", 0) or 0)
                high     = int(severity.get("high", 0) or 0)
                if bugs > 0 and (critical > 0 or high > 0):
                    s.set_role_feedback(project_id, "dev", od)
                    s.update_task_status(task_id, TaskStatus.APPROVED, "auto-approved (QA→DEV bug loop)")
                    s.update_project_role(project_id, "dev", "in_progress")
                    log(f"   🔁 QA bugs ({bugs}, crit={critical}/high={high}) → DEV fix", Y)
                    return
            except Exception:
                pass

    next_role = s.get_next_role(role)
    s.update_task_status(task_id, TaskStatus.APPROVED, "auto-approved (DB direct)")
    if next_role:
        s.update_project_role(project_id, next_role, "in_progress")
        log(f"   ✅ DB approved → {next_role.upper()}", G)
    else:
        s.update_project_role(project_id, "completed", "completed")
        log(f"   🎉 DB approved → PROJECT COMPLETE", G)


def show_results(project_id: str):
    print(f"\n{BOLD}{C}{'━'*62}{RS}")
    print(f"{BOLD}{W}  PIPELINE RESULTS — {project_id}{RS}")
    print(f"{C}{'━'*62}{RS}\n")

    tasks = db_rows(
        "SELECT * FROM role_tasks WHERE project_id=? ORDER BY created_at",
        (project_id,),
    )
    total_s = 0; total_cost = 0.0

    for t in tasks:
        dur_s  = t.get("duration_seconds") or 0
        cost   = t.get("cost_usd") or 0.0
        status = t.get("status", "?")
        role   = t.get("role", "?").upper()
        model  = (t.get("model_used") or "?")[:32]
        rev    = t.get("revision_count", 0)
        total_s += dur_s; total_cost += cost

        m, s = divmod(dur_s, 60)
        h, m = divmod(m, 60)
        dur_str = f"{h}h{m:02}m{s:02}s" if h else f"{m}m{s:02}s"

        sc = G if status == "approved" else (Y if "progress" in status else R)
        ic = "✅" if status == "approved" else ("⏳" if "progress" in status else "🔄")
        rv = f"  (rev={rev})" if rev > 0 else ""
        print(f"  {sc}{ic}{RS} {BOLD}{role:8}{RS}  {D}{dur_str:10}{RS}  {Y}${cost:.5f}{RS}  {D}{model}{RS}{rv}")

    h, r = divmod(total_s, 3600); m, s = divmod(r, 60)
    print(f"\n  {'─'*55}")
    print(f"  ⏱️  Total: {h}h {m}m {s}s   💰 ${total_cost:.4f}")

    # Output files
    out_dir = Path(OUTPUT_BASE) / "projects" / project_id
    if out_dir.exists():
        files = sorted(f for f in out_dir.rglob("*") if f.is_file())
        print(f"\n  📁 Output files ({len(files)} total):")
        for f in files:
            print(f"    • {D}{f.relative_to(out_dir)}{RS}  ({f.stat().st_size:,} B)")
    else:
        print(f"\n  📁 No output files found at {out_dir}")

    print(f"\n{C}{'━'*62}{RS}\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None, help="Resume an existing project ID")
    args = ap.parse_args()
    asyncio.run(main(resume_project_id=args.project))
