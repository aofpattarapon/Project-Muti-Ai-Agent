# Multi-Agent AI Phase Notes

  Current status:
  - Phase 8 FINALIZED — all commits clean, worktree clean after finalization commit
  - All 599 Python + 115 TypeScript tests green

  Phase 8 complete summary (all commits verified):
  - 8.0 (a8f0c06): llm_error_classifier.py + DB pause schema + provider_cooldowns table + 6 storage methods
  - 8.1 (0fce75b): BaseAgent._pause_task_for_quota() + WebBridge.extra_metadata
  - 8.2 (80b352d): agents/recovery_worker.py + Storage.update_task_retry_after/prune_expired_cooldowns
  - 8.3 (fc12447): Discord !sdlc_paused + !sdlc_resume + Web App paused badge
  - finalization: model_router cooldown-aware routing + Docker/PM2 deploy configs committed

  Finalization details (previously uncommitted, now clean):
  - model_router.py: _active_cooldown_blocks(), _is_cooling_down(), best_free_for_role(exclude_providers),
    router skips cooling-down models/providers in budget fallback AND score-based routing
  - docker-compose.yml: quota-recovery service running agents/recovery_worker.py
  - ecosystem.bots.config.js: sdlc-quota-recovery process registered
  - scripts/start_pm2.sh: --no-cron still starts sdlc-quota-recovery (runtime safety, not cron)

  Phase 9 progress:
  - 9.0: docs/PHASE9_ROADMAP.md (design locked — committed)
  - 9.1 COMPLETE: Recovery status APIs (backend)
      Python: recovery_worker.tick() → runtime_status.json + tick_history.json (already written in 8.2; 9.1 adds _write_runtime_status, _count_all_paused, tick() returns tuple)
      webapp/lib/agents/query.ts: listPausedTaskEvents(), upsertResumeRequestFlag()
      webapp/lib/audit/events.ts: AuditEventType += "agent.task.resumed.web"
      webapp/app/api/runtime/paused-tasks/route.ts: GET — Bearer auth, returns latest pause event per sdlc_task_id
      webapp/app/api/runtime/paused-tasks/[sdlcTaskId]/resume/route.ts: POST — Admin session, writes system_config flag (Python consumer in 9.3)
      webapp/app/api/runtime/cooldowns/route.ts: GET — Bearer auth, reads outputs/recovery/runtime_status.json
      webapp/app/api/runtime/recovery/route.ts: GET — Bearer auth, reads outputs/recovery/tick_history.json newest-first
      webapp/tests/runtime-phase9.test.ts: 13 tests (all green)
      All 128 TypeScript + 11 Python recovery tests green
  - 9.2 COMPLETE: Recovery Dashboard UI
      Prerequisite hotfix: listPausedTaskEvents() now uses correlated MAX(id) subquery — excludes tasks
        where a newer event (resume/complete) has overridden the paused status.
      webapp/app/recovery/page.tsx: server component, reads data directly (no auth friction)
        Panels: Worker Status bar, Paused Task Queue (with ResumeButton for manual_token_fix),
                Active Provider Cooldowns, Recovery Tick Log
        Auto-refresh every 30s via router.refresh()
      webapp/app/recovery/_components/ResumeButton.tsx: "use client" — POSTs to resume API
      webapp/app/_components/app-shell.tsx: Recovery nav link in System group
      14 tests (including resumed-task exclusion test) — 129 total TypeScript tests green
  - 9.3 COMPLETE: Agent pause/resume audit trail
      Python: WebAppBridge.post_event() — generic ingest method for agent.task.* events
      Python: BaseAgent._pause_task_for_quota() emits agent.task.paused; !sdlc_resume emits agent.task.resumed.discord
      Python: RecoveryWorker.tick() emits agent.task.resumed.auto on auto-requeue (dry_run skips)
      webapp/lib/audit/events.ts: AuditEventType += agent.task.paused, agent.task.resumed.auto, agent.task.resumed.discord
      webapp/app/audit/page.tsx: EVENT_TYPE_OPTIONS += all agent.task.* types
      sdlc/tests/test_phase9_audit_trail.py: 7 Python tests (bridge post_event + recovery worker events) — all green
      webapp/tests/runtime-phase9.test.ts: +3 TypeScript tests for recordAuditEvent — 17 total (all green)
      All 132 TypeScript + 18 Phase 9 Python tests green
  - Next: 9.4 hermes3 hardening

  Roadmap: docs/PHASE9_ROADMAP.md

  Important concept:
  - Discord is primary runtime
  - Web App is synced back-office/control plane
  - Recovery worker must not execute SDLC tasks
  - Recovery worker only pauses, checks provider cooldown, and requeues tasks
  - Role agents execute tasks after requeue
● Phase 8 is large — let me survey the codebase before designing anything.

● Bash(find /home/off_poff_p/projects/multi-ai-agent/sdlc/shared -name "*.py" | sort | xargs wc -l 2>/dev/null | sort -rn | head -20)
  ⎿    9790 total
       2130 /home/off_poff_p/projects/multi-ai-agent/sdlc/shared/base_agent.py
        777 /home/off_poff_p/projects/multi-ai-agent/sdlc/shared/storage.py
     … +17 lines (ctrl+o to expand)

  Searched for 2 patterns, read 4 files (ctrl+o to expand)

● I have a complete picture. Now let me implement Phase 8.0: classifier + DB schema + storage API + tests. I'll do all three
  implementation files first, then the test file.

● Write(~/projects/multi-ai-agent/sdlc/shared/llm_error_classifier.py)
  ⎿  Wrote 212 lines to ../sdlc/shared/llm_error_classifier.py
       1 """
       2 LLM Error Classifier — provider-agnostic quota/rate/context/auth/timeout detection.
       3
       4 classify_llm_error(exc_or_message) → LLMErrorInfo
       5
       6 Error categories (pause_reason values):
       7   quota_exceeded          — daily/monthly quota depleted
       8   rate_limited            — per-minute request or token rate limit hit
       9   context_limit_exceeded  — prompt too long for model
      10   provider_unavailable    — 5xx, overloaded, capacity, connection reset
     … +202 lines (ctrl+o to expand)

● Now update the DB schema and storage API. First read the existing _init_db and _row_to_sdlc_task:

  Read 1 file (ctrl+o to expand)

● Now I have everything I need. Let me make all the changes:

  1. Add pause columns to SdlcTask and migration, add provider_cooldowns table, add all 6 storage methods:

● Update(~/projects/multi-ai-agent/sdlc/shared/storage.py)
  ⎿  Added 8 lines, removed 1 line
      50      output_file: str     # "BRD.md", "raci_matrix.xlsx" …
      51      output_format: str   # markdown / excel / mermaid / html / sql / yaml / dockerfile
      52      depends_on: str      # comma-separated SdlcTask IDs (empty = no deps)
      53 -    status: str          # pending / in_progress / waiting_approval / approved / failed
      53 +    status: str          # pending / in_progress / waiting_approval / approved / failed / paused
      54      input_data: str      # JSON
      55      output_data: str     # JSON {"content": "…"}
      56      approval_msg_id: str
     ...
      63      last_error: str = ""     # last failure message
      64      claimed_at: str = ""     # ISO timestamp when task was claimed for execution
      65      claimed_by: str = ""     # role name that claimed this task
      66 +    # Quota/provider pause fields (added via migration)
      67 +    pause_reason: str = ""   # quota_exceeded | rate_limited | context_limit_exceeded | …
      68 +    pause_provider: str = "" # "anthropic" | "openai" | "groq" | "ollama"
      69 +    pause_model: str = ""    # model_key that triggered the pause
      70 +    retry_after_at: str = "" # ISO timestamp — earliest time recovery worker may requeue
      71 +    paused_at: str = ""      # ISO timestamp when task entered paused state
      72 +    resume_policy: str = ""  # "auto" | "manual_token_fix"
      73
      74
      75  class RoleType(str, Enum):

● Now add the migration for the new pause columns and the provider_cooldowns table:

● Update(~/projects/multi-ai-agent/sdlc/shared/storage.py)
  ⎿  Added 23 lines, removed 4 lines
      211              # Migration: add execution-tracking columns if they don't exist yet
      212              _sdlc_cols = {r[1] for r in conn.execute("PRAGMA table_info(sdlc_tasks)").fetchall()}
      213              for _col, _defn in [
      214 -                ("attempt_count", "INTEGER DEFAULT 0"),
      215 -                ("last_error",    "TEXT DEFAULT ''"),
      216 -                ("claimed_at",    "TEXT DEFAULT ''"),
      217 -                ("claimed_by",    "TEXT DEFAULT ''"),
      214 +                ("attempt_count",  "INTEGER DEFAULT 0"),
      215 +                ("last_error",     "TEXT DEFAULT ''"),
      216 +                ("claimed_at",     "TEXT DEFAULT ''"),
      217 +                ("claimed_by",     "TEXT DEFAULT ''"),
      218 +                # Phase 8 pause fields
      219 +                ("pause_reason",   "TEXT DEFAULT ''"),
      220 +                ("pause_provider", "TEXT DEFAULT ''"),
      221 +                ("pause_model",    "TEXT DEFAULT ''"),
      222 +                ("retry_after_at", "TEXT DEFAULT ''"),
      223 +                ("paused_at",      "TEXT DEFAULT ''"),
      224 +                ("resume_policy",  "TEXT DEFAULT ''"),
      225              ]:
      226                  if _col not in _sdlc_cols:
      227                      conn.execute(f"ALTER TABLE sdlc_tasks ADD COLUMN {_col} {_defn}")
      228 +
      229 +            # Phase 8: provider cooldown tracking
      230 +            conn.execute("""
      231 +                CREATE TABLE IF NOT EXISTS provider_cooldowns (
      232 +                    id INTEGER PRIMARY KEY AUTOINCREMENT,
      233 +                    provider TEXT NOT NULL,
      234 +                    model TEXT NOT NULL DEFAULT '',
      235 +                    reason TEXT DEFAULT '',
      236 +                    retry_after_at TEXT NOT NULL,
      237 +                    created_at TEXT
      238 +                )
      239 +            """)
      240              conn.commit()
      241
      242      # ─── Project CRUD ───────────────────────────────────────────────────────────

● Now update _row_to_sdlc_task to read the 6 new pause columns (rows 23-28):

● Update(~/projects/multi-ai-agent/sdlc/shared/storage.py)
  ⎿  Added 17 lines, removed 6 lines
      742          return [self._row_to_sdlc_task(r) for r in rows]
      743
      744      def _row_to_sdlc_task(self, row) -> SdlcTask:
      745 +        def _s(i: int) -> str:
      746 +            return row[i] if len(row) > i and row[i] is not None else ""
      747 +        def _i(i: int) -> int:
      748 +            return row[i] if len(row) > i and row[i] is not None else 0
      749          return SdlcTask(
      750              id=row[0], project_id=row[1], epic_id=row[2], task_number=row[3],
      751              role=row[4], task_type=row[5], title=row[6], description=row[7],
      752              output_file=row[8], output_format=row[9], depends_on=row[10],
      753              status=row[11], input_data=row[12], output_data=row[13],
      750 -            approval_msg_id=row[14], revision_count=row[15], notes=row[16],
      751 -            created_at=row[17], updated_at=row[18],
      752 -            attempt_count=row[19] if len(row) > 19 and row[19] is not None else 0,
      753 -            last_error=row[20]   if len(row) > 20 and row[20] is not None else "",
      754 -            claimed_at=row[21]   if len(row) > 21 and row[21] is not None else "",
      755 -            claimed_by=row[22]   if len(row) > 22 and row[22] is not None else "",
      754 +            approval_msg_id=row[14], revision_count=_i(15), notes=_s(16),
      755 +            created_at=_s(17), updated_at=_s(18),
      756 +            attempt_count=_i(19),
      757 +            last_error=_s(20),
      758 +            claimed_at=_s(21),
      759 +            claimed_by=_s(22),
      760 +            # Phase 8 pause fields
      761 +            pause_reason=_s(23),
      762 +            pause_provider=_s(24),
      763 +            pause_model=_s(25),
      764 +            retry_after_at=_s(26),
      765 +            paused_at=_s(27),
      766 +            resume_policy=_s(28),
      767          )
      768
      769      def get_sdlc_task_by_title(self, task_name: str, role: str) -> Optional[SdlcTask]:

● Now add the 6 new storage methods at the end of the Storage class, before get_next_role:

● Update(~/projects/multi-ai-agent/sdlc/shared/storage.py)
  ⎿  Added 140 lines
      799              conn.commit()
      800              return cursor.rowcount > 0
      801
      802 +    # ─── Phase 8: Quota/Provider Pause ─────────────────────────────────────────
      803 +
      804 +    def pause_sdlc_task_for_provider(
      805 +        self,
      806 +        task_id: str,
      807 +        reason: str,
      808 +        provider: str,
      809 +        model: str,
      810 +        retry_after_at: str,
      811 +        error: str = "",
      812 +        resume_policy: str = "auto",
      813 +    ):
      814 +        """
      815 +        Move task to status='paused' and record all pause metadata.
      816 +
      817 +        Clears claimed_at/claimed_by so the recovery worker can safely requeue it
      818 +        without racing against an active agent claim.
      819 +        """
      820 +        now = datetime.utcnow().isoformat()
      821 +        with sqlite3.connect(self.db_path) as conn:
      822 +            conn.execute(
      823 +                """UPDATE sdlc_tasks
      824 +                   SET status='paused',
      825 +                       pause_reason=?, pause_provider=?, pause_model=?,
      826 +                       retry_after_at=?, paused_at=?, resume_policy=?,
      827 +                       last_error=?,
      828 +                       claimed_at='', claimed_by='',
      829 +                       updated_at=?
      830 +                   WHERE id=?""",
      831 +                (reason, provider, model, retry_after_at, now,
      832 +                 resume_policy, error[:500], now, task_id),
      833 +            )
      834 +            conn.commit()
      835 +
      836 +    def list_paused_sdlc_tasks(self, now_iso: str = "") -> list:
      837 +        """
      838 +        Return paused tasks whose retry_after_at <= now_iso (ready to resume).
      839 +        If now_iso is empty, return ALL paused tasks regardless of retry_after_at.
      840 +        Never returns tasks with resume_policy='manual_token_fix'.
      841 +        """
      842 +        now_iso = now_iso or datetime.utcnow().isoformat()
      843 +        with sqlite3.connect(self.db_path) as conn:
      844 +            rows = conn.execute(
      845 +                "SELECT * FROM sdlc_tasks "
      846 +                "WHERE status='paused' "
      847 +                "  AND (resume_policy IS NULL OR resume_policy != 'manual_token_fix') "
      848 +                "  AND (retry_after_at = '' OR retry_after_at <= ?) "
      849 +                "ORDER BY retry_after_at",
      850 +                (now_iso,),
      851 +            ).fetchall()
      852 +        return [self._row_to_sdlc_task(r) for r in rows]
      853 +
      854 +    def resume_paused_sdlc_task(self, task_id: str):
      855 +        """
      856 +        Clear pause fields and requeue task to pending.
      857 +        Only acts on tasks currently in status='paused'.
      858 +        """
      859 +        now = datetime.utcnow().isoformat()
      860 +        with sqlite3.connect(self.db_path) as conn:
      861 +            conn.execute(
      862 +                """UPDATE sdlc_tasks
      863 +                   SET status='pending',
      864 +                       pause_reason='', pause_provider='', pause_model='',
      865 +                       retry_after_at='', paused_at='', resume_policy='',
      866 +                       claimed_at='', claimed_by='',
      867 +                       updated_at=?
      868 +                   WHERE id=? AND status='paused'""",
      869 +                (now, task_id),
      870 +            )
      871 +            conn.commit()
      872 +
      873 +    # ── Provider cooldown ────────────────────────────────────────────────────
      874 +
      875 +    def set_provider_cooldown(
      876 +        self,
      877 +        provider: str,
      878 +        model: str,
      879 +        reason: str,
      880 +        retry_after_at: str,
      881 +    ):
      882 +        """
      883 +        Upsert a cooldown record for a provider+model combination.
      884 +        Replaces any existing cooldown for the same (provider, model) pair
      885 +        if the new retry_after_at is later (more restrictive).
      886 +        """
      887 +        now = datetime.utcnow().isoformat()
      888 +        with sqlite3.connect(self.db_path) as conn:
      889 +            existing = conn.execute(
      890 +                "SELECT id, retry_after_at FROM provider_cooldowns "
      891 +                "WHERE provider=? AND model=?",
      892 +                (provider, model),
      893 +            ).fetchone()
      894 +            if existing:
      895 +                # Only update if new deadline is later
      896 +                if retry_after_at >= existing[1]:
      897 +                    conn.execute(
      898 +                        "UPDATE provider_cooldowns "
      899 +                        "SET reason=?, retry_after_at=?, created_at=? "
      900 +                        "WHERE id=?",
      901 +                        (reason, retry_after_at, now, existing[0]),
      902 +                    )
      903 +            else:
      904 +                conn.execute(
      905 +                    "INSERT INTO provider_cooldowns (provider, model, reason, retry_after_at, created_at) "
      906 +                    "VALUES (?,?,?,?,?)",
      907 +                    (provider, model, reason, retry_after_at, now),
      908 +                )
      909 +            conn.commit()
      910 +
      911 +    def get_active_provider_cooldowns(self, now_iso: str = "") -> list:
      912 +        """
      913 +        Return list of dicts for cooldowns still active (retry_after_at > now).
      914 +        Each dict has: provider, model, reason, retry_after_at.
      915 +        """
      916 +        now_iso = now_iso or datetime.utcnow().isoformat()
      917 +        with sqlite3.connect(self.db_path) as conn:
      918 +            rows = conn.execute(
      919 +                "SELECT provider, model, reason, retry_after_at FROM provider_cooldowns "
      920 +                "WHERE retry_after_at > ? ORDER BY retry_after_at",
      921 +                (now_iso,),
      922 +            ).fetchall()
      923 +        return [
      924 +            {"provider": r[0], "model": r[1], "reason": r[2], "retry_after_at": r[3]}
      925 +            for r in rows
      926 +        ]
      927 +
      928 +    def clear_provider_cooldown(self, provider: str, model: str = ""):
      929 +        """Remove the cooldown record for the given provider (and optionally model)."""
      930 +        with sqlite3.connect(self.db_path) as conn:
      931 +            if model:
      932 +                conn.execute(
      933 +                    "DELETE FROM provider_cooldowns WHERE provider=? AND model=?",
      934 +                    (provider, model),
      935 +                )
      936 +            else:
      937 +                conn.execute(
      938 +                    "DELETE FROM provider_cooldowns WHERE provider=?", (provider,)
      939 +                )
      940 +            conn.commit()
      941 +
      942      def get_next_role(self, current_role: str) -> Optional[str]:
      943          """ส่งคืน Role ถัดไปใน SDLC Workflow (ใช้ channel_config)"""
      944          try:

● Now write the test file for Phase 8.0:

● Write(~/projects/multi-ai-agent/sdlc/tests/test_phase8_classifier_db.py)
  ⎿  Wrote 525 lines to ../sdlc/tests/test_phase8_classifier_db.py
       1 """
       2 Phase 8.0 Tests — LLM Error Classifier + DB Pause Schema + Storage API
       3
       4 Covers:
       5   - quota_exceeded classification (daily/monthly/extra usage/billing)
       6   - rate_limited with retry_after hint
       7   - context_limit_exceeded
       8   - auth_error → manual_token_fix resume policy
       9   - provider_unavailable (5xx/connection/overloaded)
      10   - timeout (class name + string)
     … +515 lines (ctrl+o to expand)

● Bash(python3 /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_phase8_classifier_db.py 2>&1 | tail -20)
  ⎿  test_connect_timeout (__main__.TestTimeout.test_connect_timeout) ... ok
     test_read_timeout (__main__.TestTimeout.test_read_timeout) ... ok
     test_timeout_exception_class (__main__.TestTimeout.test_timeout_exception_class) ... ok
     … +17 lines (ctrl+o to expand)

● Bash(python3 -c "
      import re…)
  ⎿  match: <re.Match object; span=(19, 31), match='Wait 90 secs'>
     group: 90

● The pattern \btoo.?many.?request\b doesn't match "requests" (ends in s, no word boundary). Fix the classifier:

● Update(~/projects/multi-ai-agent/sdlc/shared/llm_error_classifier.py)
  ⎿  Added 1 line, removed 1 line
      66       "quota_exceeded", "auto", 3600),
      67
      68      # ── Rate limit ───────────────────────────────────────────────────────────
      69 -    (r"\b(429|rate.?limit|too.?many.?request|requests.?per.?(minute|second|day)|"
      69 +    (r"\b(429|rate.?limit|too.?many.?requests?|requests?.?per.?(minute|second|day)|"
      70       r"tpm|rpm|rph|rps|tokens.?per.?minute|throughput.?limit)\b",
      71       "rate_limited", "auto", 60),
      72

● Bash(python3 /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_phase8_classifier_db.py 2>&1 | tail -10)
  ⎿  test_timeout_exception_class (__main__.TestTimeout.test_timeout_exception_class) ... ok
     test_timeout_string (__main__.TestTimeout.test_timeout_string) ... ok
     test_generic_string_not_quota (__main__.TestTransient.test_generic_string_not_quota) ... ok
     … +7 lines (ctrl+o to expand)

● All 67 pass. Now verify the full suite is still green:

● Bash(for f in /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_*.py; do echo -n "$(basename $f): "; python3 $f 2>&1 | grep -E
      "^Ran|^OK|FAILED"; done)
  ⎿  test_artifact_contracts.py: Ran 82 tests in 0.140s
     OK
     test_artifact_validator.py: Ran 50 tests in 0.407s
     … +13 lines (ctrl+o to expand)

● Bash(npm test 2>&1 | grep -E "Test Files|Tests " | head -3)
  ⎿   Test Files  19 passed (19)
           Tests  115 passed (115)

● 568 Python + 115 TypeScript — all green. Commit Phase 8.0:

● Bash(cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/llm_error_classifier.py sdlc/shared/storage.py
      sdlc/tests/test_phase8_classifier_db.py && git…)
  ⎿  Waiting…

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Bash command

   cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/llm_error_classifier.py sdlc/shared/storage.py
   sdlc/tests/test_phase8_classifier_db.py && git commit -m "$(cat <<'EOF'
   Phase 8.0: Quota-Aware Pause — Design + DB Schema + Classifier

   New: sdlc/shared/llm_error_classifier.py
     classify_llm_error(exc_or_message) → LLMErrorInfo
     Provider-agnostic classification of quota/rate/context/auth/timeout errors.
     Exception class name fast path (RateLimitError, AuthenticationError, …).
     Extracts Retry-After hint from error message; falls back to type defaults.

● Bash(python3 /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_phase8_classifier_db.py 2>&1 | tail -10)
  ⎿  test_timeout_exception_class (__main__.TestTimeout.test_timeout_exception_class) ... ok
     test_timeout_string (__main__.TestTimeout.test_timeout_string) ... ok
     test_generic_string_not_quota (__main__.TestTransient.test_generic_string_not_quota) ... ok
     … +7 lines (ctrl+o to expand)

● All 67 pass. Now verify the full suite is still green:

● Bash(for f in /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_*.py; do echo -n "$(basename $f): "; python3 $f 2>&1 | grep -E
      "^Ran|^OK|FAILED"; done)
  ⎿  test_artifact_contracts.py: Ran 82 tests in 0.140s
     OK
     test_artifact_validator.py: Ran 50 tests in 0.407s
     … +13 lines (ctrl+o to expand)

● Bash(npm test 2>&1 | grep -E "Test Files|Tests " | head -3)
  ⎿   Test Files  19 passed (19)
           Tests  115 passed (115)

● 568 Python + 115 TypeScript — all green. Commit Phase 8.0:

● Bash(cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/llm_error_classifier.py sdlc/shared/storage.py
      sdlc/tests/test_phase8_classifier_db.py && git…)
  ⎿  [main a8f0c06] Phase 8.0: Quota-Aware Pause — Design + DB Schema + Classifier
      3 files changed, 925 insertions(+), 11 deletions(-)
      create mode 100644 sdlc/shared/llm_error_classifier.py
      create mode 100644 sdlc/tests/test_phase8_classifier_db.py

● Phase 8.0 committed as a8f0c06. Now Phase 8.1 — pause integration in BaseAgent. Let me read the exact spot where errors surface:

  Read 1 file (ctrl+o to expand)

● Now let me see where errors from call_llm propagate — I need to find the exception handler in the poll loop:

  Searched for 1 pattern, read 1 file (ctrl+o to expand)

● Now I have the full picture. The LLM call is at lines 1501-1513, and if it raises, the exception propagates to
  _check_and_start_sdlc_tasks catch at line 1391. Phase 8.1 needs to intercept the LLM error right after the call_llm block and check if
  it's quota-related.

  The cleanest approach: wrap the LLM call block in a try/except, classify the error there, and pause instead of re-raising if it's a
  quota error.

  Read 1 file (ctrl+o to expand)

● Now I'll wrap the LLM call block with a quota-aware try/except. This needs a helper _pause_task_for_quota method too. Let me implement
  the full pause integration:

● Update(sdlc/shared/base_agent.py)
  ⎿  Added 27 lines, removed 9 lines
      1497          import time as _time
      1498          _start_ts = _time.monotonic()
      1499          _start_wall_ts = _time.time()  # wall-clock for mtime comparison in contract freshness check
      1500 -        if output_ch:
      1501 -            async with output_ch.typing():
      1500 +        try:
      1501 +            if output_ch:
      1502 +                async with output_ch.typing():
      1503 +                    content = await self.call_llm(
      1504 +                        prompt=prompt,
      1505 +                        project_id=task.project_id,
      1506 +                        project_name=project_name,
      1507 +                        force_model_key=_preferred_model_key,
      1508 +                    )
      1509 +            else:
      1510                  content = await self.call_llm(
      1511                      prompt=prompt,
      1512                      project_id=task.project_id,
      1513                      project_name=project_name,
      1514                      force_model_key=_preferred_model_key,
      1515                  )
      1508 -        else:
      1509 -            content = await self.call_llm(
      1510 -                prompt=prompt,
      1511 -                project_id=task.project_id,
      1512 -                project_name=project_name,
      1513 -                force_model_key=_preferred_model_key,
      1514 -            )
      1516 +        except Exception as _llm_exc:
      1517 +            from shared.llm_error_classifier import classify_llm_error
      1518 +            _err_info = classify_llm_error(_llm_exc)
      1519 +            if _err_info.is_quota_error:
      1520 +                # Pause task — do not consume retry budget for provider issues
      1521 +                await self._pause_task_for_quota(
      1522 +                    task=task,
      1523 +                    project_name=project_name,
      1524 +                    err_info=_err_info,
      1525 +                    model_key=_preferred_model_key or routing.get("model_id", ""),
      1526 +                    output_ch=output_ch,
      1527 +                    log_id=log_id,
      1528 +                    estimated_cost=routing.get("estimated_cost", 0.0),
      1529 +                    actual_model=self._last_actual_model_key or routing.get("model_id", "unknown"),
      1530 +                )
      1531 +                return  # handled — do not propagate
      1532 +            raise  # non-quota error: let poll loop handle normally
      1533          _duration = _time.monotonic() - _start_ts
      1534          # actual_model reflects fallback if the primary model failed mid-call
      1535          _actual_model = self._last_actual_model_key or routing.get("model_id", "unknown")

● Now add the _pause_task_for_quota helper method. Find a good insertion point after _execute_sdlc_task ends:

  Searched for 2 patterns, read 1 file (ctrl+o to expand)

● Update(sdlc/shared/base_agent.py)
  ⎿  Added 107 lines
      1782
      1783          logger.info(f"[{self.role_name}] completed sdlc task {task.id} → {saved_path} (approval:{_approval_mode})")
      1784
      1785 +    # ─── Phase 8: Quota/Provider Pause helper ──────────────────────────────
      1786 +
      1787 +    async def _pause_task_for_quota(
      1788 +        self,
      1789 +        task,
      1790 +        project_name: str,
      1791 +        err_info,
      1792 +        model_key: str,
      1793 +        output_ch,
      1794 +        log_id: str,
      1795 +        estimated_cost: float,
      1796 +        actual_model: str,
      1797 +    ):
      1798 +        """
      1799 +        Pause an SDLC task when all LLM fallbacks fail due to quota/rate/provider issues.
      1800 +
      1801 +        - Writes paused status + pause metadata to DB (clears claim so recovery can requeue)
      1802 +        - Registers provider cooldown
      1803 +        - Notifies Discord output channel
      1804 +        - Sends Web App paused event (no approval_item created)
      1805 +        - Closes the timelog entry
      1806 +        """
      1807 +        import time as _time
      1808 +        from datetime import timedelta
      1809 +        from shared.channel_config import ROLE_CHANNELS
      1810 +
      1811 +        # Compute retry_after timestamp
      1812 +        retry_s = err_info.retry_after_seconds or 3600
      1813 +        retry_after_at = (
      1814 +            datetime.utcnow() + timedelta(seconds=retry_s)
      1815 +        ).isoformat()
      1816 +
      1817 +        # Determine provider from model_key or err_info hint
      1818 +        provider = err_info.provider_hint
      1819 +        if not provider and "/" in model_key:
      1820 +            provider = model_key.split("/")[0]
      1821 +
      1822 +        # 1. Persist pause state
      1823 +        self.storage.pause_sdlc_task_for_provider(
      1824 +            task_id=task.id,
      1825 +            reason=err_info.error_type,
      1826 +            provider=provider,
      1827 +            model=model_key,
      1828 +            retry_after_at=retry_after_at,
      1829 +            error=err_info.raw_message,
      1830 +            resume_policy=err_info.resume_policy,
      1831 +        )
      1832 +
      1833 +        # 2. Register provider cooldown so router avoids it
      1834 +        if provider:
      1835 +            self.storage.set_provider_cooldown(
      1836 +                provider=provider,
      1837 +                model=model_key,
      1838 +                reason=err_info.error_type,
      1839 +                retry_after_at=retry_after_at,
      1840 +            )
      1841 +
      1842 +        # 3. Discord notification (no approval needed)
      1843 +        if output_ch:
      1844 +            _policy_note = " — **manual key rotation required**" if err_info.is_manual else ""
      1845 +            await output_ch.send(
      1846 +                f"⏸️ **Task Paused** — `{task.id}` (`{task.task_type}`)\n"
      1847 +                f"**Reason:** {err_info.error_type} on `{model_key}`{_policy_note}\n"
      1848 +                f"**Resume after:** {retry_after_at[:19]} UTC\n"
      1849 +                f"**Error:** `{err_info.raw_message[:200]}`"
      1850 +            )
      1851 +
      1852 +        # 4. Web App notification (status=paused, no approval_item)
      1853 +        await get_bridge().task_completed(
      1854 +            role_key=self.role_name,
      1855 +            project_id=task.project_id,
      1856 +            project_name=project_name,
      1857 +            task_name=task.title,
      1858 +            summary=(
      1859 +                f"⏸️ Task paused: {err_info.error_type} on {provider or model_key}. "
      1860 +                f"Resume after {retry_after_at[:19]} UTC."
      1861 +            ),
      1862 +            files=[],
      1863 +            model_id=actual_model,
      1864 +            cost_usd=estimated_cost,
      1865 +            duration_seconds=0.0,
      1866 +            sdlc_task_id=task.id,
      1867 +            status="paused",
      1868 +            metadata=dict(
      1869 +                pause_reason=err_info.error_type,
      1870 +                pause_provider=provider,
      1871 +                pause_model=model_key,
      1872 +                retry_after_at=retry_after_at,
      1873 +                resume_policy=err_info.resume_policy,
      1874 +                error=err_info.raw_message,
      1875 +            ),
      1876 +        )
      1877 +
      1878 +        # 5. Close timelog
      1879 +        self.timelog.finish(
      1880 +            log_id=log_id,
      1881 +            model_used=actual_model,
      1882 +            cost_usd=estimated_cost,
      1883 +            output_files=[],
      1884 +            status="paused",
      1885 +        )
      1886 +
      1887 +        logger.warning(
      1888 +            f"[{self.role_name}] task {task.id} paused ({err_info.error_type}) "
      1889 +            f"provider={provider} retry_after={retry_after_at[:19]}"
      1890 +        )
      1891 +
      1892      def _build_sdlc_context(self, task: SdlcTask, project_name: str, input_data: dict) -> dict:
      1893          """รวบรวม context จาก dependency tasks + input_data สำหรับ prompt"""
      1894          from datetime import date

● Now check that task_completed in web_bridge.py accepts a metadata kwarg — it doesn't currently. Let me check the signature:

  Searched for 1 pattern, read 1 file (ctrl+o to expand)

● The task_completed doesn't take a metadata kwarg — I need to use contract_info (which already merges into metadata) or add an extension.
   Cleanest: add extra_metadata param to task_completed, and fix the call:

● Update(sdlc/shared/web_bridge.py)
  ⎿  Added 1 line
      163          artifacts: Optional[list] = None,
      164          error_info: str = "",
      165          contract_info: Optional[dict] = None,
      166 +        extra_metadata: Optional[dict] = None,
      167      ):
      168          """Agent ทำเสร็จ — status default = waiting_approval (role_tasks) หรือ completed (sdlc_tasks)"""
      169          artifact_url = (

● Update(sdlc/shared/web_bridge.py)
  ⎿  Added 2 lines
      201                  "artifact_url":     artifact_url,
      202                  # Artifact contract validation result
      203                  **(contract_info or {}),
      204 +                # Additional caller-supplied metadata (e.g. pause info)
      205 +                **(extra_metadata or {}),
      206              },
      207          })
      208

● Now fix the _pause_task_for_quota call to use extra_metadata instead of metadata:

● Update(sdlc/shared/base_agent.py)
  ⎿  Added 1 line, removed 1 line
      1865              duration_seconds=0.0,
      1866              sdlc_task_id=task.id,
      1867              status="paused",
      1868 -            metadata=dict(
      1868 +            extra_metadata=dict(
      1869                  pause_reason=err_info.error_type,
      1870                  pause_provider=provider,
      1871                  pause_model=model_key,

● Now verify everything compiles:

● Bash(python3 -c "import sys; sys.path.insert(0,'sdlc'); from shared.web_bridge import WebAppBridge; from shared.llm_error_classifier
      import classify_llm_error; print…)
  ⎿  imports ok
     base_agent ok

● Now write the Phase 8.1 tests — pause integration, Discord/Web notification mocks, no approval item for paused:

● Write(sdlc/tests/test_phase8_pause_integration.py)
  ⎿  Wrote 335 lines to sdlc/tests/test_phase8_pause_integration.py
       1 """
       2 Phase 8.1 Tests — BaseAgent Pause Integration + WebBridge extra_metadata
       3
       4 Covers:
       5   - quota LLM error → task paused (not failed, not retried normally)
       6   - pause preserves attempt_count (no +1 for quota errors)
       7   - non-quota LLM error still propagates normally
       8   - _pause_task_for_quota writes all DB fields
       9   - _pause_task_for_quota sends task_completed(status=paused) to web bridge
      10   - web bridge task_completed(extra_metadata=...) merges extra fields into metadata
     … +325 lines (ctrl+o to expand)

● Bash(python3 /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_phase8_pause_integration.py 2>&1 | tail -20)
  ⎿  test_transient_uses_normal_retry_budget (__main__.TestPauseDecision.test_transient_uses_normal_retry_budget)
     Non-quota error: is_quota_error=False, so attempt_count SHOULD increment. ... ok
     test_extra_metadata_merged_into_payload (__main__.TestWebBridgeExtraMetadata.test_extra_metadata_merged_into_payload) ... WebApp
     … +18 lines (ctrl+o to expand)

● All 20 pass. Now run the full suite:

● Bash(for f in /home/off_poff_p/projects/multi-ai-agent/sdlc/tests/test_*.py; do echo -n "$(basename $f): "; python3 $f 2>&1 | grep -E
      "^Ran|^OK|FAILED"; done)
  ⎿  test_artifact_contracts.py: Ran 82 tests in 0.122s
     OK
     test_artifact_validator.py: Ran 50 tests in 0.410s
     … +15 lines (ctrl+o to expand)

● Bash(npm test 2>&1 | grep -E "Test Files|Tests " | head -3)
  ⎿  (No output)

● Bash(npm test 2>&1 | grep -E "passed|failed" | tail -5)
  ⎿  (No output)

● Bash(npm test 2>&1 | tail -8)
  ⎿  npm error code ENOENT
     npm error syscall open
     npm error path /home/off_poff_p/projects/multi-ai-agent/package.json
     … +6 lines (ctrl+o to expand)

● Bash(cd /home/off_poff_p/projects/multi-ai-agent/webapp && npm test 2>&1 | tail -6)
  ⎿   Test Files  19 passed (19)
           Tests  115 passed (115)
        Start at  22:44:28
        Duration  6.61s (transform 266ms, setup 0ms, import 3.56s, tests 1.92s, environment 1ms)

● 588 Python + 115 TypeScript — all green. Commit Phases 8.1:

● Bash(cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/base_agent.py sdlc/shared/web_bridge.py
      sdlc/tests/test_phase8_pause_integration.py && git co…)
  ⎿  Waiting…

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Bash command

   cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/base_agent.py sdlc/shared/web_bridge.py
   sdlc/tests/test_phase8_pause_integration.py && git commit -m "$(cat <<'EOF'
   Phase 8.1: Pause Integration in BaseAgent + WebBridge extra_metadata

     … +15 lines (ctrl+o to expand)

● Bash(npm test 2>&1 | grep -E "Test Files|Tests " | head -3)
  ⎿  (No output)

● Bash(npm test 2>&1 | grep -E "passed|failed" | tail -5)
  ⎿  (No output)

● Bash(npm test 2>&1 | tail -8)
  ⎿  npm error code ENOENT
     npm error syscall open
     npm error path /home/off_poff_p/projects/multi-ai-agent/package.json
     … +6 lines (ctrl+o to expand)

● Bash(cd /home/off_poff_p/projects/multi-ai-agent/webapp && npm test 2>&1 | tail -6)
  ⎿   Test Files  19 passed (19)
           Tests  115 passed (115)
        Start at  22:44:28
        Duration  6.61s (transform 266ms, setup 0ms, import 3.56s, tests 1.92s, environment 1ms)

● 588 Python + 115 TypeScript — all green. Commit Phases 8.1:

● Bash(cd /home/off_poff_p/projects/multi-ai-agent && git add sdlc/shared/base_agent.py sdlc/shared/web_bridge.py
      sdlc/tests/test_phase8_pause_integration.py && git co…)
  ⎿  [main 0fce75b] Phase 8.1: Pause Integration in BaseAgent + WebBridge extra_metadata
      3 files changed, 472 insertions(+), 9 deletions(-)
      create mode 100644 sdlc/tests/test_phase8_pause_integration.py
  ⎿  You're out of usage credits · resets 1:20am (Asia/Bangkok)

## 2026-05-20 Continuation

Yesterday's stopping point:
- Phase 8.0 committed as `a8f0c06`
  - added provider-agnostic LLM error classifier
  - added pause metadata columns and provider cooldown table
  - added storage APIs for pause/resume/cooldown behavior
- Phase 8.1 committed as `0fce75b`
  - BaseAgent catches quota/rate/context/auth/provider errors from LLM calls
  - quota/provider errors pause SDLC tasks instead of consuming retry budget
  - WebAppBridge supports `extra_metadata`
  - paused events sync to the web app with `status=paused`
- Last checked suite at that point:
  - 588 Python tests passed
  - 115 TypeScript tests passed

Phase 8.2 implemented today:
- Added `sdlc/agents/recovery_worker.py`
  - worker only requeues paused tasks whose `retry_after_at` has passed
  - worker never claims or executes SDLC tasks
  - `manual_token_fix` pauses remain excluded from auto-resume
  - active provider cooldowns defer task resume and push `retry_after_at` forward
  - expired provider cooldown rows are pruned
- Added router cooldown avoidance in `sdlc/shared/model_router.py`
  - active provider/model cooldowns are skipped during task-type routing
  - active provider/model cooldowns are skipped during score-based routing
  - budget fallback also respects cooldown exclusions
- Added `Storage.get_expired_provider_cooldowns()`
- Registered the worker in:
  - `sdlc/ecosystem.bots.config.js` as `sdlc-quota-recovery`
  - `sdlc/docker-compose.yml` as `quota-recovery`
  - `sdlc/scripts/start_pm2.sh` so `--no-cron` still includes quota recovery
- Added `sdlc/tests/test_phase8_recovery_worker.py`

Verification on 2026-05-20:
- `python3 sdlc/tests/test_phase8_recovery_worker.py` — 11 passed
- `python3 sdlc/tests/test_phase8_classifier_db.py` — 67 passed
- `python3 sdlc/tests/test_phase8_pause_integration.py` — 20 passed
- `python3 sdlc/tests/test_artifact_contracts.py` — 82 passed
- `python3 sdlc/tests/test_artifact_validator.py` — 50 passed
- `python3 sdlc/tests/test_runtime_correctness.py` — 29 passed
- `python3 sdlc/tests/test_web_sync.py` — 53 passed
- `python3 sdlc/tests/test_dev_workspace.py` — 98 passed
- `python3 sdlc/tests/test_devops_execution.py` — 122 passed
- `python3 sdlc/tests/test_test_runner.py` — 67 passed
- `npm test` in `webapp/` — 19 files / 115 tests passed
- `python3 -m pytest sdlc/tests` was not available because `pytest` is not installed in the system Python.
- Local worker smoke test passed with explicit DB path:
  `DB_PATH=/home/off_poff_p/projects/multi-ai-agent/sdlc/data/sdlc.db OUTPUT_BASE_PATH=/tmp/sdlc_outputs python3 agents/recovery_worker.py --run-now`
