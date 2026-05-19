# Phase 5.2 Environment and Config Validation Plan

## Goal

Fail early when required runtime configuration is missing, unsafe, or inconsistent.

## Scope

- centralize runtime config access
- validate required env vars
- reject obviously unsafe defaults where practical
- preserve local developer usability

## Initial Success Criteria

- required config is read through one module
- unsafe or missing config causes a clear failure
- tests still pass
- build still passes
