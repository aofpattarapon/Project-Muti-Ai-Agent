# Phase 6 Roadmap

## Goal

Move the pilot from a hardened MVP into a more operationally realistic internal application.

## Phase 6.1 - Password Reset Placeholder Flow

Objective:
- add the first recovery-oriented authentication flow without full email infrastructure

Scope:
- request reset page
- neutral user-facing response
- audit event hook
- future token/email handoff note

## Phase 6.2 - User Management Expansion

Objective:
- extend the Admin user directory into a more useful operational tool

Scope:
- user detail view
- role/status presentation
- future edit hooks kept out of scope for now

## Phase 6.3 - Audit and Operations Maturity

Objective:
- make operational visibility more practical

Scope:
- richer audit filtering
- pagination or capped browsing
- better timestamp and event presentation

## Phase 6.4 - Deployment and Runtime Hardening

Objective:
- reduce surprises when running outside pure local development

Scope:
- runtime assumptions review
- trusted proxy handling
- cookie policy by environment
- tighter CSP refinement

## Recommended First Step

Start with Phase 6.1 to introduce the next authentication lifecycle step with minimal risk.
