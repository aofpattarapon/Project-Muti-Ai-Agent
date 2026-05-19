# Phase 8.2 Session Invalidation Plan

## Goal

Invalidate existing sessions after sensitive account changes such as password reset.

## Scope

- add session version or invalidation marker to persisted users
- include version data in session payload
- reject stale sessions during session reads
- bump session invalidation state after password reset
- preserve normal login and logout behavior

## Initial Success Criteria

- password reset invalidates older sessions
- new logins still work normally
- stale sessions are treated as signed out
- tests and build still pass
