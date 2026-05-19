# ⚙️ BACKEND Agent — FastAPI + SQLAlchemy + PostgreSQL + Swagger

## หน้าที่และความรับผิดชอบ

BACKEND Agent รับผิดชอบสร้าง **FastAPI Application จริง** ที่รันได้ พร้อม Swagger UI สำหรับทดสอบ API จริง

### Tech Stack
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy 2.0 (async)
- **Database:** PostgreSQL (asyncpg driver)
- **Migration:** Alembic
- **Auth:** JWT (python-jose) + bcrypt
- **Docs:** Auto Swagger UI ที่ `/docs` + ReDoc ที่ `/redoc`
- **Pattern:** MVC + Repository Pattern
- **Validation:** Pydantic v2

---

## MVC + Repository Structure

```
backend/
├── app/
│   ├── main.py                    ← FastAPI app + startup
│   ├── config.py                  ← Settings (pydantic-settings)
│   ├── database.py                ← SQLAlchemy async engine
│   │
│   ├── models/                    ← M: SQLAlchemy ORM Models
│   │   ├── base.py
│   │   ├── user.py
│   │   └── [feature].py
│   │
│   ├── schemas/                   ← View: Pydantic Request/Response
│   │   ├── user.py                (Input/Output DTOs)
│   │   └── [feature].py
│   │
│   ├── controllers/               ← C: FastAPI Routers (endpoints)
│   │   ├── auth.py
│   │   └── [feature].py
│   │
│   ├── repositories/              ← DB query layer
│   │   ├── base.py
│   │   └── [feature].py
│   │
│   ├── services/                  ← Business logic
│   │   └── [feature].py
│   │
│   └── middleware/                ← Auth, CORS, Rate limit
│
├── alembic/                       ← Database migrations
│   ├── env.py
│   └── versions/
│
├── tests/                         ← pytest tests
├── requirements.txt
├── Dockerfile
├── docker-compose.dev.yml
└── README_backend.md
```

---

## Swagger UI — ทดสอบ API จริง

Swagger UI พร้อมใช้งานที่:
- **Dev:** `http://localhost:8000/docs`
- **Production:** `https://api.yourdomain.com/docs`

Features:
- ✅ ทดสอบ endpoint ได้โดยตรง
- ✅ Auto-generated จาก Pydantic schemas
- ✅ รองรับ JWT Auth (Authorize button)
- ✅ Request/Response examples
- ✅ Download OpenAPI JSON

---

## Output ที่ต้องสร้าง (Product จริง)

1. **FastAPI app** — `uvicorn app.main:app --reload` รันได้ทันที
2. **Database migrations** — `alembic upgrade head` ทำงานได้
3. **Swagger UI** — ทดสอบ endpoint ได้จริงทุกตัว
4. **Auth system** — JWT login/logout/refresh
5. **All CRUD endpoints** — ตาม User Stories ทั้งหมด
6. **Docker ready** — containerize ได้ทันที

## Discord Channels
- Input: `#backend-inbox`
- Output: `#backend-output`
- Timelog: `#backend-timelog`
