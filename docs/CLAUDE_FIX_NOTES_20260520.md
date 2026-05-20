# Claude Fix Notes — SDLC Runtime Cleanup & Retry Issues

Date: 2026-05-20

## Context

Latest test project was `Paper Trading Bot MVP` (`93F945FF`). Runtime data has been purged after capturing model usage in:

- `docs/runtime_snapshots/20260520_paper_trading_model_usage.txt`

Agents are currently stopped in PM2 so the next test can start cleanly.

## Issues Observed

### 1. Failed retry artifacts appeared as final output

Root cause:

- `_execute_sdlc_task()` saved output directly to the canonical project output path before role contract validation.
- On validation/contract failure, `record_sdlc_task_error(..., requeue=True)` moved the task back to `pending`.
- Retry then started again and wrote another artifact, while failed artifacts still appeared in the final output folder.

Fix direction:

- Write each attempt to an isolated `.attempts/<task-id>-attempt-N-<timestamp>/` staging directory.
- Run validation and contract checks against staging only.
- Promote/copy staging files to the canonical output directory only after all checks pass.
- Do not create approval cards for failed/blocked attempts.

Current patch:

- `sdlc/shared/base_agent.py`
  - `_build_attempt_output_dir()`
  - `_promote_attempt_artifacts()`
  - `_execute_sdlc_task()` now stages first, validates/contracts, then promotes.
- `sdlc/tests/test_hotfix_approvals.py`
  - failed attempt does not overwrite final artifact
  - passing attempt promotes artifact

### 2. Approved task should not require approval again if downstream hook fails

Root cause:

- After Discord/Web approve, `_on_sdlc_task_completed()` can fail.
- Previous behavior only logged the error; user did not get a clear runtime notification.

Fix direction:

- Once a human approves, preserve `status='approved'`.
- If post-approval hook fails, notify Discord/Web with error details.
- Do not generate a second approval card for the same approved artifact.

Current patch:

- `sdlc/shared/base_agent.py`
  - Discord approval path sends `Post-Approval Error` message and `get_bridge().error(...)`.
  - Web approval path does the same in the role approve channel.
- Tests added for both Discord and Web approval hook error behavior.

### 3. Discord purge skipped timelog channels by accident

Root cause:

- `scripts/purge_all_messages.py` used `SKIP_KEYWORDS = ["log"]`.
- That skipped `#ba-timelog`, `#pm-timelog`, etc., even though only `#log` should be preserved.

Fix direction:

- Preserve exact channel names only.
- `#log` is preserved.
- `*-timelog` channels are purgeable.

Current patch:

- `sdlc/scripts/purge_all_messages.py`
  - `SKIP_CHANNEL_NAMES = {"log"}`

### 4. PM tasks were too parallel after Project Charter

Observed:

- `project_management_plan`, `raci_matrix`, `risk_register`, and `communications_plan` all depended only on `project_charter`.
- This allowed PM tasks to run out of expected order and made the output stream look noisy during retries.

Runtime fix already applied:

- `project_management_plan` depends on `project_charter`
- `raci_matrix` depends on `project_management_plan`
- `risk_register` depends on `project_management_plan`
- `communications_plan` depends on `project_management_plan`
- `project_status_report` depends on `communications_plan` and `risk_register`

Remaining Claude work:

- Improve PM prompt/contract quality so `project_management_plan` reliably includes a concrete `schedule`.
- Improve `risk_register` prompt/contract quality so every risk includes clear `mitigation`.

### 5. Model fallback problems caused low-quality/invalid output

Observed from logs:

- Anthropic API returned `401 Unauthorized`.
- Claude CLI ran out of usage credits.
- Groq returned `413 Payload Too Large` for large prompts.
- Runtime fell back to `ollama/qwen3`, which produced several contract/validation failures.

Recommended fix:

- Add prompt-size guards before Groq fallback.
- For large SDLC docs, route to Claude CLI when available or split context into smaller sections.
- Treat `413 Payload Too Large` as a routing signal to choose local model or compressed prompt, not as a normal retry.
- Add model/provider reason to task error messages and web audit metadata.

## Detailed Claude Assignment

Claude should continue from the current patched state. The runtime has already been cleaned for a fresh test, so this work should focus on prompt quality, contract accuracy, and model routing. Do not restart agents, recreate test data, or repopulate Discord/Web messages unless the user explicitly asks.

### Current State Claude Must Preserve

- PM2 SDLC agents are stopped.
- SDLC runtime DB tables have been cleared.
- Web app runtime/cache tables have been cleared.
- `sdlc/outputs/projects/*` has been cleared.
- Discord SDLC channels have been cleared except exact channel `#log`.
- Timelog channels are intentionally purgeable and should not be protected by a broad `log` keyword rule.
- Failed SDLC attempts now write to `.attempts/...` first and only promote to canonical output after validation and contract checks pass.
- Human approval must remain approved even if a downstream post-approval hook fails.

### Files Claude Should Read First

- `docs/PHASE_NOTES.md`
- `docs/CLAUDE_FIX_NOTES_20260520.md`
- `docs/runtime_snapshots/20260520_paper_trading_model_usage.txt`
- `sdlc/shared/base_agent.py`
- `sdlc/shared/task_catalog.py`
- `sdlc/shared/artifact_contracts.py`
- `sdlc/shared/artifact_validator.py`
- `sdlc/shared/model_router.py`
- `sdlc/shared/llm_client.py`
- `sdlc/agents/pm/prompts.py`
- `sdlc/agents/pm/task_prompts.py`
- `sdlc/agents/ba/prompts.py`
- `sdlc/agents/ba/task_prompts.py`
- `sdlc/tests/test_artifact_contracts.py`
- `sdlc/tests/test_hotfix_requirements.py`
- `sdlc/tests/test_hotfix_approvals.py`
- `sdlc/tests/test_phase9_model_router.py`

### Task 1: Harden PM Prompt Output

Problem:

- `project_management_plan` failed because contract checks could not find a concrete schedule.
- `risk_register` failed because contract checks could not find mitigation content.
- During provider fallback, weaker/local models were more likely to emit incomplete artifacts.

Claude should update PM prompts so required sections are explicit and hard to skip.

Acceptance criteria for `project_management_plan`:

- Output must include a clear heading or table using at least one recognized schedule term:
  - `schedule`
  - `timeline`
  - `project schedule`
  - `ตารางเวลา`
  - `แผนเวลา`
- For a Paper Trading Bot project, include a concrete 4-week or milestone-based schedule.
- Include milestone names, owner/role, expected output, and dependency.
- Include WBS, resource plan, cost/budget baseline, communication plan, risk/change control, and acceptance criteria.
- Avoid placeholders such as `...`, `[TBD]`, `[Assumption]`, `[ความเสี่ยง]`, or empty rows.
- If assumptions are necessary, label them as real assumptions with concrete values, not placeholders.

Acceptance criteria for `risk_register`:

- Output must include risk rows with these fields or obvious equivalents:
  - Risk ID
  - Description
  - Probability or `โอกาส`
  - Impact or `ผลกระทบ`
  - Mitigation or `มาตรการลดความเสี่ยง` / `แผนลดความเสี่ยง`
  - Owner
  - Trigger
  - Status
- Every risk must have a mitigation action, not just a mitigation heading.
- Include project-specific safety risks for Paper Trading Bot:
  - accidental real order placement
  - exchange API secret leakage
  - missing or disabled `PAPER_TRADING_MODE`
  - live exchange calls accidentally enabled
  - model fallback generating invalid requirements/design
  - Docker/local deployment failure
  - portfolio balance simulation mismatch

Acceptance criteria for other PM artifacts:

- `raci_matrix`, `communications_plan`, and `project_status_report` must still satisfy current artifact contracts.
- `project_status_report` should read like a real status artifact based on upstream PM outputs, not a generic template.

### Task 2: Harden BA Prompt Output

Problem:

- Some BA artifacts from fallback models had weak structure and risked failing Markdown/contract validation.
- The Paper Trading Bot scope must stay simulation-only.

Claude should update BA prompts so outputs are structured Markdown with required headings.

Acceptance criteria:

- BRD, SRS, user stories, and data dictionary outputs must use Markdown headings such as `#`, `##`, and tables where appropriate.
- Avoid one-line plain text or JSON-only output for document artifacts.
- Preserve simulation-only safety rules:
  - no real exchange order execution
  - no real API secret collection
  - no leverage/margin/live trading
  - no direct live exchange calls
  - paper balances and simulated fills only
- SRS must include functional requirements, non-functional requirements, security/safety requirements, assumptions, constraints, and traceability to BRD/business goals.
- User stories must be concrete and testable, with acceptance criteria for each story.
- Data dictionary must include field name, type, required/optional, source, validation rule, and description.

### Task 3: Tighten Contracts Without Weakening Quality

Problem:

- Some contract failures may come from missing Thai/English aliases even when the artifact contains the correct meaning.
- Contracts should catch genuinely incomplete output while accepting valid Thai/English wording.

Claude should update `sdlc/shared/artifact_contracts.py` carefully.

Acceptance criteria:

- Add aliases only for real required concepts, especially:
  - schedule/timeline/ตารางเวลา/แผนเวลา
  - mitigation/มาตรการลดความเสี่ยง/แผนลดความเสี่ยง
  - probability/likelihood/โอกาส
  - impact/ผลกระทบ
- Do not remove important required sections just to make tests pass.
- Fix the duplicated `stakeholders` entry in the PM `project_charter` contract.
- Contract failure messages should help the retry model understand exactly what is missing.
- Missing mitigation content in a risk register should still fail.

### Task 4: Improve Model Routing And Payload Handling

Problem from latest test logs:

- Anthropic API returned `401 Unauthorized`.
- Claude CLI hit usage/credit limits.
- Groq returned `413 Payload Too Large`.
- Runtime fell back to `ollama/qwen3`, which produced several contract failures.

Claude should improve routing so provider-limit errors are handled intentionally.

Acceptance criteria:

- Detect or estimate oversized prompts before sending them to Groq when possible.
- Treat Groq `413 Payload Too Large` as a provider payload/routing issue, not as a normal content retry.
- Do not burn repeated retry cycles on a provider that cannot accept the payload.
- Verify both role-aware fallback and role-less/static fallback exclude Groq after a Groq `413`; do not only fix the role-aware branch.
- Preserve existing quota pause behavior for `429`, quota, and credit-limit cases.

## Latest UAT Finding — PM/BA Error Flow Still Not Correct

Date/time checked: 2026-05-20 23:11 +07

Latest active UAT project:

- Project ID: `9C4F3F1D`
- Project scope: `Paper Trading Bot MVP`
- PM2 agents were running during this check.
- This note is read-only observation; do not assume runtime was manually corrected.

### What The User Expected

For PM/BA and every other role:

1. If validation or contract check fails, the error must be visible in Discord and Web App.
2. The error must be recorded in timelog with enough detail to identify:
   - project id
   - role
   - task id
   - task type/title
   - failure type
   - missing sections or validation reason
   - attempt number and cycle-attempt number
   - model/provider used
   - next retry behavior
3. Failed attempts must not generate approval cards.
4. Failed attempts must not overwrite final output.
5. Attempts 1 and 2 can requeue, but users must still see the error.
6. Attempt 3 must stop normal flow and move the task to recovery:
   - `status='paused'`
   - `resume_policy='auto_contract_retry'`
   - `retry_after_at` set around 3-5 minutes later
   - recovery worker later resumes it to `pending`
7. If a later retry passes, the task should continue the normal SDLC flow.
8. If it fails again, repeat pause/recovery indefinitely unless a human cancels or pauses it.
9. If a task has already been approved and a downstream/post-approval hook fails, do not ask for approval again. Notify the error and keep the approved task approved.

### What Actually Happened

Current DB status at check time:

```text
status       count
-----------  -----
approved     7
in_progress  2
pending      185
```

There were no paused tasks:

```text
status='paused' count = 0
```

PM/BA tasks with errors were requeued as `pending`, not paused yet:

```text
9C4F3F1D-PROJECT-PM03  pm  project_plan_excel  pending  attempt_count=2
last_error=Validation failed: Excel output could not be parsed as JSON with 'sheets' key, and contains no markdown table structure.

9C4F3F1D-E001-BA01     ba  brd  pending  attempt_count=1
last_error=Validation failed: Markdown output has no headings and fewer than 2 paragraphs. Content appears to be incomplete.

9C4F3F1D-E002-BA01     ba  brd  pending  attempt_count=1
last_error=Validation failed: Markdown output has no headings and fewer than 2 paragraphs. Content appears to be incomplete.

9C4F3F1D-E003-BA01     ba  brd  pending  attempt_count=1
last_error=Validation failed: Markdown output has no headings and fewer than 2 paragraphs. Content appears to be incomplete.

9C4F3F1D-E004-BA01     ba  brd  pending  attempt_count=1
last_error=Validation failed: Markdown output has no headings and fewer than 2 paragraphs. Content appears to be incomplete.
```

`time_logs` did record failed tasks:

```text
role  task_type  status             n
----  ---------  -----------------  -
ba    sdlc_task  validation_failed  4
pm    sdlc_task  validation_failed  1
```

But the Discord timelog behavior is incomplete:

- For non-exhausted validation/contract failures, `_execute_sdlc_task()` calls `self.timelog.finish(...)`.
- It does not send `self.timelog.build_finish_embed(...)` to `tlog_ch` in the non-exhausted failure branches.
- Result: DB has `validation_failed`, but Discord timelog can look like no error was logged.

Current recovery behavior:

- `sdlc-quota-recovery` is running.
- It polls every 300 seconds.
- It only picks up tasks returned by `storage.list_paused_sdlc_tasks(now)`.
- Because the failed PM/BA tasks are currently `pending`, not `paused`, the recovery worker has nothing to pick up yet.
- This means the recovery design exists, but it only starts after the current code marks attempt 3 as exhausted and calls `_pause_task_for_contract()`.

### Important Flow Clarification

This project should use the dedicated Recovery Worker, not Hermes cron, for contract/validation retry recovery.

Correct mechanism:

- Runtime process: `sdlc-quota-recovery`
- Worker file: `sdlc/agents/recovery_worker.py`
- Storage selector: `storage.list_paused_sdlc_tasks(now)`
- Pause policy: `resume_policy='auto_contract_retry'`
- Resume action: `storage.resume_paused_sdlc_task(task.id)`

Hermes cron should not be responsible for SDLC contract recovery. Hermes cron may still run unrelated scheduled jobs, but do not mix contract recovery into the gold/DNA/obsidian cron path.

### Code Areas To Inspect

Primary:

- `sdlc/shared/base_agent.py`
  - non-exhausted validation failure branch around `validate_artifact(...)`
  - non-exhausted contract failure branch around `validate_role_artifact_contract(...)`
  - `_pause_task_for_contract(...)`
  - success path after artifact promotion and before approval card creation
  - Discord/Web approval hooks
- `sdlc/shared/storage.py`
  - `record_sdlc_task_error(...)`
  - `pause_sdlc_task_for_contract(...)`
  - `resume_paused_sdlc_task(...)`
  - `update_sdlc_task_status(...)`
  - any method that should clear stale `last_error`
- `sdlc/agents/recovery_worker.py`
  - verify it requeues only `auto_contract_retry` and does not require provider cooldown fields for contract failures
- Web App status pages/components that render `last_error`, `attempt_count`, `paused`, `pending`, and `validation_failed` history.

### Required Fixes

#### 1. Send Discord timelog on every failed attempt

In both non-exhausted failure branches:

- validation failed but will retry
- contract failed but will retry

After `self.timelog.finish(...)`, send a timelog embed to `tlog_ch` when available, same as successful tasks and paused tasks.

Also send an additional short detail message if needed:

```text
Contract/Validation Error Detail
Task: <task id/title>
Error: <validation_failed|contract_failed>
Attempt: <cycle-attempt>/<max attempts>
Model: <actual model>
Action: requeued pending, will retry
```

Acceptance criteria:

- Attempt 1/3 and 2/3 failures show in Discord timelog.
- Web App receives an error/retry event.
- DB `time_logs` still records `validation_failed` or `contract_failed`.

#### 2. Make pending-with-error visible in Web App and Discord status

Current behavior stores error state on the task:

- `status='pending'`
- `last_error != ''`
- `attempt_count > 0`

This is technically a retryable state, but it is invisible/confusing to operators.

Required:

- Discord status commands should show pending tasks that have `last_error` as retrying/error state, not normal clean pending.
- Web App should surface `last_error`, `attempt_count`, and `recovery_count` for pending tasks.
- Display should make clear:
  - "will retry"
  - "attempt 1/3" or "attempt 2/3"
  - "not waiting for approval"

Acceptance criteria:

- User can tell which task failed and where it will retry from.
- Pending failed tasks do not look identical to untouched pending tasks.

#### 3. Ensure attempt 3 pauses instead of looping as normal pending

Current code appears intended to do this:

```python
_MAX_AUTO_RETRIES = 2
_fail_count_in_cycle = _fail_count - _recovery_count * (_MAX_AUTO_RETRIES + 1)
_exhausted = _fail_count_in_cycle > _MAX_AUTO_RETRIES
```

With `MAX_AUTO_RETRIES=2`, cycle-attempt 3 should call `_pause_task_for_contract(...)`.

Claude must verify with an integration test that:

- attempt 1 -> `pending`, `last_error`, timelog error, no approval card
- attempt 2 -> `pending`, `last_error`, timelog error, no approval card
- attempt 3 -> `paused`, `resume_policy='auto_contract_retry'`, `retry_after_at` set, `recovery_count += 1`, timelog error, Discord/Web pause notification
- recovery worker after delay -> `pending`, pause fields cleared, claim fields cleared
- attempt 4 after recovery is treated as cycle-attempt 1

#### 4. Clear stale error state after successful retry

Observed:

```text
9C4F3F1D-PROJECT-PM02  pm  project_management_plan  approved  attempt_count=1
last_error=[contract] Missing sections: resources, milestone
approval_msg_id=<present>
```

This is misleading: the task is approved, but still has old `last_error`.

Required:

When an attempt passes validation/contract and is promoted to final output, clear stale runtime error fields:

- `last_error=''`
- `pause_reason=''`
- `pause_provider=''`
- `pause_model=''`
- `retry_after_at=''`
- `paused_at=''`
- `resume_policy=''`
- `claimed_at=''`
- `claimed_by=''`

Do not necessarily reset `attempt_count` or `recovery_count`; those can remain as audit counters unless there is already a clear project convention to reset them.

Acceptance criteria:

- Approved/completed/waiting approval tasks do not show stale error text from failed attempts.
- Web App does not display approved tasks as errored unless there is a real post-approval error event.

#### 5. Do not create approval cards for failed attempts

Reconfirm the existing staging logic:

- failed validation before save -> no output, no approval card
- failed contract after attempt staging -> no final output promotion, no approval card
- only after validation + contract pass should the code post approval card in manual mode

Add/keep tests that assert `approval_msg_id=''` after validation/contract failure.

#### 6. Keep approved tasks approved after post-approval hook error

Already partially fixed, but verify again:

- Human approval sets `status='approved'`.
- `_on_sdlc_task_completed()` error must not revert to pending, waiting approval, or create a new approval card.
- Notify Discord/Web with "Post-Approval Error" and no new approval required.

#### 7. Add tests for Discord/Web notification behavior

Existing tests check storage/recovery. Add tests for notification side effects where feasible:

- non-exhausted validation failure posts output channel warning and timelog embed/detail
- non-exhausted contract failure posts output channel warning and timelog embed/detail
- exhausted validation/contract failure posts paused event to Web bridge
- no approval card on failures
- stale `last_error` cleared on success

### Suggested Test Commands

Run focused tests first:

```bash
cd sdlc
venv/bin/python -m pytest \
  tests/test_hotfix_contract_recovery.py \
  tests/test_hotfix_approvals.py \
  tests/test_hotfix_requirements.py \
  tests/test_artifact_contracts.py \
  tests/test_phase9_model_router.py \
  tests/test_hotfix_pm_ba_routing.py \
  -q
```

Then run Web tests:

```bash
cd webapp
npm test
```

Also check lint, but note that lint was already failing on unrelated Web App issues before this note:

```bash
cd webapp
npm run lint
```

Known lint failures to either fix or document:

- `webapp/app/api/runtime/decisions/route.ts`: `@typescript-eslint/no-explicit-any`
- `webapp/app/cron/page.tsx`: `react-hooks/set-state-in-effect`
- plus several unused variable warnings

### Runtime Verification Checklist After Fix

After code changes and before UAT:

1. Stop PM2 agents.
2. Purge runtime data while preserving exact `#log` only.
3. Start all SDLC agents and Web App.
4. Submit new Paper Trading Bot MVP prompt from Discord.
5. Force or observe one PM/BA validation failure.
6. Confirm Discord output channel shows failure and retry attempt.
7. Confirm Discord timelog channel shows failed attempt.
8. Confirm Web App shows pending-with-error/retrying state.
9. Let task hit attempt 3 if it still fails.
10. Confirm task becomes `paused` with `auto_contract_retry`.
11. Confirm recovery worker resumes it after delay.
12. Confirm no duplicate approval cards and no failed artifact promoted as final output.
- Add or preserve task/web error metadata showing provider, model, and failure reason.
- Prefer a deterministic fallback path for large SDLC artifacts:
  - route to Claude CLI when available, or
  - route to local model with a stricter prompt/contract retry, or
  - compress/summarize context before retrying Groq.
- Do not introduce real network calls in tests.

### Task 5: Tests Claude Must Add Or Update

Claude should add focused regression tests instead of only changing prompts manually.

Required tests:

- PM prompt/template tests:
  - `project_management_plan` prompt requires schedule/timeline wording.
  - `risk_register` prompt requires probability and mitigation wording.
  - PM prompts do not ask for empty placeholders.
- Contract tests:
  - Thai schedule aliases pass for project management plan.
  - Thai mitigation aliases pass for risk register.
  - risk register without mitigation still fails.
  - duplicated `stakeholders` contract entry is removed.
- Model routing tests:
  - oversized Groq payload is classified or routed without repeated normal retries.
  - `429`/quota handling still follows the existing quota pause path.

Expected existing tests must continue to pass.

### Task 6: Add PM Excel Project Plan Deliverable

New user requirement:

- PM still needs a project plan similar to an MS Project schedule, but exported/generated as Excel.
- This file should become the single executable plan that all Agents follow.
- It must include manday estimation per task/role so PM can manage workload and timeline.
- User provided an example workbook:
  - Windows path: `C:\Users\off_p\Desktop\Muti-ai-agent\case-study-excel-project-plan.xlsx`
  - WSL path on this machine: `/mnt/c/Users/off_p/Desktop/Muti-ai-agent/case-study-excel-project-plan.xlsx`
- The example workbook has sheets `Initial`, `Final`, and `About Us`.
- The useful structure from the example is:
  - project title row
  - `Task ID`
  - `Task`
  - `Start Date`
  - `End Date`
  - `Duration (Days)`
  - calendar/Gantt columns showing task span with markers

Claude should inspect the example workbook before implementing this. If using Python, prefer a parser such as `openpyxl` if already available; otherwise it can inspect the `.xlsx` XML structure without adding a runtime dependency unless the project already supports Excel generation that needs one.

Implementation expectation:

- Add a new PM deliverable for an Excel project plan, for example:
  - task type: `project_plan_excel` or another consistent existing naming pattern
  - output file: `project_plan.xlsx`
  - role: `pm`
  - dependency: should run after `project_management_plan`
  - before or alongside `raci_matrix`, `risk_register`, and `communications_plan`
- Do not replace `project_management_plan.docx`; this Excel plan is an additional PM artifact.
- Downstream Agent work should be able to reference this plan where useful.
- If the system has a shared task context builder, include completed `project_plan.xlsx` metadata/content in downstream context in a lightweight way.
- If Excel content is generated through JSON-to-XLSX prompts, add a PM prompt that returns strict JSON only, then use the existing Excel writer path.
- If no Excel writer exists for this task type, add one following existing patterns for `raci_matrix.xlsx`, `user_stories.xlsx`, or other Excel artifacts.

Required workbook sheets:

- `Project Plan`
  - This is the main MS Project-like schedule.
  - Required columns:
    - `Task ID`
    - `WBS`
    - `Phase`
    - `Task`
    - `Description`
    - `Owner Agent`
    - `Start Date`
    - `End Date`
    - `Duration Days`
    - `Manday`
    - `Dependency`
    - `Deliverable`
    - `Status`
  - Include summary phase rows and child task rows.
  - Use WBS numbering such as `1`, `1.1`, `1.2`, `2`, `2.1`.
  - Include every Agent role at least once: CEO, PM, BA, SA, UXUI, DEV, QA, DevOps.
  - Include task dependencies that match the SDLC flow.
  - Duration and manday must be numeric, not placeholders.
  - Status should default to `Planned`.

- `Gantt`
  - Calendar-style timeline view.
  - Rows should align to tasks from `Project Plan`.
  - Columns can be days or weeks depending on project size.
  - Use markers such as `x` or filled cells to show active work dates.
  - The Gantt dates must match Start/End dates from `Project Plan`.

- `Manday Summary`
  - Required columns:
    - `Owner Agent`
    - `Total Tasks`
    - `Total Manday`
    - `First Start`
    - `Last End`
    - `Critical Deliverables`
  - Totals must match the task rows.
  - Include total project manday.

- `Milestones`
  - Required columns:
    - `Milestone ID`
    - `Milestone`
    - `Target Date`
    - `Owner`
    - `Exit Criteria`
    - `Dependency`
  - Must align with `project_management_plan`.

- `Assumptions`
  - Record planning assumptions clearly, such as team capacity, working days, local deployment assumption, and paper-trading safety assumption.

Paper Trading Bot example expectation:

- The Excel plan should include tasks such as:
  - Project brief and approval
  - Project charter
  - Project management plan
  - Excel project plan
  - BRD
  - SRS
  - User stories
  - Architecture
  - API spec
  - Wireframe/design system
  - Frontend implementation
  - Backend implementation
  - Paper trading safety checks
  - QA test cases
  - QA test report
  - Docker/local deployment
  - Deployment guide
  - UAT/release readiness
- Include safety-specific work:
  - verify `PAPER_TRADING_MODE=true`
  - verify no real exchange order path
  - verify no real API secret storage
  - verify simulated balance/fill behavior

Manday rules:

- Use realistic manday values per task, not all `1`.
- Summary phase manday should equal the sum of child tasks.
- A task assigned to one Agent for one full work day = `1.0` manday.
- Partial work is allowed, for example `0.5`.
- For parallel work, calendar duration may be shorter than total manday. Do not confuse duration with manday.
- Add a project total manday.

Acceptance criteria:

- New Excel plan artifact is generated automatically as part of PM project tasks.
- Artifact appears in canonical project output only after validation passes.
- Contract validation or artifact validation checks that required sheets/columns exist.
- Output is not duplicated on retry.
- Every downstream role can still run if this artifact is missing, but should use it when available.
- Tests cover task catalog dependency, prompt structure, Excel JSON/schema generation, and validation failure for missing `Manday` or missing required sheet.

Suggested tests:

- `build_project_tasks()` includes the PM Excel project plan task.
- Excel project plan depends on `project_management_plan`.
- PM prompt for Excel plan includes `Manday`, `Duration Days`, `Dependency`, `Owner Agent`, and Gantt instructions.
- Generated JSON schema contains sheets `Project Plan`, `Gantt`, `Manday Summary`, `Milestones`, `Assumptions`.
- Validator rejects Excel plan output missing `Manday`.
- Validator rejects Excel plan output missing `Project Plan` sheet.
- Existing PM sequencing tests still pass.

### Task 7: Things Claude Must Not Change

- Do not revert attempt staging/promotion in `sdlc/shared/base_agent.py`.
- Do not write failed contract attempts to canonical project output.
- Do not create approval cards for failed attempts.
- Do not require a second human approval after an already-approved artifact has a post-approval hook error.
- Do not change purge behavior back to broad `log` keyword matching.
- Do not preserve `*-timelog` channels during purge unless the user asks.
- Do not restart PM2 agents unless the user asks.
- Do not insert real exchange API integration, real order placement, leverage, margin, or real credentials into Paper Trading Bot prompts.

### Commands Claude Should Run

From repo root:

```bash
cd sdlc
venv/bin/python -m pytest tests/test_hotfix_requirements.py tests/test_hotfix_approvals.py tests/test_artifact_contracts.py tests/test_web_sync.py tests/test_phase9_model_router.py -q
venv/bin/python -m py_compile shared/base_agent.py shared/task_catalog.py shared/artifact_contracts.py shared/model_router.py shared/llm_client.py agents/pm/task_prompts.py agents/ba/task_prompts.py scripts/purge_all_messages.py
```

If Claude changes PM/BA prompt modules, task catalog, Excel generation, or artifact validation, also run any nearby prompt-specific/catalog/Excel tests it creates.

### Claude Deliverable Back To User

Claude should report:

- Exact files changed.
- Prompt improvements made for PM and BA.
- Contract aliases or validation behavior changed.
- Model routing/payload behavior changed.
- PM Excel project plan behavior changed, including generated sheets and manday rules.
- Full test commands and results.
- Whether PM2 agents were started. Expected answer: no, unless the user asked.
- Remaining risks or manual test steps before the user starts a new end-to-end run.

## Additional UAT Findings For Claude

These issues were observed during the fresh UAT run for `Paper Trading Bot MVP` project `CDF4274B`. Claude should treat these as the next implementation batch after the prompt/contract/routing fixes.

### 1. Max-Retry Contract Failure Should Pause And Auto-Recover, Not Permanently Stop

Observed UAT state:

- `CDF4274B-PROJECT-PM01`
- role: `pm`
- task type: `project_charter`
- status: `failed`
- attempt_count: `3`
- last_error: `[contract] Missing sections: stakeholders`
- downstream tasks stayed `pending`, which correctly prevented duplicate downstream output.

Desired behavior:

- When validation/contract failure reaches max attempts, stop immediate execution to prevent duplicate output.
- Do not promote failed attempt artifacts to canonical output.
- Do not create approval cards for failed attempts.
- Notify Discord and Web App clearly.
- Put the task into a recovery queue with a 3-5 minute delay.
- Recovery worker/cron should requeue the task after the delay.
- If the next run passes, resume the normal SDLC flow.
- If it fails again, repeat the same loop: notify, pause, delay, auto-retry.
- This should continue until it passes or a human explicitly pauses/cancels it.

Recommended implementation approach:

- Reuse the existing paused-task recovery mechanism instead of creating a second scheduler.
- On max validation/contract attempts, set task status to `paused` rather than final `failed`.
- Use existing fields:
  - `pause_reason`: include `contract_failed` or `validation_failed`
  - `retry_after_at`: now + configurable delay
  - `paused_at`: now
  - `resume_policy`: use a new policy such as `auto_contract_retry`
  - `pause_provider` / `pause_model`: model/provider that produced the failing output if available
- Add env config:
  - `CONTRACT_RECOVERY_DELAY_SECONDS=300`
  - optional min/max jitter, e.g. 180-300 seconds
- Update `RecoveryWorker.tick()` only if needed so it includes these policy types. Current `resume_paused_sdlc_task()` already moves paused tasks back to `pending`.
- Keep `attempt_count` for audit, but define what happens on resume:
  - Option A: preserve cumulative attempt count and add a separate `recovery_count`
  - Option B: reset `attempt_count` for each recovery cycle but append history to notes/metadata
- Prefer Option A if schema migration is acceptable; otherwise preserve `attempt_count` and avoid using it as a permanent hard stop after recovery pause.

Acceptance criteria:

- A task that fails contract validation 3 times becomes `paused`, not terminal `failed`, when `resume_policy='auto_contract_retry'`.
- Downstream tasks remain blocked while task is paused.
- Recovery worker requeues it to `pending` after 3-5 minutes.
- Role agent picks it up again normally.
- If it passes on a later recovery run, downstream flow continues without duplicate final artifacts.
- Failed attempt artifacts remain only inside `.attempts/...`.
- Web App recovery page shows the paused/retry state.
- Discord receives a clear notification with task id, role, missing sections, attempt count, next retry time, and command hints.

### 2. Error/Retry Must Be Written To Timelog For Every Role

User requirement:

- Every role must write validation/contract errors to timelog.
- Timelog must make it clear which task failed, where it started, and what will happen next.

Required timelog fields/content:

- project_id
- role
- task_id
- task_type
- task title
- error type: `contract_failed`, `validation_failed`, `post_approval_error`, etc.
- missing sections, e.g. `stakeholders`
- attempt number and max attempts, e.g. `3/3`
- provider/model used
- upstream dependency if relevant
- downstream task count blocked if easy to calculate
- next retry time if auto recovery is scheduled
- final action: `paused_for_recovery`, `will_retry`, `blocked`, or `manual_required`

Observed current behavior:

- Timelog had a `contract_failed` row for PM, but not enough detail for user debugging.

Acceptance criteria:

- Any role hitting a validation/contract error writes a detailed timelog entry.
- Discord role timelog channels show the error summary.
- Web App shows the same error in activity/recovery views.
- Error notification does not create duplicate approval cards.

### 3. Discord And Web App Notification Requirements

When a task enters paused auto-recovery due to max validation/contract attempts, notify:

- role output channel
- role timelog channel
- central `#log`
- Web App `agent_activity_logs`
- Web App recovery page / paused tasks API

Message should include:

- task id
- role
- task type/title
- project id/name
- error type
- missing sections or validation reason
- attempt count
- provider/model
- next retry time
- downstream impact
- command hint:
  - `!sdlc_status <project_id>`
  - `!sdlc_paused`
  - `!sdlc_resume <task_id>`
  - `!sdlc_retry <task_id>` if manual retry remains supported

### 4. Preserve Previous Fixes

Do not regress these already-fixed behaviors:

- Failed attempts must not overwrite final output.
- Failed attempts must not create approval cards.
- Approved tasks must not require another approval if post-approval hook fails.
- Discord purge must preserve only exact `#log`, not every channel containing `log`.
- PM task sequencing must remain:
  - `project_management_plan` after `project_charter`
  - `project_plan_excel` after `project_management_plan`
  - PM downstream plan artifacts after the management/excel plan as appropriate
- Groq `413` should not repeatedly route back to the same Groq provider.
- Paper Trading Bot prompts must remain simulation-only.
- PM Excel Project Plan must remain part of PM deliverables.

### 5. Web App Bugs Observed During UAT

AutoRefresh React error:

- File: `webapp/app/workboard/_components/WorkboardClient.tsx`
- Problem: `router.refresh()` is called inside `setCountdown((c) => ...)`.
- React error: `Cannot call startTransition while rendering` and `Cannot update a component (Router) while rendering a different component (AutoRefresh)`.
- Fix: move `router.refresh()` out of the state updater callback. Use a refresh flag/effect or another safe scheduling pattern.

Gateway/heartbeat path error:

- Error: `EACCES: permission denied, mkdir '/home/socket9companylimited'`
- Likely cause: old hardcoded fallback path in Web App config/routes:
  - `webapp/lib/config/env-manager.ts`
  - `webapp/app/api/project-logs/files/route.ts`
  - `webapp/app/api/project-logs/files/download/route.ts`
  - `webapp/app/api/project-logs/files/download-zip/route.ts`
  - `webapp/ecosystem.config.js`
- Fix: use `OUTPUT_BASE_PATH` consistently and remove old `/home/socket9companylimited/...` fallback paths.

### 6. Commands/Tests Claude Should Add Or Run

Add focused tests for:

- max contract attempts transitions task to `paused` with `auto_contract_retry`
- recovery worker requeues paused contract-failed task after retry time
- downstream tasks remain blocked while task is paused
- no canonical output promotion on failed attempts
- no approval card on paused/failed attempt
- timelog contains task id, role, missing section, attempt count, provider/model, next retry
- Web bridge receives paused/recovery event
- AutoRefresh no longer calls router refresh inside state updater

Run at minimum:

```bash
cd sdlc
venv/bin/python -m pytest tests/test_hotfix_approvals.py tests/test_hotfix_requirements.py tests/test_artifact_contracts.py tests/test_phase9_model_router.py tests/test_hotfix_pm_ba_routing.py -q
venv/bin/python -m py_compile shared/base_agent.py shared/storage.py agents/recovery_worker.py shared/task_catalog.py
```

For Web App fixes:

```bash
cd webapp
npm test
npm run lint
```

## Verification Already Run

- `venv/bin/python -m pytest tests/test_hotfix_approvals.py -q` → 13 passed
- `venv/bin/python -m pytest tests/test_artifact_contracts.py tests/test_web_sync.py -q` → 135 passed
- `venv/bin/python -m pytest tests/test_hotfix_requirements.py tests/test_hotfix_approvals.py tests/test_runtime_correctness.py -q` → 64 passed
- `venv/bin/python -m py_compile shared/base_agent.py shared/task_catalog.py scripts/purge_all_messages.py` → pass

## Cleanup Performed

SDLC DB cleared:

- `projects`
- `epics`
- `sdlc_tasks`
- `role_tasks`
- `llm_usage`
- `time_logs`
- `provider_cooldowns`

Web app DB cleared:

- `agent_activity_logs`
- `approval_items`
- `audit_events`
- `project_hot_cache`
- `task_artifacts`
- `password_reset_tokens`

Outputs cleared:

- `sdlc/outputs/projects/*`

Discord cleared:

- All accessible SDLC channels except `#log`.
- Timelog channels were cleared after the purge script fix.
