"""
Role Output Schemas — per-role templates, file specs, required sections
Each role produces structured artifacts beyond plain markdown.
"""
from dataclasses import dataclass, field
from typing import Literal

OutputType = Literal["md", "xlsx", "sql", "py", "ts", "tsx", "yaml", "sh", "json", "docx", "mmd"]


@dataclass
class RoleOutputSpec:
    role: str
    required_sections: list[str]
    mermaid_types: list[str]            # mermaid diagram types this role should produce
    output_files: list[tuple[str, OutputType]]  # (filename_pattern, type)
    template: str                       # compressed format guide injected into system prompt
    token_budget: int = 4096


# ─── Per-Role Templates (compressed, ~300-400 tokens each) ───────────────────
# Goal: prescribe FORMAT precisely so model fills content, not invent structure.

_CEO_TEMPLATE = """
## OUTPUT FORMAT — CEO ROLE
Produce exactly these sections in order:

### 1. Strategic Decision
One-sentence directive.

### 2. Objectives (table)
| # | Objective | Success Metric | Priority |
|---|-----------|---------------|----------|

### 3. Scope & Constraints
- In scope: ...
- Out of scope: ...
- Constraints: budget, timeline, team

### 4. Decision Log (table)
| Decision | Rationale | Risk | Owner |
|----------|-----------|------|-------|

### 5. Next Steps
| Step | Owner | Deadline | Depends On |
|------|-------|----------|-----------|

**Files to produce:** strategic_brief.md, decision_log.xlsx
""".strip()

_PM_TEMPLATE = """
## OUTPUT FORMAT — PM ROLE
Produce exactly these sections:

### 1. Project Overview
Brief + tech stack + team size.

### 2. Work Breakdown (table)
| Story ID | Feature | Description | Complexity(S/M/L/XL) | FE Days | BE Days | QA Days | Total Days |
|----------|---------|-------------|----------------------|---------|---------|---------|-----------|

### 3. Manday Summary (table)
| Role | Total Days | FTE Needed |
|------|-----------|-----------|

### 4. Gantt Chart (Mermaid)
```mermaid
gantt
    title Project Timeline
    dateFormat YYYY-MM-DD
    section Phase 1
    ...
```

### 5. Risk Matrix (table)
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|

**Files to produce:** project_plan.md, estimation.xlsx, gantt.md
""".strip()

_BA_TEMPLATE = """
## OUTPUT FORMAT — BA ROLE
Produce exactly these sections:

### 1. System Overview
Domain + actors + core flows summary.

### 2. Use Cases (table)
| UC-ID | Actor | Goal | Trigger | Precondition | Main Flow | Alt Flow | Priority |
|-------|-------|------|---------|--------------|-----------|----------|---------|

### 3. Activity Flow (Mermaid)
```mermaid
flowchart TD
    A[Actor] --> B{Decision}
    ...
```

### 4. Sequence Diagram (Mermaid)
```mermaid
sequenceDiagram
    Actor->>System: action
    System-->>DB: query
    ...
```

### 5. Business Rules (table)
| Rule ID | Description | Source | Validation |
|---------|-------------|--------|-----------|

### 6. Acceptance Criteria
For each UC: Given / When / Then format.

**Files to produce:** requirements.md, usecases.xlsx, diagrams.md
""".strip()

_SA_TEMPLATE = """
## OUTPUT FORMAT — SA ROLE
Produce exactly these sections:

### 1. Architecture Overview
Pattern (monolith/microservice/etc.), rationale, tech stack.

### 2. Component Diagram (Mermaid)
```mermaid
graph TB
    Client --> API_GW[API Gateway]
    API_GW --> ServiceA
    ...
```

### 3. ER Diagram (Mermaid)
```mermaid
erDiagram
    ENTITY_A {
        int id PK
        string name
    }
    ENTITY_A ||--o{ ENTITY_B : "has"
```

### 4. Sequence Diagram (Mermaid) — critical flow
```mermaid
sequenceDiagram
    Client->>API: POST /resource
    ...
```

### 5. API Design Summary (table)
| Method | Endpoint | Auth | Request Body | Response | Notes |
|--------|----------|------|-------------|----------|-------|

### 6. OpenAPI Spec
```yaml
openapi: 3.0.0
info:
  title: ...
paths:
  /resource:
    post:
      ...
```

### 7. Database Schema (SQL)
```sql
CREATE TABLE table_name (
  id BIGSERIAL PRIMARY KEY,
  ...
);
```

**Files to produce:** architecture.md, api_spec.yaml, schema.sql, diagrams.md
""".strip()

_UXUI_TEMPLATE = """
## OUTPUT FORMAT — UXUI ROLE
Produce exactly these sections:

### 1. Screen Inventory (table)
| Screen ID | Name | Route | Actor | Description | Components |
|-----------|------|-------|-------|-------------|-----------|

### 2. User Flow Diagram (Mermaid)
```mermaid
flowchart TD
    Login --> Dashboard
    Dashboard --> |action| Feature
    ...
```

### 3. Component State Diagram (Mermaid) — for key component
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Loading: submit
    ...
```

### 4. UI Specifications (table)
| Component | Props | States | Behavior | Accessibility |
|-----------|-------|--------|----------|--------------|

### 5. Design Tokens
```json
{
  "colors": { "primary": "#...", "surface": "#..." },
  "spacing": { "base": "8px" },
  "typography": { "body": "14px/1.5" }
}
```

**Files to produce:** ux_flows.md, screen_inventory.xlsx, design_tokens.json
""".strip()

_DEV_TEMPLATE = """
## OUTPUT FORMAT — DEV ROLE
Produce complete, runnable code. Structure:

### 1. OpenAPI Spec
```yaml
openapi: 3.0.0
info:
  title: ...
  version: 1.0.0
paths:
  /api/resource:
    get:
      summary: ...
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Resource'
components:
  schemas:
    Resource:
      type: object
      properties:
        ...
```

### 2. Database Schema
```sql
-- migrations/001_init.sql
CREATE TABLE IF NOT EXISTS resource (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3. Backend Implementation
```python
# backend/routes/resource.py
from fastapi import APIRouter, Depends
...
```

### 4. Frontend Component
```tsx
// frontend/components/ResourceList.tsx
import React from 'react';
...
```

### 5. API Client
```typescript
// frontend/lib/api.ts
export const api = {
  getResource: async () => { ... }
}
```

### 6. Test Cases
```python
# tests/test_resource.py
def test_create_resource():
    ...
```

**Files to produce:** api_spec.yaml, schema.sql, backend/*.py, frontend/*.tsx, tests/*.py
""".strip()

_QA_TEMPLATE = """
## OUTPUT FORMAT — QA ROLE
Produce exactly these sections:

### 1. Test Strategy
Scope, approach (unit/integration/e2e), tools.

### 2. Test Cases (table)
| TC-ID | Feature | Scenario | Steps | Expected | Priority | Type |
|-------|---------|---------|-------|----------|----------|------|

### 3. Coverage Matrix (table)
| UC-ID | Use Case | TC-IDs | Coverage% | Risk |
|-------|---------|--------|-----------|------|

### 4. Defect Report (table) — if reviewing existing
| Bug-ID | Severity | Component | Description | Steps to Reproduce | Status |
|--------|----------|-----------|-------------|-------------------|--------|

### 5. Test Automation Script
```python
# tests/test_e2e.py
import pytest
def test_main_flow():
    ...
```

**Files to produce:** test_plan.md, test_cases.xlsx, tests/test_e2e.py
""".strip()

_DEVOPS_TEMPLATE = """
## OUTPUT FORMAT — DEVOPS ROLE
Produce complete, runnable configuration:

### 1. Deployment Architecture
Environment (dev/staging/prod), infra overview.

### 2. Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
...
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=...
  db:
    image: postgres:16
    ...
```

### 3. CI/CD Pipeline
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      ...
```

### 4. Kubernetes (if applicable)
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
...
```

### 5. Runbook
```bash
#!/bin/bash
# scripts/deploy.sh
set -euo pipefail
...
```

### 6. Environment Variables (template)
```bash
# .env.example
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=changeme
...
```

**Files to produce:** Dockerfile, docker-compose.yml, .github/workflows/deploy.yml, scripts/deploy.sh, .env.example
""".strip()


# ─── Role Output Specs ────────────────────────────────────────────────────────

ROLE_OUTPUT_SPECS: dict[str, RoleOutputSpec] = {
    "ceo": RoleOutputSpec(
        role="ceo",
        required_sections=["Strategic Decision", "Objectives", "Decision Log", "Next Steps"],
        mermaid_types=[],
        output_files=[
            ("strategic_brief.md", "md"),
            ("decision_log.xlsx",  "xlsx"),
        ],
        template=_CEO_TEMPLATE,
        token_budget=2048,
    ),
    "pm": RoleOutputSpec(
        role="pm",
        required_sections=["Work Breakdown", "Manday Summary", "Gantt Chart", "Risk Matrix"],
        mermaid_types=["gantt"],
        output_files=[
            ("project_plan.md",  "md"),
            ("estimation.xlsx",  "xlsx"),
            ("gantt.md",         "md"),
        ],
        template=_PM_TEMPLATE,
        token_budget=3000,
    ),
    "ba": RoleOutputSpec(
        role="ba",
        required_sections=["Use Cases", "Activity Flow", "Sequence Diagram", "Business Rules", "Acceptance Criteria"],
        mermaid_types=["flowchart", "sequenceDiagram"],
        output_files=[
            ("requirements.md", "md"),
            ("usecases.xlsx",   "xlsx"),
            ("diagrams.md",     "md"),
        ],
        template=_BA_TEMPLATE,
        token_budget=4096,
    ),
    "sa": RoleOutputSpec(
        role="sa",
        required_sections=["Architecture Overview", "Component Diagram", "ER Diagram", "API Design Summary", "OpenAPI Spec", "Database Schema"],
        mermaid_types=["graph", "erDiagram", "sequenceDiagram"],
        output_files=[
            ("architecture.md", "md"),
            ("api_spec.yaml",   "yaml"),
            ("schema.sql",      "sql"),
            ("diagrams.md",     "md"),
        ],
        template=_SA_TEMPLATE,
        token_budget=6000,
    ),
    "uxui": RoleOutputSpec(
        role="uxui",
        required_sections=["Screen Inventory", "User Flow Diagram", "Component State Diagram", "UI Specifications"],
        mermaid_types=["flowchart", "stateDiagram-v2"],
        output_files=[
            ("ux_flows.md",          "md"),
            ("screen_inventory.xlsx","xlsx"),
            ("design_tokens.json",   "json"),
        ],
        template=_UXUI_TEMPLATE,
        token_budget=3000,
    ),
    "dev": RoleOutputSpec(
        role="dev",
        required_sections=["OpenAPI Spec", "Database Schema", "Backend Implementation", "Frontend Component"],
        mermaid_types=[],
        output_files=[
            ("api_spec.yaml",       "yaml"),
            ("schema.sql",          "sql"),
            ("backend/routes.py",   "py"),
            ("frontend/App.tsx",    "tsx"),
            ("tests/test_api.py",   "py"),
        ],
        template=_DEV_TEMPLATE,
        token_budget=8192,
    ),
    "qa": RoleOutputSpec(
        role="qa",
        required_sections=["Test Strategy", "Test Cases", "Coverage Matrix"],
        mermaid_types=[],
        output_files=[
            ("test_plan.md",         "md"),
            ("test_cases.xlsx",      "xlsx"),
            ("tests/test_e2e.py",    "py"),
        ],
        template=_QA_TEMPLATE,
        token_budget=4096,
    ),
    "devops": RoleOutputSpec(
        role="devops",
        required_sections=["Docker Configuration", "CI/CD Pipeline", "Runbook", "Environment Variables"],
        mermaid_types=[],
        output_files=[
            ("Dockerfile",                        "sh"),
            ("docker-compose.yml",                "yaml"),
            (".github/workflows/deploy.yml",      "yaml"),
            ("scripts/deploy.sh",                 "sh"),
            (".env.example",                      "md"),
        ],
        template=_DEVOPS_TEMPLATE,
        token_budget=5000,
    ),
}


def get_role_template(role: str) -> str:
    """Return the compressed format template for a role (injected into system prompt)."""
    spec = ROLE_OUTPUT_SPECS.get(role)
    return spec.template if spec else ""


def get_role_token_budget(role: str) -> int:
    spec = ROLE_OUTPUT_SPECS.get(role)
    return spec.token_budget if spec else 4096
