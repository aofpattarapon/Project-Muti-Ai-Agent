# Phase 7.2 Role Change Flow Plan

## Goal

Allow Admin to update user roles with simple validation and audit coverage.

## Scope

- add role update action for Admin
- validate against allowed pilot roles
- show current role clearly in user detail
- record audit event for role changes

## Initial Success Criteria

- Admin can change a user's role
- invalid role submissions are rejected
- audit event is recorded for role changes
- tests and build still pass
