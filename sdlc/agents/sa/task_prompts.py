"""SA Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "system_purpose": """
คุณเป็น Solution Architect ในทีม Multi-Agent SDLC

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}
- **เป้าหมาย:** {epic_goal}

## Project Brief:
{project_brief}

## Data Dictionary (BA):
{ba_data_dictionary}

## สิ่งที่ต้องส่งมอบ: system_purpose_goals.md
สร้าง **System Purpose & Goals** ภาษาไทย

---
# System Purpose & Goals — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. วัตถุประสงค์ระบบ
(อธิบาย WHY ระบบนี้มีอยู่ — ปัญหาที่แก้ไขและคุณค่าที่ส่งมอบ)

## 2. Vision Statement
> "ระบบ [ชื่อ] จะช่วยให้ [กลุ่มผู้ใช้] สามารถ [ทำอะไร] เพื่อ [ผลลัพธ์] โดย [วิธีการ]"

## 3. Quality Attribute Goals
| Quality Attribute | เป้าหมาย | ตัวชี้วัด |
|-----------------|---------|---------|
| Performance | Response time < 2s | P95 latency |
| Availability | 99.9% uptime | Monthly uptime |
| Security | Zero data breach | Pen test score |
| Scalability | 10x traffic growth | TPS |
| Maintainability | Easy to extend | Code coverage > 80% |

## 4. Architecture Principles
| หลักการ | คำอธิบาย | เหตุผล |
|-------|---------|------|
| API-First | ออกแบบ API ก่อน implement | เพื่อ decouple frontend/backend |
| Domain-Driven | แบ่ง domain ตาม business | ง่ายต่อการ maintain |
| Defense in Depth | หลาย layer of security | ลดความเสี่ยง |

## 5. Technology Vision
| Layer | Technology | เหตุผลที่เลือก |
|-------|-----------|--------------|
| Frontend | ... | ... |
| Backend | ... | ... |
| Database | ... | ... |
| Infrastructure | ... | ... |

## 6. Success Metrics
| Metric | Baseline | Target | วิธีวัด |
|--------|---------|--------|-------|
| ... | ... | ... | ... |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "scope_definition": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## System Purpose ที่สร้างไว้:
{system_purpose_content}

## สิ่งที่ต้องส่งมอบ: scope_in_out.md
สร้าง **In-Scope / Out-of-Scope** ภาษาไทย

---
# Scope Definition — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. In-Scope (สิ่งที่อยู่ในขอบเขต)
| # | Component/Feature | คำอธิบาย | Priority |
|---|------------------|---------|---------|
| 1 | ... | ... | P0 |

## 2. Out-of-Scope (สิ่งที่ไม่รวมใน Phase นี้)
| # | Component/Feature | เหตุผลที่ยกออก | แผน Phase ถัดไป |
|---|------------------|--------------|--------------|
| 1 | ... | ... | Phase 2 |

## 3. Boundary Diagram
```
┌─────────────────────────────────────┐
│           System Boundary           │
│                                     │
│  [Component A]  ←→  [Component B]  │
│                                     │
└─────────────────────────────────────┘
     ↑                      ↑
[External System]    [External System]
```

## 4. Integration Points
| System | Direction | Protocol | Data | In/Out Scope |
|--------|---------|---------|------|-------------|
| ... | Inbound | REST | ... | In |

## 5. Assumptions
1. ...

## 6. Constraints
| ประเภท | ข้อจำกัด | ผลกระทบต่อ Scope |
|-------|---------|----------------|
| Technical | ... | ... |
| Business | ... | ... |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "architecture": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Scope Definition:
{scope_content}

## สิ่งที่ต้องส่งมอบ: architecture_diagram.md
สร้าง **Architecture Diagram** แบบ Mermaid ภาษาไทย

ต้องมี 3 diagrams:

### Diagram 1: C4 Container Diagram (ภาพรวมระบบ)
```mermaid
C4Container
    title Container Diagram — {epic_title}

    Person(user, "ผู้ใช้งาน", "ใช้งานผ่าน Web Browser")
    Person(admin, "ผู้ดูแลระบบ", "จัดการระบบ")

    System_Boundary(sys, "{project_name}") {{
        Container(web, "Web Application", "React/Next.js", "หน้าต่างผู้ใช้")
        Container(api, "API Server", "Node.js/FastAPI", "Business Logic")
        ContainerDb(db, "Database", "PostgreSQL", "เก็บข้อมูลหลัก")
        Container(cache, "Cache", "Redis", "Session & Cache")
    }}

    System_Ext(ext, "External Service", "บริการภายนอก")

    Rel(user, web, "ใช้งานผ่าน", "HTTPS")
    Rel(web, api, "เรียก API", "REST/JSON")
    Rel(api, db, "อ่าน/เขียนข้อมูล", "SQL")
    Rel(api, cache, "Cache", "Redis Protocol")
    Rel(api, ext, "เชื่อมต่อ", "HTTPS")
```

### Diagram 2: Component Diagram (ภายใน API Layer)
```mermaid
graph TB
    subgraph "API Server"
        Router["Router Layer"]
        Auth["Auth Middleware"]
        Controller["Controllers"]
        Service["Services / Business Logic"]
        Repository["Repository / DAO"]
    end
    subgraph "Data Layer"
        DB[(Database)]
        Cache[(Redis)]
    end

    Router --> Auth --> Controller --> Service --> Repository
    Repository --> DB
    Service --> Cache
```

### Diagram 3: Deployment Architecture
```mermaid
graph LR
    subgraph "Client"
        Browser["Web Browser"]
    end
    subgraph "Cloud / Server"
        LB["Load Balancer"]
        App1["App Server 1"]
        App2["App Server 2"]
        DB[(Primary DB)]
        DBR[(Replica DB)]
    end

    Browser -->|HTTPS| LB
    LB --> App1 & App2
    App1 & App2 -->|Write| DB
    App1 & App2 -->|Read| DBR
    DB -->|Replication| DBR
```

---
ตอบด้วย Markdown (พร้อม mermaid blocks) เท่านั้น
""",

    "sequence_diagram": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture ที่สร้างไว้:
{architecture_content}

## สิ่งที่ต้องส่งมอบ: sequence_diagram.md
สร้าง **Sequence Diagrams** แบบ Mermaid ภาษาไทย

สร้าง sequence diagram สำหรับทุก main flow ใน Epic นี้ (อย่างน้อย 3 flows)

### Flow 1: [ชื่อ Flow หลัก เช่น User Login]
```mermaid
sequenceDiagram
    actor User as ผู้ใช้
    participant FE as Frontend
    participant API as API Server
    participant Auth as Auth Service
    participant DB as Database
    participant Cache as Redis

    User->>FE: กรอก username/password
    FE->>API: POST /api/auth/login
    API->>Auth: validate credentials
    Auth->>DB: SELECT user WHERE username=?
    DB-->>Auth: user record
    Auth-->>API: user valid
    API->>Cache: SET session token
    API-->>FE: 200 OK + JWT token
    FE-->>User: redirect to dashboard
```

### Flow 2: [ชื่อ Flow รอง เช่น Data CRUD]
```mermaid
sequenceDiagram
    (ทำต่อตามรูปแบบ)
```

### Flow 3: [ชื่อ Flow Error handling]
```mermaid
sequenceDiagram
    (แสดง error case ที่สำคัญ)
```

---
ตอบด้วย Markdown (พร้อม mermaid blocks) เท่านั้น
""",

    "activity_workflow": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture ที่สร้างไว้:
{architecture_content}

## สิ่งที่ต้องส่งมอบ: activity_workflow.md
สร้าง **Activity & Workflow Diagrams** แบบ Mermaid ภาษาไทย

### Workflow 1: [Main Business Process]
```mermaid
flowchart TD
    Start([เริ่มต้น]) --> A[ขั้นตอนที่ 1]
    A --> Decision{ตรวจสอบ?}
    Decision -->|ใช่| B[ขั้นตอนที่ 2]
    Decision -->|ไม่ใช่| C[แจ้งข้อผิดพลาด]
    B --> D[ขั้นตอนที่ 3]
    C --> End([สิ้นสุด])
    D --> End
```

### Workflow 2: [State Machine / Status Flow]
```mermaid
stateDiagram-v2
    [*] --> Draft : สร้างใหม่
    Draft --> Pending : ส่งอนุมัติ
    Pending --> Approved : อนุมัติ
    Pending --> Rejected : ปฏิเสธ
    Approved --> Active : เปิดใช้งาน
    Rejected --> Draft : แก้ไข
    Active --> Inactive : ปิดการใช้งาน
    Inactive --> [*]
```

### Workflow 3: [Error Handling / Retry Flow]
```mermaid
flowchart TD
    (ทำต่อตามรูปแบบสำหรับ flow อื่นๆ ที่เกี่ยวข้องกับ Epic)
```

---
ตอบด้วย Markdown (พร้อม mermaid blocks) เท่านั้น
""",

    "service_decomposition": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture ที่สร้างไว้:
{architecture_content}

## สิ่งที่ต้องส่งมอบ: service_decomposition.md
สร้าง **Service Decomposition** ภาษาไทย

---
# Service Decomposition — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Service Overview
```mermaid
graph LR
    subgraph "Frontend Services"
        FE_Auth["Auth Module"]
        FE_Main["Main Module"]
    end
    subgraph "Backend Services"
        SVC_Auth["Auth Service"]
        SVC_User["User Service"]
        SVC_Core["Core Business Service"]
    end
    subgraph "Infrastructure"
        DB[(Database)]
        Cache[(Cache)]
        Queue[(Message Queue)]
    end
```

## 2. Service Catalog
| Service ID | ชื่อ Service | บทบาท | Technology | Owner |
|-----------|------------|------|-----------|-------|
| SVC-001 | Auth Service | จัดการ Authentication | ... | Backend |
| SVC-002 | User Service | จัดการ User | ... | Backend |
| SVC-003 | ... | ... | ... | ... |

## 3. Service Details
### SVC-001: Auth Service
**บทบาท:** จัดการ Authentication & Authorization
**API Endpoints:**
- `POST /auth/login` — เข้าสู่ระบบ
- `POST /auth/logout` — ออกจากระบบ
- `POST /auth/refresh` — refresh token

**Dependencies:**
- Database: users table
- Cache: session storage

**SLA:** Response < 500ms | Availability 99.9%

### SVC-002: [Service Name]
(ทำต่อตามรูปแบบ)

## 4. Inter-Service Communication
| From | To | Protocol | Async/Sync | Data Format |
|------|----|---------|-----------|------------|
| Frontend | Auth Service | REST | Sync | JSON |
| Auth Service | DB | SQL | Sync | - |

## 5. Shared Libraries / Components
| Library | วัตถุประสงค์ | ใช้ใน |
|---------|------------|------|
| AuthMiddleware | ตรวจสอบ JWT | All services |
| Logger | Structured logging | All services |

---
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",

    "integration_landscape": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture ที่สร้างไว้:
{architecture_content}

## สิ่งที่ต้องส่งมอบ: integration_landscape.md
สร้าง **Integration Landscape Diagram** แบบ Mermaid + รายละเอียด

---
# Integration Landscape — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Integration Overview
```mermaid
graph TB
    subgraph "Internal Systems"
        Core["{project_name} Core"]
        subgraph "Microservices"
            Auth["Auth Service"]
            User["User Service"]
        end
    end
    subgraph "External Systems"
        Email["Email Provider\n(SendGrid/SES)"]
        SMS["SMS Gateway"]
        Payment["Payment Gateway"]
        OAuth["OAuth Provider\n(Google/Line)"]
    end

    Core <-->|"REST/JSON"| Auth
    Core <-->|"REST/JSON"| User
    Auth -->|"HTTPS"| OAuth
    User -->|"HTTPS"| Email
    User -->|"HTTPS"| SMS
    Core -->|"HTTPS"| Payment
```

## 2. Integration Catalog
| Int-ID | Source | Target | Type | Protocol | Auth Method | Data Format | SLA |
|--------|--------|--------|------|---------|------------|------------|-----|
| INT-001 | Core | Email Service | Outbound | HTTPS REST | API Key | JSON | Async |
| INT-002 | Core | OAuth | Outbound | OAuth 2.0 | Bearer | JSON | Sync <1s |

## 3. Integration Details
### INT-001: Email Service
**วัตถุประสงค์:** ส่ง transactional emails
**Trigger:** เมื่อผู้ใช้ลงทะเบียน / รีเซ็ต password
**Retry Policy:** 3 retries, exponential backoff
**Error Handling:** log + notify admin ถ้า fail 3 ครั้ง

## 4. Data Flow
| Integration | ข้อมูลที่ส่ง | ข้อมูลที่รับ | Frequency |
|------------|-----------|-----------|----------|
| INT-001 | email, template_id, data | delivery_status | Per event |

---
ตอบด้วย Markdown (พร้อม mermaid) เท่านั้น
""",

    "deployment_model": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture ที่สร้างไว้:
{architecture_content}

## สิ่งที่ต้องส่งมอบ: deployment_model.md
สร้าง **Deployment Model Diagram** แบบ Mermaid + รายละเอียด

---
# Deployment Model — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Environment Overview
| Environment | วัตถุประสงค์ | URL | สถานะ |
|------------|-----------|-----|------|
| Development | พัฒนาและทดสอบ local | localhost | Active |
| Staging | UAT & Pre-production | staging.example.com | Active |
| Production | ใช้งานจริง | app.example.com | Active |

## 2. Deployment Diagram
```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Load Balancer"
            LB["Nginx / ALB"]
        end
        subgraph "Application Tier"
            App1["App Instance 1\n(Docker Container)"]
            App2["App Instance 2\n(Docker Container)"]
        end
        subgraph "Data Tier"
            DB_Primary[(PostgreSQL Primary)]
            DB_Replica[(PostgreSQL Replica)]
            Cache[(Redis Cluster)]
        end
        subgraph "Storage"
            S3["Object Storage\n(Files/Images)"]
        end
    end
    subgraph "CI/CD"
        GitHub["GitHub Actions"]
        Registry["Container Registry"]
    end

    Internet --> LB
    LB --> App1 & App2
    App1 & App2 --> DB_Primary
    App1 & App2 --> DB_Replica
    App1 & App2 --> Cache
    App1 & App2 --> S3
    GitHub --> Registry --> App1 & App2
```

## 3. Infrastructure Specification
| Component | Spec | Count | Scaling |
|-----------|------|-------|---------|
| App Server | 2 vCPU, 4GB RAM | 2 | Horizontal |
| Database | 4 vCPU, 16GB RAM | 1+1 replica | Vertical |
| Cache | 2 vCPU, 4GB RAM | 1 | Vertical |

## 4. Containerization Strategy
| Service | Base Image | Port | Health Check |
|---------|-----------|------|-------------|
| Frontend | node:20-alpine | 3000 | GET /health |
| Backend | python:3.11-slim | 8000 | GET /health |
| Database | postgres:16 | 5432 | pg_isready |

## 5. Deployment Process
```
1. Developer push → GitHub
2. GitHub Actions trigger
3. Run tests + build Docker image
4. Push to Registry
5. Deploy to Staging (auto)
6. Run smoke tests
7. Deploy to Production (manual approval)
```

---
ตอบด้วย Markdown (พร้อม mermaid) เท่านั้น
""",

    "database_schema": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Architecture และ Data Dictionary:
{architecture_content}

## BA Data Dictionary:
{ba_data_dictionary}

## สิ่งที่ต้องส่งมอบ: database_schema.sql
สร้าง **SQL DDL** ครบถ้วนสำหรับ Epic นี้

-- ============================================================
-- Database Schema: {project_name} — Epic: {epic_title}
-- Generated: {today}
-- Database: PostgreSQL 16
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── ENUM Types ────────────────────────────────────────────
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended');
CREATE TYPE role_type AS ENUM ('admin', 'user', 'viewer');
-- (เพิ่ม enum ตาม domain)

-- ── Tables ───────────────────────────────────────────────

CREATE TABLE users (
    user_id     UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT       NOT NULL,
    role        role_type    NOT NULL DEFAULT 'user',
    status      user_status  NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ  -- soft delete
);

-- (สร้าง tables อื่นๆ ตาม domain ของ Epic)

-- ── Indexes ──────────────────────────────────────────────
CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_status   ON users(status) WHERE deleted_at IS NULL;

-- ── Triggers (updated_at auto-update) ────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Seed Data (ตัวอย่าง) ─────────────────────────────────
-- INSERT INTO users (username, email, password_hash, role) VALUES
-- ('admin', 'admin@example.com', crypt('password', gen_salt('bf')), 'admin');

-- ============================================================
-- End of Schema
-- ============================================================
""",

    "api_spec": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Sequence Diagram ที่สร้างไว้:
{sequence_content}

## สิ่งที่ต้องส่งมอบ: api_spec.yaml
สร้าง **OpenAPI 3.1 YAML** ครบถ้วนสำหรับ Epic นี้

openapi: 3.1.0
info:
  title: "{project_name} API — {epic_title}"
  description: |
    API Specification สำหรับ {epic_title} (Epic ID: {epic_id})
    สร้างโดย SA Agent วันที่ {today}
  version: "1.0.0"
  contact:
    name: Solution Architect Team

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://staging-api.example.com/v1
    description: Staging
  - url: http://localhost:8000/v1
    description: Development

security:
  - BearerAuth: []

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Error:
      type: object
      required: [code, message]
      properties:
        code:    { type: string }
        message: { type: string }

    Pagination:
      type: object
      properties:
        page:       { type: integer, minimum: 1 }
        per_page:   { type: integer, minimum: 1, maximum: 100 }
        total:      { type: integer }
        total_pages:{ type: integer }

    # ── Domain Schemas ──────────────────────────────────
    User:
      type: object
      properties:
        user_id:    { type: string, format: uuid }
        username:   { type: string }
        email:      { type: string, format: email }
        role:       { type: string, enum: [admin, user, viewer] }
        status:     { type: string, enum: [active, inactive] }
        created_at: { type: string, format: date-time }

    # (เพิ่ม schemas ตาม domain ของ Epic)

paths:
  # ── Authentication ──────────────────────────────────
  /auth/login:
    post:
      tags: [Authentication]
      summary: เข้าสู่ระบบ
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [username, password]
              properties:
                username: { type: string }
                password: { type: string, format: password }
      responses:
        '200':
          description: Login สำเร็จ
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token:  { type: string }
                  refresh_token: { type: string }
                  expires_in:    { type: integer }
                  user:
                    $ref: '#/components/schemas/User'
        '401':
          description: ข้อมูลไม่ถูกต้อง
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  # (เพิ่ม endpoints ครบทุก feature ของ Epic)
""",

    "sa_data_dictionary": """
คุณเป็น Solution Architect

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Database Schema ที่สร้างไว้:
{database_schema_content}

## สิ่งที่ต้องส่งมอบ: sa_data_dictionary.xlsx
ส่งออกข้อมูลเป็น **JSON** เพื่อแปลงเป็น Excel

```json
{{
  "sheets": [
    {{
      "name": "Tables",
      "headers": ["Table Name", "คำอธิบาย (TH)", "Primary Key", "Estimated Rows", "Partitioned", "หมายเหตุ"],
      "rows": [
        ["users", "ตารางเก็บข้อมูลผู้ใช้ระบบ", "user_id (UUID)", "10,000", "No", "Soft delete ด้วย deleted_at"],
        ["...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Columns",
      "headers": ["Table", "Column", "Data Type", "Nullable", "Default", "Index", "คำอธิบาย (TH)", "FK Reference"],
      "rows": [
        ["users", "user_id", "UUID", "No", "gen_random_uuid()", "PK", "รหัสผู้ใช้", "-"],
        ["users", "username", "VARCHAR(50)", "No", "-", "UNIQUE", "ชื่อผู้ใช้", "-"],
        ["users", "email", "VARCHAR(255)", "No", "-", "UNIQUE, IDX", "อีเมล", "-"],
        ["...", "...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Relationships",
      "headers": ["Parent Table", "Parent Column", "Child Table", "Child Column", "Cardinality", "On Delete", "คำอธิบาย"],
      "rows": [
        ["users", "user_id", "orders", "user_id", "1:N", "RESTRICT", "ผู้ใช้มีหลาย orders"],
        ["...", "...", "...", "...", "...", "...", "..."]
      ]
    }},
    {{
      "name": "Indexes",
      "headers": ["Table", "Index Name", "Type", "Columns", "Condition", "วัตถุประสงค์"],
      "rows": [
        ["users", "idx_users_email", "BTREE", "email", "-", "ค้นหา user ด้วย email"],
        ["users", "idx_users_status", "BTREE", "status", "deleted_at IS NULL", "Filter active users"],
        ["...", "...", "...", "...", "...", "..."]
      ]
    }}
  ]
}}
```
""",
}


def build_sa_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับ Epic {context.get('epic_id', '')} โปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลัก ทับศัพท์เทคนิคใช้ English ได้ เช่น Architecture, Microservice, API, Database Schema, Deployment, Container, Load Balancer, Cache\n\n"
    ctx = {"today": date.today().strftime("%Y-%m-%d"), **context}
    return lang + safe_format(template, ctx)
