# Phase 6.1 Password Reset Placeholder Plan

## Goal

Add the first recovery-oriented authentication flow without introducing full email or token infrastructure yet.

## Scope

- add a password reset request page
- add a password reset request route
- always return a neutral success response
- record an audit event hook
- add a clear note that this is a placeholder flow

## Initial Success Criteria

- user can open reset request page
- submit returns a neutral response
- audit event is recorded
- tests and build still pass
