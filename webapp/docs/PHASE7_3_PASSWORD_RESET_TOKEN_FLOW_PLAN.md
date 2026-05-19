# Phase 7.3 Password Reset Token Flow Plan

## Goal

Replace the placeholder reset request behavior with a real token-based password reset flow.

## Scope

- create reset token persistence
- issue reset token on request
- add reset form with token validation
- update password through reset submission
- invalidate used tokens
- add audit coverage for reset lifecycle

## Initial Success Criteria

- reset request creates a token for a known active user
- reset submission validates token and updates password
- used or invalid tokens are rejected
- audit events are recorded
- tests and build still pass
