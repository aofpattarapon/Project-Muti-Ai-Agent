"""PM Task Prompts — 1 task = 1 file ภาษาไทย"""

PROMPTS = {
    "project_charter": """
คุณเป็น PM Agent

## ข้อมูลโปรเจค:
{project_brief}

## สิ่งที่ต้องส่งมอบ: project_charter.md
สร้างเฉพาะ **Project Charter** เอกสารเดียว ภาษาไทย

---
# Project Charter — {project_name}
**เวอร์ชัน:** 1.0 | **วันที่:** {today} | **Project Manager:** PM Agent

## 1. บทสรุปผู้บริหาร
...

## 2. วัตถุประสงค์โครงการ
### เหตุผลทางธุรกิจ
...
### เป้าหมายและเกณฑ์ความสำเร็จ
| เป้าหมาย | เกณฑ์วัด | เป้าหมาย |
|---------|---------|---------|
| ... | ... | ... |

## 3. ข้อกำหนดเบื้องต้น
...

## 4. ข้อจำกัด
| ประเภท | รายละเอียด |
|-------|----------|
| เวลา | ... |
| งบประมาณ | ... |

## 5. สมมติฐาน
1. ...

## 6. ขอบเขตเบื้องต้น
**ใน Scope:** ...
**นอก Scope:** ...

## 7. ความเสี่ยงหลัก
| ความเสี่ยง | ผลกระทบ | แนวทาง |
|----------|--------|-------|
| ... | สูง/กลาง/ต่ำ | ... |

## 8. Deliverables
| Deliverable | ผู้รับผิดชอบ | กำหนดส่ง |
|------------|-----------|---------|
| ... | ... | สัปดาห์ที่ ... |

## 9. Milestones
| Milestone | วันที่ | เกณฑ์ |
|----------|------|------|
| Kick-off | ... | ... |
| MVP Release | ... | ... |

## 10. งบประมาณสรุป
| หมวด | จำนวน (บาท) |
|-----|-----------|
| Development | ... |
| Infrastructure | ... |
| **รวม** | **...** |

## 11. ผู้อนุมัติโครงการ
| ชื่อ | ตำแหน่ง | ลายมือชื่อ | วันที่ |
|-----|--------|---------|------|
| ... | CEO | | |
---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจคนี้โดยตรง ห้ามใส่ "..." หรือข้อความทั่วไปที่ไม่เกี่ยวข้อง
""",

    "project_management_plan": """
คุณเป็น PM Agent

## Project Charter:
{project_charter_content}

## สิ่งที่ต้องส่งมอบ: project_management_plan.md
สร้างเฉพาะ **แผนบริหารโครงการ** ภาษาไทย

---
# แผนบริหารโครงการ — {project_name}
**เวอร์ชัน:** 1.0 | **วันที่:** {today}

## 1. แนวทางบริหารโครงการ
...

## 2. ขอบเขตโครงการ
...

## 3. Milestone List
| # | Milestone | วันที่ | เกณฑ์เสร็จ | สถานะ |
|---|----------|------|----------|------|
| 1 | Kick-off | ... | ... | Planned |

## 4. Work Breakdown Structure (WBS)
```
{project_name}
├── Phase 1: Requirements & Design
│   ├── 1.1 CEO — Project Brief + Epics
│   ├── 1.2 PM — Project Charter + Plan
│   ├── 1.3 BA — BRD + User Stories
│   └── 1.4 SA — Architecture + API Spec
├── Phase 2: Development
│   ├── 2.1 UXUI — Wireframe + Design System
│   ├── 2.2 DEV — Frontend Implementation
│   └── 2.3 DEV — Backend Implementation
└── Phase 3: QA & Release
    ├── 3.1 QA — Test Cases + Test Report
    └── 3.2 DevOps — CI/CD + Deployment
```

## 5. แผนบริหารการเปลี่ยนแปลง
**ขั้นตอน:** ขอเปลี่ยน → PM ประเมินผลกระทบ → CEO อนุมัติ → แจ้งทีม

## 6. แผนการสื่อสาร
| ช่องทาง | ความถี่ | ผู้รับ | เนื้อหา |
|--------|--------|------|-------|
| Discord | Real-time | ทีม | งาน + อนุมัติ |
| Status Report | รายสัปดาห์ | CEO | ความคืบหน้า |

## 7. แผนบริหารต้นทุน
| หมวด | งบประมาณ | ใช้จริง | คงเหลือ |
|-----|---------|--------|--------|
| LLM API | ... | 0 | ... |
| Infrastructure | ... | 0 | ... |

## 8. แผนบริหารความเสี่ยง
| Risk ID | ความเสี่ยง | ผลกระทบ | โอกาส | แผนรับมือ |
|--------|----------|--------|------|---------|
| R-001 | ... | H/M/L | H/M/L | ... |

## 9. Risk Register
(ดูรายละเอียดใน risk_register.md)

## 10. แผนบริหารทรัพยากร
| Role | จำนวน | ช่วงเวลา | ความรับผิดชอบ |
|-----|------|---------|------------|
| CEO Agent | 1 | Phase 1 | กำหนดทิศทาง |
| PM Agent | 1 | ตลอดโปรเจค | บริหารโครงการ |

## 11. Resource Calendar
| Role | สัปดาห์ 1 | สัปดาห์ 2 | ... |
|-----|---------|---------|-----|
| BA | Requirements | Review | ... |

## 12. Cost Baseline
งบประมาณรวม: {budget} บาท

## 13. Quality Baseline
- Code Coverage ≥ 80%
- Critical Bug = 0 ก่อน Release
- UAT Passed ≥ 95%

## 14. การอนุมัติ
ผู้อนุมัติ: CEO Agent | วันที่: {today}
---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจคนี้โดยตรง ห้ามใส่ "..." หรือข้อความทั่วไปที่ไม่เกี่ยวข้อง
""",

    "raci_matrix": """
คุณเป็น PM Agent

## ข้อมูลโปรเจค:
{project_brief}

## Epics:
{epics_content}

## สิ่งที่ต้องส่งมอบ: raci_matrix.xlsx
สร้าง RACI Matrix ในรูปแบบ JSON สำหรับสร้าง Excel ภาษาไทย

RACI: R=Responsible (ผู้ทำ), A=Accountable (ผู้รับผิดชอบ), C=Consulted (ผู้ให้คำปรึกษา), I=Informed (ผู้รับทราบ)

ตอบด้วย JSON เท่านั้น ตามรูปแบบ:
{{
  "sheets": [
    {{
      "name": "RACI Matrix",
      "headers": ["กิจกรรม/Deliverable", "CEO", "PM", "BA", "SA", "UXUI", "DEV", "QA", "DevOps", "หมายเหตุ"],
      "rows": [
        ["Project Brief", "R", "A", "C", "", "", "", "", "", ""],
        ["Epics", "R", "A", "C", "", "", "", "", "", ""],
        ["Project Charter", "I", "R/A", "C", "C", "", "", "", "", ""],
        ["BRD", "I", "A", "R", "C", "C", "", "", "", ""],
        ["User Stories", "I", "A", "R", "C", "C", "", "", "", ""],
        ["Architecture", "I", "A", "C", "R", "C", "C", "", "", ""],
        ["API Spec", "I", "A", "C", "R", "", "C", "", "", ""],
        ["Wireframe", "I", "A", "C", "C", "R", "C", "", "", ""],
        ["Frontend Code", "I", "A", "", "C", "C", "R", "", "", ""],
        ["Backend Code", "I", "A", "", "C", "", "R", "", "", ""],
        ["Test Cases", "I", "A", "C", "", "", "", "R", "", ""],
        ["Test Report", "I", "A", "I", "", "", "C", "R", "", ""],
        ["Dockerfile", "I", "A", "", "C", "", "C", "", "R", ""],
        ["CI/CD Pipeline", "I", "A", "", "C", "", "C", "C", "R", ""],
        ["Deployment Guide", "I", "A", "", "C", "", "C", "I", "R", ""]
      ]
    }},
    {{
      "name": "Legend",
      "headers": ["ตัวย่อ", "ความหมาย", "คำอธิบาย"],
      "rows": [
        ["R", "Responsible", "ผู้ลงมือทำงาน"],
        ["A", "Accountable", "ผู้รับผิดชอบผลลัพธ์สุดท้าย"],
        ["C", "Consulted", "ผู้ให้คำปรึกษา/ข้อมูล"],
        ["I", "Informed", "ผู้รับทราบความคืบหน้า"]
      ]
    }}
  ]
}}
""",

    "risk_register": """
คุณเป็น PM Agent

## ข้อมูลโปรเจค:
{project_brief}

## สิ่งที่ต้องส่งมอบ: risk_register.md
สร้าง **Risk Register** ภาษาไทย

---
# Risk Register — {project_name}
**วันที่อัปเดต:** {today}

## 1. บทนำ
...

## 2. ความเสี่ยง 3 อันดับแรก
1. **[ความเสี่ยง 1]** — ผลกระทบ: สูง
2. **[ความเสี่ยง 2]** — ผลกระทบ: สูง
3. **[ความเสี่ยง 3]** — ผลกระทบ: กลาง

## 3. แนวทางบริหารความเสี่ยง
...

## 4. Risk Register ละเอียด
| Risk ID | หมวดหมู่ | ความเสี่ยง | ผลกระทบ (H/M/L) | โอกาส (H/M/L) | คะแนน | แผนลดความเสี่ยง | เจ้าของ | สถานะ |
|--------|--------|----------|--------------|------------|------|--------------|--------|------|
| RISK-001 | Technical | ... | H | M | 6 | ... | SA | Open |
| RISK-002 | Schedule | ... | M | H | 6 | ... | PM | Open |
| RISK-003 | Budget | ... | H | L | 4 | ... | CEO | Open |

*(คะแนน = ผลกระทบ × โอกาส: H=3, M=2, L=1)*

## 5. การระบุความเสี่ยง
...

## 6. การประเมินและจัดลำดับ
(Heat Map: Risk Score ≥ 6 = สูง, 3-5 = กลาง, 1-2 = ต่ำ)

## 7. การติดตามความเสี่ยง
ทบทวนทุกสัปดาห์ใน Status Report

## 8. แผนลดความเสี่ยง
| Risk ID | กลยุทธ์ | แผนปฏิบัติ | กำหนดเวลา |
|--------|--------|----------|---------|
| RISK-001 | Mitigate | ... | สัปดาห์ที่ 2 |
---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจคนี้โดยตรง ห้ามใส่ "..." หรือข้อความทั่วไปที่ไม่เกี่ยวข้อง
""",

    "communications_plan": """
คุณเป็น PM Agent

## ข้อมูลโปรเจค:
{project_brief}

## สิ่งที่ต้องส่งมอบ: communications_plan.md

---
# Communications Management Plan — {project_name}
**วันที่:** {today}

## 1. แนวทางการสื่อสาร
ใช้ Discord เป็นช่องทางหลัก โดยแต่ละ Agent มี channel เฉพาะ

## 2. ข้อจำกัดการสื่อสาร
...

## 3. ความต้องการการสื่อสารของผู้มีส่วนได้เสีย
| ผู้มีส่วนได้เสีย | ข้อมูลที่ต้องการ | ความถี่ | ช่องทาง |
|--------------|-------------|--------|-------|
| CEO/Human | Status + Approval | Real-time | Discord |
| ทีม Agent | งาน + Output | Real-time | Discord |

## 4. สมาชิกทีมโครงการ
| Role | Agent | Discord Channel |
|-----|-------|----------------|
| CEO | CEO Agent | #ceo-input / #ceo-approvals |
| PM | PM Agent | #pm-approvals |
| BA | BA Agent | #ba-approvals |

## 5. วิธีการและเทคโนโลยี
- Discord: Real-time messaging + Approval workflow
- SQLite DB: State management
- File System: Output storage

## 6. Communications Matrix
| ข้อมูล | ผู้ส่ง | ผู้รับ | ความถี่ | รูปแบบ |
|------|------|------|--------|------|
| Approval Request | Agent | Human | ทุก Task | Discord Embed |
| Status Update | PM Agent | CEO | รายสัปดาห์ | Status Report |
| Bug Report | QA | DEV | ทุก Issue | Discord |

## 7. Communication Flowchart
```
Human → Discord #ceo-input → CEO Agent → DB → PM Agent
PM Agent → DB → BA/SA/UXUI/DEV/QA/DevOps
Agent → Discord #role-approvals → Human Approval
Human → !approve/!revise → Agent continues
```

## 8. มาตรฐานการสื่อสาร
- ภาษา: ไทย (ผสม Technical English)
- Response Time: < 5 นาทีสำหรับ approval
- Output Format: Markdown/Excel/YAML ตามที่กำหนด

## 9. Escalation Process
Agent → PM Agent → CEO Agent → Human Owner

## 10. คำศัพท์
| คำ | ความหมาย |
|---|---------|
| Epic | กลุ่มฟีเจอร์หลัก |
| Task | งานย่อย 1 output |
| Approval | การอนุมัติจาก Human |
---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจคนี้โดยตรง ห้ามใส่ "..." หรือข้อความทั่วไปที่ไม่เกี่ยวข้อง
""",

    "project_status_report": """
คุณเป็น PM Agent

## ข้อมูลโปรเจค:
{project_brief}

## สถานะงานปัจจุบัน:
{tasks_summary}

## สิ่งที่ต้องส่งมอบ: project_status_report.md

---
# Project Status Report — {project_name}
**ช่วงเวลา:** {today} | **สถานะโดยรวม:** 🟡 In Progress

## 1. งานที่วางแผนและทำเสร็จแล้ว
| งาน | ผู้รับผิดชอบ | แผน | จริง | สถานะ |
|-----|-----------|-----|-----|------|
| ... | ... | ... | ... | ✅ Done |

## 2. งานที่ทำเสร็จสัปดาห์นี้
- ...

## 3. งานที่วางแผนสัปดาห์หน้า
- ...

## 4. ปัญหาที่เปิดอยู่
| Issue ID | รายละเอียด | ผลกระทบ | เจ้าของ | กำหนดแก้ |
|---------|----------|--------|--------|---------|
| ISS-001 | ... | H/M/L | ... | ... |

## 5. ความเสี่ยงที่เปิดอยู่
| Risk ID | ความเสี่ยง | ผลกระทบ | สถานะ |
|--------|----------|--------|------|
| R-001 | ... | H/M/L | Open |

## 6. Deliverables และ Milestones
| Deliverable | แผน | จริง | สถานะ |
|------------|-----|-----|------|
| Project Brief | ... | ... | ✅ |
| Epics | ... | ... | ✅ |

## 7. Change Requests ที่เปิดอยู่
| CR ID | คำขอ | ผลกระทบ | สถานะ |
|------|-----|--------|------|
| - | ไม่มี | - | - |

## 8. KPIs
| KPI | เป้าหมาย | จริง | สถานะ |
|-----|---------|-----|------|
| Tasks Completed | ... | ... | In Progress |
| Budget Used | ... | ... | On Track |
---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจคนี้โดยตรง ห้ามใส่ "..." หรือข้อความทั่วไปที่ไม่เกี่ยวข้อง
""",
}


def build_pm_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับโปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Milestone, Deliverable, RACI, Risk Register, Sprint, Stakeholder, Budget, Scope\n\n"
    ctx = {
        "today": date.today().strftime("%Y-%m-%d"),
        "budget": "TBD",
        "tasks_summary": "ยังไม่มีข้อมูล (tasks กำลังดำเนินการ)",
        **context,
    }
    return lang + safe_format(template, ctx)
