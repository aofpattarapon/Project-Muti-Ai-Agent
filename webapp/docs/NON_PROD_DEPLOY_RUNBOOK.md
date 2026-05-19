# Non-Production Deploy Runbook

## 1. Goal

Provide a simple, repeatable non-production deployment path for the MVP pilot application.

## 2. Target Scope

This runbook covers:
- install dependencies
- provide environment configuration
- build the app
- start the app
- verify core routes

## 3. Environment Requirements

- Node.js 20+
- npm
- writable filesystem for local SQLite database
- `.env.local` with `SESSION_SECRET`

## 4. Setup Steps

1. Clone or copy the repository
2. Install dependencies:
   - `npm install`
3. Create environment file:
   - copy `.env.example` to `.env.local`
4. Set `SESSION_SECRET`
5. Ensure `data/` is writable

## 5. Verification Before Start

- `npm run lint`
- `npm run test`
- `npm run test:e2e`
- `npm run build`

## 6. Run Options

### Option A: Production-like local start
- `./scripts/start-non-prod.sh`

### Option B: Manual start
- `npm install`
- `npm run lint`
- `npm run test`
- `npm run build`
- `HOST=0.0.0.0 PORT=3000 npm run start`

### Option C: PM2
- install PM2 if needed:
  - `npm install -g pm2`
- start:
  - `pm2 start ecosystem.config.js`
- inspect:
  - `pm2 status`
  - `pm2 logs multi-ai-agent-app`

## 7. Verification Checklist

- `/` loads
- `/login` loads
- `/dashboard` redirects to `/login` when signed out
- valid seeded login works
- logout works
- `/audit` loads for Admin
- tests pass before release candidate use

## 8. Notes

- current SQLite database is local-file based
- current session model is MVP-safe but not production-grade
- audit storage exists in SQLite and is exposed through `/audit`
- non-Admin users should not be granted audit access
