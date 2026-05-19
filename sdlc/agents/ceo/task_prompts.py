"""CEO Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "project_brief": """
คุณเป็น CEO Agent ในทีม Multi-Agent SDLC

## Requirement ที่ได้รับ:
{requirements}

## สิ่งที่ต้องส่งมอบ: project_brief.md
สร้างเฉพาะ **Project Brief** เอกสารเดียว ภาษาไทย ตามโครงสร้างด้านล่าง:

---
# Project Brief — {project_name}
**เวอร์ชัน:** 1.0 | **วันที่:** {today} | **สถานะ:** Draft

## 1. บทสรุปผู้บริหาร
(2-3 ประโยค: ทำอะไร เพื่อใคร เป้าหมายคืออะไร)

## 2. เป้าหมายทางธุรกิจ
| # | เป้าหมาย | ตัวชี้วัด (KPI) | ระยะเวลา |
|---|---------|---------------|---------|
| 1 | ... | ... | ... |

## 3. กลุ่มผู้ใช้งาน
| Role | คำอธิบาย | ความสำคัญ |
|------|---------|----------|
| Admin | ... | สูง |

## 4. MVP Scope (สิ่งที่ต้องมีใน Version แรก)
| # | Feature | Priority | เหตุผล |
|---|---------|---------|-------|
| 1 | ... | P0 | ... |

## 5. นอก Scope (Phase ถัดไป)
- ...

## 6. เกณฑ์ความสำเร็จ
| เกณฑ์ | วิธีวัด | เป้าหมาย |
|------|--------|---------|
| ... | ... | ... |

## 7. ข้อจำกัด
| ประเภท | รายละเอียด |
|-------|----------|
| เวลา | ... |
| งบประมาณ | ... |
| เทคโนโลยี | ... |

## 8. สมมติฐาน
1. ...

## 9. ผู้มีส่วนได้เสีย
| ชื่อ/หน่วยงาน | บทบาท | ระดับความสำคัญ |
|------------|------|------------|
| ... | ... | สูง/กลาง/ต่ำ |

## 10. ความเสี่ยงเบื้องต้น
| ความเสี่ยง | ผลกระทบ | โอกาส | แนวทางรับมือ |
|----------|--------|------|-----------|
| ... | สูง/กลาง/ต่ำ | สูง/กลาง/ต่ำ | ... |
---

ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",

    "epics": """
คุณเป็น CEO Agent

## Project Brief:
{project_brief_content}

## Requirement:
{requirements}

## สิ่งที่ต้องส่งมอบ: epics.md
สร้างเฉพาะ **Epics** (Jira-style) ภาษาไทย แต่ละ Epic แทน 1 กลุ่มฟีเจอร์หลัก
แตก 3-6 Epics ตาม MVP Scope เท่านั้น

---
# Epics — {project_name}
**โปรเจค:** {project_name} | **วันที่:** {today}

---

## EPIC-001: [ชื่อ Epic]
**เป้าหมาย:** ...
**Priority:** P0 | **Effort:** L | **Labels:** `mvp`, `phase-1`
**Acceptance Criteria:**
- [ ] ...
- [ ] ...

**Tasks ที่ต้องทำ (PM จะแตกต่อ):**
- BA: สร้าง BRD + User Stories สำหรับ Epic นี้
- SA: ออกแบบ Architecture + API Spec สำหรับ Epic นี้
- UXUI: สร้าง User Flow + Wireframe สำหรับ Epic นี้
- DEV: Implement Frontend + Backend สำหรับ Epic นี้
- QA: สร้าง Test Cases + Test Report สำหรับ Epic นี้

---

## EPIC-002: [ชื่อ Epic]
(ทำต่อตามรูปแบบเดิม)

---
*(ทำต่อจนครบทุก Epic ใน MVP)*

ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",
}


def build_ceo_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับโปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Epic, Sprint, KPI, Stakeholder, Scope, Risk, MVP\n\n"
    ctx = {"today": date.today().strftime("%Y-%m-%d"), **context}
    return lang + safe_format(template, ctx)
