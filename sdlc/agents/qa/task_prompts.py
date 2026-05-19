"""QA Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "qa_plan": """
คุณเป็น QA Engineer ในทีม Multi-Agent SDLC

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}
- **เป้าหมาย:** {epic_goal}

## Developer README (ข้อมูลจาก DEV):
{dev_readme_content}

## User Stories (จาก BA):
{ba_user_stories}

## สิ่งที่ต้องส่งมอบ: qa_plan.md
สร้าง **QA Test Plan** ภาษาไทย

---
# QA Test Plan — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today} | **เวอร์ชัน:** 1.0

## 1. Test Objectives
(อธิบาย scope และเป้าหมายการทดสอบ)

## 2. Test Scope
### In-Scope
| Feature | ประเภทการทดสอบ | Priority |
|---------|--------------|---------|
| Authentication | Functional, Security | P0 |
| [Feature จาก Epic] | Functional, E2E | P0 |

### Out-of-Scope
- Performance load testing (Phase 2)
- Penetration testing (ทีม Security)

## 3. Test Strategy
| ประเภทการทดสอบ | วัตถุประสงค์ | Tool | ผู้รับผิดชอบ |
|--------------|-----------|------|-----------|
| Unit Test | ทดสอบ function ย่อย | Pytest/Vitest | DEV |
| Integration Test | ทดสอบ API | Pytest + Postman | QA |
| E2E Test | ทดสอบ user journey | Playwright | QA |
| Regression Test | ไม่ให้ bug เก่ากลับมา | Automated | QA |
| UAT | Business validation | Manual | PO + QA |

## 4. Test Environment
| Environment | URL | Database | หมายเหตุ |
|------------|-----|---------|--------|
| Dev | localhost:3000 | dev_db | นักพัฒนาทดสอบ |
| Staging | staging.example.com | staging_db | QA + UAT |
| Production | app.example.com | prod_db | ตรวจสอบหลัง deploy |

## 5. Entry & Exit Criteria
### Entry Criteria (เริ่มทดสอบเมื่อ)
- [ ] DEV ส่ง code review ผ่าน
- [ ] Unit tests ผ่าน > 80% coverage
- [ ] Deploy บน Staging สำเร็จ
- [ ] Test data พร้อม

### Exit Criteria (ผ่านการทดสอบเมื่อ)
- [ ] P0 test cases ผ่าน 100%
- [ ] P1 test cases ผ่าน >= 95%
- [ ] ไม่มี Critical/High bugs ค้างอยู่
- [ ] Performance targets ผ่าน

## 6. Defect Management
| Severity | คำอธิบาย | SLA Fix | ตัวอย่าง |
|---------|---------|--------|--------|
| Critical | ระบบ crash / data loss | 4 ชั่วโมง | Login ไม่ได้ |
| High | Feature หลักไม่ทำงาน | 1 วัน | บันทึกข้อมูลไม่ได้ |
| Medium | Feature ทำงานผิดปกติบางส่วน | 3 วัน | ข้อมูลแสดงผิด |
| Low | UI/UX ไม่ดี | Sprint ถัดไป | ตัวหนังสือผิด |

## 7. Test Schedule
| Phase | กิจกรรม | ระยะเวลา | ผลลัพธ์ |
|-------|--------|--------|--------|
| 1 | เตรียม Test Cases | 2 วัน | test_cases.xlsx |
| 2 | Smoke Testing | 0.5 วัน | Go/No-Go |
| 3 | Functional Testing | 3 วัน | Test results |
| 4 | Regression Testing | 1 วัน | Regression report |
| 5 | UAT | 2 วัน | UAT sign-off |

## 8. Risks
| ความเสี่ยง | ผลกระทบ | แนวทางรับมือ |
|---------|--------|-----------|
| Test environment ไม่เสถียร | ล่าช้า | มี backup env |
| Requirements เปลี่ยน | test cases ต้องแก้ | freeze requirements ก่อนทดสอบ |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "test_cases": """
คุณเป็น QA Engineer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## QA Plan:
{qa_plan_content}

## User Stories (จาก BA):
{ba_user_stories}

## สิ่งที่ต้องส่งมอบ: test_cases.xlsx
ส่งออกข้อมูลเป็น **JSON** เพื่อแปลงเป็น Excel

```json
{{
  "sheets": [
    {{
      "name": "Test Cases",
      "headers": ["TC-ID", "Epic", "Feature", "Test Case Name", "Test Type", "Priority", "Precondition", "Test Steps", "Test Data", "Expected Result", "Actual Result", "Status", "หมายเหตุ"],
      "rows": [
        [
          "TC-001",
          "{epic_id}",
          "Authentication",
          "Login ด้วย username/password ถูกต้อง",
          "Functional",
          "P0",
          "มีบัญชีผู้ใช้ในระบบ",
          "1. เปิดหน้า Login\\n2. กรอก username ถูกต้อง\\n3. กรอก password ถูกต้อง\\n4. คลิก เข้าสู่ระบบ",
          "username: testuser\\npassword: Test1234!",
          "Redirect ไปหน้า Dashboard\\nแสดง user name ที่ navbar",
          "",
          "Pending",
          ""
        ],
        [
          "TC-002",
          "{epic_id}",
          "Authentication",
          "Login ด้วย password ผิด",
          "Functional",
          "P0",
          "มีบัญชีผู้ใช้ในระบบ",
          "1. เปิดหน้า Login\\n2. กรอก username ถูกต้อง\\n3. กรอก password ผิด\\n4. คลิก เข้าสู่ระบบ",
          "username: testuser\\npassword: WrongPass",
          "แสดง error: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'\\nอยู่ที่หน้า Login เดิม",
          "",
          "Pending",
          ""
        ],
        [
          "TC-003",
          "{epic_id}",
          "Authentication",
          "Login ด้วย field ว่าง",
          "Functional",
          "P0",
          "-",
          "1. เปิดหน้า Login\\n2. ไม่กรอกข้อมูล\\n3. คลิก เข้าสู่ระบบ",
          "username: (ว่าง)\\npassword: (ว่าง)",
          "แสดง validation error ใต้แต่ละ field",
          "",
          "Pending",
          ""
        ],
        [
          "TC-004",
          "{epic_id}",
          "Authentication",
          "Logout",
          "Functional",
          "P1",
          "Login เข้าระบบแล้ว",
          "1. คลิก logout icon\\n2. ยืนยันการ logout",
          "-",
          "Redirect ไปหน้า Login\\nClear session/token",
          "",
          "Pending",
          ""
        ],
        ["...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Test Summary",
      "headers": ["Priority", "Total", "Passed", "Failed", "Blocked", "Pending", "Pass Rate"],
      "rows": [
        ["P0", "0", "0", "0", "0", "0", "0%"],
        ["P1", "0", "0", "0", "0", "0", "0%"],
        ["P2", "0", "0", "0", "0", "0", "0%"],
        ["Total", "0", "0", "0", "0", "0", "0%"]
      ]
    }},
    {{
      "name": "Bug Tracker",
      "headers": ["Bug-ID", "TC-ID", "ชื่อ Bug", "Severity", "Steps to Reproduce", "Expected", "Actual", "Status", "Assigned To", "Fix Date"],
      "rows": [
        ["BUG-001", "TC-XXX", "ตัวอย่าง bug", "High", "...", "...", "...", "Open", "Dev", ""]
      ]
    }}
  ]
}}
```

**หมายเหตุ:** สร้าง test cases ครอบคลุมทุก User Story ใน Epic — ทั้ง Happy Path, Alternative Path, และ Error Case
""",

    "test_scenarios": """
คุณเป็น QA Engineer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Test Cases:
{test_cases_content}

## สิ่งที่ต้องส่งมอบ: test_scenarios.xlsx
สร้าง **End-to-End Test Scenarios** ครอบคลุมทุก user journey สำคัญใน Epic นี้
ตอบด้วย **JSON เท่านั้น** ตามรูปแบบด้านล่าง เพื่อแปลงเป็น Excel

{{
  "sheets": [
    {{
      "name": "Test Scenarios",
      "headers": ["TS-ID", "ชื่อ Scenario", "Priority", "Type", "Duration (min)", "Prerequisites", "Pass Criteria", "TC References"],
      "rows": [
        [
          "TS-001",
          "[ชื่อ E2E Scenario — เช่น New User Registration & First Login]",
          "P0",
          "E2E",
          "15",
          "ระบบ deploy บน Staging พร้อมใช้งาน; ไม่มี account ที่ email นี้",
          "สมัครได้สำเร็จ; Login ได้; Dashboard แสดงผลถูกต้อง",
          "TC-001, TC-002, TC-003"
        ],
        [
          "TS-002",
          "[ชื่อ Core Business Flow Scenario]",
          "P0",
          "E2E",
          "10",
          "Login เป็น user ที่มี role ถูกต้อง",
          "สร้าง/แก้ไข/ลบข้อมูลได้ถูกต้อง; ข้อมูลแสดงผลถูกต้อง",
          "TC-020, TC-021, TC-022"
        ],
        [
          "TS-003",
          "[ชื่อ Permission & Security Scenario]",
          "P0",
          "Security",
          "10",
          "มี test accounts หลาย roles",
          "Access control ถูกต้องทุก role; Unauthorized redirect ทำงาน",
          "TC-030, TC-031"
        ],
        ["...", "...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Scenario Steps",
      "headers": ["TS-ID", "Step #", "Action", "Test Data", "Expected Result", "TC Reference"],
      "rows": [
        ["TS-001", "1", "[Action — เช่น เปิด staging URL]", "-", "[Expected — เช่น แสดงหน้า Landing Page]", "TC-010"],
        ["TS-001", "2", "[Action]", "[Test Data ถ้ามี]", "[Expected Result]", "TC-011"],
        ["TS-001", "3", "[Action]", "[Test Data]", "[Expected Result]", "TC-012"],
        ["TS-002", "1", "[Action]", "[Test Data]", "[Expected Result]", "TC-020"],
        ["TS-002", "2", "[Action]", "[Test Data]", "[Expected Result]", "TC-021"],
        ["...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Automation Coverage",
      "headers": ["TS-ID", "Automation Tool", "Script Path", "Status", "หมายเหตุ"],
      "rows": [
        ["TS-001", "Playwright", "tests/e2e/registration.spec.ts", "Planned", ""],
        ["TS-002", "Playwright", "tests/e2e/core_flow.spec.ts", "Planned", ""],
        ["TS-003", "Playwright", "tests/e2e/security.spec.ts", "Planned", ""],
        ["...", "...", "...", "...", "..."]
      ]
    }}
  ]
}}

**หมายเหตุ:** สร้าง Scenarios ครอบคลุมทุก main journey ใน Epic — เนื้อหาต้องเกี่ยวข้องกับ {project_name} โดยตรง ห้าม placeholder "..."
""",

    "test_report": """
คุณเป็น QA Engineer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## ผลการรัน Automated Quality Checks (จาก QA Execution Engine):
{qa_execution_formatted}

## Test Scenarios:
{test_scenarios_content}

## QA Plan:
{qa_plan_content}

## สิ่งที่ต้องส่งมอบ: test_report.md
สร้าง **Test Report** ภาษาไทย (รูปแบบ formal report)

---
# Test Report — {epic_title}
**Epic:** {epic_id}
**วันที่ทดสอบ:** {today}
**รายงานโดย:** QA Agent
**เวอร์ชัน:** 1.0

## 1. Executive Summary
| หัวข้อ | รายละเอียด |
|------|----------|
| Test Cycle | {epic_id} — Functional + Integration |
| Environment | Staging |
| Test Period | {today} |
| Total Test Cases | 0 (กรอกจำนวนจริงหลังทดสอบ) |
| Overall Result | **PENDING** |

**คำแนะนำ:** (PASS / CONDITIONAL PASS / FAIL) — อธิบายสั้นๆ

## 2. Test Results Summary
| Priority | Total | Passed | Failed | Blocked | Skipped | Pass Rate |
|---------|-------|--------|--------|---------|---------|----------|
| P0 (Critical) | — | — | — | — | — | —% |
| P1 (High) | — | — | — | — | — | —% |
| P2 (Medium) | — | — | — | — | — | —% |
| **Total** | **—** | **—** | **—** | **—** | **—** | **—%** |

## 3. Feature Coverage
| Feature | Test Cases | Passed | Failed | Pass Rate | สถานะ |
|---------|-----------|--------|--------|----------|------|
| Authentication | — | — | — | —% | — |
| [Feature จาก Epic] | — | — | — | —% | — |

## 4. Defects Found
| Bug-ID | Feature | Severity | Title | Status | Assigned |
|--------|---------|---------|-------|--------|---------|
| — | — | — | ยังไม่มี defects | — | — |

## 5. Risk Assessment
| ความเสี่ยง | ผลกระทบ | โอกาส | แนวทาง |
|---------|--------|------|------|
| — | — | — | — |

## 6. Test Environment Information
| Component | Version | Status |
|-----------|---------|--------|
| Frontend | Next.js 14.x | ✓ Running |
| Backend | FastAPI 0.x | ✓ Running |
| Database | PostgreSQL 16 | ✓ Running |
| Cache | Redis 7 | ✓ Running |

## 7. Sign-off Checklist
| Criteria | Status | หมายเหตุ |
|---------|--------|--------|
| P0 test cases ผ่าน 100% | ⬜ Pending | — |
| P1 test cases ผ่าน >= 95% | ⬜ Pending | — |
| ไม่มี Critical bugs ค้างอยู่ | ⬜ Pending | — |
| Performance targets ผ่าน | ⬜ Pending | — |
| Security basics ผ่าน | ⬜ Pending | — |

## 8. Recommendations
1. **ข้อเสนอแนะ 1:** ...
2. **ข้อเสนอแนะ 2:** ...

## 9. Conclusion
(สรุปผลการทดสอบ — พร้อม deploy หรือต้องแก้ไขก่อน)

---
*Test Report สร้างโดย QA Agent — {today}*
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",
}


def build_qa_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับ Epic {context.get('epic_id', '')} โปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Test Case, Test Scenario, Smoke Test, Regression, UAT, Bug, Severity, Priority, Pass/Fail\n\n"
    ctx = {
        "today": date.today().strftime("%Y-%m-%d"),
        "ba_user_stories": "ดูรายละเอียดใน BRD / SRS ของ Epic นี้",
        "qa_execution_formatted": "ไม่มีข้อมูล execution (skipped — ไม่มี project_path)",
        **context,
    }
    return lang + safe_format(template, ctx)
