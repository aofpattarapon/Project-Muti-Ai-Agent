"""DevOps Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "pipeline_diagram": """
คุณเป็น DevOps Engineer ในทีม Multi-Agent SDLC

## Project:
- **Project:** {project_name}
- **Tech Stack:** {tech_stack}

## สิ่งที่ต้องส่งมอบ: pipeline_diagram.md
สร้าง **CI/CD Pipeline Diagram** แบบ Mermaid ภาษาไทย

---
# CI/CD Pipeline — {project_name}
**วันที่:** {today}

## 1. Pipeline Overview
```mermaid
flowchart LR
    subgraph "Developer"
        DEV["👨‍💻 Developer\nLocal machine"]
    end

    subgraph "Source Control"
        GH["GitHub\nRepository"]
    end

    subgraph "CI — GitHub Actions"
        direction TB
        Trigger["🔔 Trigger\n(push/PR)"]
        Test["🧪 Test\nUnit + Integration"]
        Build["🏗️ Build\nDocker Image"]
        Scan["🔒 Security Scan\nTrivy"]
        Push["📦 Push\nContainer Registry"]
    end

    subgraph "CD — Staging"
        DeployStg["🚀 Deploy\nStaging"]
        SmokeTest["💨 Smoke Test"]
    end

    subgraph "CD — Production"
        Approval["✋ Manual\nApproval"]
        DeployProd["🚀 Deploy\nProduction"]
        Notify["📢 Notify\nSlack"]
    end

    DEV -->|"git push"| GH
    GH -->|"webhook"| Trigger
    Trigger --> Test
    Test -->|"pass"| Build
    Build --> Scan
    Scan -->|"pass"| Push
    Push --> DeployStg
    DeployStg --> SmokeTest
    SmokeTest -->|"pass"| Approval
    Approval -->|"approved"| DeployProd
    DeployProd --> Notify
```

## 2. Branch Strategy
```mermaid
gitGraph
    commit id: "init"
    branch develop
    checkout develop
    commit id: "feature-A"
    branch feature/login
    checkout feature/login
    commit id: "add login"
    commit id: "fix tests"
    checkout develop
    merge feature/login id: "merge login"
    branch release/1.0
    checkout release/1.0
    commit id: "bump version"
    checkout main
    merge release/1.0 id: "release 1.0" tag: "v1.0.0"
    checkout develop
    merge main
```

## 3. Pipeline Stages Detail
| Stage | Trigger | Duration | ผลลัพธ์ถ้าล้มเหลว |
|-------|---------|---------|----------------|
| Lint & Format | Push to any branch | 1 min | Block merge |
| Unit Tests | Push to any branch | 3 min | Block merge |
| Integration Tests | Push to develop/main | 5 min | Block merge |
| Docker Build | Push to develop/main | 3 min | Block deploy |
| Security Scan | Push to develop/main | 2 min | Block deploy (Critical only) |
| Deploy Staging | Merge to develop | 2 min | Alert team |
| Smoke Tests | After staging deploy | 2 min | Rollback |
| Deploy Production | Manual approval on main | 3 min | Auto rollback |

## 4. Environments & Branches
| Environment | Branch | Auto Deploy | Approval | URL |
|------------|--------|------------|---------|-----|
| Development | feature/* | No | - | localhost |
| Staging | develop | Yes | - | staging.example.com |
| Production | main | No | Required | app.example.com |

---
ตอบด้วย Markdown (พร้อม mermaid blocks) เท่านั้น
""",

    "dockerfile": """
คุณเป็น DevOps Engineer

## Project:
- **Project:** {project_name}
- **Tech Stack:** {tech_stack}

## สิ่งที่ต้องส่งมอบ: Dockerfile
สร้าง **Dockerfile** แบบ multi-stage สำหรับ production

ต้องมี 2 Dockerfiles:
1. `Dockerfile.frontend` — สำหรับ Next.js
2. `Dockerfile.backend` — สำหรับ FastAPI/Node.js

### Dockerfile.frontend (Next.js)
```dockerfile
# ============================================================
# Dockerfile.frontend — {project_name} Frontend
# Base: Node.js 20 Alpine | Multi-stage build
# ============================================================

# Stage 1: Dependencies
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Stage 3: Runner
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
  CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
```

### Dockerfile.backend (FastAPI)
```dockerfile
# ============================================================
# Dockerfile.backend — {project_name} Backend
# Base: Python 3.11 Slim | Multi-stage build
# ============================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runner
FROM python:3.11-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq5 curl \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup && \\
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \\
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### .dockerignore
```
# .dockerignore
.git
.gitignore
.env*
!.env.example
node_modules
__pycache__
*.pyc
*.pyo
.pytest_cache
.coverage
htmlcov
.next
dist
build
*.log
README*.md
docs/
tests/
```
""",

    "docker_compose": """
คุณเป็น DevOps Engineer

## Project:
- **Project:** {project_name}

## สิ่งที่ต้องส่งมอบ: docker-compose.yml
สร้าง **Docker Compose** สำหรับ local development + staging

```yaml
# docker-compose.yml — {project_name}
# Local Development & Staging
# Generated: {today}
#
# Usage:
#   docker compose up -d          # Start all services
#   docker compose up -d backend  # Start specific service
#   docker compose logs -f        # Follow logs
#   docker compose down -v        # Stop + remove volumes

version: "3.9"

# ── Shared Networks ───────────────────────────────────────────────
networks:
  app-network:
    driver: bridge

# ── Shared Volumes ────────────────────────────────────────────────
volumes:
  postgres_data:
  redis_data:

# ── Services ─────────────────────────────────────────────────────
services:

  # ── PostgreSQL Database ────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: {project_name}-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${{POSTGRES_DB:-appdb}}
      POSTGRES_USER: ${{POSTGRES_USER:-postgres}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD:-postgres}}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${{POSTGRES_USER:-postgres}}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Redis Cache ────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: {project_name}-redis
    restart: unless-stopped
    command: redis-server --requirepass ${{REDIS_PASSWORD:-redispass}}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Backend API ────────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.backend
    container_name: {project_name}-backend
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://${{POSTGRES_USER:-postgres}}:${{POSTGRES_PASSWORD:-postgres}}@postgres:5432/${{POSTGRES_DB:-appdb}}
      REDIS_URL: redis://:${{REDIS_PASSWORD:-redispass}}@redis:6379
      JWT_SECRET: ${{JWT_SECRET:-change-in-production}}
      JWT_EXPIRE_HOURS: ${{JWT_EXPIRE_HOURS:-24}}
      CORS_ORIGINS: '["http://localhost:3000"]'
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - app-network
    volumes:
      - ./backend:/app  # Hot reload in dev (remove in prod)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── Frontend App ───────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    container_name: {project_name}-frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - app-network

  # ── Nginx Reverse Proxy (optional for staging) ─────────────────
  nginx:
    image: nginx:alpine
    container_name: {project_name}-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    networks:
      - app-network
    profiles:
      - staging  # เฉพาะ staging: docker compose --profile staging up
```

### .env.example
```bash
# .env.example — Copy to .env and fill in values
# DO NOT commit actual .env file

# Database
POSTGRES_DB=appdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change_this_password

# Redis
REDIS_PASSWORD=change_this_redis_password

# Backend
JWT_SECRET=change_this_jwt_secret_to_something_long_and_random
JWT_EXPIRE_HOURS=24

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```
""",

    "github_actions": """
คุณเป็น DevOps Engineer

## Project:
- **Project:** {project_name}

## สิ่งที่ต้องส่งมอบ: .github/workflows/ci.yml
สร้าง **GitHub Actions CI/CD Workflow**

```yaml
# .github/workflows/ci.yml
# CI/CD Pipeline — {project_name}
# Generated: {today}
#
# Triggers:
#   - Push to main/develop
#   - Pull Request to main/develop

name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{{{ github.repository }}}}

jobs:
  # ── Job 1: Test Backend ─────────────────────────────────────────
  test-backend:
    name: Test Backend
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ./backend

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Lint (ruff)
        run: ruff check .

      - name: Format check (black)
        run: black --check .

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379
          JWT_SECRET: test-secret
        run: pytest tests/ -v --cov=app --cov-report=xml --cov-fail-under=80

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml

  # ── Job 2: Test Frontend ────────────────────────────────────────
  test-frontend:
    name: Test Frontend
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ./frontend

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Lint (ESLint)
        run: npm run lint

      - name: Type check
        run: npm run type-check

      - name: Run tests
        run: npm run test:coverage

      - name: Build
        run: npm run build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1

  # ── Job 3: Build & Push Docker Images ──────────────────────────
  build-push:
    name: Build & Push Images
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    if: github.event_name == 'push'

    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{{{ env.REGISTRY }}}}
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Extract metadata (backend)
        id: meta-backend
        uses: docker/metadata-action@v5
        with:
          images: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}-backend
          tags: |
            type=ref,event=branch
            type=sha,prefix=sha-

      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          file: ./backend/Dockerfile.backend
          push: true
          tags: ${{{{ steps.meta-backend.outputs.tags }}}}
          labels: ${{{{ steps.meta-backend.outputs.labels }}}}

      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile.frontend
          push: true
          tags: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}-frontend:${{{{ github.sha }}}}
          build-args: |
            NEXT_PUBLIC_API_URL=${{{{ secrets.NEXT_PUBLIC_API_URL }}}}

  # ── Job 4: Deploy to Staging ────────────────────────────────────
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [build-push]
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
      - name: Deploy to staging server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{{{ secrets.STAGING_HOST }}}}
          username: ${{{{ secrets.STAGING_USER }}}}
          key: ${{{{ secrets.STAGING_SSH_KEY }}}}
          script: |
            cd /opt/{project_name}
            docker compose pull
            docker compose up -d --no-deps backend frontend
            docker compose exec -T backend alembic upgrade head

      - name: Run smoke tests
        run: |
          sleep 30
          curl -f https://staging.example.com/api/health || exit 1

  # ── Job 5: Deploy to Production ────────────────────────────────
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [build-push]
    if: github.ref == 'refs/heads/main'
    environment: production  # Requires manual approval in GitHub

    steps:
      - name: Deploy to production server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{{{ secrets.PROD_HOST }}}}
          username: ${{{{ secrets.PROD_USER }}}}
          key: ${{{{ secrets.PROD_SSH_KEY }}}}
          script: |
            cd /opt/{project_name}
            docker compose pull
            docker compose up -d --no-deps --scale backend=2 backend frontend

      - name: Verify deployment
        run: |
          sleep 30
          curl -f https://app.example.com/api/health || exit 1

      - name: Notify success
        if: success()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{{{ secrets.SLACK_CHANNEL }}}}
          slack-message: "✅ {project_name} deployed to Production successfully! Commit: ${{{{ github.sha }}}}"
        env:
          SLACK_BOT_TOKEN: ${{{{ secrets.SLACK_BOT_TOKEN }}}}
```

**GitHub Secrets ที่ต้องตั้งค่า:**
| Secret | คำอธิบาย |
|--------|---------|
| `STAGING_HOST` | IP/hostname ของ staging server |
| `STAGING_USER` | SSH username |
| `STAGING_SSH_KEY` | SSH private key |
| `PROD_HOST` | IP/hostname ของ production server |
| `PROD_USER` | SSH username |
| `PROD_SSH_KEY` | SSH private key |
| `NEXT_PUBLIC_API_URL` | Production API URL |
| `SLACK_BOT_TOKEN` | สำหรับ notifications (optional) |
| `SLACK_CHANNEL` | Slack channel ID (optional) |
""",

    "deployment_guide": """
คุณเป็น DevOps Engineer

## Project:
- **Project:** {project_name}

## GitHub Actions:
{github_actions_content}

## สิ่งที่ต้องส่งมอบ: deployment_guide.md
สร้าง **Deployment Guide** ภาษาไทย ครบถ้วน

---
# Deployment Guide — {project_name}
**วันที่:** {today}

## 1. Prerequisites
| Tool | Version | ติดตั้ง |
|------|---------|-------|
| Docker | >= 24.x | docs.docker.com |
| Docker Compose | >= 2.x | (รวมใน Docker Desktop) |
| Git | >= 2.x | git-scm.com |

## 2. First-Time Server Setup

### 2.1 เตรียม Server (Ubuntu 22.04 LTS)
```bash
# อัปเดต packages
sudo apt update && sudo apt upgrade -y

# ติดตั้ง Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# ติดตั้ง Docker Compose
sudo apt install docker-compose-plugin -y

# ตรวจสอบ
docker --version
docker compose version
```

### 2.2 Clone โปรเจค
```bash
sudo mkdir -p /opt/{project_name}
sudo chown $USER:$USER /opt/{project_name}
cd /opt/{project_name}
git clone <repo-url> .
```

### 2.3 ตั้งค่า Environment
```bash
cp .env.example .env
nano .env  # แก้ไขค่าต่างๆ ให้เหมาะกับ production
```

### 2.4 Start Services
```bash
docker compose pull
docker compose up -d

# รัน migrations
docker compose exec backend alembic upgrade head

# ตรวจสอบ
docker compose ps
docker compose logs backend --tail=50
```

## 3. Regular Deployment (CI/CD Auto)

### Staging (Automatic)
```
git push origin develop
→ GitHub Actions trigger
→ Test → Build → Deploy Staging (auto)
```

### Production (Manual Approval)
```
git push origin main (หรือ merge PR)
→ GitHub Actions trigger
→ Test → Build → ⏸️ รอ Approval
→ Admin approve ใน GitHub
→ Deploy Production
```

## 4. Manual Deployment (Emergency)
```bash
# 1. ดึง image ใหม่
cd /opt/{project_name}
docker compose pull

# 2. Deploy (zero-downtime rolling)
docker compose up -d --no-deps backend
sleep 5
docker compose up -d --no-deps frontend

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. ตรวจสอบ
docker compose ps
curl http://localhost:8000/health
curl http://localhost:3000/api/health
```

## 5. Rollback
```bash
# ดู image versions ล่าสุด
docker images | grep {project_name}

# Rollback ไป version ก่อนหน้า
docker compose down
docker tag {project_name}-backend:previous {project_name}-backend:latest
docker compose up -d
```

## 6. Monitoring & Logs
```bash
# ดู logs real-time
docker compose logs -f

# ดู logs ของ service เฉพาะ
docker compose logs backend -f --tail=100
docker compose logs frontend -f --tail=100

# Resource usage
docker stats

# ตรวจสอบ health
docker compose ps
curl http://localhost:8000/health
```

## 7. Backup
```bash
# Backup database
docker compose exec postgres pg_dump -U postgres appdb > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260101.sql | docker compose exec -T postgres psql -U postgres appdb
```

## 8. Health Check Endpoints
| Service | Endpoint | Expected Response |
|---------|---------|-----------------|
| Backend | `GET /health` | `{{"status": "ok"}}` |
| Frontend | `GET /api/health` | `{{"status": "ok"}}` |
| Database | `pg_isready` | `accepting connections` |

## 9. Troubleshooting
| ปัญหา | วิธีตรวจสอบ | วิธีแก้ |
|------|-----------|-------|
| Container ไม่ start | `docker compose logs <service>` | ดู error log |
| DB connection failed | ตรวจสอบ DATABASE_URL ใน .env | แก้ไข connection string |
| Port already in use | `sudo lsof -i :8000` | Kill process หรือเปลี่ยน port |
| Out of disk space | `df -h` | ลบ old images: `docker image prune` |
| Memory high | `docker stats` | Scale down หรือเพิ่ม RAM |

---
*Deployment Guide สร้างโดย DevOps Agent — {today}*
เขียนเนื้อหาให้ครบถ้วนทุกหัวข้อ — ทดแทน placeholder ทั้งหมดด้วยเนื้อหาจริงที่เกี่ยวข้องกับโปรเจค {project_name} และ Epic นี้โดยตรง ห้ามใส่ "..." หรือตัวอย่างทั่วไป
""",
}


def build_devops_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับโปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลักสำหรับ description, config/code ใช้ English ได้เลย เช่น Pipeline, Docker, Container, Registry, Deploy, Rollback, Health Check, Secret\n\n"
    ctx = {
        "today": date.today().strftime("%Y-%m-%d"),
        "tech_stack": "ตามที่กำหนดในโปรเจค (Next.js + FastAPI หรือตามจริง)",
        **context,
    }
    return lang + safe_format(template, ctx)
