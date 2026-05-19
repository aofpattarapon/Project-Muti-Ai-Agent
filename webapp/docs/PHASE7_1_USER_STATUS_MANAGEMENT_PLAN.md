# Phase 7.1 User Status Management Plan

## Goal

Allow Admin to see and control whether a user is active in the pilot system.

## Scope

- add active status to persisted users
- show status in Admin user list
- show status in Admin user detail
- prevent inactive users from logging in
- record audit events for status-aware behavior where useful

## Initial Success Criteria

- users have an active/inactive flag
- inactive users cannot log in
- Admin can see status in user views
- tests and build still pass
