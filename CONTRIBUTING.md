# Contributing to TableQueue

Version: 0.1.0
Last updated: 2026-09-10

---

## Overview

TableQueue is developed with a mix of human PM work and coding agents. This document defines:

- How issues are created and groomed
- The task template every issue must follow
- Labels, milestones, branch naming, commit convention
- Pull request flow
- Testing requirements
- Definition of Done
- Rules for coding agents

Read [`_docs/specs.md`](_docs/specs.md) before starting any work.

---

## Issue Workflow

1. **PM creates an issue** using the task template below.
2. **PM grooms the issue**: fills in metadata, acceptance criteria, dependencies, out-of-scope, constraints.
3. **PM adds label `groomed`** once the issue is ready.
4. **Coding agent or developer picks up the issue** and moves it to `in-progress`.
5. **Work is done on a branch** named per the convention below.
6. **Tests must pass** before opening a PR.
7. **PR is opened**, referencing the issue.
8. **Reviewer merges** (squash and merge).
9. **Issue is closed** after merge.

No work should start on an issue that is not `groomed`.

---

## Task Template

Every issue must use this template.

```markdown
# Task Template

PM uses this template when grooming an issue.
Each task should be small enough to finish in one session, and
independent enough that I could hand it to someone who has not read
the others.

## Metadata

- **Phase**: phase-0-specs | phase-1-frontend-mock | phase-2-backend | phase-3-integration | phase-4-database
- **Type**: feature | test | chore | docs | bug
- **Area**: frontend | backend | database | docs
- **Size**: S | M | L
- **Milestone**: Phase X - Name
- **Labels**: groomed, phase-X, frontend/backend, feature/test/chore/docs

## Goal

One or two sentences on what should be true when this is done.

## Context

Why this task exists. Link to relevant sections.

- Related: #TASK-NUMBER
- Design: `_docs/design-system.md` (if UI)
- Plan: `_docs/plan.md`
- Specs: `_docs/specs.md#section-anchor`
- UI: `_docs/ui.md#section-anchor`
- API: `_docs/openapi.yaml#operationId`
- Testing: `_docs/testing.md#section-anchor`

## Acceptance criteria

- [ ] A statement you can check by looking at the result
- [ ] One line per case, including the awkward ones
- [ ] Error cases covered
- [ ] Empty / loading / error states covered

## Test requirements

- [ ] Backend: `backend/tests/test_<name>.py`, list test names
- [ ] Frontend: `frontend/tests/<name>.test.tsx`, list test names
- [ ] Manual verification steps

## Implementation notes

- Suggested files to create or touch
- Key types / functions / endpoints
- Do NOT over-engineer; keep it simple

## Dependencies

- Blocked by: #T0, #T3 (or "None")
- Blocks: #T5, #T7
- If blocked, link to the blocking issue(s).

## Out of scope

- Something that does not belong in this task, moved to #TASK-NUMBER

## Constraints

- Files this should stay inside
- Libraries to use
- Guidelines to follow

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Backend tests pass (`uv run pytest`)
- [ ] Frontend tests pass (`npm run test`)
- [ ] No lint errors
- [ ] PR description references this issue
- [ ] Manual verification completed

---

**PM Note**: After grooming, add label `groomed` to this issue.
```

Labels
Workflow
groomed — issue is ready to be worked on

in-progress — someone is working on it

blocked — waiting on another issue

Phase
phase-0-specs

phase-1-frontend-mock

phase-2-backend

phase-3-integration

phase-4-database

Area
frontend

backend

database

docs

Type
feature

test

chore

docs

bug

Milestones
Phase 0 — Specs & Docs

Phase 1 — Frontend + Mock

Phase 2 — Backend + Mock DB

Phase 3 — Integration

Phase 4 — Database

Every issue must belong to exactly one milestone.

Branch Naming
Format: <type>/<issue-number>-<short-description>

Examples:

feat/12-join-waitlist-page

fix/34-duplicate-phone-handling

test/21-state-machine-tests

chore/8-setup-makefile

docs/3-write-specs

Rules:

Lowercase

Hyphen-separated

No spaces

Always reference the issue number

Commit Convention
Use Conventional Commits.

Format: <type>(<scope>): <subject>

Types:

feat — new feature

fix — bug fix

test — tests

chore — tooling, deps, config

docs — documentation

refactor — code change that neither fixes a bug nor adds a feature

style — formatting only

Scopes (optional):

backend

frontend

api

ui

db

docs

Examples:

feat(frontend): add join waitlist page

feat(backend): implement call endpoint

fix(api): handle duplicate phone

test(backend): add state machine tests

chore: setup makefile

docs: add specs

Rules:

Subject in lowercase

No period at the end

Max 72 characters

Pull Request
Every PR must:

Reference the issue: Closes #12

Include a summary

Include a test plan

Include screenshots for UI changes

Pass all tests

Pass lint

PR Template
markdown
## Summary

Brief description of what changed.

## Related Issue

Closes #12

## Changes

- Change 1
- Change 2

## Test Plan

- [ ] `uv run pytest` passes
- [ ] `npm run test` passes
- [ ] Manual verification completed

## Screenshots (if UI)

Before / after screenshots.

## Notes

Anything reviewers should know.
Merge Strategy
Squash and merge

Delete branch after merge

No CI in v1; reviewer runs tests manually

Testing Requirements
Backend
Every endpoint must have at least one success test and one failure test.

State machine transitions must be tested.

Lazy no-show must be tested with fixed time.

Run: cd backend && uv run pytest

Frontend
API client must have unit tests.

Key components must have tests:

WaitlistCard

Countdown

TableCard

StatusBadge

Key pages must have tests:

JoinPage

StatusPage

Run: cd frontend && npm run test

Both
make test must pass before merging.

Definition of Done
An issue is done when:

□ All acceptance criteria pass
□ uv run pytest passes
□ npm run test passes
□ No lint errors
□ PR references the issue
□ Manual verification completed
□ Issue closed
Rules for Coding Agents
Read first:

AGENTS.md

_docs/specs.md

_docs/ui.md

_docs/openapi.yaml

_docs/testing.md

Do not add features not listed in _docs/specs.md.

One issue at a time. Do not batch multiple issues into one branch.

Follow the API contract in _docs/openapi.yaml exactly.

All UI text in English.

Date format: 2026-09-10 21:00 (ISO + 24h).

Phone format: Taiwan 09xx-xxx-xxx / 02-xxxx-xxxx.

Run tests before marking done:

cd backend && uv run pytest

cd frontend && npm run test

If spec is unclear, stop and ask. Do not guess.

Do not modify _docs/specs.md without an explicit docs issue.

Do not commit .env, dev.db, node_modules, __pycache__.

Keep commits small and focused.

Reference the issue in every commit and PR.

If a dependency is not done, do not start the issue.

If tests fail, fix them before opening a PR.

File Ownership
Path	Owner
_docs/specs.md	PM
_docs/ui.md	PM
_docs/openapi.yaml	PM + backend
_docs/testing.md	PM + both
_docs/deployment.md	PM
_docs/issues/	PM
backend/	backend
frontend/	frontend
README.md	PM
CONTRIBUTING.md	PM
AGENTS.md	PM
Makefile	both
root package.json	both
Getting Help
Read _docs/specs.md first.

Read AGENTS.md.

If still unclear, open a question issue or ask in the PR.