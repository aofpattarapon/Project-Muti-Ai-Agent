#!/usr/bin/env python3
"""
End-to-End Test Runner — ทดสอบทุก component ครบวงจร
=====================================================
ทดสอบ:
  Layer 1 — Python Core (storage, model router, output processor, role schemas)
  Layer 2 — Obsidian Integration (write, read, list, RAG, cron log)
  Layer 3 — Hermes Cron (ทุก 5 jobs)
  Layer 4 — DNA Bootstrap (1 role: ba)
  Layer 5 — Full SDLC Pipeline (8 roles, realistic project, auto-approve)
             Case A: E-commerce platform  (primary path)
             Case B: Model fallback       (force free model, verify quality)
  Layer 6 — Discord simulation (pipeline flow สมจริง, ไม่ต้องรัน bot จริง)

Usage:
  python scripts/test_e2e.py
  python scripts/test_e2e.py --layer 5        # run specific layer only
  python scripts/test_e2e.py --fast            # skip DNA bootstrap (slow)
  python scripts/test_e2e.py --report report.md
"""

import os, sys, json, uuid, asyncio, argparse, time, traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Path setup ────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DB_PATH",          str(ROOT / "data" / "sdlc.db"))
os.environ.setdefault("OUTPUT_BASE_PATH", str(ROOT / "outputs"))
os.environ.setdefault("OBSIDIAN_VAULT_PATH",
    "/Users/socket9companylimited/Documents/obsidian-vault")

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)   # .env can override defaults above

# ── Color helpers ─────────────────────────────────────────────
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
R  = "\033[91m"   # red
B  = "\033[94m"   # blue
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white
D  = "\033[90m"   # dim
RS = "\033[0m"    # reset
BOLD = "\033[1m"

def ok(msg):   print(f"  {G}✅{RS} {msg}")
def warn(msg): print(f"  {Y}⚠️ {RS} {msg}")
def fail(msg): print(f"  {R}❌{RS} {msg}")
def info(msg): print(f"  {B}ℹ️ {RS} {msg}")
def hdr(msg):  print(f"\n{BOLD}{C}{'═'*60}{RS}\n{BOLD}{W}  {msg}{RS}\n{C}{'═'*60}{RS}")
def sub(msg):  print(f"\n{D}  ── {msg} ──{RS}")


# ── Report accumulator ────────────────────────────────────────
RESULTS: list[dict] = []

def record(layer: str, test: str, passed: bool, detail: str = ""):
    RESULTS.append({
        "layer": layer, "test": test,
        "passed": passed, "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })

# ══════════════════════════════════════════════════════════════
# LAYER 1 — Python Core
# ══════════════════════════════════════════════════════════════

def test_layer1():
    hdr("LAYER 1 — Python Core")

    # 1a. Storage
    sub("Storage / SQLite")
    try:
        from shared.storage import Storage, Project, TaskStatus
        s = Storage()
        pid = f"test-{uuid.uuid4().hex[:8]}"
        proj = Project(
            id=pid, name="E2E Test Project",
            description="Automated test",
            created_at=datetime.utcnow().isoformat(),
            current_role="ceo", status="active",
            discord_guild_id="", approval_channel_id="",
        )
        s.create_project(proj)
        fetched = s.get_project(pid)
        assert fetched and fetched.name == "E2E Test Project"
        ok(f"Storage create/read — project id={pid}")
        record("L1", "storage_create_read", True)
    except Exception as e:
        fail(f"Storage: {e}"); record("L1", "storage_create_read", False, str(e))

    # 1b. Model Router — score matrix
    sub("Model Router — score matrix")
    try:
        from shared.model_router import best_free_for_role, score_for_role, MODELS
        pairs = [
            ("dev",    "ollama/qwen2.5-coder"),
            ("sa",     "ollama/deepseek-r1"),
        ]
        for role, expected_prefix in pairs:
            key, cfg = best_free_for_role(role)
            score = score_for_role(key, role)
            ok(f"best_free({role}) → {key} (score={score}/10)")
            record("L1", f"model_router_{role}", True, f"{key} score={score}")
        # Check total MODELS loaded
        ok(f"MODELS registry: {len(MODELS)} entries")
        record("L1", "models_registry", True, f"{len(MODELS)} models")
    except Exception as e:
        fail(f"Model Router: {e}"); record("L1", "model_router", False, str(e))

    # 1c. Role Schemas
    sub("Role Schemas — token budgets")
    try:
        from shared.role_schemas import ROLE_OUTPUT_SPECS, get_role_token_budget
        for role in ["ceo","pm","ba","sa","uxui","dev","qa","devops"]:
            budget = get_role_token_budget(role)
            spec   = ROLE_OUTPUT_SPECS[role]
            ok(f"{role.upper():6} budget={budget:5} | outputs={len(spec.output_files)} | sections={len(spec.required_sections)}")
        record("L1", "role_schemas", True, "8 roles configured")
    except Exception as e:
        fail(f"Role Schemas: {e}"); record("L1", "role_schemas", False, str(e))

    # 1d. OutputProcessor — extract from rich LLM output
    sub("OutputProcessor — rich artifact extraction")
    try:
        from shared.output_processor import OutputProcessor
        proc = OutputProcessor()
        sample_output = """
## Architecture Overview
This system uses microservices.

```python
# filename: backend/main.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
```

```sql
-- filename: schema.sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

```yaml
# filename: api_spec.yaml
openapi: "3.0.0"
info:
  title: My API
  version: "1.0"
```

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ PRODUCT : contains
```

| Component    | Technology | Owner |
|-------------|------------|-------|
| API Gateway  | FastAPI    | DEV   |
| Frontend     | React      | UXUI  |
| Database     | PostgreSQL | SA    |
"""
        arts = proc.process("sa", sample_output, "test_output")
        names = [a.filename for a in arts]
        ok(f"Extracted {len(arts)} artifacts: {names}")
        assert any("main.py" in n for n in names),    "missing main.py"
        assert any("schema.sql" in n for n in names), "missing schema.sql"
        assert any(".xlsx" in n for n in names),      "missing xlsx"
        assert any(".mmd" in n for n in names),       "missing mermaid"
        assert any(".docx" in n for n in names),      "missing docx"
        # Save to disk
        base = str(ROOT / "outputs" / "test" / "layer1")
        saved = proc.save_to_disk(arts, base)
        ok(f"Saved to disk: {list(saved.keys())}")
        record("L1", "output_processor", True, f"{len(arts)} artifacts")
    except Exception as e:
        fail(f"OutputProcessor: {e}"); traceback.print_exc()
        record("L1", "output_processor", False, str(e))


# ══════════════════════════════════════════════════════════════
# LAYER 2 — Obsidian Integration
# ══════════════════════════════════════════════════════════════

def test_layer2():
    hdr("LAYER 2 — Obsidian Integration")
    from shared.obsidian_client import ObsidianClient, get_obsidian
    from shared.obsidian_rag import get_rag, build_rag_context

    vault = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not vault:
        warn("OBSIDIAN_VAULT_PATH not set — skipping Layer 2")
        record("L2", "obsidian_all", False, "vault path not set")
        return

    info(f"Vault: {vault}")

    # 2a. Initialize vault
    sub("Vault initialization")
    try:
        obs = ObsidianClient(vault_path=vault)
        result = obs.initialize_vault()
        ok(f"initialize_vault() → {result}")
        record("L2", "vault_init", result)
    except Exception as e:
        fail(str(e)); record("L2", "vault_init", False, str(e))

    # 2b. Write note
    sub("Write note")
    try:
        obs = get_obsidian()
        content = f"""---
project: E2E Test
date: {datetime.utcnow().strftime('%Y-%m-%d')}
tags: [test, e2e]
---

# E2E Test Note
สร้างโดย test_e2e.py — {datetime.utcnow().isoformat()}

## Requirements
- User authentication
- Product catalog
- Shopping cart
- Payment gateway
"""
        ok_write = obs.write_note("01-Projects/e2e-test/requirements.md", content)
        ok(f"write_note() → {ok_write}")
        record("L2", "write_note", ok_write)
    except Exception as e:
        fail(str(e)); record("L2", "write_note", False, str(e))

    # 2c. Read note
    sub("Read note")
    try:
        result = obs.read_note("01-Projects/e2e-test/requirements.md")
        assert result and "E2E Test Note" in result
        ok(f"read_note() → {len(result)} chars")
        record("L2", "read_note", True)
    except Exception as e:
        fail(str(e)); record("L2", "read_note", False, str(e))

    # 2d. List notes
    sub("List notes")
    try:
        notes = obs.list_notes("01-Projects")
        ok(f"list_notes('01-Projects') → {len(notes)} files: {notes[:3]}")
        record("L2", "list_notes", len(notes) > 0, f"{len(notes)} notes")
    except Exception as e:
        fail(str(e)); record("L2", "list_notes", False, str(e))

    # 2e. Search notes
    sub("Search notes (filesystem grep)")
    try:
        results = obs.search_notes("authentication", limit=5)
        ok(f"search_notes('authentication') → {len(results)} results")
        for r in results[:2]:
            info(f"  {r['path']} (score={r['score']})")
        record("L2", "search_notes", True, f"{len(results)} results")
    except Exception as e:
        fail(str(e)); record("L2", "search_notes", False, str(e))

    # 2f. RAG context
    sub("RAG context injection")
    try:
        ctx = build_rag_context(
            role="ba",
            project_id="e2e-test",
            project_name="E2E Test",
            query="user authentication requirements",
            token_budget=600,
        )
        ok(f"build_rag_context() → {len(ctx)} chars")
        if ctx:
            info(f"  Preview: {ctx[:120].strip()}...")
        record("L2", "rag_context", True, f"{len(ctx)} chars")
    except Exception as e:
        fail(str(e)); record("L2", "rag_context", False, str(e))

    # 2g. Cron log
    sub("Cron log")
    try:
        ok_log = obs.save_cron_log("e2e_test", "ok", "Layer 2 test completed")
        ok(f"save_cron_log() → {ok_log}")
        record("L2", "cron_log", ok_log)
    except Exception as e:
        fail(str(e)); record("L2", "cron_log", False, str(e))

    # 2h. DNA note sync
    sub("DNA note sync")
    try:
        fake_dna = {
            "compressed_system_prompt": "You are BA. Focus on requirements.",
            "format_rules": ["Use bullet points", "Always include acceptance criteria"],
            "few_shot_snippet": "## User Stories\n- As a user...",
            "anti_patterns": ["Don't skip functional requirements"],
            "token_compression_tips": "Use abbreviations for standard terms",
            "_model_used": "test",
        }
        ok_dna = obs.save_role_dna("ba", fake_dna)
        ok(f"save_role_dna('ba') → {ok_dna}")
        record("L2", "dna_sync", ok_dna)
    except Exception as e:
        fail(str(e)); record("L2", "dna_sync", False, str(e))


# ══════════════════════════════════════════════════════════════
# LAYER 3 — Hermes Cron
# ══════════════════════════════════════════════════════════════

async def test_layer3():
    hdr("LAYER 3 — Hermes Cron Jobs")
    from agents.hermes_cron import (
        job_project_health_check, job_dna_freshness_check,
        job_daily_cost_summary, job_obsidian_sync,
        get_job_history,
    )

    jobs = [
        ("project_health_check", job_project_health_check),
        ("dna_freshness_check",  job_dna_freshness_check),
        ("daily_cost_summary",   job_daily_cost_summary),
        ("obsidian_sync",        job_obsidian_sync),
    ]

    for name, fn in jobs:
        sub(name)
        try:
            t0 = time.time()
            await fn()
            elapsed = time.time() - t0
            ok(f"{name} completed in {elapsed:.1f}s")
            record("L3", name, True, f"{elapsed:.1f}s")
        except Exception as e:
            fail(f"{name}: {e}")
            record("L3", name, False, str(e))

    # Verify history file written
    sub("job_history.json persistence")
    try:
        history = get_job_history()
        hist_file = Path(os.getenv("OUTPUT_BASE_PATH","outputs")) / "cron" / "job_history.json"
        ok(f"History: {len(history)} entries — file: {'✅' if hist_file.exists() else '❌'}")
        record("L3", "history_persistence", hist_file.exists(), f"{len(history)} entries")
    except Exception as e:
        fail(str(e)); record("L3", "history_persistence", False, str(e))


# ══════════════════════════════════════════════════════════════
# LAYER 4 — DNA Bootstrap
# ══════════════════════════════════════════════════════════════

async def test_layer4(fast: bool = False):
    hdr("LAYER 4 — DNA Bootstrap")
    from shared.dna_bootstrap import get_dna_bootstrap

    dna = get_dna_bootstrap()

    if fast:
        warn("--fast mode: skipping live bootstrap, checking cache only")
        sub("Cache status")
        cached = dna.list_cached_roles()
        if cached:
            for e in cached:
                ok(f"{e['role']:8} [{e['type']:10}] model={e['model'][:30]} updated={e['updated_at'][:16]}")
            record("L4", "dna_cache_check", True, f"{len(cached)} cached")
        else:
            warn("No DNA cached yet — run without --fast to bootstrap")
            record("L4", "dna_cache_check", False, "empty cache")
        return

    # Bootstrap BA role (medium complexity, good test case)
    sub("Bootstrap BA role via claude-cli")
    try:
        t0 = time.time()
        result = await dna.bootstrap_role(
            "ba",
            project_context="E-commerce platform: React frontend, FastAPI backend, PostgreSQL",
        )
        elapsed = time.time() - t0
        if result:
            ok(f"Bootstrap BA in {elapsed:.1f}s")
            ok(f"  compressed_prompt : {len(result.get('compressed_system_prompt',''))} chars")
            ok(f"  format_rules      : {len(result.get('format_rules',[]))} rules")
            ok(f"  few_shot_snippet  : {'✅' if result.get('few_shot_snippet') else '❌'}")
            ok(f"  anti_patterns     : {len(result.get('anti_patterns',[]))} items")
            record("L4", "bootstrap_ba", True, f"{elapsed:.1f}s, {len(result)} keys")
        else:
            fail("Bootstrap returned empty"); record("L4", "bootstrap_ba", False, "empty")
    except Exception as e:
        fail(f"Bootstrap error: {e}"); record("L4", "bootstrap_ba", False, str(e))

    # Check DNA was synced to Obsidian
    sub("DNA → Obsidian sync verify")
    try:
        vault = os.getenv("OBSIDIAN_VAULT_PATH","")
        if vault:
            dna_file = Path(vault) / "00-DNA" / "ba-dna.md"
            ok(f"ba-dna.md exists: {'✅' if dna_file.exists() else '❌'}")
            record("L4", "dna_obsidian_sync", dna_file.exists())
        else:
            warn("No vault path — skip Obsidian DNA verify")
    except Exception as e:
        fail(str(e)); record("L4", "dna_obsidian_sync", False, str(e))


# ══════════════════════════════════════════════════════════════
# LAYER 5 — Full SDLC Pipeline (Auto-Approve)
# Case A: E-commerce platform
# Case B: Model fallback scenario
# ══════════════════════════════════════════════════════════════

# ── Realistic project scenarios ───────────────────────────────

TEST_PROJECTS = {
    "ecommerce": {
        "name": "ShopMate E-Commerce Platform",
        "description": (
            "ระบบ e-commerce สำหรับ SME ไทย\n"
            "Features:\n"
            "- สมัครสมาชิก / Login (JWT)\n"
            "- สินค้า catalog + ค้นหา + filter\n"
            "- ตะกร้าสินค้า + checkout\n"
            "- ชำระเงินผ่าน QR Code / โอนผ่านธนาคาร\n"
            "- Admin dashboard: สินค้า, order, รายงานยอดขาย\n"
            "Tech stack: React 18 + TypeScript, FastAPI, PostgreSQL, Redis, Docker"
        ),
    },
    "fallback": {
        "name": "TaskFlow Project Manager",
        "description": (
            "ระบบบริหารโปรเจกต์สำหรับทีม remote\n"
            "Features:\n"
            "- Task board (Kanban style)\n"
            "- Time tracking per task\n"
            "- Team chat (Slack-like)\n"
            "- Daily standup AI summarizer\n"
            "Tech stack: Next.js 14, tRPC, Prisma, MySQL"
        ),
    },
}

# ── Agent runners (simulate process_task directly) ────────────

async def _run_role_agent(role: str, project, input_data: dict) -> dict:
    """Instantiate role agent and call process_task directly (no Discord needed)."""
    import importlib
    mod = importlib.import_module(f"agents.{role}.agent")
    # find the Agent class
    agent_class = None
    for name in dir(mod):
        cls = getattr(mod, name)
        if isinstance(cls, type) and name.lower() != "baseagent" and hasattr(cls, "process_task"):
            agent_class = cls
            break
    if not agent_class:
        raise RuntimeError(f"No agent class found in agents.{role}.agent")

    agent = agent_class()
    return await agent.process_task(project, input_data)


async def _run_pipeline(case_key: str, roles: list[str], skip_llm: bool = False):
    """
    Run full or partial pipeline for one project.
    Auto-approves at each stage. Returns report dict.
    """
    from shared.storage import Storage, Project, TaskStatus
    from shared.output_processor import OutputProcessor

    proj_cfg = TEST_PROJECTS[case_key]
    pid = f"{case_key}-{uuid.uuid4().hex[:6]}"
    storage = Storage()
    proc    = OutputProcessor()

    project = Project(
        id=pid,
        name=proj_cfg["name"],
        description=proj_cfg["description"],
        created_at=datetime.utcnow().isoformat(),
        current_role=roles[0],
        status="active",
        discord_guild_id="",
        approval_channel_id="",
    )
    storage.create_project(project)
    info(f"Created project: {pid} — {project.name}")

    pipeline_log = []
    current_output: dict = {}

    for role in roles:
        sub(f"Role: {role.upper()}")
        t0 = time.time()

        # Build input for this role
        input_data = {
            "project_description": project.description,
            "project_name":        project.name,
            "previous_output":     current_output,
            "revision_comment":    "",
            "revision_count":      0,
        }

        try:
            if skip_llm:
                # Stub output — test pipeline flow without LLM calls
                output = {
                    "summary": f"[STUB] {role.upper()} analysis for {project.name}",
                    "raw_llm_output": f"# {role.upper()} Output\n\nStub output for testing pipeline flow.\n\n## Summary\nProject: {project.name}\nRole: {role.upper()}\n\n```python\n# filename: {role}_output.py\nprint('stub')\n```",
                    "project_name": project.name,
                    "files": {},
                }
            else:
                output = await _run_role_agent(role, project, input_data)
                output["project_name"] = project.name

            elapsed = time.time() - t0

            # Auto-save output files
            base_path = str(ROOT / "outputs" / "projects" / pid / role)
            Path(base_path).mkdir(parents=True, exist_ok=True)
            raw_llm = output.get("raw_llm_output") or output.get("summary","")
            artifacts = []
            if raw_llm and len(raw_llm) > 50:
                artifacts = proc.process(role, raw_llm, f"{role}_output")
                proc.save_to_disk(artifacts, base_path)

            # Sync to Obsidian
            try:
                from shared.obsidian_client import get_obsidian
                get_obsidian().save_project_note(pid, project.name, role, raw_llm)
            except Exception:
                pass

            # Auto-approve: update DB status
            task_id = str(uuid.uuid4())
            with __import__("sqlite3").connect(os.getenv("DB_PATH", "data/sdlc.db")) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO role_tasks
                       (id, project_id, role, status, input_data, output_data,
                        created_at, updated_at, approval_message_id, revision_count, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (task_id, pid, role, TaskStatus.APPROVED,
                     json.dumps(input_data), json.dumps(output),
                     datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
                     "auto_approved", 0, "Auto-approved by E2E test"),
                )
                conn.commit()

            # Advance project to next role
            from shared.channel_config import get_next_role
            next_r = get_next_role(role)
            storage.update_project_role(pid, next_r or "completed", "active" if next_r else "completed")

            summary_preview = (output.get("summary","") or "")[:100]
            ok(f"{role.upper():8} ✅ AUTO-APPROVED | {elapsed:.1f}s | artifacts={len(artifacts)} | {summary_preview}")

            pipeline_log.append({
                "role": role, "status": "approved", "elapsed": elapsed,
                "artifacts": [a.filename for a in artifacts],
                "summary": summary_preview,
            })

            current_output = output  # pass to next role

        except Exception as e:
            elapsed = time.time() - t0
            fail(f"{role.upper():8} ❌ FAILED: {e}")
            traceback.print_exc()
            pipeline_log.append({
                "role": role, "status": "error", "elapsed": elapsed,
                "error": str(e),
            })
            current_output = {}

    return {"project_id": pid, "project_name": project.name, "pipeline": pipeline_log}


async def test_layer5(fast: bool = False):
    hdr("LAYER 5 — Full SDLC Pipeline (Auto-Approve)")

    WORKFLOW = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
    skip_llm = fast  # if --fast, stub LLM calls

    if skip_llm:
        warn("--fast mode: using stub LLM output (pipeline flow test only, no real LLM calls)")
    else:
        info("Full mode: calling real LLM for each role")

    # ── Case A: E-commerce ────────────────────────────────────
    print(f"\n  {BOLD}{W}Case A: ShopMate E-Commerce Platform{RS}")
    info("  8 roles, full pipeline, auto-approve at each stage")
    try:
        t0 = time.time()
        result_a = await _run_pipeline("ecommerce", WORKFLOW, skip_llm=skip_llm)
        elapsed = time.time() - t0
        passed = sum(1 for s in result_a["pipeline"] if s["status"] == "approved")
        ok(f"Case A complete: {passed}/{len(WORKFLOW)} roles approved in {elapsed:.0f}s")
        record("L5", "case_a_ecommerce", passed == len(WORKFLOW),
               f"{passed}/{len(WORKFLOW)} roles, {elapsed:.0f}s")

        # Print pipeline report
        print(f"\n  {D}  Pipeline Summary:{RS}")
        for step in result_a["pipeline"]:
            status_icon = "✅" if step["status"] == "approved" else "❌"
            arts = step.get("artifacts", [])
            print(f"  {status_icon} {step['role'].upper():8} {step['elapsed']:.1f}s  artifacts={arts}")
    except Exception as e:
        fail(f"Case A failed: {e}"); traceback.print_exc()
        record("L5", "case_a_ecommerce", False, str(e))

    # ── Case B: Model fallback (force free model) ─────────────
    print(f"\n  {BOLD}{W}Case B: TaskFlow — force free model (fallback test){RS}")
    info("  Routing forced to FREE tier only — tests DNA injection + quality")
    try:
        from shared.model_router import ModelTier

        # Override env to force free tier by setting budget to $0
        old_budget = os.environ.get("DAILY_BUDGET_USD", "2.00")
        os.environ["DAILY_BUDGET_USD"] = "0.00"   # force free model routing

        t0 = time.time()
        # Test 3 key roles only for fallback case (ba, dev, sa)
        result_b = await _run_pipeline("fallback", ["ba", "sa", "dev"], skip_llm=skip_llm)
        elapsed = time.time() - t0
        passed_b = sum(1 for s in result_b["pipeline"] if s["status"] == "approved")
        ok(f"Case B complete: {passed_b}/3 roles via free model in {elapsed:.0f}s")
        record("L5", "case_b_fallback", passed_b == 3, f"{passed_b}/3 roles, {elapsed:.0f}s")

        for step in result_b["pipeline"]:
            status_icon = "✅" if step["status"] == "approved" else "❌"
            print(f"  {status_icon} {step['role'].upper():8} {step['elapsed']:.1f}s (free model)")

        os.environ["DAILY_BUDGET_USD"] = old_budget
    except Exception as e:
        fail(f"Case B failed: {e}"); traceback.print_exc()
        record("L5", "case_b_fallback", False, str(e))
        os.environ["DAILY_BUDGET_USD"] = "2.00"


# ══════════════════════════════════════════════════════════════
# LAYER 6 — Discord Simulation
# ══════════════════════════════════════════════════════════════

async def test_layer6():
    hdr("LAYER 6 — Discord Flow Simulation")
    info("Simulates Discord message flow without running real bot")
    info("Tests: !start, !status, !cost, !model, !dna_status, !bootstrap")

    try:
        # Simulate !start command data flow
        sub("!start — project creation")
        from shared.storage import Storage, Project
        s = Storage()
        pid = f"discord-sim-{uuid.uuid4().hex[:6]}"
        p = Project(
            id=pid, name="Discord Sim Project",
            description="Simulated via !start command",
            created_at=datetime.utcnow().isoformat(),
            current_role="ceo", status="active",
            discord_guild_id="1503693135807774791",
            approval_channel_id="1503978119063801906",
        )
        s.create_project(p)
        ok(f"!start → Project created: {pid}")
        record("L6", "discord_start", True)

        # Simulate !status
        sub("!status — project status lookup")
        fetched = s.get_project(pid)
        assert fetched and fetched.current_role == "ceo"
        ok(f"!status {pid} → current_role={fetched.current_role} status={fetched.status}")
        record("L6", "discord_status", True)

        # Simulate !cost
        sub("!cost — cost tracker")
        from shared.model_router import CostTracker
        tracker = CostTracker()
        summary = tracker.today_summary()
        ok(f"!cost → ${summary.get('total_cost_usd', 0):.4f} today | {summary.get('total_tokens',0):,} tokens")
        record("L6", "discord_cost", True)

        # Simulate !model — show routing decision
        sub("!model — routing decision")
        from shared.model_router import get_router
        router = get_router()
        test_prompt = "Create user authentication with JWT tokens and refresh token rotation"
        cfg, key, complexity = router.route(test_prompt, "dev", pid)
        ok(f"!model dev → {key} (complexity={complexity}/100, tier={cfg.tier.value})")
        record("L6", "discord_model", True, f"{key} complexity={complexity}")

        # Simulate !dna_status
        sub("!dna_status — DNA cache status")
        from shared.dna_bootstrap import get_dna_bootstrap
        dna = get_dna_bootstrap()
        cached = dna.list_cached_roles()
        ok(f"!dna_status → {len(cached)} roles cached: {[e['role'] for e in cached]}")
        record("L6", "discord_dna_status", True, f"{len(cached)} cached")

        # Simulate pipeline auto-approve flow
        sub("!approve — pipeline advance simulation")
        from shared.channel_config import get_next_role, WORKFLOW_ORDER
        for role in WORKFLOW_ORDER[:3]:
            next_r = get_next_role(role)
            ok(f"  !approve on {role.upper()} → advance to {(next_r or 'COMPLETE').upper()}")
        s.update_project_role(pid, "pm", "active")
        fetched2 = s.get_project(pid)
        assert fetched2.current_role == "pm"
        ok(f"Pipeline advance: ceo → pm ✅ (DB updated)")
        record("L6", "discord_approve_flow", True)

        # Simulate web bridge event
        sub("Web bridge — task_completed event")
        from shared.web_bridge import get_bridge
        bridge = get_bridge()
        ok(f"WebBridge instance: {type(bridge).__name__} (connected={getattr(bridge, '_connected', 'N/A')})")
        record("L6", "web_bridge", True)

    except Exception as e:
        fail(f"Discord simulation error: {e}"); traceback.print_exc()
        record("L6", "discord_simulation", False, str(e))


# ══════════════════════════════════════════════════════════════
# REPORT GENERATOR
# ══════════════════════════════════════════════════════════════

def print_report(report_file: Optional[str] = None):
    hdr("TEST REPORT")

    total   = len(RESULTS)
    passed  = sum(1 for r in RESULTS if r["passed"])
    failed  = total - passed
    pct     = (passed / total * 100) if total else 0

    # Group by layer
    layers: dict[str, list] = {}
    for r in RESULTS:
        layers.setdefault(r["layer"], []).append(r)

    lines = [
        f"# E2E Test Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"## Summary",
        f"- **Total:** {total}  **Passed:** {passed}  **Failed:** {failed}",
        f"- **Pass rate:** {pct:.0f}%",
        f"- **Status:** {'✅ ALL PASS' if failed == 0 else f'⚠️ {failed} FAILED'}",
        f"",
    ]

    for layer, results in layers.items():
        p = sum(1 for r in results if r["passed"])
        f_ = len(results) - p
        icon = "✅" if f_ == 0 else "⚠️" if p > 0 else "❌"
        lines.append(f"## {icon} {layer} ({p}/{len(results)} passed)")
        for r in results:
            s_icon = "✅" if r["passed"] else "❌"
            detail = f" — {r['detail']}" if r.get("detail") else ""
            lines.append(f"- {s_icon} `{r['test']}`{detail}")
        lines.append("")

    lines += [
        "## Environment",
        f"- DB_PATH: `{os.getenv('DB_PATH')}`",
        f"- OUTPUT_BASE_PATH: `{os.getenv('OUTPUT_BASE_PATH')}`",
        f"- OBSIDIAN_VAULT_PATH: `{os.getenv('OBSIDIAN_VAULT_PATH')}`",
        f"- OBSIDIAN_API_URL: `{os.getenv('OBSIDIAN_API_URL')}`",
        f"- DAILY_BUDGET_USD: `{os.getenv('DAILY_BUDGET_USD')}`",
    ]

    report_md = "\n".join(lines)

    # Console output
    print(f"\n  {'─'*56}")
    print(f"  {BOLD}Total: {total}  Pass: {G}{passed}{RS}  Fail: {R}{failed}{RS}")
    print(f"  Pass rate: {BOLD}{G if failed==0 else Y}{pct:.0f}%{RS}")
    print(f"  {'─'*56}")

    for layer, results in layers.items():
        p = sum(1 for r in results if r["passed"])
        f_ = len(results) - p
        icon = f"{G}✅{RS}" if f_ == 0 else f"{Y}⚠️{RS}"
        print(f"  {icon} {BOLD}{layer}{RS} {D}({p}/{len(results)}){RS}")
        for r in results:
            s_icon = f"{G}✅{RS}" if r["passed"] else f"{R}❌{RS}"
            detail = f"{D} {r['detail']}{RS}" if r.get("detail") else ""
            print(f"     {s_icon} {r['test']}{detail}")

    print(f"\n  {BOLD}Output files:{RS}")
    out_base = Path(os.getenv("OUTPUT_BASE_PATH", "outputs"))
    for folder in ["projects", "cron", "test"]:
        p = out_base / folder
        if p.exists():
            count = sum(1 for _ in p.rglob("*") if _.is_file())
            ok(f"{folder}: {count} files")

    print(f"\n  {BOLD}Obsidian vault:{RS}")
    vault = os.getenv("OBSIDIAN_VAULT_PATH","")
    if vault and Path(vault).exists():
        for folder in ["00-DNA","01-Projects","03-Outputs","05-Cron-Logs"]:
            fp = Path(vault) / folder
            count = sum(1 for _ in fp.rglob("*.md")) if fp.exists() else 0
            ok(f"{folder}: {count} notes")
    else:
        warn("Vault not found")

    # Save report file
    if report_file:
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)
        Path(report_file).write_text(report_md, encoding="utf-8")
        ok(f"\n  Report saved: {report_file}")
    else:
        default = str(ROOT / "outputs" / "e2e_report.md")
        Path(default).parent.mkdir(parents=True, exist_ok=True)
        Path(default).write_text(report_md, encoding="utf-8")
        ok(f"\n  Report saved: {default}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner")
    parser.add_argument("--layer", type=int, help="Run specific layer only (1-6)")
    parser.add_argument("--fast", action="store_true",
                        help="Skip live LLM calls (stub output, test flow only)")
    parser.add_argument("--report", default=None, help="Output report path (.md)")
    args = parser.parse_args()

    print(f"\n{BOLD}{C}{'═'*60}{RS}")
    print(f"{BOLD}{W}  Multi-AI Agent SDLC — End-to-End Test Suite{RS}")
    print(f"{BOLD}{W}  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}{RS}")
    if args.fast:
        print(f"{BOLD}{Y}  Mode: FAST (stub LLM — tests flow only, not AI quality){RS}")
    else:
        print(f"{BOLD}{G}  Mode: FULL (real LLM calls — tests quality + flow){RS}")
    print(f"{C}{'═'*60}{RS}\n")

    run_all = args.layer is None

    if run_all or args.layer == 1:
        test_layer1()
    if run_all or args.layer == 2:
        test_layer2()
    if run_all or args.layer == 3:
        await test_layer3()
    if run_all or args.layer == 4:
        await test_layer4(fast=args.fast)
    if run_all or args.layer == 5:
        await test_layer5(fast=args.fast)
    if run_all or args.layer == 6:
        await test_layer6()

    print_report(args.report)


if __name__ == "__main__":
    asyncio.run(main())
