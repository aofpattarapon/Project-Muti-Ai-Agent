# 🔄 Workflow Guide - วิธีใช้งานระบบ

---

## SDLC Workflow ทั้งหมด

```
Human Input → CEO → PM → BA → SA → UXUI → DEV → QA → DEVOPS → Done
              ↑Approve ↑Approve ↑Approve ↑Approve ↑Approve ↑Approve ↑Approve ↑Approve
```

**ทุก step ต้องผ่าน Human Approval ก่อน**

---

## วิธีเริ่ม Project ใหม่

### Option 1: Interactive Mode
พิมพ์ใน `#ceo-input`:
```
!project start
```
Bot จะถามคำถามทีละข้อ

### Option 2: Single Command
พิมพ์ใน `#ceo-input`:
```
!new [Project Name] | [Description] | [Goals]
```

ตัวอย่าง:
```
!new Trading Bot AI | ระบบ AI วิเคราะห์ตลาด crypto ด้วย web scraping และ ML | เพิ่ม ROI 20%, reduce manual work 80%
```

### Option 3: Structured Format
```
!new
Project Name: AI Trading Bot
Description: ระบบที่ใช้ AI วิเคราะห์ข่าวและข้อมูลตลาด crypto
Goals: เพิ่ม ROI 20%, automation trading
Constraints: Budget < $100/month, Python stack
Priority: High
```

---

## Approval Flow ใน `#approvals`

เมื่อ Agent ทำงานเสร็จ จะส่ง Embed message ไปที่ `#approvals`:

```
🔔 Human Approval Required - CEO
Reply: !approve | !revise [comment] | !reject [reason]

📋 CEO Output - Trading Bot AI
Summary: วิเคราะห์แล้ว โปรเจคเป็น Trading Bot ที่ใช้ AI...
Project ID: A1B2C3D4
Role: CEO
Task ID: ab12cd34
Revision #0
📄 Output Files:
• project_brief.md
• epics.md
• role_assignment.md
```

### Commands ใน `#approvals`:
```bash
# Reply ไปที่ message นั้นพร้อม:

!approve                        # Approve และส่งต่อ
!revise แก้ Epic 2 ให้ละเอียดขึ้น  # ขอแก้ไข พร้อม comment
!reject scope ใหญ่เกินไป           # Reject พร้อมเหตุผล
```

---

## ดู Output Files

Output ของแต่ละ Role จะบันทึกที่:
```
outputs/projects/{PROJECT_ID}/{ROLE}/
├── ceo/
│   ├── project_brief.md
│   ├── epics.md
│   └── role_assignment.md
├── pm/
│   ├── project_plan.md
│   ├── timeline.md
│   ├── risk_register.md
│   └── raci_matrix.md
├── ba/
│   ├── BRD.md
│   ├── use_cases.md
│   ├── user_stories.md
│   └── data_dictionary.md
├── sa/
│   ├── system_architecture.md
│   ├── database_design.md
│   ├── api_spec.yaml
│   └── SRS.md
├── uxui/
│   ├── user_flow.md
│   ├── wireframe_spec.md
│   ├── design_system.md
│   └── ux_guidelines.md
├── dev/
│   ├── src/          ← Source Code จริง
│   ├── tests/        ← Unit Tests จริง
│   └── README_dev.md
├── qa/
│   ├── test_plan.md
│   ├── test_cases.md
│   ├── test_results.md
│   └── bug_report.md
└── devops/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .github/workflows/
    └── deployment_guide.md
```

---

## Commands Summary

| Command | Channel | ความหมาย |
|---------|---------|---------|
| `!new [text]` | #ceo-input | เริ่ม Project ใหม่ |
| `!project start` | #ceo-input | Interactive start |
| `!project status` | ทุก Channel | ดู Active Projects |
| `!status [id]` | ทุก Channel | ดูสถานะ Project |
| `!approve` | #approvals | Approve (reply) |
| `!revise [comment]` | #approvals | ขอแก้ไข (reply) |
| `!reject [reason]` | #approvals | Reject (reply) |

---

## ตัวอย่าง Full Workflow (ประมาณ Timeline)

```
วันที่ 1:
  09:00 - Human พิมพ์ Requirement ใน #ceo-input
  09:02 - CEO Agent วิเคราะห์ (Claude Haiku, ~30 วินาที)
  09:03 - CEO โพสต์ใน #approvals รอ Approve
  09:10 - Human !approve → PM เริ่มทำงาน
  09:12 - PM สร้าง Project Plan
  09:13 - PM โพสต์ใน #approvals
  09:20 - Human !approve → BA เริ่มทำงาน
  ...
วันที่ 1-2:
  BA, SA, UXUI ทำงาน (แต่ละ step ~2-5 นาที)

วันที่ 2-5:
  DEV Agent เขียน Code (Ollama local, อาจใช้เวลา 10-30 นาที)
  QA Agent รัน Tests

วันที่ 5:
  DEVOPS สร้าง Infrastructure
  🎉 Project Complete!
```
