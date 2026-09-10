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