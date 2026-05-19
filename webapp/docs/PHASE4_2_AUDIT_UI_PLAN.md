# Phase 4.2 Audit UI Plan

## Goal

Expose authentication and session audit activity in a simple Admin-only UI.

## Scope

- add `/audit` page
- show recent audit events from SQLite
- display event type, actor, detail, timestamp
- limit access to Admin users only
- add navigation entry from dashboard
- add basic automated coverage for access expectations

## Initial Success Criteria

- Admin can open `/audit`
- non-Admin cannot access `/audit`
- recent login/logout events are visible
