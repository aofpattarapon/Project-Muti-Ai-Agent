"""UXUI Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "user_flow": """
คุณเป็น UX/UI Designer ในทีม Multi-Agent SDLC

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}
- **เป้าหมาย:** {epic_goal}

## API Spec จาก SA:
{sa_api_spec}

## สิ่งที่ต้องส่งมอบ: user_flow.md
สร้าง **User Flow Diagrams** แบบ Mermaid ภาษาไทย

ต้องมี User Flow สำหรับทุก main journey ใน Epic (อย่างน้อย 3 flows)

---
# User Flow — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## Overview: User Journey Map
```mermaid
journey
    title User Journey — {epic_title}
    section การเข้าสู่ระบบ
      เปิดแอป: 5: ผู้ใช้
      กรอก Email/Password: 3: ผู้ใช้
      ยืนยัน OTP: 3: ผู้ใช้
      เข้า Dashboard: 5: ผู้ใช้
    section การใช้งานหลัก
      เลือก Feature: 4: ผู้ใช้
      กรอกข้อมูล: 3: ผู้ใช้
      ยืนยัน: 4: ผู้ใช้
      ดูผลลัพธ์: 5: ผู้ใช้
```

## Flow 1: [ชื่อ Main Flow — เช่น Login & Onboarding]
```mermaid
flowchart TD
    Start([เริ่มต้น: เปิดแอป]) --> Landing[หน้า Landing Page]
    Landing --> HasAccount{มีบัญชีแล้ว?}
    HasAccount -->|ใช่| LoginPage[หน้า Login]
    HasAccount -->|ไม่ใช่| RegisterPage[หน้า Register]

    LoginPage --> EnterCreds[กรอก Email + Password]
    EnterCreds --> ValidLogin{Login สำเร็จ?}
    ValidLogin -->|ใช่| Dashboard[หน้า Dashboard]
    ValidLogin -->|ไม่ใช่| ShowError[แสดงข้อผิดพลาด]
    ShowError --> LoginPage

    RegisterPage --> FillForm[กรอกข้อมูลลงทะเบียน]
    FillForm --> VerifyEmail[ยืนยัน Email]
    VerifyEmail --> Dashboard

    Dashboard --> End([เสร็จสิ้น])
```

## Flow 2: [ชื่อ Core Feature Flow]
```mermaid
flowchart TD
    Dashboard[Dashboard] --> SelectFeature[เลือก Feature]
    SelectFeature --> FeaturePage[หน้า Feature หลัก]

    FeaturePage --> CreateNew{สร้างใหม่?}
    CreateNew -->|ใช่| NewForm[แบบฟอร์มสร้างใหม่]
    CreateNew -->|ไม่| ViewList[ดูรายการ]

    NewForm --> FillData[กรอกข้อมูล]
    FillData --> Validate{ข้อมูลถูกต้อง?}
    Validate -->|ใช่| Confirm[หน้ายืนยัน]
    Validate -->|ไม่ใช่| ShowErrors[แสดง Validation Errors]
    ShowErrors --> FillData

    Confirm --> Submit[ส่งข้อมูล]
    Submit --> Success[หน้าสำเร็จ]
    Success --> ViewList
```

## Flow 3: [Error & Edge Case Flow]
```mermaid
flowchart TD
    (สร้าง flow สำหรับ error cases, timeout, network error ฯลฯ)
```

## Screen Inventory
| Screen ID | ชื่อหน้า | Flow | ประเภทผู้ใช้ | หมายเหตุ |
|----------|---------|------|-----------|--------|
| SCR-001 | Landing Page | Flow 1 | ทุกคน | Public |
| SCR-002 | Login | Flow 1 | ผู้ใช้ | Auth required |
| SCR-003 | Dashboard | All | ผู้ใช้/Admin | Role-based content |
| SCR-004 | ... | ... | ... | ... |

---
ตอบด้วย Markdown (พร้อม mermaid blocks) เท่านั้น
""",

    "wireframe": """
คุณเป็น UX/UI Designer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## User Flow:
{user_flow_content}

## API Spec:
{sa_api_spec}

## สิ่งที่ต้องส่งมอบ: wireframe.html
สร้าง **HTML Wireframe** ด้วย Tailwind CSS สำหรับ Epic นี้

ต้องมีทุกหน้าที่อยู่ใน Screen Inventory (จาก User Flow)
ใช้ Tailwind CDN, สีเทา/ขาวแบบ wireframe, ไม่ต้องสวยงาม — เน้น structure และ layout

```html
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wireframe — {epic_title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .wireframe-box {{ border: 2px dashed #9ca3af; background: #f9fafb; }}
    .wireframe-img {{ border: 2px dashed #9ca3af; background: #e5e7eb; min-height: 120px; display: flex; align-items: center; justify-content: center; color: #6b7280; }}
    .screen-label {{ background: #1f2937; color: white; padding: 8px 16px; font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; }}
  </style>
</head>
<body class="bg-gray-100 p-8 font-sans">

  <h1 class="text-2xl font-bold text-gray-800 mb-2">{project_name} — Wireframes</h1>
  <p class="text-gray-500 mb-8">Epic: {epic_title} | วันที่: {today}</p>

  <!-- ====== SCR-001: Landing Page ====== -->
  <div class="mb-12">
    <div class="screen-label">SCR-001 · Landing Page</div>
    <div class="bg-white border-2 border-gray-300 p-0" style="width:1200px; min-height:600px;">

      <!-- Navbar -->
      <div class="flex items-center justify-between px-8 py-4 border-b border-gray-200 bg-gray-50">
        <div class="wireframe-box px-4 py-2 text-gray-400 text-sm">[LOGO]</div>
        <div class="flex gap-4">
          <div class="wireframe-box px-4 py-2 text-gray-400 text-sm">[เมนู 1]</div>
          <div class="wireframe-box px-4 py-2 text-gray-400 text-sm">[เมนู 2]</div>
        </div>
        <div class="flex gap-2">
          <button class="wireframe-box px-4 py-2 text-gray-500 text-sm">เข้าสู่ระบบ</button>
          <button class="bg-gray-800 text-white px-4 py-2 text-sm">สมัครใช้งาน</button>
        </div>
      </div>

      <!-- Hero -->
      <div class="flex items-center justify-between px-16 py-16">
        <div class="flex-1 pr-8">
          <div class="wireframe-box p-2 mb-4 text-gray-400 text-xs">[HEADLINE TEXT — ชื่อผลิตภัณฑ์]</div>
          <div class="wireframe-box p-2 mb-6 h-12 text-gray-400 text-xs">[Sub-headline — คำอธิบายสั้น]</div>
          <div class="flex gap-3">
            <button class="bg-gray-800 text-white px-6 py-3 text-sm">[CTA Primary]</button>
            <button class="wireframe-box px-6 py-3 text-gray-500 text-sm">[CTA Secondary]</button>
          </div>
        </div>
        <div class="wireframe-img" style="width:400px; height:300px;">[Hero Image / Illustration]</div>
      </div>
    </div>
  </div>

  <!-- ====== SCR-002: Login Page ====== -->
  <div class="mb-12">
    <div class="screen-label">SCR-002 · Login Page</div>
    <div class="bg-white border-2 border-gray-300 flex items-center justify-center" style="width:1200px; min-height:600px;">
      <div class="wireframe-box p-8" style="width:400px;">
        <div class="wireframe-box p-2 mb-6 text-center text-gray-400">[LOGO]</div>
        <h2 class="text-xl font-semibold text-gray-700 mb-6 text-center">เข้าสู่ระบบ</h2>
        <div class="mb-4">
          <label class="block text-sm text-gray-600 mb-1">อีเมล</label>
          <div class="wireframe-box p-3 text-gray-400 text-sm">[Email Input Field]</div>
        </div>
        <div class="mb-4">
          <label class="block text-sm text-gray-600 mb-1">รหัสผ่าน</label>
          <div class="wireframe-box p-3 text-gray-400 text-sm">[Password Input Field]</div>
        </div>
        <div class="flex justify-between items-center mb-6">
          <div class="text-sm text-gray-500">[Remember me checkbox]</div>
          <div class="text-sm text-gray-500">[ลืมรหัสผ่าน?]</div>
        </div>
        <button class="w-full bg-gray-800 text-white py-3 text-sm mb-4">เข้าสู่ระบบ</button>
        <div class="text-center text-sm text-gray-500">[ยังไม่มีบัญชี? สมัครใช้งาน]</div>
      </div>
    </div>
  </div>

  <!-- ====== SCR-003: Dashboard ====== -->
  <div class="mb-12">
    <div class="screen-label">SCR-003 · Dashboard</div>
    <div class="bg-white border-2 border-gray-300 flex" style="width:1200px; min-height:700px;">

      <!-- Sidebar -->
      <div class="wireframe-box border-r-2" style="width:220px;">
        <div class="p-4 border-b border-gray-200">
          <div class="wireframe-box p-2 text-gray-400 text-xs text-center">[LOGO]</div>
        </div>
        <nav class="p-4 space-y-2">
          <div class="bg-gray-200 px-3 py-2 text-sm text-gray-700">[เมนู Active]</div>
          <div class="px-3 py-2 text-sm text-gray-500">[เมนู 2]</div>
          <div class="px-3 py-2 text-sm text-gray-500">[เมนู 3]</div>
          <div class="px-3 py-2 text-sm text-gray-500">[เมนู 4]</div>
        </nav>
      </div>

      <!-- Main Content -->
      <div class="flex-1 p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-xl font-semibold text-gray-700">Dashboard</h2>
          <button class="bg-gray-800 text-white px-4 py-2 text-sm">+ สร้างใหม่</button>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-4 gap-4 mb-6">
          {{#each ["KPI 1", "KPI 2", "KPI 3", "KPI 4"]}}
          <div class="wireframe-box p-4">
            <div class="text-xs text-gray-400 mb-1">[ชื่อ Metric]</div>
            <div class="text-2xl font-bold text-gray-700">—</div>
            <div class="text-xs text-gray-400">[trend indicator]</div>
          </div>
          {{/each}}
          <div class="wireframe-box p-4">
            <div class="text-xs text-gray-400 mb-1">[KPI 1]</div>
            <div class="text-2xl font-bold text-gray-700">—</div>
          </div>
          <div class="wireframe-box p-4">
            <div class="text-xs text-gray-400 mb-1">[KPI 2]</div>
            <div class="text-2xl font-bold text-gray-700">—</div>
          </div>
          <div class="wireframe-box p-4">
            <div class="text-xs text-gray-400 mb-1">[KPI 3]</div>
            <div class="text-2xl font-bold text-gray-700">—</div>
          </div>
          <div class="wireframe-box p-4">
            <div class="text-xs text-gray-400 mb-1">[KPI 4]</div>
            <div class="text-2xl font-bold text-gray-700">—</div>
          </div>
        </div>

        <!-- Data Table -->
        <div class="wireframe-box">
          <div class="flex justify-between items-center p-4 border-b border-gray-200">
            <div class="wireframe-box px-3 py-2 text-gray-400 text-sm" style="width:200px;">[Search...]</div>
            <div class="flex gap-2">
              <div class="wireframe-box px-3 py-2 text-gray-400 text-sm">[Filter]</div>
              <div class="wireframe-box px-3 py-2 text-gray-400 text-sm">[Export]</div>
            </div>
          </div>
          <table class="w-full">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200">
                <th class="px-4 py-3 text-left text-xs text-gray-500">[Column 1]</th>
                <th class="px-4 py-3 text-left text-xs text-gray-500">[Column 2]</th>
                <th class="px-4 py-3 text-left text-xs text-gray-500">[Column 3]</th>
                <th class="px-4 py-3 text-left text-xs text-gray-500">[Status]</th>
                <th class="px-4 py-3 text-left text-xs text-gray-500">[Actions]</th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-b border-gray-100">
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3"><span class="bg-gray-200 px-2 py-1 text-xs text-gray-600">Active</span></td>
                <td class="px-4 py-3 text-sm"><span class="text-gray-500 mr-2">[Edit]</span><span class="text-gray-500">[Delete]</span></td>
              </tr>
              <tr class="border-b border-gray-100">
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3 text-sm text-gray-600">————</td>
                <td class="px-4 py-3"><span class="bg-gray-200 px-2 py-1 text-xs text-gray-600">Pending</span></td>
                <td class="px-4 py-3 text-sm"><span class="text-gray-500 mr-2">[Edit]</span><span class="text-gray-500">[Delete]</span></td>
              </tr>
            </tbody>
          </table>
          <div class="flex justify-between items-center p-4">
            <div class="text-sm text-gray-500">[แสดง 1-10 จาก 100 รายการ]</div>
            <div class="flex gap-1">
              <button class="wireframe-box px-3 py-1 text-sm text-gray-500">ก่อนหน้า</button>
              <button class="bg-gray-800 text-white px-3 py-1 text-sm">1</button>
              <button class="wireframe-box px-3 py-1 text-sm text-gray-500">2</button>
              <button class="wireframe-box px-3 py-1 text-sm text-gray-500">ถัดไป</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ====== สร้างหน้าเพิ่มเติมตาม Screen Inventory ====== -->
  <!-- ทำต่อสำหรับทุกหน้าที่อยู่ใน Epic นี้ -->

</body>
</html>
```
""",

    "design_system": """
คุณเป็น UX/UI Designer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Project Brief:
{project_brief}

## สิ่งที่ต้องส่งมอบ: design_system.md
สร้าง **Design System** ภาษาไทย

---
# Design System — {project_name}
**วันที่:** {today}

## 1. Brand Identity
| Element | Value | หมายเหตุ |
|---------|-------|--------|
| Brand Name | {project_name} | |
| Brand Tone | Professional, Friendly | |
| Language | Thai Primary | |

## 2. Color Palette
| Token | Hex | RGB | ใช้เมื่อ |
|-------|-----|-----|--------|
| `--color-primary-500` | #3B82F6 | 59, 130, 246 | CTA, Links |
| `--color-primary-700` | #1D4ED8 | 29, 78, 216 | Hover states |
| `--color-neutral-900` | #111827 | 17, 24, 39 | Body text |
| `--color-neutral-500` | #6B7280 | 107, 114, 128 | Secondary text |
| `--color-neutral-100` | #F3F4F6 | 243, 244, 246 | Background |
| `--color-success` | #10B981 | | Success states |
| `--color-warning` | #F59E0B | | Warning states |
| `--color-error` | #EF4444 | | Error states |

## 3. Typography
| Token | Font | Size | Weight | Line Height | ใช้เมื่อ |
|-------|------|------|--------|------------|--------|
| `--text-h1` | Sarabun / Inter | 32px | 700 | 1.25 | Page titles |
| `--text-h2` | Sarabun / Inter | 24px | 600 | 1.33 | Section headers |
| `--text-h3` | Sarabun / Inter | 20px | 600 | 1.4 | Card headers |
| `--text-body` | Sarabun / Inter | 16px | 400 | 1.5 | Body text |
| `--text-small` | Sarabun / Inter | 14px | 400 | 1.5 | Labels, meta |
| `--text-caption` | Sarabun / Inter | 12px | 400 | 1.6 | Captions |

## 4. Spacing Scale
| Token | Value | ใช้เมื่อ |
|-------|-------|--------|
| `--space-1` | 4px | Tight padding |
| `--space-2` | 8px | Component padding |
| `--space-4` | 16px | Default padding |
| `--space-6` | 24px | Section spacing |
| `--space-8` | 32px | Large sections |

## 5. Component Library
### Button
| Variant | State | คำอธิบาย |
|---------|-------|--------|
| Primary | Default / Hover / Disabled | CTA actions |
| Secondary | Default / Hover / Disabled | Secondary actions |
| Danger | Default / Hover | Destructive actions |
| Ghost | Default / Hover | Subtle actions |

### Form Elements
| Component | States | Validation |
|-----------|--------|-----------|
| Text Input | Default / Focus / Error / Disabled | Required, Min/Max length |
| Dropdown | Default / Open / Selected | Required |
| Checkbox | Unchecked / Checked / Indeterminate | - |
| Radio | Unselected / Selected | Required |

### Feedback Components
| Component | ใช้เมื่อ |
|-----------|--------|
| Toast / Snackbar | Success/Error messages |
| Modal / Dialog | Confirmation, Forms |
| Loading Spinner | Async operations |
| Empty State | No data |
| Error State | API errors |

## 6. Grid System
| Breakpoint | Width | Columns | Gutter |
|-----------|-------|---------|--------|
| Mobile | < 640px | 4 | 16px |
| Tablet | 640-1024px | 8 | 24px |
| Desktop | > 1024px | 12 | 32px |

## 7. Iconography
- **Library:** Heroicons / Phosphor Icons
- **Size:** 16px, 20px, 24px
- **Style:** Outline for actions, Solid for status

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "ux_guidelines": """
คุณเป็น UX/UI Designer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Design System:
{design_system_content}

## สิ่งที่ต้องส่งมอบ: ux_guidelines.md
สร้าง **UX Guidelines & Accessibility** ภาษาไทย

---
# UX Guidelines & Accessibility — {project_name}
**วันที่:** {today}

## 1. UX Principles
| หลักการ | คำอธิบาย | ตัวอย่าง |
|-------|---------|--------|
| Clarity | ทุก UI element ต้องชัดเจน ไม่คลุมเครือ | ปุ่ม "บันทึก" ชัดกว่า "OK" |
| Consistency | ใช้ pattern เดิมในทุกหน้า | Navigation ตำแหน่งเดิมเสมอ |
| Feedback | ระบบต้องตอบสนองทุก action | Loading indicator, success toast |
| Forgiveness | ผู้ใช้สามารถย้อนกลับได้ | Undo, Confirm before delete |
| Efficiency | ลด steps ให้ task สำเร็จ | Smart defaults, autofill |

## 2. Interaction Guidelines
### Forms
- Label ต้องอยู่ด้านบน input (ไม่ใช่ placeholder แทน label)
- Validation แบบ inline (แสดงทันทีที่ user ออกจาก field)
- Error message ต้องบอก "ทำอะไร" ไม่ใช่แค่ "ผิดพลาด"
- Required fields ระบุด้วย * และ legend

### Navigation
- Breadcrumb สำหรับ hierarchy > 2 levels
- Active state ต้องชัดเจน
- Back button พฤติกรรมสม่ำเสมอ

### Loading States
- < 100ms: ไม่ต้องแสดง indicator
- 100ms - 1s: Spinner เล็กๆ ใน component
- > 1s: Progress bar + cancel option
- > 5s: แจ้งเวลาโดยประมาณ

## 3. Accessibility (WCAG 2.1 AA)
| หมวด | Criterion | ข้อกำหนด |
|------|-----------|--------|
| Perceivable | 1.4.3 Color Contrast | Minimum 4.5:1 (body text) |
| Perceivable | 1.4.1 Color Only | ไม่ใช้สีเดียวสื่อความหมาย |
| Operable | 2.1.1 Keyboard | ทุก function ใช้ keyboard ได้ |
| Operable | 2.4.3 Focus Order | Focus order logical |
| Understandable | 3.1.1 Language | ระบุ lang="th" |
| Robust | 4.1.2 Name, Role | ARIA labels ครบ |

### ARIA Guidelines
```html
<!-- Form inputs -->
<label for="email">อีเมล *</label>
<input id="email" type="email" required aria-required="true"
       aria-describedby="email-error" />
<div id="email-error" role="alert" aria-live="polite">
  <!-- error message -->
</div>

<!-- Buttons -->
<button aria-label="ลบรายการ: ชื่อไอเทม">
  <svg aria-hidden="true">...</svg>
</button>
```

## 4. Mobile Guidelines
| หัวข้อ | ข้อกำหนด |
|------|--------|
| Touch targets | ขั้นต่ำ 44x44px |
| Font size | ขั้นต่ำ 16px (ป้องกัน auto-zoom บน iOS) |
| Viewport | responsive ทุก breakpoint |
| Swipe gestures | อธิบาย gesture ด้วย text/icon |

## 5. Error Handling UX
| สถานการณ์ | การแสดงผล | ตัวอย่าง message |
|---------|---------|----------------|
| Form validation | Inline error ใต้ field | "กรุณากรอกอีเมลให้ถูกต้อง" |
| API error | Toast notification | "เกิดข้อผิดพลาด กรุณาลองใหม่" |
| Not found | Full page 404 | "ไม่พบหน้าที่ต้องการ" |
| Unauthorized | Redirect to login | - |
| Network error | Banner + retry button | "ไม่มีการเชื่อมต่ออินเทอร์เน็ต" |

## 6. Content Guidelines
- ใช้ภาษาไทยเป็นหลัก ศัพท์เทคนิคทับศัพท์ได้
- ประโยคสั้น กระชับ ได้ใจความ
- CTA: กริยาการกระทำ เช่น "บันทึก", "ยืนยัน", "ดูรายละเอียด"
- Error: บอกสาเหตุ + วิธีแก้ไข

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",
}


def build_uxui_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับ Epic {context.get('epic_id', '')} โปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Wireframe, User Flow, Design System, Component, Breakpoint, Accessibility, UX Pattern\n\n"
    ctx = {"today": date.today().strftime("%Y-%m-%d"), **context}
    return lang + safe_format(template, ctx)
