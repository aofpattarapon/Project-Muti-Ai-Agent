# Phase 5 Roadmap

## Goal

Move the pilot from non-production readiness toward safer and more production-conscious operation.

## Phase 5.1 - Security Hardening

Objective:
- strengthen request and session safety for the MVP

Scope:
- security headers
- basic rate limiting for login
- safer cookie settings review
- reduce easy abuse paths

## Phase 5.2 - Environment and Config Validation

Objective:
- fail early when required runtime configuration is missing or unsafe

Scope:
- validate required env vars
- validate obvious unsafe defaults
- centralize runtime config access

## Phase 5.3 - Audit UX Improvements

Objective:
- make audit visibility more useful for operators

Scope:
- better formatting
- filtering/search options
- clearer event grouping or paging

## Phase 5.4 - User Lifecycle Features

Objective:
- improve authentication operations beyond the seeded-demo baseline

Scope:
- password reset path
- optional user management flow
- optional MFA planning hook

## Recommended First Step

Start with Phase 5.1 to improve security posture before adding more feature surface.
