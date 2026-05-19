# Phase 7.4 Email Delivery Integration Plan

## Goal

Deliver password reset links through an email delivery abstraction instead of only showing them in the pilot UI.

## Scope

- add reset email delivery abstraction
- add environment-driven delivery mode
- support a local development sink/log mode
- update password reset request flow to use delivery layer
- keep audit coverage and neutral responses

## Initial Success Criteria

- reset request uses a delivery service for known active users
- local development can inspect delivered reset links safely
- production mode is configuration-driven
- tests and build still pass
