#!/usr/bin/env python3
"""
Pre-Test DNA Bootstrap — seed all 8 roles before Discord live test
เรียกใช้: python3 scripts/pre_test_bootstrap.py

สิ่งที่ทำ:
  1. Bootstrap DNA ครบ 8 roles ด้วย claude-cli (paid model, once-only)
  2. Sync DNA ทุก role ไปยัง Obsidian vault
  3. พิมพ์ summary ว่า role ไหน cached / ข้ามแล้ว
"""
import os, sys, asyncio, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

from shared.dna_bootstrap import get_dna_bootstrap

ROLES = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]

PROJECT_CONTEXT = (
    "Thai SME software development. Projects include e-commerce, mobile apps, "
    "internal tools. Tech stack: React/Next.js frontend, FastAPI/Node backend, "
    "PostgreSQL/MongoDB, Docker, deployed to cloud (AWS/GCP). "
    "Language: Thai + English mixed."
)

async def main():
    dna = get_dna_bootstrap()
    print("\n🧬 Pre-Test DNA Bootstrap")
    print("=" * 50)

    cached_before = {e["role"] for e in dna.list_cached_roles()}
    print(f"Already cached: {cached_before or 'none'}\n")

    results = {}
    for role in ROLES:
        if role in cached_before:
            print(f"  ⏭️  {role.upper():8} — already cached, skip")
            results[role] = "skip"
            continue

        print(f"  🔄 {role.upper():8} — bootstrapping...", end="", flush=True)
        t0 = time.time()
        try:
            result = await dna.bootstrap_role(role, project_context=PROJECT_CONTEXT)
            elapsed = time.time() - t0
            if result:
                print(f" ✅ {elapsed:.1f}s ({len(result.get('compressed_system_prompt',''))} chars)")
                results[role] = "ok"
            else:
                print(f" ⚠️  empty result")
                results[role] = "empty"
        except Exception as e:
            print(f" ❌ {e}")
            results[role] = f"error: {e}"

    print("\n" + "=" * 50)
    print("Summary:")
    for role, status in results.items():
        icon = "✅" if status in ("ok","skip") else "❌"
        print(f"  {icon} {role.upper():8} {status}")

    cached_after = dna.list_cached_roles()
    print(f"\nTotal cached: {len(cached_after)}/8 roles")

asyncio.run(main())
