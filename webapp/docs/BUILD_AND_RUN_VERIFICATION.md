# Build and Run Verification

## Verification Commands

### Lint
- `npm run lint`

### Tests
- `npm run test`

### E2E
- `npm run test:e2e`

### Development Run
- `npm run dev`

### Production Build
- `npm run build`

### Production-Like Start
- `./scripts/start-non-prod.sh`

## Expected Results

- lint completes without errors
- tests complete successfully
- E2E checks pass
- app starts locally
- login flow works with seeded accounts
- dashboard protection works
- audit page works for Admin
- logout works

## Current Seed Accounts

- Admin
  - username: `admin`
  - email: `admin@example.com`
  - password: `Admin123!`

- Operator
  - username: `operator`
  - email: `operator@example.com`
  - password: `Operator123!`

- Viewer
  - username: `viewer`
  - email: `viewer@example.com`
  - password: `Viewer123!`

## Release Readiness for Non-Prod

Minimum non-production readiness requires:
- `.env.local` present
- `SESSION_SECRET` configured
- lint passing
- tests passing
- E2E passing
- build passing
