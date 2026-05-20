# Phase 9: Runtime Observability & Operator Control Plane

**Status:** Design locked — ready for implementation  
**Design date:** 2026-05-20  
**Prerequisites:** Phase 8 complete (f38e41e)

---

## Goal

Make the runtime state of the multi-agent system fully visible via the web
back-office, covering: paused tasks, provider cooldowns, recovery worker
health, operator resume actions, and a resume audit trail.

---

## Current gaps (surveyed 2026-05-20)

### Data that exists but has no web visibility

| Data | Where it lives | Gap |
|------|---------------|-----|
| Paused SDLC tasks | `sdlc_tasks WHERE status='paused'` (Python SQLite) | No webapp API or UI |
| Provider cooldowns | `provider_cooldowns` table (Python SQLite) | No webapp API or UI |
| Recovery tick history | `outputs/recovery/tick_history.json` (file) | File written, no API route |
| Pause events | `agent_activity_logs WHERE status='paused'` (webapp SQLite, `metadata` JSON) | Stored but no dedicated UI panel |

### What already works (patterns to reuse)

- `/cron` page reads `outputs/cron/job_history.json` → **reuse for recovery worker**
- `/api/runtime/tasks/blocked` reads `agent_activity_logs` → **reuse pattern for paused**
- Phase 8.1 already POSTs `status=paused` + pause metadata to webapp ingest on every pause
- `metadata` JSON column in `agent_activity_logs` already receives:
  `pause_reason`, `pause_provider`, `pause_model`, `retry_after_at`, `resume_policy`

### Architecture principle (no change)

The Python SQLite (sdlc.db) and webapp SQLite are separate files.
The bridge is:
1. **Ingest POST** — bots push pause/resume events to `/api/agent-activity/ingest` (already live)
2. **File-based JSON** — recovery worker writes `runtime_status.json` (to add in 9.1)

No direct cross-SQLite reads — concurrent write risk is unacceptable.

---

## Phase 9 sub-phase breakdown

### 9.0 — Design & Roadmap (this document, doc-only commit)

Lock the plan before any implementation.

---

### 9.1 — Backend: Recovery Status APIs

**New file: `outputs/recovery/runtime_status.json`** (written by recovery_worker on each tick)

```json
{
  "last_tick": "2026-05-20T14:00:00",
  "worker_alive": true,
  "paused_count": 3,
  "ready_to_resume_count": 1,
  "cooldowns": [
    {
      "provider": "groq",
      "model": "llama-3.3-70b",
      "reason": "rate_limited",
      "retry_after_at": "2026-05-20T15:00:00"
    }
  ]
}
```

**New API routes (Next.js):**

| Route | Method | Source | Description |
|-------|--------|--------|-------------|
| `/api/runtime/paused-tasks` | GET | `agent_activity_logs` (webapp SQLite) | Latest pause event per `sdlc_task_id` where `status='paused'` |
| `/api/runtime/paused-tasks/[sdlcTaskId]/resume` | POST | Audit table | Operator-triggered resume — logs audit event; Python polls webapp or webhook |
| `/api/runtime/cooldowns` | GET | `outputs/recovery/runtime_status.json` | Active provider cooldowns from recovery worker |
| `/api/runtime/recovery` | GET | `outputs/recovery/tick_history.json` | Recovery worker tick log |

**Response shape for `GET /api/runtime/paused-tasks`:**

```json
{
  "paused": [
    {
      "sdlcTaskId": "task-abc",
      "taskName": "Backend Code",
      "roleKey": "dev",
      "pauseReason": "rate_limited",
      "pauseProvider": "groq",
      "pauseModel": "llama-3.3-70b",
      "retryAfterAt": "2026-05-20T15:00:00",
      "resumePolicy": "auto",
      "pausedAt": "2026-05-20T14:00:00",
      "projectId": "proj-xyz"
    }
  ],
  "total": 1
}
```

**Python side for `POST /api/runtime/paused-tasks/[id]/resume`:**

Option chosen: **webapp DB flag poll** (simpler, no webhook needed)
- POST writes a `system_config` row: `key=runtime.resume_requested.{sdlcTaskId}` `value=<operator_user>`
- BaseAgent poll loop checks for resume_requested flags every N cycles
- On match: calls `storage.resume_paused_sdlc_task(task_id)`, deletes config key, logs audit

Alternative (Phase 9.4 stretch): direct webhook to Python bot HTTP endpoint.

**Tests needed (9.1):**
- `GET /api/runtime/paused-tasks` — returns only `status='paused'` logs, parsed metadata
- `GET /api/runtime/cooldowns` — returns `[]` when file missing, parses JSON correctly
- `GET /api/runtime/recovery` — returns tick history, newest first
- `POST /api/runtime/paused-tasks/[id]/resume` — creates system_config flag, logs audit

---

### 9.2 — Web UI: Recovery Dashboard

**New page: `/recovery`** (added to app-shell sidebar)

Panels on the page:

1. **Recovery Worker Status** (top bar)
   - Running / Offline indicator (last_tick age < 10 min = running)
   - Last tick time + stats (requeued / deferred / pruned)

2. **Paused Task Queue** (table)
   - Columns: Task | Role | Pause Reason | Provider | Retry After | Policy | Action
   - `auto` policy → "⏳ Will auto-resume" label
   - `manual_token_fix` policy → "⚠️ Manual" badge + **Resume** button
   - Resume button → POST to `/api/runtime/paused-tasks/[id]/resume`
   - Auto-refresh every 30s (same pattern as `/cron` page)

3. **Active Provider Cooldowns** (card grid)
   - One card per active cooldown: Provider / Model / Reason / Expires in
   - Shows "No active cooldowns ✅" when empty

4. **Recovery Tick Log** (expandable table)
   - Same component style as hermes_cron log
   - Columns: Time | Requeued | Deferred | Pruned

**Sidebar nav change:** Add "Recovery" link between "Cron" and "Backoffice".

**No new tests required for page** (server-rendered, tested via API tests in 9.1).

---

### 9.3 — Operator Audit Trail Extension

**New audit event types:**

| Event type | Trigger | Actor |
|-----------|---------|-------|
| `agent.task.paused` | BaseAgent calls `_pause_task_for_quota` | system |
| `agent.task.resumed.auto` | RecoveryWorker requeues a task | system |
| `agent.task.resumed.discord` | `!sdlc_resume` Discord command | discord_user |
| `agent.task.resumed.web` | Web resume button POST | web_operator |

**Implementation:**
- Python: `_pause_task_for_quota` → POST ingest with `event_type="agent.task.paused"`
- Python: `RecoveryWorker.tick()` → POST ingest for each requeued task with `event_type="agent.task.resumed.auto"`
- Python: `!sdlc_resume` → POST ingest with `event_type="agent.task.resumed.discord"` + `actor=ctx.author`
- Webapp: `/api/runtime/paused-tasks/[id]/resume` → write `audit_events` row directly with `event_type="agent.task.resumed.web"`

**Audit page extension:**
- Add `agent.task.*` events to `EVENT_TYPE_OPTIONS` filter list on `/audit` page

**Tests needed (9.3):**
- Verify pause/resume events flow through ingest → `agent_activity_logs`
- Verify web resume writes audit row

---

### 9.4 — Hardening

#### hermes3 last-resort cooldown behavior

**The edge case (identified in Phase 8 finalization):**

Two places in `model_router.py` fall back to `ollama/hermes3` unconditionally,
bypassing the cooldown check:

```python
# model_router.py:238 — best_free_for_role() ultimate fallback
if not best_key:
    best_key = "ollama/hermes3"          # ← no cooldown check
    best_cfg = MODELS["ollama/hermes3"]

# model_router.py:726 — route() last-resort
if not selected_key:
    selected_key    = "ollama/hermes3"   # ← no cooldown check
    selected_config = MODELS["ollama/hermes3"]
```

**Design decision:**

hermes3 runs on local Ollama — it has no external quota. An Ollama provider
cooldown would be set if Ollama is unreachable (5xx / connection reset).

Correct behavior:
- If `ollama` is in the active cooldown set → **warn, but still use hermes3**
  (it's the last resort; silently failing is worse than trying a stale model).
  Log: `[Router] WARNING: hermes3 last-resort used despite ollama cooldown`
- If `ollama` is NOT in cooldown → current behavior unchanged.

**Implementation (9.4):**
- Wrap both fallback sites with: `if _is_cooling_down(...): logger.warning(...)`
- Do NOT skip hermes3 — log only; keep the safety net.

**Tests needed (9.4):**
- `test_model_router.py`: last-resort hermes3 used when ollama in cooldown → warning logged, key still returned
- `test_model_router.py`: `best_free_for_role()` fallback hermes3 → same

---

## Files to create/modify per sub-phase

### 9.1 (Backend APIs)
```
sdlc/agents/recovery_worker.py         — add runtime_status.json write on each tick
webapp/app/api/runtime/paused-tasks/route.ts          — new
webapp/app/api/runtime/paused-tasks/[sdlcTaskId]/resume/route.ts  — new
webapp/app/api/runtime/cooldowns/route.ts             — new
webapp/app/api/runtime/recovery/route.ts              — new
webapp/lib/agents/query.ts             — add listPausedTaskEvents(), findSystemConfigByKey already exists
webapp/tests/runtime-paused-tasks.test.ts             — new
webapp/tests/runtime-cooldowns.test.ts                — new
webapp/tests/runtime-recovery.test.ts                 — new
```

### 9.2 (Web UI)
```
webapp/app/recovery/page.tsx           — new page
webapp/app/_components/app-shell.tsx   — add Recovery nav link
```

### 9.3 (Audit trail)
```
sdlc/shared/base_agent.py              — POST pause/resume ingest events
sdlc/agents/recovery_worker.py         — POST resume.auto ingest events
webapp/app/audit/page.tsx              — add agent.task.* to filter options
webapp/app/api/runtime/paused-tasks/[sdlcTaskId]/resume/route.ts — write audit row
```

### 9.4 (hermes3 hardening)
```
sdlc/shared/model_router.py            — add warning log at both last-resort sites
sdlc/tests/test_phase9_model_router.py — new (hermes3 cooldown edge case)
```

---

## Invariants (must not change)

- Discord remains primary runtime — bots are task executors, web is control plane
- Recovery worker does NOT execute SDLC tasks — requeue only
- Phase 8 pause/resume behavior unchanged
- Webapp-initiated resume goes through the same `resume_paused_sdlc_task()` code path
- `manual_token_fix` tasks are NEVER auto-resumed — web Resume button works but shows warning

---

## Phase 9 commit sequence (planned)

```
Phase 9.0: Runtime Observability Roadmap          ← this commit
Phase 9.1: Recovery status APIs (backend)
Phase 9.2: Recovery dashboard page
Phase 9.3: Agent pause/resume audit trail
Phase 9.4: hermes3 last-resort cooldown hardening
Phase 9 finalization: integration + full test suite
```
