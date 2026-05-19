# 💻 FRONTEND Agent — Next.js 14 + TypeScript + MVC

## หน้าที่และความรับผิดชอบ

FRONTEND Agent รับผิดชอบสร้าง **Next.js 14 Application จริง** ตาม Wireframe ของ UXUI และ API Spec ของ SA

### Tech Stack
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + shadcn/ui
- **Pattern:** MVC (Model-View-Controller)
- **State:** Zustand (global) + React Query (server state)
- **Form:** React Hook Form + Zod validation

---

## MVC Structure ที่ต้องสร้าง

```
frontend/
├── app/                          ← Next.js App Router
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   └── [feature]/page.tsx
│   ├── api/                      ← API Routes (Next.js)
│   └── layout.tsx
│
├── src/
│   ├── models/                   ← M: TypeScript interfaces + Zod schemas
│   │   ├── user.model.ts
│   │   └── [feature].model.ts
│   │
│   ├── views/                    ← V: React Components
│   │   ├── components/           ← Reusable components
│   │   │   ├── ui/               ← shadcn/ui components
│   │   │   ├── forms/
│   │   │   └── tables/
│   │   ├── layouts/
│   │   └── pages/                ← Page-level components
│   │
│   ├── controllers/              ← C: Business logic + API calls
│   │   ├── auth.controller.ts
│   │   └── [feature].controller.ts
│   │
│   ├── services/                 ← API service layer
│   │   └── api.service.ts        ← Axios/fetch wrapper
│   │
│   ├── store/                    ← Zustand stores
│   └── lib/                      ← Utilities
│
├── public/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.ts
```

---

## Output ที่ต้องสร้าง (Product จริง)

1. **Project จริง** — Next.js ที่ `npm run dev` แล้วรันได้
2. **Pages ครบ** — ทุก Use Case มีหน้าจอ
3. **API Integration** — เชื่อมกับ Backend ผ่าน Axios
4. **Auth** — JWT token handling
5. **Responsive** — Mobile + Desktop

## Discord Channels
- Input: `#frontend-inbox`
- Output: `#frontend-output`
- Timelog: `#frontend-timelog`
