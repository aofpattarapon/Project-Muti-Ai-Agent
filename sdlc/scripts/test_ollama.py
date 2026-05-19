#!/usr/bin/env python3
"""
Test Ollama connectivity from OrbStack → Mac
รัน: python3 scripts/test_ollama.py
"""
import os, sys, asyncio, httpx
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

async def test():
    print(f"Testing Ollama at: {OLLAMA_URL}\n")

    # 1. Connectivity
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"✅ Connected! Installed models ({len(models)}):")
            for m in models:
                print(f"   • {m}")
    except Exception as e:
        print(f"❌ Cannot connect: {e}")
        print(f"  ► On Mac: OLLAMA_HOST=0.0.0.0 ollama serve")
        return

    # 2. Inference test (use first available model)
    if models:
        test_model = next((m for m in models if "hermes3" in m), models[0])
        print(f"\nTesting inference with {test_model}...")
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": test_model,
                    "messages": [{"role": "user", "content": "Reply with exactly: OLLAMA_OK"}],
                    "stream": False,
                })
                r.raise_for_status()
                content = r.json()["message"]["content"]
                print(f"✅ Inference OK: {content[:80]}")
        except Exception as e:
            print(f"❌ Inference failed: {e}")

    # 3. Model upgrade status
    print("\nModel upgrade path (pull these for higher quality):")
    upgrades = [
        ("qwen2.5-coder:7b",  "qwen2.5-coder:14b", "DEV/DevOps  85-90% Claude"),
        ("deepseek-r1:7b",    "deepseek-r1:14b",   "SA  85-90% o1-mini reasoning"),
        ("qwen3:8b",          "qwen3:14b",          "PM/BA/QA  75-80% Claude"),
    ]
    for current, upgrade, note in upgrades:
        has_current = current in models
        has_upgrade = upgrade in models
        if has_upgrade:
            print(f"  ✅ {upgrade:30} ({note})")
        elif has_current:
            print(f"  ⬆️  {current:30} → run: ollama pull {upgrade}  ({note})")
        else:
            print(f"  ⏳ not installed         → run: ollama pull {upgrade}  ({note})")

asyncio.run(test())
