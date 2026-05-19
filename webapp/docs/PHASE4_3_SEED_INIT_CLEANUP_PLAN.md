# Phase 4.3 Seed / Init Cleanup Plan

## Goal

Separate database bootstrap and seed responsibilities from general runtime behavior.

## Scope

- reduce implicit side effects during module import
- make database initialization easier to reason about
- prepare a cleaner path for future migration/seed scripts
- preserve current local developer convenience

## Initial Success Criteria

- app still runs locally
- tests still pass
- build still passes
- DB init code is more explicit and easier to extend
