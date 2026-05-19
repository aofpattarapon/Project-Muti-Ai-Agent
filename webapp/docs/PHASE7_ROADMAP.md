# Phase 7 Roadmap

## Goal

Move the internal MVP toward operational administration and more realistic account lifecycle management.

## Phase 7.1 - User Status Management

Objective:
- allow Admin to manage whether a user is active in the system

Scope:
- add active/inactive status to users
- show status in user list and detail views
- block inactive users from logging in
- keep changes simple and auditable

## Phase 7.2 - Role Change Flow

Objective:
- let Admin adjust user role assignments with clear guardrails

Scope:
- role update action
- audit event for role changes
- basic validation for allowed roles

## Phase 7.3 - Password Reset Token Flow

Objective:
- move from placeholder reset request to a real token-based reset flow

Scope:
- token issuance
- token validation
- password update submission
- audit coverage

## Phase 7.4 - Email Delivery Integration

Objective:
- connect account recovery flow to an actual outbound delivery path

Scope:
- provider abstraction
- reset email delivery
- environment configuration and failure handling

## Recommended First Step

Start with Phase 7.1 to add the lowest-risk Admin action and prepare for later lifecycle features.
