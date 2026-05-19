# Phase 8.4 Token Cleanup And Retention Plan

## Goal

Reduce stale password reset artifacts and improve operational hygiene.

## Scope

- add cleanup helpers for expired and used reset tokens
- keep active valid tokens intact
- add test coverage for cleanup behavior
- preserve existing reset flows

## Initial Success Criteria

- expired tokens can be removed safely
- used tokens can be removed safely
- valid active tokens remain available
- tests and build still pass
