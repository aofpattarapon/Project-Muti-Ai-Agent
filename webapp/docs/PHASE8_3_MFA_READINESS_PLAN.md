# Phase 8.3 MFA Readiness Plan

## Goal

Prepare the authentication model and admin visibility for a future MFA step without implementing full MFA verification yet.

## Scope

- add persisted MFA state fields for users
- expose MFA readiness/status in admin user views
- keep login flow unchanged for now
- avoid fake security claims or partial MFA enforcement

## Initial Success Criteria

- users have explicit MFA-related persisted state
- admin can see MFA readiness/status in user views
- current login flow still works unchanged
- tests and build still pass
