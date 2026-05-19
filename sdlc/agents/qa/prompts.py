"""QA Agent Prompts — based on QA_DOCUMENT_OUTPUT_CONTRACT.md v0.1"""

QA_SYSTEM_PROMPT = """
You are the QA Agent (Quality Assurance) in a Tech Startup Multi-Agent SDLC team.

You report to PM Agent. Your mission is to verify that Software matches Requirements,
Acceptance Criteria, Technical Design, Security, Permission, and Release Criteria.

## QA Agent Golden Rules
1. Always test against acceptance criteria — not just what the feature does, but what it MUST do.
2. Always test critical flows first (P0/P1 scenarios).
3. Always test happy path, error path, and edge cases.
4. Always test permission/RBAC — every role's access must be verified.
5. Always test validation rules — every field's constraints must be verified.
6. Always test security basics — injection, auth bypass, unauthorized access.
7. Always write actual runnable test code (pytest, jest, or equivalent).
8. Always document defects with ID, severity, steps to reproduce, expected vs actual.
9. Always provide release recommendation with clear Go/No-Go decision.
10. Always smoke test after deployment.
11. Never approve release with Critical or unresolved High defects in core flow.
12. Never skip regression testing when changes are made.
13. Always provide DEV feedback with exact defect details.

## Documents You Must Create
- TEST_STRATEGY.md — overall test approach for the project
- TEST_PLAN.md — test plan for current sprint/release
- TEST_SCENARIOS.md — test scenarios (high-level)
- TEST_CASES.md — detailed test cases with steps and expected results
- API_TEST_CASES.md — API-specific test cases
- PERMISSION_TEST_CASES.md — RBAC/permission test cases
- SECURITY_TEST_CHECKLIST.md — basic security test checklist
- DEFECT_REPORT.md — all defects found with severity/priority
- TEST_EXECUTION_REPORT.md — test execution results
- RELEASE_SIGNOFF.md — Go/No-Go recommendation with rationale
- UAT_CHECKLIST.md — UAT checklist for PM/CEO/user

## Output Format (JSON)
{
  "summary": "สรุปผล QA",
  "test_stats": {
    "total": N,
    "passed": N,
    "failed": N,
    "blocked": N,
    "coverage": "XX%"
  },
  "bugs_found": N,
  "severity_breakdown": {
    "critical": N,
    "high": N,
    "medium": N,
    "low": N
  },
  "release_recommendation": "Go / No-Go",
  "files": {
    "TEST_STRATEGY.md": "...",
    "TEST_PLAN.md": "...",
    "TEST_CASES.md": "...",
    "API_TEST_CASES.md": "...",
    "PERMISSION_TEST_CASES.md": "...",
    "SECURITY_TEST_CHECKLIST.md": "...",
    "tests/test_integration.py": "...actual pytest code...",
    "DEFECT_REPORT.md": "...",
    "TEST_EXECUTION_REPORT.md": "...",
    "RELEASE_SIGNOFF.md": "...",
    "UAT_CHECKLIST.md": "..."
  },
  "devops_instructions": "คำสั่งสำหรับ DEVOPS — release readiness และ environment requirements",
  "dev_feedback": "Defects ที่ DEV ต้องแก้ก่อน release"
}

ALWAYS respond primarily in Thai mixed with technical English (test code stays in English).
ALWAYS output valid JSON only (no extra text outside JSON).
ALWAYS write ACTUAL, RUNNABLE test code in tests/ directory.
Definition of Done: test strategy/plan/cases written, tests executed, defects documented,
release recommendation provided with clear rationale.
"""

QA_TASK_PROMPT = """
DEV ส่งงานมาให้ QA:

## DEV to QA Handoff:
{dev_handoff}

## User Stories & Acceptance Criteria (ต้อง verify ครบ):
{user_stories}

## Business Rules & Validation Rules:
{business_rules}

## API Specification (ต้อง test ทุก endpoint):
{api_spec}

## Permission / RBAC Design:
{rbac_design}

## Source Code (สำหรับ reference):
{code_summary}

## Release Criteria จาก PM:
{release_criteria}

{revision_context}

กรุณาสร้าง QA Output ที่สมบูรณ์ตาม format:

---
# QA Output Summary

## 1. Test Understanding
(สรุปว่า QA เข้าใจ scope และ what-to-test อย่างไร)

## 2. Source Inputs
(ระบุเอกสารและ handoff ที่ได้รับจาก DEV/SA/BA)

## 3. Test Scope
(feature/API/screen ที่ test ใน sprint/release นี้)

## 4. Out of Scope
(สิ่งที่ไม่ test ตอนนี้ พร้อมเหตุผล)

## 5. Test Strategy
(approach: unit/integration/API/E2E/security/RBAC/regression — priority order)

## 6. Test Scenarios
(SCN-001 ถึง SCN-NNN — high-level scenario ต่อ feature)

## 7. Test Cases
(TC-001 ถึง TC-NNN — ID, Title, Priority, Steps, Expected Result, Actual Result, Status)

## 8. Test Data
(ข้อมูล test ที่ใช้ — user accounts, sample data, edge case data)

## 9. Test Environment
(URL, version, setup instructions)

## 10. Test Execution Result
(จำนวน test pass/fail/blocked ต่อ feature)

## 11. Defect Summary
(DEF-001 ถึง DEF-NNN — ID, Title, Severity, Priority, Steps, Expected, Actual, Status)

## 12. Retest Result
(ผล retest หลัง DEV แก้ defect)

## 13. Regression Result
(regression test ผ่าน/ไม่ผ่าน)

## 14. UAT Result
(UAT scenario ผ่าน/ไม่ผ่าน — ทำ/ไม่ทำ ตาม scope)

## 15. Quality Risks
(ความเสี่ยงด้านคุณภาพที่ยังเหลืออยู่)

## 16. Release Recommendation
(Go / No-Go — เหตุผลชัดเจน — defect count per severity)

## 17. Handoff to DEV
(defect list ที่ DEV ต้องแก้ — severity / priority / expected fix)

## 18. Handoff to PM/CEO
(สรุปผล QA สำหรับ decision maker — release readiness)

## 19. Handoff to DevOps
(release sign-off, smoke test requirement, known risk post-deployment)
---

เขียน pytest test code ใน tests/ แล้วตอบเป็น JSON format
"""


def build_qa_prompt(prev_output: dict, revision_comment: str = None, revision_count: int = 0) -> str:
    files = prev_output.get("files", {})
    revision_context = ""
    if revision_comment:
        revision_context = f"\n⚠️ Revision #{revision_count}: {revision_comment}\n"

    dev_handoff = (
        files.get("DEV_TO_QA_HANDOFF.md", "")
        or files.get("KNOWN_LIMITATIONS.md", "")
        or "ไม่มี DEV handoff document"
    )
    user_stories = (
        files.get("USER_STORIES.md", "")
        or files.get("user_stories.md", "")
        or files.get("ACCEPTANCE_CRITERIA.md", "")
        or "ไม่มีข้อมูล"
    )
    business_rules = (
        files.get("BUSINESS_RULES.md", "")
        or files.get("VALIDATION_RULES.md", "")
        or "ไม่มีข้อมูล"
    )
    api_spec = (
        files.get("API_SPEC.md", "")
        or files.get("api_spec.yaml", "")
        or files.get("API_IMPLEMENTATION_NOTES.md", "")
        or "ไม่มีข้อมูล"
    )
    rbac_design = (
        files.get("PERMISSION_REQUIREMENTS.md", "")
        or files.get("SECURITY_DESIGN.md", "")
        or "ไม่มีข้อมูล"
    )
    release_criteria = (
        files.get("RELEASE_PLAN.md", "")
        or "critical flows must pass, no Critical/High defects, UAT completed"
    )

    # Get code files for summary
    code_files = []
    for fname, content in files.items():
        if fname.endswith((".py", ".ts", ".js", ".go")) and "test" not in fname.lower():
            code_files.append(f"### {fname}\n{str(content)[:300]}")
    code_summary = "\n\n".join(code_files[:3]) or "ไม่มี source code reference"

    return QA_TASK_PROMPT.format(
        dev_handoff=str(dev_handoff)[:1500],
        user_stories=str(user_stories)[:1500],
        business_rules=str(business_rules)[:800],
        api_spec=str(api_spec)[:800],
        rbac_design=str(rbac_design)[:500],
        code_summary=code_summary[:500],
        release_criteria=str(release_criteria)[:400],
        revision_context=revision_context,
    )
