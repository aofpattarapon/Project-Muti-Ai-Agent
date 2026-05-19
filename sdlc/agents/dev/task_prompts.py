"""DEV Task Prompts — 1 task = 1 file output ภาษาไทย"""

PROMPTS = {
    "frontend_structure": """
คุณเป็น Senior Frontend Developer ในทีม SDLC

## Project: {project_name}
## Epic: {epic_id} — {epic_title}
## Goal: {epic_goal}

## Architecture (จาก SA):
{architecture_content}

## API Spec (จาก SA):
{sa_api_spec}

## Wireframe (จาก UXUI):
{uxui_wireframe}

## สิ่งที่ต้องส่งมอบ: frontend_structure.md
วางแผน **Frontend Structure** ให้ตรงกับ tech stack ที่ SA กำหนด — ถ้า SA ระบุ React/Next.js ใช้ React/Next.js, ถ้า SA ระบุ Vue ใช้ Vue
ห้ามเปลี่ยน tech stack เอง

---
# Frontend Structure — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Tech Stack
| Layer | Technology | Version | เหตุผล |
|-------|-----------|---------|------|
| Framework | Next.js / React | 14.x | SSR + App Router |
| Language | TypeScript | 5.x | Type safety |
| Styling | Tailwind CSS | 3.x | Utility-first |
| State | Zustand / Redux Toolkit | - | Global state |
| HTTP Client | Axios / Fetch | - | API calls |
| Form | React Hook Form + Zod | - | Validation |
| Testing | Vitest + Testing Library | - | Unit tests |

## 2. Project Structure
```
src/
├── app/                    # Next.js App Router
│   ├── (auth)/
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── register/
│   │       └── page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   └── [feature]/
│   │       └── page.tsx
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ui/                 # Base components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   └── Table.tsx
│   ├── forms/              # Form components
│   └── layouts/            # Layout components
├── hooks/                  # Custom hooks
├── lib/                    # Utilities, API client
├── stores/                 # State management
├── types/                  # TypeScript types
└── styles/
    └── globals.css
```

## 3. Component Inventory
| Component | Type | ใช้ใน | Props หลัก | State |
|-----------|------|------|-----------|-------|
| `<Button>` | UI | ทุกหน้า | variant, onClick, disabled | - |
| `<DataTable>` | UI | List pages | columns, data, pagination | local |
| `<LoginForm>` | Form | Login page | onSubmit | form state |
| `<DashboardLayout>` | Layout | All auth pages | children | - |
| `<[Feature]Page>` | Page | /feature | - | async |

## 4. Page Components
| Route | Component | Data Source | Auth Required |
|-------|-----------|------------|--------------|
| `/` | `HomePage` | Static | No |
| `/login` | `LoginPage` | - | No |
| `/dashboard` | `DashboardPage` | GET /api/dashboard | Yes |
| `/[feature]` | `FeaturePage` | GET /api/[feature] | Yes |

## 5. State Management
```typescript
// Zustand store structure
interface AppStore {{
  user: User | null;
  isAuthenticated: boolean;
  // feature state
  [feature]: {{
    items: Item[];
    pagination: Pagination;
    loading: boolean;
    error: string | null;
  }};
}}
```

## 6. API Integration Layer
```typescript
// lib/api.ts
const api = axios.create({{
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 10000,
}});

// Request interceptor — add JWT
api.interceptors.request.use((config) => {{
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${{token}}`;
  return config;
}});

// Response interceptor — handle 401
api.interceptors.response.use(
  (res) => res,
  (err) => {{
    if (err.response?.status === 401) redirect('/login');
    return Promise.reject(err);
  }}
);
```

## 7. TypeScript Types
```typescript
// types/index.ts — ประกาศ types ตาม API spec
export interface User {{
  user_id: string;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  status: 'active' | 'inactive';
  created_at: string;
}}

// (เพิ่ม types ตาม API spec ของ Epic)
```

---
ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",

    "frontend_code": """
คุณเป็น Senior Frontend Developer ในทีม SDLC

## Project: {project_name}
## Epic: {epic_id} — {epic_title}
## Goal: {epic_goal}
{rework_context}

## Tech Stack (จาก SA + Frontend Structure):
{frontend_structure_content}

## Wireframe/UI Design (จาก UXUI):
{uxui_wireframe}

## API Spec (จาก SA):
{sa_api_spec}

## สิ่งที่ต้องส่งมอบ
สร้าง **source code จริงที่รันได้** สำหรับ Epic นี้ ใช้ tech stack ที่ SA กำหนด

**กฎสำคัญ:**
1. เขียน code จริงทุกไฟล์ — ครบ ไม่มี placeholder เช่น "// TODO" หรือ "// implement later"
2. ใช้ format: `=== FILE: path/to/file.ext ===` ก่อนทุกไฟล์
3. path ต้องเป็น relative path จาก root ของ frontend เช่น `src/app/page.tsx`
4. code ต้องใช้งานได้จริง — import ถูกต้อง, types ครบ, error handling มี
5. ทุก component ต้องเกี่ยวข้องกับ Epic นี้โดยตรง — ไม่ใส่ feature ที่ไม่ได้ร้องขอ

**ตัวอย่าง format (ใช้ format นี้เท่านั้น):**
=== FILE: src/app/layout.tsx ===
import type {{ Metadata }} from 'next'
// ... code จริง ...

=== FILE: src/components/ui/Button.tsx ===
// ... code จริง ...

เริ่ม output ด้วย `=== FILE:` ทันที ไม่มี prefix text อื่น

---
# Frontend Implementation — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Component Implementations

### Button Component (Base UI)
```typescript
// components/ui/Button.tsx
import React from 'react';
import clsx from 'clsx';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {{
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: React.ReactNode;
}}

const variantStyles = {{
  primary:   'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300',
  secondary: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
  danger:    'bg-red-600 text-white hover:bg-red-700',
  ghost:     'text-gray-600 hover:bg-gray-100',
}};

const sizeStyles = {{
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}};

export function Button({{
  variant = 'primary', size = 'md', loading = false,
  className, children, disabled, ...props
}}: ButtonProps) {{
  return (
    <button
      className={{clsx(
        'inline-flex items-center justify-center rounded-lg font-medium',
        'transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variantStyles[variant], sizeStyles[size], className
      )}}
      disabled={{disabled || loading}}
      {{...props}}
    >
      {{loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      )}}
      {{children}}
    </button>
  );
}}
```

### Login Page
```typescript
// app/(auth)/login/page.tsx
'use client';
import {{ useForm }} from 'react-hook-form';
import {{ zodResolver }} from '@hookform/resolvers/zod';
import {{ z }} from 'zod';
import {{ Button }} from '@/components/ui/Button';
import {{ useAuthStore }} from '@/stores/auth';
import {{ useRouter }} from 'next/navigation';

const loginSchema = z.object({{
  username: z.string().min(1, 'กรุณากรอก Username'),
  password: z.string().min(6, 'Password ต้องมีอย่างน้อย 6 ตัวอักษร'),
}});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {{
  const router = useRouter();
  const {{ login, loading, error }} = useAuthStore();

  const {{ register, handleSubmit, formState: {{ errors }} }} = useForm<LoginFormData>({{
    resolver: zodResolver(loginSchema),
  }});

  const onSubmit = async (data: LoginFormData) => {{
    const success = await login(data.username, data.password);
    if (success) router.push('/dashboard');
  }};

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-xl shadow-sm p-8 border border-gray-100">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 text-center">เข้าสู่ระบบ</h1>

        {{error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600" role="alert">
            {{error}}
          </div>
        )}}

        <form onSubmit={{handleSubmit(onSubmit)}} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
              Username <span className="text-red-500">*</span>
            </label>
            <input
              id="username"
              type="text"
              {{...register('username')}}
              className={{`w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent
                ${{errors.username ? 'border-red-300' : 'border-gray-300'}}`}}
              aria-invalid={{!!errors.username}}
              aria-describedby="username-error"
            />
            {{errors.username && (
              <p id="username-error" className="mt-1 text-xs text-red-500">{{errors.username.message}}</p>
            )}}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password <span className="text-red-500">*</span>
            </label>
            <input
              id="password"
              type="password"
              {{...register('password')}}
              className={{`w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent
                ${{errors.password ? 'border-red-300' : 'border-gray-300'}}`}}
            />
            {{errors.password && (
              <p className="mt-1 text-xs text-red-500">{{errors.password.message}}</p>
            )}}
          </div>

          <Button type="submit" className="w-full" loading={{loading}}>
            เข้าสู่ระบบ
          </Button>
        </form>
      </div>
    </div>
  );
}}
```

## 2. Auth Store (Zustand)
```typescript
// stores/auth.ts
import {{ create }} from 'zustand';
import {{ persist }} from 'zustand/middleware';
import api from '@/lib/api';

interface AuthState {{
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({{
      user: null, token: null, loading: false, error: null,
      login: async (username, password) => {{
        set({{ loading: true, error: null }});
        try {{
          const {{ data }} = await api.post('/auth/login', {{ username, password }});
          set({{ user: data.user, token: data.access_token, loading: false }});
          return true;
        }} catch (err: any) {{
          set({{ error: err.response?.data?.message || 'เกิดข้อผิดพลาด', loading: false }});
          return false;
        }}
      }},
      logout: () => set({{ user: null, token: null }}),
    }}),
    {{ name: 'auth-storage', partialize: (s) => ({{ token: s.token }}) }}
  )
);
```

## 3. สรุป Files ที่ต้องสร้าง
| File | ประเภท | หมายเหตุ |
|------|-------|--------|
| `components/ui/Button.tsx` | Base component | Reusable |
| `app/(auth)/login/page.tsx` | Page | Auth flow |
| `stores/auth.ts` | State | Zustand |
| `lib/api.ts` | Utility | Axios instance |
| (ทำต่อตาม Epic scope) | ... | ... |

""",

    "backend_structure": """
คุณเป็น Full-Stack Developer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## API Spec จาก SA:
{sa_api_spec}

## Database Schema จาก SA:
{sa_database_schema}

## สิ่งที่ต้องส่งมอบ: backend_structure.md
สร้าง **Backend Structure & API Plan** ภาษาไทย

---
# Backend Structure — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Tech Stack
| Layer | Technology | Version | เหตุผล |
|-------|-----------|---------|------|
| Runtime | Python / Node.js | 3.11 / 20 | ... |
| Framework | FastAPI / Express | - | OpenAPI auto-gen |
| ORM | SQLAlchemy / Prisma | - | Type-safe DB |
| Database | PostgreSQL | 16 | Primary store |
| Cache | Redis | 7 | Session/Cache |
| Auth | JWT + bcrypt | - | Stateless auth |
| Testing | Pytest / Jest | - | Unit + integration |

## 2. Project Structure (FastAPI example)
```
backend/
├── app/
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Settings (Pydantic BaseSettings)
│   ├── database.py         # DB connection & session
│   ├── deps.py             # Dependency injection
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── [feature].py
│   ├── schemas/            # Pydantic request/response schemas
│   │   ├── user.py
│   │   └── [feature].py
│   ├── routers/            # API route handlers
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── [feature].py
│   ├── services/           # Business logic
│   │   ├── auth_service.py
│   │   └── [feature]_service.py
│   └── utils/              # Helpers
│       ├── security.py
│       └── pagination.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_[feature].py
├── alembic/                # DB migrations
├── requirements.txt
└── .env.example
```

## 3. API Endpoints Plan
| Method | Path | Handler | Auth | สรุป |
|--------|------|---------|------|-----|
| POST | /api/v1/auth/login | auth.login | No | เข้าสู่ระบบ |
| POST | /api/v1/auth/logout | auth.logout | JWT | ออกจากระบบ |
| GET | /api/v1/users/me | users.get_me | JWT | ดูข้อมูลตัวเอง |
| GET | /api/v1/[feature] | [feature].list | JWT | ดูรายการ |
| POST | /api/v1/[feature] | [feature].create | JWT | สร้างใหม่ |
| GET | /api/v1/[feature]/{{id}} | [feature].get | JWT | ดูรายละเอียด |
| PUT | /api/v1/[feature]/{{id}} | [feature].update | JWT | แก้ไข |
| DELETE | /api/v1/[feature]/{{id}} | [feature].delete | JWT+Admin | ลบ |

## 4. Dependency Injection
```python
# deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import SessionLocal
from .utils.security import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(token)
    user = db.query(User).filter(User.user_id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user
```

## 5. Error Handling
| HTTP Status | เหตุการณ์ | Response |
|------------|---------|---------|
| 400 | Validation error | `{{code, message, details}}` |
| 401 | Unauthorized | `{{code: "UNAUTHORIZED"}}` |
| 403 | Forbidden | `{{code: "FORBIDDEN"}}` |
| 404 | Not found | `{{code: "NOT_FOUND"}}` |
| 409 | Conflict (duplicate) | `{{code: "CONFLICT"}}` |
| 500 | Server error | `{{code: "INTERNAL_ERROR"}}` |

---
ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",

    "backend_code": """
คุณเป็น Senior Backend Developer ในทีม SDLC

## Project: {project_name}
## Epic: {epic_id} — {epic_title}
## Goal: {epic_goal}
{rework_context}

## Backend Structure (จาก DEV planning):
{backend_structure_content}

## API Spec (จาก SA):
{sa_api_spec}

## Database Schema (จาก SA):
{sa_database_schema}

## สิ่งที่ต้องส่งมอบ
สร้าง **source code จริงที่รันได้** สำหรับ backend ของ Epic นี้ ใช้ tech stack ที่ SA กำหนด

**กฎสำคัญ:**
1. เขียน code จริงทุกไฟล์ — ครบ ไม่มี placeholder เช่น "# TODO" หรือ "pass # implement"
2. ใช้ format: `=== FILE: path/to/file.ext ===` ก่อนทุกไฟล์
3. path ต้องเป็น relative path จาก root ของ backend เช่น `app/routers/auth.py`
4. implement ทุก endpoint ที่อยู่ใน API spec — validation, error handling, DB queries ครบ
5. รวม requirements.txt หรือ package.json ด้วยเสมอ
6. code ต้องเกี่ยวข้องกับ Epic นี้ตาม API spec จริง — ไม่ใส่ feature ที่ไม่ได้ร้องขอ

**ตัวอย่าง format:**
=== FILE: app/main.py ===
# ... code จริง ...

=== FILE: app/routers/auth.py ===
# ... code จริง ...

=== FILE: requirements.txt ===
fastapi==0.111.0
# ...

เริ่ม output ด้วย `=== FILE:` ทันที ไม่มี prefix text อื่น

---
# Backend Implementation — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Main Application
```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import auth, users
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="{project_name} API",
    description="API for {epic_title}",
    version="1.0.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,  prefix="/api/v1/auth",  tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
# (เพิ่ม routers ตาม Epic)
```

## 2. Auth Router
```python
# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..deps import get_db
from ..schemas.auth import LoginRequest, TokenResponse
from ..services.auth_service import AuthService

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    result = service.authenticate(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result
```

## 3. Auth Service
```python
# app/services/auth_service.py
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from ..config import settings
from ..models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, db):
        self.db = db

    def authenticate(self, username: str, password: str):
        user = self.db.query(User).filter(User.username == username).first()
        if not user or not pwd_context.verify(password, user.password_hash):
            return None
        token = self._create_token({{"sub": str(user.user_id), "role": user.role}})
        return {{"access_token": token, "token_type": "bearer", "user": user}}

    def _create_token(self, data: dict) -> str:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
        return jwt.encode(
            {{**data, "exp": expire}},
            settings.JWT_SECRET, algorithm="HS256"
        )
```

## 4. Pydantic Schemas
```python
# app/schemas/auth.py
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

# app/schemas/user.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID

class UserResponse(BaseModel):
    user_id: UUID
    username: str
    email: EmailStr
    role: str
    status: str
    created_at: datetime

    model_config = {{"from_attributes": True}}
```

## 5. SQLAlchemy Model
```python
# app/models/user.py
from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from ..database import Base

class User(Base):
    __tablename__ = "users"

    user_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username     = Column(String(50), unique=True, nullable=False)
    email        = Column(String(255), unique=True, nullable=False)
    password_hash= Column(String, nullable=False)
    role         = Column(Enum("admin", "user", "viewer", name="role_type"), default="user")
    status       = Column(Enum("active", "inactive", name="user_status"), default="active")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at   = Column(DateTime(timezone=True), nullable=True)
```

## 6. Config
```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL:  str = "postgresql://user:pass@localhost/dbname"
    REDIS_URL:     str = "redis://localhost:6379"
    JWT_SECRET:    str = "change-this-in-production"
    JWT_EXPIRE_HOURS: int = 24
    CORS_ORIGINS:  list = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
```

---
ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",

    "unit_tests": """
คุณเป็น Senior QA/Developer ในทีม SDLC

## Project: {project_name}
## Epic: {epic_id} — {epic_title}
{rework_context}

## Frontend Code (manifest):
{frontend_code_content}

## Backend Code (manifest):
{backend_code_content}

## สิ่งที่ต้องส่งมอบ
สร้าง **unit test files จริง** ที่รันได้ ครอบคลุม frontend + backend ของ Epic นี้

**กฎสำคัญ:**
1. เขียน test code จริงทุกไฟล์ — test cases ครอบคลุม happy path + error cases
2. ใช้ format: `=== FILE: path/to/test_file.ext ===` ก่อนทุกไฟล์
3. Backend: ใช้ testing framework ตาม tech stack (pytest / jest)
4. Frontend: ใช้ Vitest + Testing Library (หรือ framework ที่ระบุใน structure)
5. ทุก test ต้องเกี่ยวข้องกับ code จริงของ Epic — test function/class ที่มีใน codebase

**ตัวอย่าง format:**
=== FILE: tests/test_auth.py ===
# ... test code จริง ...

=== FILE: src/components/ui/Button.test.tsx ===
// ... test code จริง ...

เริ่ม output ด้วย `=== FILE:` ทันที

---
# Unit Tests — {epic_title}
**Epic:** {epic_id} | **วันที่:** {today}

## 1. Backend Tests (Pytest)

### Test: Auth Service
```python
# tests/test_auth_service.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.auth_service import AuthService

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def auth_service(mock_db):
    return AuthService(mock_db)

class TestAuthenticate:
    def test_login_success(self, auth_service, mock_db):
        # Arrange
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_user.password_hash = "$2b$12$..."
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.pwd_context.verify", return_value=True):
            # Act
            result = auth_service.authenticate("testuser", "password123")

        # Assert
        assert result is not None
        assert "access_token" in result

    def test_login_wrong_password(self, auth_service, mock_db):
        mock_user = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.pwd_context.verify", return_value=False):
            result = auth_service.authenticate("testuser", "wrongpass")

        assert result is None

    def test_login_user_not_found(self, auth_service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = auth_service.authenticate("unknown", "password")
        assert result is None
```

### Test: API Endpoints (Integration)
```python
# tests/test_auth_router.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    response = client.post("/api/v1/auth/login", json={{
        "username": "testuser",
        "password": "password123"
    }})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_invalid_credentials():
    response = client.post("/api/v1/auth/login", json={{
        "username": "wrong",
        "password": "wrong"
    }})
    assert response.status_code == 401

def test_protected_endpoint_without_token():
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
```

## 2. Frontend Tests (Vitest + Testing Library)

### Test: Button Component
```typescript
// components/ui/Button.test.tsx
import {{ render, screen, fireEvent }} from '@testing-library/react';
import {{ describe, it, expect, vi }} from 'vitest';
import {{ Button }} from './Button';

describe('Button', () => {{
  it('renders correctly', () => {{
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click me');
  }});

  it('calls onClick when clicked', () => {{
    const onClick = vi.fn();
    render(<Button onClick={{onClick}}>Click</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  }});

  it('shows loading spinner when loading', () => {{
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  }});

  it('disables button when disabled prop', () => {{
    render(<Button disabled>Click</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  }});
}});
```

### Test: Login Form
```typescript
// app/(auth)/login/login.test.tsx
import {{ render, screen, fireEvent, waitFor }} from '@testing-library/react';
import {{ describe, it, expect, vi }} from 'vitest';
import LoginPage from './page';

vi.mock('@/stores/auth', () => ({{
  useAuthStore: () => ({{
    login: vi.fn().mockResolvedValue(true),
    loading: false,
    error: null,
  }}),
}}));

describe('LoginPage', () => {{
  it('renders login form', () => {{
    render(<LoginPage />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  }});

  it('shows validation error for empty fields', async () => {{
    render(<LoginPage />);
    fireEvent.click(screen.getByRole('button', {{ name: /เข้าสู่ระบบ/i }}));
    await waitFor(() => {{
      expect(screen.getByText(/กรุณากรอก username/i)).toBeInTheDocument();
    }});
  }});
}});
```

## 3. Test Coverage Summary
| Module | Statements | Branches | Functions | Lines |
|--------|-----------|---------|----------|-------|
| auth_service.py | > 90% | > 85% | 100% | > 90% |
| auth_router.py | > 85% | > 80% | 100% | > 85% |
| Button.tsx | > 95% | > 90% | 100% | > 95% |
| LoginPage.tsx | > 80% | > 75% | > 80% | > 80% |
| **Target** | **> 80%** | **> 75%** | **> 90%** | **> 80%** |

---
ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",

    "dev_readme": """
คุณเป็น Full-Stack Developer

## Epic:
- **Epic ID:** {epic_id}
- **ชื่อ:** {epic_title}

## Unit Tests Summary:
{unit_tests_content}

## สิ่งที่ต้องส่งมอบ: README_dev.md
สร้าง **Developer README** ภาษาไทย ครบถ้วนสำหรับ setup และ run โปรเจค

---
# Developer Guide — {project_name}
**Epic:** {epic_title} | **อัปเดต:** {today}

## Prerequisites
| Tool | Version | Download |
|------|---------|----------|
| Node.js | >= 20.x | nodejs.org |
| Python | >= 3.11 | python.org |
| PostgreSQL | >= 16 | postgresql.org |
| Redis | >= 7 | redis.io |
| Docker | >= 24 | docker.com |

## Quick Start (Docker Compose)
```bash
# 1. Clone โปรเจค
git clone <repo-url>
cd {project_name}

# 2. Copy environment variables
cp .env.example .env
# แก้ไข .env ตามค่าที่ต้องการ

# 3. Start ทุก services
docker compose up -d

# 4. รัน migrations
docker compose exec backend alembic upgrade head

# 5. เปิด browser
open http://localhost:3000
```

## Manual Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\\Scripts\\activate
pip install -r requirements.txt

# Setup environment
cp .env.example .env

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
# API Docs: http://localhost:8000/api/docs
```

### Frontend
```bash
cd frontend
npm install

# Setup environment
cp .env.local.example .env.local

# Start dev server
npm run dev
# http://localhost:3000
```

## Environment Variables
### Backend (.env)
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key-here
JWT_EXPIRE_HOURS=24
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Running Tests
```bash
# Backend tests
cd backend
pytest tests/ -v --cov=app --cov-report=html
# Report: htmlcov/index.html

# Frontend tests
cd frontend
npm run test           # run once
npm run test:watch     # watch mode
npm run test:coverage  # coverage report
```

## Project Structure
```
{project_name}/
├── frontend/           # Next.js app
├── backend/            # FastAPI app
├── docker-compose.yml
├── .env.example
└── README_dev.md
```

## Common Issues
| ปัญหา | สาเหตุ | วิธีแก้ |
|------|-------|-------|
| Cannot connect to DB | PostgreSQL ไม่ได้ run | `docker compose up -d postgres` |
| JWT invalid | Secret key ไม่ตรง | ตรวจสอบ JWT_SECRET ใน .env |
| CORS error | Origins ไม่ตรง | เพิ่ม origin ใน CORS_ORIGINS |
| Module not found | venv ไม่ active | `source venv/bin/activate` |

## Git Workflow
```bash
git checkout -b feature/{epic_id}-{task_description}
# พัฒนา...
git commit -m "feat({epic_id}): add [description]"
git push origin feature/{epic_id}-{task_description}
# สร้าง Pull Request
```

---
ตอบด้วย Markdown เท่านั้น ไม่ต้องใส่ JSON wrapper
""",
}


def build_dev_task_prompt(task_type: str, context: dict) -> str:
    from shared.output_formatter import safe_format
    from datetime import date
    template = PROMPTS.get(task_type, "")
    if not template:
        return f"สร้าง {task_type} สำหรับ Epic {context.get('epic_id', '')} โปรเจค {context.get('project_name', '')}"
    lang = "\n> **Language:** ภาษาไทยเป็นหลักสำหรับ description/comment, code และ technical terms ใช้ English ได้เลย เช่น Component, State, Hook, Middleware, Repository, Controller, Service\n\n"

    _feedback = (context.get("role_feedback") or "").strip()
    _rev = int(context.get("revision_count") or 0)
    if _rev > 0 and _feedback:
        _rework = (
            f"\n## ⚠️ Rework Context — Revision #{_rev}\n"
            f"QA execution failed. แก้ไข code ตาม feedback ด้านล่าง:\n\n"
            f"```\n{_feedback}\n```\n\n"
            f"**สำคัญ:** เขียน files ทั้งหมดที่ได้รับ feedback ใหม่ให้ครบ\n"
        )
    elif _rev > 0:
        _rework = f"\n## ⚠️ Revision #{_rev} — แก้ไขตาม QA feedback\n"
    else:
        _rework = ""

    ctx = {"today": date.today().strftime("%Y-%m-%d"), "rework_context": _rework, **context}
    return lang + safe_format(template, ctx)
