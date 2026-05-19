# Phase 3.4 Test Plan

## Goal

Add basic automated test coverage for the pilot authentication and access flow.

## Priority Coverage

- login success
- login failure
- dashboard access requires session
- logout clears session
- role-based dashboard response basics
- seeded user lookup behavior

## Suggested Layers

- unit tests for auth/user lookup and RBAC helpers
- integration-style tests for login/logout routes if feasible
- route protection verification for dashboard access

## Recommended Next Step

Choose a test runner and add the first small passing test set before expanding coverage.
