#!/usr/bin/env python3
"""
Reset all runtime data — ล้าง DB ทั้ง SDLC + Web App
เก็บ: DNA cache, agent_role_configs, system_configs, users

Run: python3 scripts/reset_all_data.py
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SDLC_DB = os.getenv("DB_PATH", "/home/socket9companylimited/projects/multi-ai-agent/sdlc/data/sdlc.db")
WEBAPP_DB = "/home/socket9companylimited/projects/multi-ai-agent/webapp/data/multi-ai-agent-app.db"

SDLC_CLEAR = ["sdlc_tasks", "epics", "role_tasks", "projects", "llm_usage", "time_logs"]
WEBAPP_CLEAR = ["agent_activity_logs", "project_hot_cache", "approval_items", "audit_events"]


def reset_db(path: str, tables: list, label: str):
    if not os.path.exists(path):
        print(f"  ⏭️  {label}: DB not found at {path}, skip")
        return
    with sqlite3.connect(path) as conn:
        for t in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                conn.execute(f"DELETE FROM {t}")
                # Reset auto-increment sequences
                conn.execute(f"DELETE FROM sqlite_sequence WHERE name=?", (t,))
                print(f"  🗑️  {label}.{t}: {count} rows deleted")
            except Exception as e:
                print(f"  ⚠️  {label}.{t}: {e}")
        conn.commit()


def main():
    print("\n🧹 Reset All Runtime Data")
    print("=" * 50)
    print(f"\n📦 SDLC DB ({SDLC_DB}):")
    reset_db(SDLC_DB, SDLC_CLEAR, "sdlc")

    print(f"\n🌐 Web App DB ({WEBAPP_DB}):")
    reset_db(WEBAPP_DB, WEBAPP_CLEAR, "webapp")

    # Clear outputs directory (keep structure, delete files)
    output_base = os.getenv("OUTPUT_BASE_PATH", "/home/socket9companylimited/projects/multi-ai-agent/sdlc/outputs")
    projects_dir = os.path.join(output_base, "projects")
    if os.path.exists(projects_dir):
        import shutil
        count = 0
        for item in os.listdir(projects_dir):
            item_path = os.path.join(projects_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                count += 1
        print(f"\n📁 Outputs: {count} project directories removed")
    else:
        print(f"\n📁 Outputs: {projects_dir} not found, skip")

    print("\n✅ Reset complete. DNA cache preserved.")
    print("   Next: run discord purge → python3 scripts/purge_all_messages.py")
    print("   Then: start agents → ./scripts/start_pm2.sh")


if __name__ == "__main__":
    main()
