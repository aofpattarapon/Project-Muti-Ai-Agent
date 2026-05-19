#!/usr/bin/env python3
"""
Bot Config Manager — ตรวจสอบและจัดการ Discord config ทุกอย่าง

Commands:
  check           — ตรวจสอบ config ทั้งหมด (intents, channels, roles, permissions)
  fix-channels    — สร้าง/แก้ไข channels ที่หายไปหรือ topic ผิด
  fix-topics      — อัพเดท channel topics ทุกช่องให้ถูกต้อง
  edit-topic      — แก้ topic ช่องที่ระบุ
  add-channel     — สร้าง channel ใหม่
  delete-channel  — ลบ channel
  invite-urls     — แสดง invite URL ของทุก bot (ใช้ re-invite เพื่อให้ได้ permission ใหม่)
  bot-profiles    — แสดงและแก้ไข bot username/description

Run: venv/bin/python scripts/bot_config.py <command> [options]
"""
import os, sys, json, subprocess, argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
GUILD_ID   = os.getenv("DISCORD_GUILD_ID", "")
API_BASE   = "https://discord.com/api/v10"

BOTS = {
    "ceo":    {"token": os.getenv("CEO_DISCORD_TOKEN", ""),    "id": "1503718256685486200"},
    "pm":     {"token": os.getenv("PM_DISCORD_TOKEN", ""),     "id": "1503700367391854622"},
    "ba":     {"token": os.getenv("BA_DISCORD_TOKEN", ""),     "id": "1503701507827302530"},
    "sa":     {"token": os.getenv("SA_DISCORD_TOKEN", ""),     "id": "1503701780444479508"},
    "uxui":   {"token": os.getenv("UXUI_DISCORD_TOKEN", ""),   "id": "1504048722806571058"},
    "dev":    {"token": os.getenv("FRONTEND_DISCORD_TOKEN", ""), "id": "1503702193969041418"},
    "qa":     {"token": os.getenv("QA_DISCORD_TOKEN", ""),     "id": "1503702019897294928"},
    "devops": {"token": os.getenv("DEVOPS_DISCORD_TOKEN", ""), "id": "1503702399158718624"},
}

CEO_TOKEN = BOTS["ceo"]["token"]

# Required bot permissions integer (VIEW_CHANNEL + SEND_MESSAGES + READ_MESSAGE_HISTORY
# + ADD_REACTIONS + EMBED_LINKS + ATTACH_FILES + MANAGE_MESSAGES + USE_SLASH_COMMANDS)
BOT_PERMISSIONS = 534723950656

# Intent flag bits
FLAG_MESSAGE_CONTENT     = 1 << 17   # 131072  — full approved
FLAG_MESSAGE_CONTENT_LTD = 1 << 18   # 262144  — dev portal enabled (small bot)
FLAG_GUILD_MEMBERS       = 1 << 9    # 512
FLAG_GUILD_MEMBERS_LTD   = 1 << 14   # 16384

# Required channels per role
ROLE_CHANNELS = {
    "ceo":    ["ceo-inbox",    "ceo-room",    "ceo-output",    "ceo-timelog",    "ceo-approve"],
    "pm":     ["pm-inbox",     "pm-room",     "pm-output",     "pm-timelog",     "pm-approve"],
    "ba":     ["ba-inbox",     "ba-room",     "ba-output",     "ba-timelog",     "ba-approve"],
    "sa":     ["sa-inbox",     "sa-room",     "sa-output",     "sa-timelog",     "sa-approve"],
    "uxui":   ["uxui-inbox",   "uxui-room",   "uxui-output",   "uxui-timelog",   "uxui-approve"],
    "dev":    ["dev-inbox",    "dev-room",    "dev-output",    "dev-timelog",    "dev-approve"],
    "qa":     ["qa-inbox",     "qa-room",     "qa-output",     "qa-timelog",     "qa-approve"],
    "devops": ["devops-inbox", "devops-room", "devops-output", "devops-timelog", "devops-approve"],
}

EXTRA_CHANNELS = ["ceo-input", "project-dashboard", "room-all-role-for-discus",
                  "report-agent", "report-output", "log"]

_DISPLAY = {
    "ceo": "CEO", "pm": "PM", "ba": "BA", "sa": "SA",
    "uxui": "UX/UI", "dev": "DEV", "qa": "QA", "devops": "DevOps"
}

CHANNEL_TOPICS = {
    "ceo-input":                "👤 Assign project or task — !new ProjectName | description",
    "project-dashboard":        "📊 Summary of all pipeline processes",
    "room-all-role-for-discus": "🗣️ Cross-role discussion channel",
    "report-agent":             "📋 Agent activity reports",
    "report-output":            "📋 Final pipeline reports & exports",
    "log":                      "📝 System logs",
    **{f"{r}-inbox":   f"📥 Manually assign task to {_DISPLAY[r]} agent"           for r in ROLE_CHANNELS},
    **{f"{r}-room":    f"💬 Talk with {_DISPLAY[r]} agent / status updates"        for r in ROLE_CHANNELS},
    **{f"{r}-output":  f"📤 {_DISPLAY[r]} agent output & results"                  for r in ROLE_CHANNELS},
    **{f"{r}-timelog": f"⏱️ {_DISPLAY[r]} Jira-style time log"                     for r in ROLE_CHANNELS},
    **{f"{r}-approve": f"✅ {_DISPLAY[r]} approval — reply !approve | !revise [note] | !reject [reason]" for r in ROLE_CHANNELS},
}

# ─── Colors ───────────────────────────────────────────────────────────────────
G="\033[92m"; Y="\033[93m"; R="\033[91m"; B="\033[94m"; C="\033[96m"
W="\033[97m"; D="\033[90m"; RS="\033[0m"; BOLD="\033[1m"

def ok(msg):  print(f"  {G}✅{RS} {msg}")
def warn(msg): print(f"  {Y}⚠️ {RS} {msg}")
def err(msg): print(f"  {R}❌{RS} {msg}")
def info(msg): print(f"  {D}ℹ️ {RS} {msg}")

# ─── Discord API helpers ──────────────────────────────────────────────────────

def api_get(path, token=None):
    token = token or CEO_TOKEN
    r = subprocess.run(
        ["curl", "-s", f"{API_BASE}{path}", "-H", f"Authorization: Bot {token}"],
        capture_output=True, text=True, timeout=10
    )
    try: return json.loads(r.stdout)
    except: return {}

def api_post(path, data, token=None):
    token = token or CEO_TOKEN
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{API_BASE}{path}",
         "-H", f"Authorization: Bot {token}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(data)],
        capture_output=True, text=True, timeout=10
    )
    try: return json.loads(r.stdout)
    except: return {}

def api_patch(path, data, token=None):
    token = token or CEO_TOKEN
    r = subprocess.run(
        ["curl", "-s", "-X", "PATCH", f"{API_BASE}{path}",
         "-H", f"Authorization: Bot {token}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(data)],
        capture_output=True, text=True, timeout=10
    )
    try: return json.loads(r.stdout)
    except: return {}

def api_delete(path, token=None):
    token = token or CEO_TOKEN
    r = subprocess.run(
        ["curl", "-s", "-X", "DELETE", f"{API_BASE}{path}",
         "-H", f"Authorization: Bot {token}"],
        capture_output=True, text=True, timeout=10
    )
    return r.returncode == 0

def get_channels():
    chs = api_get(f"/guilds/{GUILD_ID}/channels")
    if isinstance(chs, list):
        return {c["name"]: c for c in chs if c.get("type") == 0}
    return {}

def get_categories():
    chs = api_get(f"/guilds/{GUILD_ID}/channels")
    if isinstance(chs, list):
        return {c["name"]: c for c in chs if c.get("type") == 4}
    return {}

# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_check():
    """ตรวจสอบ config ทั้งหมด"""
    print(f"\n{BOLD}{C}{'━'*65}{RS}")
    print(f"{BOLD}{W}  Discord Bot Config Audit{RS}")
    print(f"{C}{'━'*65}{RS}\n")

    has_issues = False

    # ── 1. Privileged Intents ─────────────────────────────────────────────────
    print(f"{BOLD}{B}1. Privileged Gateway Intents{RS}")
    print(f"   {D}(ต้องแก้ที่ discord.com/developers/applications — ไม่มี API สำหรับเปลี่ยน){RS}\n")

    intent_issues = []
    for role, info_d in BOTS.items():
        token = info_d["token"]
        if not token:
            err(f"{role.upper()}: ไม่มี token ใน .env")
            intent_issues.append(role)
            continue
        d = api_get("/applications/@me", token=token)
        flags = d.get("flags", 0)
        app_id = d.get("id", "?")
        uname = d.get("name", "?")

        mc = bool(flags & FLAG_MESSAGE_CONTENT) or bool(flags & FLAG_MESSAGE_CONTENT_LTD)
        gm = bool(flags & FLAG_GUILD_MEMBERS) or bool(flags & FLAG_GUILD_MEMBERS_LTD)

        mc_str = f"{G}✅ ON{RS}" if mc else f"{R}❌ OFF{RS}"
        gm_str = f"{G}✅ ON{RS}" if gm else f"{Y}⚠️ OFF{RS}"

        status = f"{role.upper():<8} [{app_id}] {uname:<20} MSG_CONTENT={mc_str}  GUILD_MEMBERS={gm_str}"
        print(f"   {status}")

        if not mc:
            intent_issues.append(role)

    if intent_issues:
        has_issues = True
        print(f"\n   {R}{BOLD}⚠️  {len(intent_issues)} bot(s) ขาด MESSAGE_CONTENT intent:{RS}")
        print(f"   {Y}Steps to fix:{RS}")
        for role in intent_issues:
            bot_id = BOTS[role]["id"]
            print(f"   {D}→{RS} https://discord.com/developers/applications/{bot_id}/bot")
            print(f"     Privileged Gateway Intents → MESSAGE CONTENT INTENT → ON")
        print(f"\n   {D}หลังจากแก้แล้ว restart bot: pm2 restart sdlc-{intent_issues[0]} (หรือ pm2 restart all){RS}")
    else:
        ok("All bots have MESSAGE_CONTENT intent enabled")

    # ── 2. Channels ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}{B}2. Discord Channels{RS}\n")
    channels = get_channels()
    all_required = EXTRA_CHANNELS[:]
    for chs in ROLE_CHANNELS.values():
        all_required.extend(chs)

    missing = [c for c in all_required if c not in channels]
    extra   = [c for c in channels if c not in all_required]

    if missing:
        has_issues = True
        for c in missing:
            err(f"Missing channel: #{c}")
    else:
        ok(f"All {len(all_required)} required channels exist")

    if extra:
        for c in extra:
            warn(f"Extra channel (not in config): #{c}")

    # ── 3. Channel Topics ─────────────────────────────────────────────────────
    print(f"\n{BOLD}{B}3. Channel Topics{RS}\n")
    wrong_topics = []
    for name, expected_topic in CHANNEL_TOPICS.items():
        if name not in channels:
            continue
        actual = (channels[name].get("topic") or "").strip()
        if actual != expected_topic:
            wrong_topics.append((name, actual, expected_topic))

    if wrong_topics:
        has_issues = True
        for name, actual, expected in wrong_topics:
            warn(f"#{name}: topic mismatch")
            print(f"     {D}actual  : {actual[:60] or '(empty)'}{RS}")
            print(f"     {Y}expected: {expected[:60]}{RS}")
    else:
        ok(f"All channel topics correct")

    # ── 4. Bot Roles in Guild ─────────────────────────────────────────────────
    print(f"\n{BOLD}{B}4. Bot Guild Roles & Permissions{RS}\n")
    for role, info_d in BOTS.items():
        bot_id = info_d["id"]
        member = api_get(f"/guilds/{GUILD_ID}/members/{bot_id}")
        if "user" not in member:
            err(f"{role.upper()} bot (ID {bot_id}) not in guild!")
            has_issues = True
            continue
        roles_in_guild = member.get("roles", [])
        if not roles_in_guild:
            warn(f"{role.upper()}: no role assigned in guild")
            has_issues = True
        else:
            ok(f"{role.upper()}: in guild with {len(roles_in_guild)} role(s)")

    # ── 5. PM2 Process Status ─────────────────────────────────────────────────
    print(f"\n{BOLD}{B}5. PM2 Process Status{RS}\n")
    r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
    try:
        processes = json.loads(r.stdout)
        pm2_map = {p["name"]: p for p in processes}
    except:
        pm2_map = {}

    pm2_names = [f"sdlc-{role}" for role in BOTS] + ["sdlc-cron"]
    for pname in pm2_names:
        if pname in pm2_map:
            p = pm2_map[pname]
            status = p.get("pm2_env", {}).get("status", "?")
            restarts = p.get("pm2_env", {}).get("restart_time", 0)
            mem = p.get("monit", {}).get("memory", 0) // 1024 // 1024
            col = G if status == "online" else R
            print(f"   {col}{'●'}{RS} {pname:<15} {col}{status}{RS}  restarts={restarts}  mem={mem}MB")
        else:
            err(f"{pname}: not found in PM2")
            has_issues = True

    # ── 6. Environment Variables ──────────────────────────────────────────────
    print(f"\n{BOLD}{B}6. Environment Variables (.env){RS}\n")
    env_checks = [
        ("DISCORD_GUILD_ID",         os.getenv("DISCORD_GUILD_ID")),
        ("DISCORD_APPROVAL_CHANNEL_ID", os.getenv("DISCORD_APPROVAL_CHANNEL_ID")),
        ("ANTHROPIC_API_KEY",        os.getenv("ANTHROPIC_API_KEY")),
        ("GROQ_API_KEY",             os.getenv("GROQ_API_KEY")),
        ("OLLAMA_URL",               os.getenv("OLLAMA_URL")),
        ("DB_PATH",                  os.getenv("DB_PATH")),
        ("OUTPUT_BASE_PATH",         os.getenv("OUTPUT_BASE_PATH")),
    ]
    for key, val in env_checks:
        if val:
            masked = val[:8] + "..." if len(val) > 8 else val
            ok(f"{key} = {masked}")
        else:
            warn(f"{key} not set")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{C}{'━'*65}{RS}")
    if has_issues:
        print(f"{R}{BOLD}  ⚠️  Issues found — run 'fix-channels' or check portal links above{RS}")
    else:
        print(f"{G}{BOLD}  ✅ All config looks good!{RS}")
    print(f"{C}{'━'*65}{RS}\n")


def cmd_fix_channels():
    """สร้าง channels ที่ขาดและอัพเดท topics ที่ผิด"""
    print(f"\n{BOLD}{C}Fix Channels{RS}\n")
    channels = get_channels()
    categories = get_categories()

    # Build list of all required channels
    all_required = {}
    all_required["ceo-input"] = CHANNEL_TOPICS.get("ceo-input", "")
    all_required["project-dashboard"] = CHANNEL_TOPICS.get("project-dashboard", "")
    for name, topic in CHANNEL_TOPICS.items():
        all_required[name] = topic

    created = 0; updated = 0; skipped = 0

    for name, topic in all_required.items():
        if name not in channels:
            # Create channel
            r = api_post(f"/guilds/{GUILD_ID}/channels", {
                "name": name, "type": 0, "topic": topic
            })
            if "id" in r:
                ok(f"Created #{name}")
                created += 1
            else:
                err(f"Failed to create #{name}: {r}")
        else:
            # Update topic if wrong
            actual = (channels[name].get("topic") or "").strip()
            if actual != topic:
                r = api_patch(f"/channels/{channels[name]['id']}", {"topic": topic})
                if "id" in r:
                    ok(f"Updated topic: #{name}")
                    updated += 1
                else:
                    err(f"Failed to update #{name}: {r}")
            else:
                skipped += 1

    print(f"\n  {G}Created: {created}{RS}  {Y}Updated: {updated}{RS}  {D}Skipped (ok): {skipped}{RS}\n")


def cmd_fix_topics():
    """อัพเดท channel topics ทุกช่องให้ตรงกับ config"""
    print(f"\n{BOLD}{C}Fix Channel Topics{RS}\n")
    channels = get_channels()
    updated = 0; failed = 0

    for name, topic in CHANNEL_TOPICS.items():
        if name not in channels:
            warn(f"#{name} doesn't exist — run fix-channels first")
            continue
        r = api_patch(f"/channels/{channels[name]['id']}", {"topic": topic})
        if "id" in r:
            ok(f"#{name}")
            updated += 1
        else:
            err(f"#{name} failed: {r}")
            failed += 1

    print(f"\n  {G}Updated: {updated}{RS}  {R}Failed: {failed}{RS}\n")


def cmd_edit_topic(channel_name: str, new_topic: str):
    """แก้ topic ของ channel ที่ระบุ"""
    channels = get_channels()
    if channel_name not in channels:
        err(f"Channel #{channel_name} not found")
        print(f"  Available: {', '.join(sorted(channels.keys()))}")
        return
    r = api_patch(f"/channels/{channels[channel_name]['id']}", {"topic": new_topic})
    if "id" in r:
        ok(f"Updated #{channel_name} topic: {new_topic}")
    else:
        err(f"Failed: {r}")


def cmd_add_channel(name: str, topic: str = "", category: str = None):
    """สร้าง channel ใหม่"""
    channels = get_channels()
    if name in channels:
        err(f"#{name} already exists (ID: {channels[name]['id']})")
        return

    data = {"name": name, "type": 0}
    if topic:
        data["topic"] = topic
    if category:
        cats = get_categories()
        if category in cats:
            data["parent_id"] = cats[category]["id"]
        else:
            warn(f"Category '{category}' not found — creating without category")

    r = api_post(f"/guilds/{GUILD_ID}/channels", data)
    if "id" in r:
        ok(f"Created #{name} (ID: {r['id']})")
        if topic: info(f"Topic: {topic}")
        if category: info(f"Category: {category}")
    else:
        err(f"Failed: {r}")


def cmd_delete_channel(name: str, confirm: bool = False):
    """ลบ channel"""
    channels = get_channels()
    if name not in channels:
        err(f"Channel #{name} not found")
        return

    ch_id = channels[name]["id"]
    if not confirm:
        print(f"  {Y}Are you sure you want to delete #{name} (ID: {ch_id})?{RS}")
        answer = input("  Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("  Cancelled.")
            return

    r = subprocess.run(
        ["curl", "-s", "-X", "DELETE", f"{API_BASE}/channels/{ch_id}",
         "-H", f"Authorization: Bot {CEO_TOKEN}"],
        capture_output=True, text=True, timeout=10
    )
    if r.returncode == 0 and (r.stdout == "" or r.stdout == "{}"):
        ok(f"Deleted #{name}")
    else:
        try:
            d = json.loads(r.stdout)
            err(f"Failed: {d.get('message', r.stdout)}")
        except:
            ok(f"Deleted #{name}")


def cmd_invite_urls():
    """แสดง invite URL พร้อม permissions ที่ถูกต้องสำหรับทุก bot"""
    print(f"\n{BOLD}{C}Bot Invite URLs{RS}")
    print(f"{D}(ใช้ URL นี้เพื่อ re-invite bot และให้ permissions ที่ถูกต้อง){RS}\n")
    print(f"  Permissions included:")
    print(f"  {D}VIEW_CHANNEL, SEND_MESSAGES, READ_MESSAGE_HISTORY, ADD_REACTIONS{RS}")
    print(f"  {D}EMBED_LINKS, ATTACH_FILES, MANAGE_MESSAGES, USE_SLASH_COMMANDS{RS}\n")

    # 8 = ADMINISTRATOR (simplest — gives all permissions)
    PERMS = 8
    SCOPES = "bot%20applications.commands"

    for role, info_d in BOTS.items():
        bot_id = info_d["id"]
        url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions={PERMS}&scope={SCOPES}&guild_id={GUILD_ID}"
        print(f"  {BOLD}{role.upper():<8}{RS} {bot_id}")
        print(f"  {B}{url}{RS}\n")


def cmd_bot_profiles():
    """แสดง bot profiles และอัพเดทได้"""
    print(f"\n{BOLD}{C}Bot Profiles{RS}\n")
    for role, info_d in BOTS.items():
        token = info_d["token"]
        if not token:
            err(f"{role.upper()}: no token")
            continue
        d = api_get("/users/@me", token=token)
        app = api_get("/applications/@me", token=token)
        flags = app.get("flags", 0)
        mc = bool(flags & FLAG_MESSAGE_CONTENT) or bool(flags & FLAG_MESSAGE_CONTENT_LTD)
        mc_icon = f"{G}✅{RS}" if mc else f"{R}❌{RS}"

        print(f"  {BOLD}{role.upper():<8}{RS} {d.get('username','?'):<20} ID={d.get('id','?')}")
        print(f"           MSG_CONTENT={mc_icon}  flags={flags}")
        print(f"           Portal: {B}https://discord.com/developers/applications/{info_d['id']}/bot{RS}")
        print()


def cmd_portal_guide():
    """แสดง step-by-step guide สำหรับ enable MESSAGE_CONTENT ทุก bot"""
    print(f"\n{BOLD}{Y}{'━'*65}{RS}")
    print(f"{BOLD}{W}  Manual Steps: Enable MESSAGE CONTENT INTENT{RS}")
    print(f"{Y}{'━'*65}{RS}")
    print(f"\n  {W}ทำสำหรับทุก bot ด้านล่าง (8 ตัว):{RS}\n")
    print(f"  1. เปิด: {B}https://discord.com/developers/applications{RS}")
    print(f"  2. คลิกชื่อ application → เลือก {W}Bot{RS} (ในเมนูซ้าย)")
    print(f"  3. เลื่อนลงหา {W}Privileged Gateway Intents{RS}")
    print(f"  4. เปิด {G}MESSAGE CONTENT INTENT{RS} ✅")
    print(f"  5. กด {W}Save Changes{RS}")
    print(f"  6. ทำซ้ำกับ bot ถัดไป\n")
    print(f"  {Y}Links (คลิกเลย):{RS}\n")

    for role, info_d in BOTS.items():
        bid = info_d["id"]
        print(f"  {BOLD}{role.upper():<8}{RS} https://discord.com/developers/applications/{bid}/bot")

    print(f"\n  {W}หลังทำครบแล้ว restart bots:{RS}")
    print(f"  {B}pm2 restart all{RS}\n")
    print(f"  {W}หรือ restart ทีละตัว:{RS}")
    print(f"  {B}pm2 restart sdlc-ceo{RS}\n")
    print(f"{Y}{'━'*65}{RS}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Bot Config Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/bot_config.py check
  python scripts/bot_config.py fix-channels
  python scripts/bot_config.py fix-topics
  python scripts/bot_config.py edit-topic dev-approve "✅ DEV approval — !approve | !revise | !reject"
  python scripts/bot_config.py add-channel my-channel --topic "My channel topic"
  python scripts/bot_config.py delete-channel my-channel
  python scripts/bot_config.py invite-urls
  python scripts/bot_config.py bot-profiles
  python scripts/bot_config.py portal-guide
        """
    )
    ap.add_argument("command", choices=[
        "check", "fix-channels", "fix-topics", "edit-topic",
        "add-channel", "delete-channel", "invite-urls",
        "bot-profiles", "portal-guide"
    ])
    ap.add_argument("args", nargs="*", help="Additional arguments")
    ap.add_argument("--topic", default="", help="Channel topic for add-channel/edit-topic")
    ap.add_argument("--category", default=None, help="Category name for add-channel")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation for delete")

    args = ap.parse_args()
    cmd = args.command

    if cmd == "check":
        cmd_check()
    elif cmd == "fix-channels":
        cmd_fix_channels()
    elif cmd == "fix-topics":
        cmd_fix_topics()
    elif cmd == "edit-topic":
        if len(args.args) < 1:
            err("Usage: edit-topic <channel-name> <new-topic>")
            sys.exit(1)
        channel = args.args[0]
        new_topic = args.topic or (" ".join(args.args[1:]) if len(args.args) > 1 else "")
        if not new_topic:
            err("Please provide --topic 'new topic text'")
            sys.exit(1)
        cmd_edit_topic(channel, new_topic)
    elif cmd == "add-channel":
        if not args.args:
            err("Usage: add-channel <channel-name> [--topic '...' --category '...']")
            sys.exit(1)
        cmd_add_channel(args.args[0], topic=args.topic, category=args.category)
    elif cmd == "delete-channel":
        if not args.args:
            err("Usage: delete-channel <channel-name> [--yes]")
            sys.exit(1)
        cmd_delete_channel(args.args[0], confirm=args.yes)
    elif cmd == "invite-urls":
        cmd_invite_urls()
    elif cmd == "bot-profiles":
        cmd_bot_profiles()
    elif cmd == "portal-guide":
        cmd_portal_guide()


if __name__ == "__main__":
    main()
