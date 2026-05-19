#!/usr/bin/env python3
"""
Pipeline Watcher — monitor SDLC pipeline events in real-time from terminal
เรียกใช้: python3 scripts/watch_pipeline.py [--project PROJECT_ID]

แสดง:
  - Pipeline phase transitions
  - Model routing decisions (free/cheap/smart)
  - Fallback events
  - Cost running total
  - Approval/rejection events
"""
import os, sys, time, json, sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/sdlc.db")

# Colors
G  = "\033[92m"; Y  = "\033[93m"; R  = "\033[91m"
B  = "\033[94m"; C  = "\033[96m"; W  = "\033[97m"
D  = "\033[90m"; RS = "\033[0m";  BOLD = "\033[1m"

def ts():
    return datetime.now().strftime("%H:%M:%S")

def watch(project_filter: str = None):
    print(f"\n{BOLD}{C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RS}")
    print(f"{BOLD}{W}  SDLC Pipeline Watcher — {ts()}{RS}")
    if project_filter:
        print(f"{D}  Filtering: project={project_filter}{RS}")
    print(f"{C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RS}\n")
    print(f"{D}  DB: {DB_PATH} | Press Ctrl+C to exit{RS}\n")

    seen_tasks = set()
    seen_projects = {}
    last_cost_check = time.time()

    ROLE_EMOJI = {
        "ceo":"👔","pm":"📋","ba":"📝","sa":"🏗️",
        "uxui":"🎨","dev":"💻","qa":"🧪","devops":"⚙️",
    }
    STATUS_COLOR = {
        "pending":   Y, "in_progress": B,
        "approved":  G, "completed":   G,
        "rejected":  R, "revision_requested": Y,
    }

    while True:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row

                # ── Projects ────────────────────────────────────────────
                for p in conn.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT 20").fetchall():
                    pid, role, status = p["id"], p["current_role"], p["status"]
                    if project_filter and pid != project_filter:
                        continue
                    prev = seen_projects.get(pid)
                    if prev != (role, status):
                        if prev is None:
                            print(f"{ts()} {B}NEW{RS} `{pid}` {p['name']} — phase: {ROLE_EMOJI.get(role,'')}{BOLD}{role.upper()}{RS}")
                        else:
                            prev_role, _ = prev
                            if role == "completed":
                                print(f"{ts()} {G}🎉 COMPLETE{RS} `{pid}` — {p['name']}")
                            elif role == "rejected":
                                print(f"{ts()} {R}✗ REJECTED{RS} `{pid}`")
                            elif prev_role != role:
                                print(f"{ts()} {G}▶ {prev_role.upper()} → {ROLE_EMOJI.get(role,'')}{BOLD}{role.upper()}{RS}  `{pid}`")
                        seen_projects[pid] = (role, status)

                # ── Tasks ──────────────────────────────────────────────
                for t in conn.execute("SELECT * FROM role_tasks ORDER BY created_at DESC LIMIT 50").fetchall():
                    tid = t["id"]
                    if tid in seen_tasks:
                        continue
                    if project_filter and t["project_id"] != project_filter:
                        continue
                    seen_tasks.add(tid)
                    role, status = t["role"], t["status"]
                    sc = STATUS_COLOR.get(status, W)
                    emoji = ROLE_EMOJI.get(role, "")
                    rev = f" rev={t['revision_count']}" if t.get("revision_count", 0) > 0 else ""
                    note = f"  {D}{str(t.get('notes',''))[:40]}{RS}" if t.get("notes") else ""
                    print(f"{ts()} {sc}{status.upper():22}{RS} {emoji}{role.upper():8} `{t['project_id']}`{rev}{note}")

            # ── Cost every 30s ────────────────────────────────────────
            if time.time() - last_cost_check > 30:
                last_cost_check = time.time()
                try:
                    from shared.model_router import CostTracker
                    s = CostTracker().today_summary()
                    if s.get("total_calls", 0) > 0:
                        print(f"\n{D}  ── 💰 ${s['total_spend']:.4f} today ({s['total_calls']} calls) ──{RS}\n")
                except Exception:
                    pass

            time.sleep(2)

        except KeyboardInterrupt:
            print(f"\n{D}  Watcher stopped.{RS}")
            break
        except Exception as e:
            print(f"{R}  Error: {e}{RS}")
            time.sleep(5)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None, help="Filter by project ID")
    args = ap.parse_args()
    watch(args.project)
