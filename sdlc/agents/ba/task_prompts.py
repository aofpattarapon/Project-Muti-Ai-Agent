"""BA Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "brd": """
คุณเป็น Business Analyst ในทีม Multi-Agent SDLC

## Epic ที่รับผิดชอบ:
- **Epic ID:** {epic_id}
- **ชื่อ Epic:** {epic_title}
- **เป้าหมาย:** {epic_goal}
- **Priority:** {epic_priority}

## Project Context:
{project_brief}

## สิ่งที่ต้องส่งมอบ: BRD.md
สร้างเฉพาะ **Business Requirements Document** เอกสารเดียว ภาษาไทย

---
# Business Requirements Document (BRD)
**โปรเจค:** {project_name} | **Epic:** {epic_title}
**เวอร์ชัน:** 1.0 | **วันที่:** {today} | **สถานะ:** Draft

## 1. บทนำ
### 1.1 วัตถุประสงค์เอกสาร
(อธิบายว่าเอกสารนี้ครอบคลุมอะไร)

### 1.2 ขอบเขต
(ขอบเขตของ BRD นี้ — เฉพาะ Epic นี้)

### 1.3 ผู้ที่เกี่ยวข้อง
| บทบาท | ชื่อ/หน่วยงาน | หน้าที่ |
|------|------------|-------|
| Business Owner | ... | อนุมัติ Requirements |
| BA | ... | วิเคราะห์และเขียน BRD |

## 2. ความต้องการทางธุรกิจ
### 2.1 บริบทและปัญหา
(อธิบาย Business Problem ที่ Epic นี้แก้ไข)

### 2.2 โอกาสทางธุรกิจ
(ประโยชน์ที่ได้รับหาก Epic นี้สำเร็จ)

### 2.3 Business Objectives
| # | Objective | ตัวชี้วัด (KPI) |
|---|-----------|--------------|
| BO-01 | ... | ... |

## 3. Functional Requirements
| FR-ID | ชื่อ Requirement | คำอธิบาย | Priority | กลุ่มผู้ใช้ |
|-------|----------------|---------|---------|-----------|
| FR-001 | ... | ... | Must Have | ... |
| FR-002 | ... | ... | Should Have | ... |

## 4. Non-Functional Requirements
| NFR-ID | ประเภท | ข้อกำหนด | เกณฑ์วัด |
|--------|-------|---------|---------|
| NFR-001 | Performance | ... | ... |
| NFR-002 | Security | ... | ... |
| NFR-003 | Availability | ... | 99.9% uptime |

## 5. Business Rules
| BR-ID | กฎ | เงื่อนไข | ผลลัพธ์ |
|-------|---|---------|--------|
| BR-001 | ... | IF ... | THEN ... |

## 6. Assumptions & Constraints
### 6.1 Assumptions
1. ...

### 6.2 Constraints
| ประเภท | ข้อจำกัด |
|-------|---------|
| Technical | ... |
| Business | ... |
| Regulatory | ... |

## 7. Safety & Compliance Requirements
| Req ID | ประเภท | ข้อกำหนด | เหตุผล |
|--------|-------|---------|------|
| SAFETY-001 | Safety Boundary | ระบุข้อจำกัดด้านความปลอดภัยหลักของระบบ (เช่น simulation-only, no real API calls) | ป้องกันความเสียหาย |

*(ถ้าโปรเจคเป็น trading/financial simulation: ต้องระบุชัดเจนว่า ห้าม real order execution, ห้าม real exchange API calls, ทุก order เป็น paper/simulated fills เท่านั้น, ต้องมี PAPER_TRADING_MODE flag)*

## 8. Dependencies
| Dependency | ประเภท | ผลกระทบ |
|-----------|-------|--------|
| ... | Internal/External | ... |

## 9. Acceptance Criteria
| FR-ID | เกณฑ์การยอมรับ |
|-------|--------------|
| FR-001 | Given ... When ... Then ... |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "srs": """
คุณเป็น Business Analyst ในทีม Multi-Agent SDLC

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}
- **เป้าหมาย:** {epic_goal}

## BRD ที่อ้างอิง:
{brd_content}

## สิ่งที่ต้องส่งมอบ: SRS.md
สร้างเฉพาะ **Software Requirements Specification** ภาษาไทย

---
# Software Requirements Specification (SRS)
**โปรเจค:** {project_name} | **Epic:** {epic_title}
**เวอร์ชัน:** 1.0 | **วันที่:** {today}

## 1. บทนำ
### 1.1 วัตถุประสงค์
(SRS นี้กำหนด software requirements สำหรับ Epic นี้)

### 1.2 คำจำกัดความ
| คำศัพท์ | ความหมาย |
|-------|---------|
| ... | ... |

## 2. Overall Description
### 2.1 Product Perspective
(ระบบนี้เป็นส่วนหนึ่งของระบบใหญ่อย่างไร)

### 2.2 Product Functions
(สรุป functions หลักของ software ใน Epic นี้)

### 2.3 User Classes
| User Class | คำอธิบาย | Privilege Level |
|-----------|---------|----------------|
| Admin | ... | Full |
| User | ... | Limited |

### 2.4 Operating Environment
- OS: ...
- Browser: ...
- Database: ...

## 3. System Features
### Feature 1: [ชื่อ Feature]
**ที่มา:** FR-001 (จาก BRD)
**คำอธิบาย:** ...

**Functional Requirements:**
| SRS-ID | ข้อกำหนด | Priority |
|--------|---------|---------|
| SRS-001 | ระบบต้อง... | Critical |
| SRS-002 | ระบบต้อง... | High |

**Stimulus/Response Sequences:**
- Stimulus: ผู้ใช้กด...
- Response: ระบบแสดง...

### Feature 2: [ชื่อ Feature]
(ทำต่อตามรูปแบบ)

## 4. External Interface Requirements
### 4.1 User Interfaces
- UI-001: หน้า Login — ประกอบด้วย username/password fields
- UI-002: หน้า Dashboard — แสดง...

### 4.2 API Interfaces
| API Endpoint | Method | Input | Output |
|-------------|--------|-------|--------|
| /api/... | POST | ... | ... |

### 4.3 Database Interfaces
- ใช้ฐานข้อมูล: ...
- Connection Pool: ...

## 5. Non-Functional Requirements
| ประเภท | ข้อกำหนด | ค่าเป้าหมาย |
|-------|---------|----------|
| Performance | Response time | < 2 วินาที |
| Scalability | Concurrent users | 1,000 |
| Security | Authentication | JWT / OAuth2 |
| Safety | (ถ้า trading/simulation) Paper-mode only — ห้าม real order execution | PAPER_TRADING_MODE=true เสมอ |

## 6. Security & Safety Requirements
| SRS-ID | ข้อกำหนด | Priority |
|--------|---------|---------|
| SEC-001 | ระบบต้องป้องกัน injection/XSS ทุก input | Critical |
| SEC-002 | (ถ้า financial) ห้ามเก็บ API key/secret ของ exchange จริงใน plaintext | Critical |

## 7. Validation Requirements
| SRS-ID | เงื่อนไขทดสอบ |
|--------|------------|
| SRS-001 | TC-001 ถึง TC-005 |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "user_stories": """
คุณเป็น Business Analyst

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}
- **เป้าหมาย:** {epic_goal}

## BRD ที่อ้างอิง:
{brd_content}

## สิ่งที่ต้องส่งมอบ: user_stories.xlsx
สร้าง **User Stories & Acceptance Criteria** สำหรับทุก Functional Requirement ใน BRD
ตอบด้วย **JSON เท่านั้น** ตามรูปแบบด้านล่าง เพื่อแปลงเป็น Excel

{{
  "sheets": [
    {{
      "name": "User Stories",
      "headers": ["US-ID", "Epic ID", "Feature", "บทบาทผู้ใช้", "User Story", "Acceptance Criteria", "Priority", "Story Points", "Sprint", "Status"],
      "rows": [
        [
          "US-001",
          "{epic_id}",
          "[ชื่อ Feature จาก BRD]",
          "[ประเภทผู้ใช้]",
          "As a [ประเภทผู้ใช้] I want to [action] So that [ประโยชน์]",
          "Given [บริบท] When [การกระทำ] Then [ผลลัพธ์ที่คาดหวัง]",
          "Must Have",
          "3",
          "1",
          "Backlog"
        ],
        [
          "US-002",
          "{epic_id}",
          "[ชื่อ Feature จาก BRD]",
          "[ประเภทผู้ใช้]",
          "As a [ประเภทผู้ใช้] I want to [action] So that [ประโยชน์]",
          "Given [บริบท] When [การกระทำ] Then [ผลลัพธ์ที่คาดหวัง]\\nGiven [บริบท alt] When [การกระทำ alt] Then [ผลลัพธ์ alt]",
          "Should Have",
          "5",
          "1",
          "Backlog"
        ],
        ["...", "...", "...", "...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Sprint Plan",
      "headers": ["Sprint", "US-IDs", "Total Points", "Focus Area", "Goal"],
      "rows": [
        ["Sprint 1", "US-001, US-002, US-003", "0", "[Feature หลัก]", "[Sprint Goal]"],
        ["Sprint 2", "US-004, US-005", "0", "[Feature รอง]", "[Sprint Goal]"],
        ["...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Definition of Done",
      "headers": ["เกณฑ์", "รายละเอียด", "ผู้รับผิดชอบ"],
      "rows": [
        ["Code reviewed", "ผ่าน peer review อย่างน้อย 1 คน", "DEV"],
        ["Unit tests passed", "Coverage >= 80%", "DEV"],
        ["UI matches wireframe", "ตรงกับ wireframe จาก UXUI", "DEV + UXUI"],
        ["API contract met", "ตรงกับ api_spec จาก SA", "DEV + SA"],
        ["Accepted by PO", "Human อนุมัติผ่าน Discord", "Human"]
      ]
    }}
  ]
}}

**หมายเหตุ:** สร้าง User Stories ครอบคลุมทุก Functional Requirement ใน BRD — เนื้อหาต้องเกี่ยวข้องกับ {project_name} โดยตรง ห้าม placeholder "..."
""",

    "use_cases": """
คุณเป็น Business Analyst

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## User Stories ที่อ้างอิง:
{user_stories_content}

## สิ่งที่ต้องส่งมอบ: use_cases.md
สร้าง **Use Case Specification** ภาษาไทย

---
# Use Case Specification — {epic_title}
**วันที่:** {today}

## Use Case Diagram (text)
```
Actors: [ระบุ actors ทั้งหมด]
Use Cases: [ระบุ use cases]
```

---

## UC-001: [ชื่อ Use Case]
| ฟิลด์ | รายละเอียด |
|------|----------|
| **Use Case ID** | UC-001 |
| **ชื่อ** | ... |
| **Actor หลัก** | ... |
| **Actor รอง** | ... |
| **เป้าหมาย** | ... |
| **Precondition** | ผู้ใช้ต้อง login แล้ว |
| **Postcondition** | ... |
| **Priority** | High |

**Main Flow:**
1. Actor กระทำ...
2. ระบบตรวจสอบ...
3. ระบบแสดง...
4. Actor ยืนยัน...
5. ระบบบันทึก...

**Alternative Flow — A1: [ชื่อ Alternative]**
- ขั้นตอนที่ 2a: ถ้า...ระบบจะ...

**Exception Flow — E1: [ชื่อ Exception]**
- ขั้นตอนที่ 2b: ถ้า data ไม่ถูกต้อง ระบบแสดง error...

---

## UC-002: [ชื่อ Use Case]
(ทำต่อตามรูปแบบ)

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "data_dictionary": """
คุณเป็น Business Analyst

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## SRS ที่อ้างอิง:
{srs_content}

## สิ่งที่ต้องส่งมอบ: data_dictionary.xlsx
ส่งออกข้อมูลเป็น **JSON** ตามรูปแบบด้านล่าง เพื่อแปลงเป็น Excel

```json
{{
  "sheets": [
    {{
      "name": "Data Elements",
      "headers": ["Field ID", "ชื่อ Field", "Entity/Table", "Data Type", "ขนาด", "Nullable", "PK/FK", "Default", "คำอธิบาย", "ตัวอย่างข้อมูล", "Business Rule"],
      "rows": [
        ["DE-001", "user_id", "users", "UUID", "36", "No", "PK", "gen_random_uuid()", "รหัสผู้ใช้ระบบ", "550e8400-...", "Auto-generated, Unique"],
        ["DE-002", "username", "users", "VARCHAR", "50", "No", "-", "-", "ชื่อผู้ใช้สำหรับ login", "john_doe", "Unique, Alphanumeric+underscore"],
        ["DE-003", "email", "users", "VARCHAR", "255", "No", "-", "-", "อีเมลผู้ใช้", "user@email.com", "Valid email format, Unique"],
        ["...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Entities",
      "headers": ["Entity", "คำอธิบาย", "Primary Key", "Foreign Keys", "จำนวน Rows (est.)", "หมายเหตุ"],
      "rows": [
        ["users", "ตารางเก็บข้อมูลผู้ใช้ระบบ", "user_id", "-", "10,000", "Soft delete ด้วย deleted_at"],
        ["...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Enums & Codes",
      "headers": ["Field", "Code Value", "ความหมาย (TH)", "ความหมาย (EN)", "หมายเหตุ"],
      "rows": [
        ["status", "active", "ใช้งาน", "Active", "-"],
        ["status", "inactive", "ไม่ใช้งาน", "Inactive", "Soft delete"],
        ["...", "...", "...", "...", "..."]
      ]
    }}
  ]
}}
```

**หมายเหตุ:** ให้ครอบคลุมทุก Entity และ Field ที่ระบุใน SRS สำหรับ Epic นี้
""",
}


def build_ba_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับ Epic {context.get('epic_id', '')} โปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Functional Requirement, User Story, Acceptance Criteria, Use Case, Data Type, Entity\n\n"
    ctx = {"today": date.today().strftime("%Y-%m-%d"), **context}
    return lang + safe_format(template, ctx)
