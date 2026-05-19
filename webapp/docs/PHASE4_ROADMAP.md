# Phase 4 Roadmap

## Goal

Move the MVP pilot from verified local implementation into a more delivery-ready product slice with stronger end-to-end confidence and operational readiness.

## Phase 4.1 - E2E / Browser Validation

Objective:
- validate the real user flow in a browser-like environment

Scope:
- login success
- login failure
- dashboard redirect when signed out
- dashboard access when signed in
- logout flow

## Phase 4.2 - Audit UI

Objective:
- expose audit history in a simple user-facing/admin-facing page

Scope:
- audit list page or dashboard section
- recent auth events visibility
- basic formatting/filtering if needed

## Phase 4.3 - Seed / Init Cleanup

Objective:
- separate database bootstrap concerns from runtime app logic

Scope:
- cleaner DB init path
- optional seed script
- reduced coupling between app runtime and seed behavior

## Phase 4.4 - Non-Production Delivery

Objective:
- make the app easier to run outside local dev

Scope:
- non-prod environment checklist
- optional process manager/container path
- deploy notes refinement

## Recommended First Step

Start with Phase 4.1 to add browser-level confidence to the pilot flow.
