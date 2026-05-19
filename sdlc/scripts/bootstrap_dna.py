#!/usr/bin/env python3
"""
Bootstrap DNA for all roles (or a specific role) using paid model.
Run once per project type to dramatically improve free model quality.

Usage:
    python scripts/bootstrap_dna.py
    python scripts/bootstrap_dna.py --role ba
    python scripts/bootstrap_dna.py --context "E-commerce platform with React + FastAPI"
    python scripts/bootstrap_dna.py --refresh   # force re-generate all
"""
import os, sys, asyncio, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

from shared.dna_bootstrap import DNABootstrap

async def main():
    parser = argparse.ArgumentParser(description="Bootstrap model DNA for free model quality improvement")
    parser.add_argument("--role",    help="Bootstrap single role (e.g. ba, dev, sa)")
    parser.add_argument("--context", default="", help="Project context description")
    parser.add_argument("--refresh", action="store_true", help="Force re-generate even if cached")
    args = parser.parse_args()

    dna = DNABootstrap()

    if args.role:
        print(f"\n🧬 Bootstrapping DNA for role: {args.role.upper()}")
        result = await dna.bootstrap_role(args.role, args.context, force_refresh=args.refresh)
        print(f"✅ Done: {args.role.upper()}")
        print(f"   Compressed prompt: {len(result.get('compressed_system_prompt',''))} chars")
        print(f"   Format rules: {len(result.get('format_rules', []))}")
        print(f"   Has few-shot: {'Yes' if result.get('few_shot_snippet') else 'No'}")
        print(f"   Anti-patterns: {len(result.get('anti_patterns', []))}")
    else:
        print("\n🧬 Bootstrapping DNA for ALL 8 roles...")
        print(f"   Context: {args.context[:80] or '(none — generic software project)'}\n")
        results = await dna.bootstrap_all(args.context, force_refresh=args.refresh)
        print("\n📊 Results:")
        print(f"{'Role':10} {'Status':8} {'Prompt':12} {'Rules':8} {'Example':8}")
        print("-" * 55)
        for role, d in results.items():
            status = "✅ OK" if d else "❌ FAIL"
            prompt_len = len(d.get("compressed_system_prompt", ""))
            rules = len(d.get("format_rules", []))
            has_ex = "✅" if d.get("few_shot_snippet") else "❌"
            print(f"{role:10} {status:8} {prompt_len:12} {rules:8} {has_ex:8}")

    # Show current cache status
    print("\n📋 Current DNA cache:")
    for entry in dna.list_cached_roles():
        print(f"   {entry['role']:8} [{entry['type']:10}] via {entry['model']:<30} updated {entry['updated_at'][:16]}")

if __name__ == "__main__":
    asyncio.run(main())
