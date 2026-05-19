# Phase 5.1 Security Hardening Plan

## Goal

Improve baseline security posture without overcomplicating the MVP.

## Scope

- add basic login rate limiting
- review and tighten cookie behavior where practical
- add security headers through Next.js config or middleware
- preserve existing login/logout/dashboard/audit behavior

## Initial Success Criteria

- repeated failed login attempts are slowed or blocked temporarily
- common security headers are present
- existing tests still pass
- build still passes
