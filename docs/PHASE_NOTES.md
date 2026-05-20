# Multi-Agent AI Phase Notes

  Current status:
  - Phase 9 FINALIZED — all sub-phases complete, all tests green, worktree clean

  Important concept:
  - Discord is primary runtime — bots are task executors, web is back-office control plane
  - Recovery worker must not execute SDLC tasks — requeue only
  - Webapp-initiated resume goes through the same resume_paused_sdlc_task() code path
  - manual_token_fix tasks are NEVER auto-resumed — web Resume button works but shows warning
  - Two-SQLite architecture: Python sdlc.db ↔ webapp SQLite — never cross-read; bridge via ingest POST + file JSON

  Roadmap: docs/PHASE9_ROADMAP.md

---

## Phase 8 FINALIZED

  Phase 8 complete summary (all commits verified):
  - 8.0 (a8f0c06): llm_error_classifier.py + DB pause schema + provider_cooldowns table + 6 storage methods
  - 8.1 (0fce75b): BaseAgent._pause_task_for_quota() + WebBridge.extra_metadata
  - 8.2 (80b352d): agents/recovery_worker.py + Storage.update_task_retry_after/prune_expired_cooldowns
  - 8.3 (fc12447): Discord !sdlc_paused + !sdlc_resume + Web App paused badge
  - finalization: model_router cooldown-aware routing + Docker/PM2 deploy configs committed

  Finalization details:
  - model_router.py: _active_cooldown_blocks(), _is_cooling_down(), best_free_for_role(exclude_providers)
    router skips cooling-down models/providers in budget fallback AND score-based routing
  - docker-compose.yml: quota-recovery service running agents/recovery_worker.py
  - ecosystem.bots.config.js: sdlc-quota-recovery process registered
  - scripts/start_pm2.sh: --no-cron still starts sdlc-quota-recovery (runtime safety, not cron)

  Test totals at Phase 8 finalization: 599 Python + 115 TypeScript — all green

---

## Phase 9 FINALIZED

  Goal: Runtime Observability & Operator Control Plane

  Commit sequence (all verified, worktree clean after finalization):
  - 9.0 (7da0dde): docs/PHASE9_ROADMAP.md — design locked
  - 9.1 (b619505): Recovery status APIs (backend)
  - 9.2 (57fe1a9): Recovery dashboard UI
  - 9.2 hotfix (61eec2f): Lint fix — Date.now() moved out of render, typed aliases, trailing whitespace
  - 9.3 (cad58ba): Agent pause/resume audit trail
  - 9.4 (b0aa818): hermes3 last-resort cooldown hardening

  Sub-phase details:

  9.1 COMPLETE — Recovery status APIs (backend)
    Python: recovery_worker.tick() returns tuple, writes runtime_status.json (_write_runtime_status),
            _count_all_paused() for paused_count in status file
    webapp/lib/agents/query.ts: listPausedTaskEvents() (correlated MAX(id) subquery, excludes resumed tasks),
                                upsertResumeRequestFlag()
    webapp/lib/audit/events.ts: AuditEventType += "agent.task.resumed.web"
    webapp/app/api/runtime/paused-tasks/route.ts: GET — Bearer auth
    webapp/app/api/runtime/paused-tasks/[sdlcTaskId]/resume/route.ts: POST — Admin session, system_config flag
    webapp/app/api/runtime/cooldowns/route.ts: GET — Bearer auth, reads runtime_status.json
    webapp/app/api/runtime/recovery/route.ts: GET — Bearer auth, reads tick_history.json newest-first
    13 TypeScript tests (all green)

  9.2 COMPLETE — Recovery dashboard UI
    Hotfix prerequisite: listPausedTaskEvents() correlated subquery excludes tasks where newer event
      has overridden paused status (resume/complete event after pause)
    webapp/app/recovery/page.tsx: server component, Admin-gated, 4 panels
      Worker Status bar (workerAlive computed in readRuntimeStatus(), not render body)
      Paused Task Queue (ResumeButton for manual_token_fix tasks only)
      Active Provider Cooldowns card grid
      Recovery Tick Log table
    webapp/app/recovery/_components/ResumeButton.tsx: "use client", POSTs to resume API, router.refresh()
    webapp/app/_components/app-shell.tsx: Recovery nav link in System group
    14 TypeScript tests (all green, includes resumed-task exclusion test)

  9.3 COMPLETE — Agent pause/resume audit trail
    Python shared/web_bridge.py: WebAppBridge.post_event() — generic ingest for agent.task.* events;
      actor merged into metadata dict
    Python shared/base_agent.py: _pause_task_for_quota() step 5 emits agent.task.paused;
      sdlc_resume_cmd emits agent.task.resumed.discord after ctx.send()
    Python agents/recovery_worker.py: tick() requeue branch emits agent.task.resumed.auto;
      dry_run and deferred paths skip emission
    webapp/lib/audit/events.ts: AuditEventType += agent.task.paused, agent.task.resumed.auto,
      agent.task.resumed.discord
    webapp/app/audit/page.tsx: EVENT_TYPE_OPTIONS += all 4 agent.task.* types
    sdlc/tests/test_phase9_audit_trail.py: 7 tests (TestWebBridgePostEvent × 4, TestRecoveryWorkerAuditEvents × 3)
    webapp/tests/runtime-phase9.test.ts: +3 TypeScript tests using top-level import (not require())
    17 TypeScript + 7 Python Phase 9.3 tests — all green

  9.4 COMPLETE — hermes3 last-resort cooldown hardening
    shared/model_router.py: module-level logger added; warning-only (never skip hermes3)
      best_free_for_role(): logger.warning when "ollama" in exclude_providers at ultimate fallback
      ModelRouter.route(): logger.warning when "ollama" in cooldown_providers at last-resort
      Warning message: "[Router] WARNING: hermes3 last-resort used despite ollama cooldown"
    sdlc/tests/test_phase9_model_router.py: 6 tests (3 × best_free_for_role, 3 × route())
      returns hermes3, logs warning when cooling, no warning when not cooling

  Final test totals (Phase 9 finalization):
    Python: 11 (phase8 recovery) + 20 (phase8 pause) + 67 (phase8 classifier) + 7 (phase9 audit) + 6 (phase9 router) = 111 Phase 8+9 tests
    TypeScript: 20 files / 132 tests — all green
    py_compile: recovery_worker.py, base_agent.py, web_bridge.py, model_router.py, storage.py — all pass

  Known remaining lint issues (pre-Phase 9 legacy, not fixed in this phase):
    3 errors (not warnings):
      app/api/admin/settings/load/route.ts: no-explicit-any (2 occurrences)
      app/cron/page.tsx:84: react-hooks/set-state-in-effect (setState inside useEffect body)
    8 warnings:
      app/workboard/_components/WorkboardClient.tsx: unused useRef, unused STATUS_COLOR
      tests/control-plane.test.ts: 3× unused 'now', 1× unused 'meta'
      app/api/audit/export/route.ts and app/api/runtime/decisions/route.ts: no-explicit-any

  Hotfix (post-Phase-9): legacy role pipeline blocked against SDLC projects
    sdlc/shared/base_agent.py:
      _check_and_start_pending_task() — guard changed from role-scoped to project-scoped:
        Before: list_sdlc_tasks(project_id=..., role=self.role_name) — only checked own role
        After:  list_sdlc_tasks(project_id=...) — checks ANY sdlc_task in project
        Symptom: PM/BA/SA/UXUI agents fired legacy pipeline on projects with only CEO tasks
      process_task() stub — now raises NotImplementedError instead of returning fake output:
        Before: returned {"summary": "PM stub (SDLC task flow active)"} → posted as "Complete"
        After:  raises NotImplementedError → caught by receive_task error handler → task "failed"
        Symptom: PM Agent — Complete posted to Discord even though no PM work was done
    sdlc/tests/test_hotfix_legacy_guard.py: 6 tests (legacy guard + process_task stub) — all green

  Feature: CEO attachment intake (.txt / .md / .csv / .xlsx)
    sdlc/shared/attachment_intake.py: new helper module
      parse_bytes(data, filename) → AttachmentResult — sync, safe to test
      gather_intake(message, inline_text) → (combined, warnings) — async, Discord-compatible
      Limits: 4 MB per file, 15k chars per parsed attachment, 25k total combined
      .txt/.md: UTF-8 with latin-1 fallback
      .csv: pipe-delimited rows
      .xlsx: openpyxl (graceful ImportError if not installed)
      .xls: rejected with conversion hint; unsupported extensions rejected clearly
    sdlc/agents/ceo/agent.py:
      !new command: calls gather_intake(ctx.message, inline_text) — merges text + attachments
      _interactive_project_start: calls gather_intake(response, response.content)
      _MAX_REQ_CHARS raised 8k → 25k to match MAX_TOTAL_CHARS
    sdlc/tests/test_attachment_intake.py: 24 tests — all green
    Image (PNG/JPG) and PDF support deferred to a future phase (OCR/vision dependency)

  Hotfix: preserve full CEO requirements + SDLC stage gates
    sdlc/shared/base_agent.py — _build_sdlc_context():
      ctx["requirements"] now prefers input_data["requirements"] (full text, never truncated)
      Falls back to project.description (500-char truncation) only when input_data lacks key.
    sdlc/agents/ceo/agent.py:
      _on_sdlc_task_completed (epics): injects full requirements into every downstream task's
        input_data["requirements"] so BA/SA/UXUI/DEV prompts receive the full text.
      _start_project_from_text(): project_name parser strips "## Attachment:" headers and
        "!<command>" Discord prefixes before splitting on "|" or "name:" key.
    sdlc/shared/task_catalog.py:
      TASK_CATALOG["ceo"]: both project_brief and epics get preferred_model =
        "claude-cli/claude-sonnet-4-6"
      TASK_CATALOG["uxui"]["design_system"]: depends_on_types changed [] → ["user_flow"]
        so design_system waits for user_flow (was starting immediately)
      CROSS_ROLE_DEPS: added "ba": {"brd": "pm:project_charter"} — BA now waits for PM
      resolve_deps(): fallback to project_epic_id for cross-scope deps
        (epic-level BA depending on project-level PM)
    Stage gate order (complete):
      CEO epics → [all tasks created] → PM project_charter → BA brd → BA ... → BA data_dictionary
      → SA system_purpose → ... → SA api_spec → UXUI user_flow → UXUI wireframe → UXUI design_system
      DEV frontend_structure (from UXUI wireframe) | DEV backend_structure (from SA api_spec)
      → DEV unit_tests → DEV dev_readme → QA qa_plan → ...
    sdlc/agents/ceo/prompts.py: CEO Golden Rules 9-11 added:
      Preserve explicit user constraints (timeline, budget, team size) exactly as stated.
      Do not invent numbers; mark invented values as [Assumption] or TBD.
    sdlc/tests/test_hotfix_requirements.py: 14 tests — all green
      TestBuildSdlcContextRequirements × 4 (requirements preservation + fallback)
      TestCEOProjectNameExtraction × 4 (clean name from attachment/command prefix)
      TestStageGates × 6 (cross-role deps, build_project_tasks resolution, preferred_model)

  Hotfix: bi-directional SDLC approvals
    Problems fixed:
      1. Approval card was posted to #{role}-output (not #{role}-approve)
      2. Discord embed said only !revise / !reject, not !approve
      3. Web decision notifications used DISCORD_APPROVAL_CHANNEL_ID env var
         (single global channel) instead of role-specific #{role}-approve
    Changes — sdlc/shared/base_agent.py:
      _execute_sdlc_task(): approve_ch now fetched alongside output_ch and tlog_ch
      Completion block restructured:
        output_ch: brief summary ("Awaiting approval in #pm-approve")
        approve_ch (manual mode): explicit approval card embed with:
          Task ID, Type, Model, Duration, Artifact download link
          Description: "Reply to this message with: !approve / !revise / !reject"
          approval_msg_id stored from approve_ch message (not output_ch)
        Auto-approve path uses already-resolved approve_ch (no redundant re-fetch)
      _execute_web_decision(): replaced os.getenv("DISCORD_APPROVAL_CHANNEL_ID")
        with role-specific ROLE_CHANNELS.get(role_name).approve lookup
    Tests:
      sdlc/tests/test_hotfix_approvals.py: 9 tests — all green
        TestApprovalChannelRouting × 3 (manual posts to approve ch, approval_msg_id
          from approve ch, auto-mode does not set approval_msg_id)
        TestDiscordApproveSync × 2 (!approve updates sdlc.db, calls bridge with sdlc_task_id)
        TestWebDecisionRoleChannel × 2 (web decision notifies role-specific channel,
          no reliance on DISCORD_APPROVAL_CHANNEL_ID env var)
        TestContractFailedNoApproval × 1 (status="blocked" → no approval_item)
        TestApproveChannelNames × 1 (every role has #{role}-approve channel)
      webapp/tests/approval-bidirectional.test.ts: 6 tests — all green
        approval_item stores discord_message_id from approve channel
        !approve ingest syncs to approval_item by sdlc_task_id
        revision_requested event updates approval_item to rework_requested
        web UI approve → item appears in decisions endpoint with discord_message_id
        blocked status does not create approval_item
        validation-failed (blocked) items absent from decisions endpoint

  Next: Phase 10 TBD
