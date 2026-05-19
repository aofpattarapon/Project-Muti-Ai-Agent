# Phase 8 Roadmap

## Goal

Move the internal app from solid pilot workflows toward stronger account security and operational resilience.

## Phase 8.1 - Stronger Password Policy And Reset Safeguards

Objective:
- improve password quality requirements and tighten reset behavior

Scope:
- stronger password validation
- prevent weak reset submissions
- keep reset token handling disciplined
- preserve current flows

## Phase 8.2 - Session Invalidation Controls

Objective:
- give the system better control over active sessions after sensitive account changes

Scope:
- invalidate sessions after password reset
- prepare for future account-wide sign-out controls
- preserve current login and logout UX

## Phase 8.3 - MFA Readiness

Objective:
- prepare the authentication model for a future MFA step

Scope:
- schema and flow preparation
- pilot-safe placeholder states
- avoid full MFA implementation in this phase

## Phase 8.4 - Token Cleanup And Retention

Objective:
- reduce stale security artifacts and improve operational hygiene

Scope:
- cleanup helpers for expired reset tokens
- retention-minded housekeeping
- test coverage for cleanup behavior

## Recommended First Step

Start with Phase 8.1 to strengthen the highest-risk area with the lowest implementation cost.
