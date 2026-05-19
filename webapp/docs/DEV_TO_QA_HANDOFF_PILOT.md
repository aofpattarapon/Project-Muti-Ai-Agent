# DEV to QA Handoff

## 1. Work Item Name

Login + Role-Based Access + Basic Dashboard

## 2. Implementation Summary

Implemented MVP pilot flow for:
- login
- dashboard access
- role-aware dashboard sections
- logout
- basic in-memory audit event visibility

## 3. Routes to Test

- `/`
- `/login`
- `/dashboard`
- `POST /api/auth/login`
- `POST /api/auth/logout`

## 4. Seed Test Accounts

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

## 5. Expected Behaviors

- signed-out user accessing `/dashboard` is redirected to `/login`
- valid login redirects to `/dashboard`
- invalid login returns safe error message
- dashboard renders according to signed-in role
- logout clears session and returns user to login flow

## 6. Validation Focus

- missing username/email
- missing password
- invalid credentials
- redirect behavior for unauthenticated dashboard access
- logout behavior
- visible role-based section differences

## 7. Known Limitations

- auth is MVP-only and uses seeded in-memory users
- audit events are in-memory only
- no database persistence yet
- no advanced rate limiting
- no MFA or password reset

## 8. Suggested QA Result Types

- functional pass/fail
- permission mismatch
- session flow issue
- validation/error behavior issue
- audit visibility issue
