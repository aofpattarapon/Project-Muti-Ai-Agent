# DEV to DevOps Handoff

## 1. Work Item Name

Login + Role-Based Access + Basic Dashboard + Audit UI

## 2. Implementation Summary

Implemented MVP pilot flow for:
- login
- signed session cookie handling
- role-aware dashboard access
- logout
- SQLite-backed user storage
- SQLite-backed audit event storage
- Admin-only audit page

## 3. Runtime Notes

- application uses Next.js app router
- login and logout are handled by route handlers
- session state is stored in an HTTP-only signed cookie
- seeded users are persisted into local SQLite on initialization
- local SQLite file is stored under `data/`

## 4. Routes / Endpoints

- `/`
- `/login`
- `/dashboard`
- `/audit`
- `POST /api/auth/login`
- `POST /api/auth/logout`

## 5. Config / Secret Notes

- requires `SESSION_SECRET`
- use `.env.local` for local/non-production setup
- `.env.example` is provided as template
- session signing depends on configured secret

## 6. Logging / Observability Notes

- audit events are stored in SQLite
- login success, login failure, logout, and related events are modeled
- audit data is visible through `/audit` for Admin users
- no external log sink yet
- no full observability stack yet

## 7. Known Limitations

- no production-grade session store
- no external auth provider
- no advanced rate limiting
- no MFA
- no password reset
- no centralized external logging yet

## 8. DevOps Support Expectations

- prepare simple non-production runtime first
- ensure writable local filesystem for SQLite
- ensure `SESSION_SECRET` is configured
- verify lint, test, E2E, and build before non-production rollout
- support either direct `npm run start` or PM2-based process management

## 9. Suggested Non-Prod Start Paths

- script-based:
  - `./scripts/start-non-prod.sh`
- manual:
  - `HOST=0.0.0.0 PORT=3000 npm run start`
- PM2:
  - `pm2 start ecosystem.config.js`

## 10. Suggested Next DevOps Focus

- non-production deployment setup
- environment variable handling
- future persistent external session strategy
- future centralized logging/observability path
