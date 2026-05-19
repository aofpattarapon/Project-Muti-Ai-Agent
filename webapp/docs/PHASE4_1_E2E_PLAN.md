# Phase 4.1 E2E Plan

## Goal

Add browser-level validation for the pilot authentication flow.

## Core Journeys

- signed-out user is redirected away from dashboard
- user can open login page
- invalid login shows safe error
- valid Admin login reaches dashboard
- valid Operator login reaches dashboard
- valid Viewer login reaches dashboard
- logout returns user to login flow

## Recommended Tool

- Playwright

## Initial Success Criteria

- one passing browser test file
- covers login, dashboard, logout
- can run locally against the app
