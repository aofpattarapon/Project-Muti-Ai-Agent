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

## 3. Project Schedule / ตารางเวลาโครงการ
**ระบุ schedule ที่ชัดเจน ห้ามใช้ '...' หรือ 'TBD' แทนวันที่จริง — ใช้ "สัปดาห์ที่ N" หรือ "YYYY-MM-DD" เสมอ**

| # | Milestone | สัปดาห์/วันที่เริ่ม | สัปดาห์/วันที่เสร็จ | Owner | ผลลัพธ์ที่คาดหวัง | Dependency | สถานะ |
|---|----------|-----------------|----------------|-------|----------------|-----------|------|
| 1 | Kick-off & Requirements | สัปดาห์ที่ 1 | สัปดาห์ที่ 1 | CEO/PM | Project Charter approved | - | Planned |
| 2 | Analysis & Design | สัปดาห์ที่ 1 | สัปดาห์ที่ 2 | BA/SA/UXUI | BRD, SRS, Architecture, Wireframe | Milestone 1 | Planned |
| 3 | Development | สัปดาห์ที่ 2 | สัปดาห์ที่ 3 | DEV | Frontend + Backend code | Milestone 2 | Planned |
| 4 | QA & Testing | สัปดาห์ที่ 3 | สัปดาห์ที่ 4 | QA | Test Report, Defects resolved | Milestone 3 | Planned |
| 5 | Deployment & Release | สัปดาห์ที่ 4 | สัปดาห์ที่ 4 | DevOps | System live, Deployment Guide | Milestone 4 | Planned |

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

    "project_plan_excel": """
คุณเป็น PM Agent

## Project Charter:
{project_charter_content}

## แผนบริหารโครงการ (Project Management Plan):
{pm_plan_content}

## สิ่งที่ต้องส่งมอบ: project_plan.xlsx
สร้าง **Excel Project Plan** สไตล์ MS Project ตอบด้วย **JSON เท่านั้น** ตามรูปแบบด้านล่าง

**ข้อบังคับ:**
- Duration Days และ Manday ต้องเป็นตัวเลข (float) ห้ามว่าง ห้ามใส่ "-" หรือ "TBD"
- Phase manday = ผลรวม child tasks ของ phase นั้น
- ใส่ทุก Agent role อย่างน้อย 1 task: CEO, PM, BA, SA, UXUI, DEV, QA, DevOps
- Dependency ให้อ้างอิง Task ID ที่มีอยู่จริง เช่น "T-001" ห้ามว่างสำหรับ task ที่มี upstream

{{
  "sheets": [
    {{
      "name": "Project Plan",
      "headers": ["Task ID","WBS","Phase","Task","Description","Owner Agent","Start Date","End Date","Duration Days","Manday","Dependency","Deliverable","Status"],
      "rows": [
        ["T-001","1","Initiation","Project Brief & Approval","CEO กำหนดทิศทางโครงการ","CEO Agent","สัปดาห์ที่ 1","สัปดาห์ที่ 1",1,1.0,"","project_brief.md","Planned"],
        ["T-002","1.1","Initiation","Epics Definition","แบ่ง Epic ทั้งหมด","CEO Agent","สัปดาห์ที่ 1","สัปดาห์ที่ 1",1,1.0,"T-001","epics.md","Planned"],
        ["T-003","2","Planning","Project Charter","กำหนดขอบเขต วัตถุประสงค์","PM Agent","สัปดาห์ที่ 1","สัปดาห์ที่ 1",1,1.0,"T-002","project_charter.docx","Planned"],
        ["T-004","2.1","Planning","Project Management Plan","แผนบริหารโครงการครบถ้วน","PM Agent","สัปดาห์ที่ 1","สัปดาห์ที่ 2",2,2.0,"T-003","project_management_plan.docx","Planned"],
        ["T-005","2.2","Planning","Excel Project Plan","MS-Project style schedule","PM Agent","สัปดาห์ที่ 2","สัปดาห์ที่ 2",1,0.5,"T-004","project_plan.xlsx","Planned"],
        ["T-006","3","Analysis","BRD","Business Requirements Document","BA Agent","สัปดาห์ที่ 2","สัปดาห์ที่ 2",2,2.0,"T-003","BRD.docx","Planned"],
        ["T-007","3.1","Analysis","SRS","Software Requirements Spec","BA Agent","สัปดาห์ที่ 2","สัปดาห์ที่ 3",2,2.0,"T-006","SRS.docx","Planned"],
        ["T-008","3.2","Analysis","User Stories","User Stories + Acceptance Criteria","BA Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 3",1,1.0,"T-006","user_stories.xlsx","Planned"],
        ["T-009","4","Architecture","System Architecture","Architecture Diagram","SA Agent","สัปดาห์ที่ 2","สัปดาห์ที่ 3",2,2.0,"T-007","architecture_diagram.mmd","Planned"],
        ["T-010","4.1","Architecture","API Specification","OpenAPI YAML","SA Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 3",2,2.0,"T-009","api_spec.yaml","Planned"],
        ["T-011","5","Design","User Flow","User Flow Diagram","UXUI Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 3",1,1.0,"T-010","user_flow.mmd","Planned"],
        ["T-012","5.1","Design","Wireframe","HTML Wireframe","UXUI Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 4",1,1.5,"T-011","wireframe.html","Planned"],
        ["T-013","5.2","Design","Design System","Color, Typography, Components","UXUI Agent","สัปดาห์ที่ 4","สัปดาห์ที่ 4",1,1.0,"T-012","design_system.md","Planned"],
        ["T-014","6","Development","Frontend Structure","Tech stack, folder structure","DEV Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 4",2,2.0,"T-012","frontend_structure.docx","Planned"],
        ["T-015","6.1","Development","Backend Structure","API design, service layout","DEV Agent","สัปดาห์ที่ 3","สัปดาห์ที่ 4",2,2.0,"T-010","backend_structure.docx","Planned"],
        ["T-016","6.2","Development","Frontend Code","Implementation","DEV Agent","สัปดาห์ที่ 4","สัปดาห์ที่ 5",3,3.0,"T-014","frontend_code/","Planned"],
        ["T-017","6.3","Development","Backend Code","API + business logic","DEV Agent","สัปดาห์ที่ 4","สัปดาห์ที่ 5",3,3.0,"T-015","backend_code/","Planned"],
        ["T-018","6.4","Development","Unit Tests","Automated unit tests","DEV Agent","สัปดาห์ที่ 5","สัปดาห์ที่ 5",1,1.0,"T-016,T-017","unit_tests/","Planned"],
        ["T-019","7","QA","QA Plan","Test strategy + scope","QA Agent","สัปดาห์ที่ 5","สัปดาห์ที่ 5",1,1.0,"T-018","qa_plan.docx","Planned"],
        ["T-020","7.1","QA","Test Cases","TC-NNN test cases","QA Agent","สัปดาห์ที่ 5","สัปดาห์ที่ 6",2,2.0,"T-008,T-019","test_cases.xlsx","Planned"],
        ["T-021","7.2","QA","Test Report","Execution result + defects","QA Agent","สัปดาห์ที่ 6","สัปดาห์ที่ 6",1,1.5,"T-020","test_report.docx","Planned"],
        ["T-022","8","Deployment","Dockerfile + Compose","Container build config","DevOps Agent","สัปดาห์ที่ 5","สัปดาห์ที่ 6",2,1.5,"T-018","Dockerfile","Planned"],
        ["T-023","8.1","Deployment","CI/CD Pipeline","GitHub Actions workflow","DevOps Agent","สัปดาห์ที่ 6","สัปดาห์ที่ 6",1,1.0,"T-022","ci.yml","Planned"],
        ["T-024","8.2","Deployment","Deployment Guide","Runbook + ENV setup","DevOps Agent","สัปดาห์ที่ 6","สัปดาห์ที่ 6",1,1.0,"T-023","deployment_guide.docx","Planned"]
      ]
    }},
    {{
      "name": "Gantt",
      "headers": ["Task ID","Task","Owner","Week 1","Week 2","Week 3","Week 4","Week 5","Week 6"],
      "rows": [
        ["T-001","Project Brief","CEO Agent","x","","","","",""],
        ["T-002","Epics Definition","CEO Agent","x","","","","",""],
        ["T-003","Project Charter","PM Agent","x","","","","",""],
        ["T-004","Project Management Plan","PM Agent","x","x","","","",""],
        ["T-005","Excel Project Plan","PM Agent","","x","","","",""],
        ["T-006","BRD","BA Agent","","x","","","",""],
        ["T-007","SRS","BA Agent","","x","x","","",""],
        ["T-008","User Stories","BA Agent","","","x","","",""],
        ["T-009","Architecture","SA Agent","","x","x","","",""],
        ["T-010","API Spec","SA Agent","","","x","","",""],
        ["T-011","User Flow","UXUI Agent","","","x","","",""],
        ["T-012","Wireframe","UXUI Agent","","","x","x","",""],
        ["T-013","Design System","UXUI Agent","","","","x","",""],
        ["T-014","Frontend Structure","DEV Agent","","","x","x","",""],
        ["T-015","Backend Structure","DEV Agent","","","x","x","",""],
        ["T-016","Frontend Code","DEV Agent","","","","x","x",""],
        ["T-017","Backend Code","DEV Agent","","","","x","x",""],
        ["T-018","Unit Tests","DEV Agent","","","","","x",""],
        ["T-019","QA Plan","QA Agent","","","","","x",""],
        ["T-020","Test Cases","QA Agent","","","","","x","x"],
        ["T-021","Test Report","QA Agent","","","","","","x"],
        ["T-022","Dockerfile + Compose","DevOps Agent","","","","","x","x"],
        ["T-023","CI/CD Pipeline","DevOps Agent","","","","","","x"],
        ["T-024","Deployment Guide","DevOps Agent","","","","","","x"]
      ]
    }},
    {{
      "name": "Manday Summary",
      "headers": ["Owner Agent","Total Tasks","Total Manday","First Start","Last End","Critical Deliverables"],
      "rows": [
        ["CEO Agent",2,2.0,"สัปดาห์ที่ 1","สัปดาห์ที่ 1","project_brief.md, epics.md"],
        ["PM Agent",3,3.5,"สัปดาห์ที่ 1","สัปดาห์ที่ 2","project_charter.docx, project_plan.xlsx"],
        ["BA Agent",3,5.0,"สัปดาห์ที่ 2","สัปดาห์ที่ 3","BRD.docx, SRS.docx, user_stories.xlsx"],
        ["SA Agent",2,4.0,"สัปดาห์ที่ 2","สัปดาห์ที่ 3","architecture_diagram.mmd, api_spec.yaml"],
        ["UXUI Agent",3,3.5,"สัปดาห์ที่ 3","สัปดาห์ที่ 4","wireframe.html, design_system.md"],
        ["DEV Agent",5,10.0,"สัปดาห์ที่ 3","สัปดาห์ที่ 5","frontend_code/, backend_code/, unit_tests/"],
        ["QA Agent",3,4.5,"สัปดาห์ที่ 5","สัปดาห์ที่ 6","test_cases.xlsx, test_report.docx"],
        ["DevOps Agent",3,3.5,"สัปดาห์ที่ 5","สัปดาห์ที่ 6","Dockerfile, ci.yml, deployment_guide.docx"],
        ["TOTAL","24",36.0,"สัปดาห์ที่ 1","สัปดาห์ที่ 6","Full SDLC Delivery"]
      ]
    }},
    {{
      "name": "Milestones",
      "headers": ["Milestone ID","Milestone","Target Date","Owner","Exit Criteria","Dependency"],
      "rows": [
        ["M-001","Project Kickoff Complete","สัปดาห์ที่ 1","PM Agent","Project Charter approved","T-003"],
        ["M-002","Requirements Frozen","สัปดาห์ที่ 3","BA Agent","BRD + SRS + User Stories approved","-"],
        ["M-003","Architecture Approved","สัปดาห์ที่ 3","SA Agent","Architecture + API Spec approved","M-002"],
        ["M-004","Design Complete","สัปดาห์ที่ 4","UXUI Agent","Wireframe + Design System approved","M-003"],
        ["M-005","Development Complete","สัปดาห์ที่ 5","DEV Agent","Frontend + Backend + Unit Tests pass","M-004"],
        ["M-006","QA Pass","สัปดาห์ที่ 6","QA Agent","Test Report: 0 Critical Defects","M-005"],
        ["M-007","Deployment Ready","สัปดาห์ที่ 6","DevOps Agent","Deployment Guide + CI/CD verified","M-006"],
        ["M-008","Project Complete / UAT Signed Off","สัปดาห์ที่ 6","PM Agent","CEO/Human approval received","M-007"]
      ]
    }},
    {{
      "name": "Assumptions",
      "headers": ["#","Category","Assumption","Impact if Wrong","Owner"],
      "rows": [
        [1,"Team","1 Agent = 1.0 manday per task day","Delivery delayed","PM Agent"],
        [2,"Calendar","6-week timeline, 5 working days/week","Milestone slippage","PM Agent"],
        [3,"Infrastructure","Ollama local deployment available","LLM fallback to Groq/Claude CLI","DevOps Agent"],
        [4,"Safety","PAPER_TRADING_MODE=true always enabled","Real exchange orders executed (critical)","DEV Agent"],
        [5,"Safety","No real API key/secret stored in codebase","API secret leakage (critical)","DEV Agent"],
        [6,"Safety","All trades are paper/simulated fills only","Real financial loss (critical)","QA Agent"],
        [7,"Quality","Model fallback to local models may reduce output quality","Contract validation failures","PM Agent"],
        [8,"Dependency","BA depends on PM Charter before starting BRD","Rework if started in parallel","BA Agent"]
      ]
    }}
  ]
}}

**ข้อบังคับ:** แทนที่เนื้อหาทั้งหมดด้วยข้อมูลจริงของโปรเจค {project_name} — ห้าม placeholder ห้าม TBD ห้าม "..."
ให้ตรวจสอบ manday ใน Manday Summary ตรงกับผลรวม tasks ใน Project Plan เสมอ
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

**ข้อบังคับ:** ทุกแถวใน Risk Register ต้องมีคอลัมน์ "แผนลดความเสี่ยง" ที่มีเนื้อหาจริง — ห้ามว่างเปล่า ห้ามใส่ "..." หรือ "-" เพียงอย่างเดียว
**ข้อบังคับ:** ถ้าโปรเจคนี้เกี่ยวข้องกับระบบการเงิน, trading, simulation ให้เพิ่ม safety risks เหล่านี้ด้วย:
- การสั่ง order จริง (accidental real order execution) แทน paper trade
- API secret/key ของ exchange รั่วไหล
- PAPER_TRADING_MODE flag ถูกปิดโดยไม่ตั้งใจ
- ระบบ simulation คำนวณ balance ผิดพลาด

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
