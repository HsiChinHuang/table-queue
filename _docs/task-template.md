# Task Template

PM uses this template when grooming.
`[SA]` = filled by SA. `[PM]` = filled by PM. `[SW]` = filled by SW.

## Metadata `[SA]`

- **Phase**: phase-0-specs | phase-1-frontend-mock | phase-2-backend | phase-3-integration | phase-4-database
- **Type**: feature | test | chore | docs | bug
- **Area**: frontend | backend | database | docs
- **Size**: S | M | L
- **Milestone**: Phase X - Name

## Goal `[SA]`

One or two sentences on what should be true when this is done.

## Context `[PM]`

Why this task exists. Links:

- Related: #TASK-NUMBER
- Design: `_docs/design-system.md` (if UI)
- Plan: `_docs/plan.md`

## Acceptance criteria `[SA draft; PM refines]`

- [ ] A statement you can check by looking at the result
- [ ] One line per case, including awkward ones
- [ ] Error cases covered
- [ ] Empty / loading / error states covered

## Test requirements `[SW]`

- [ ] Test file paths
- [ ] Test function names
- [ ] Manual verification steps (if any)

## Implementation notes `[SW]`

- Suggested files to touch
- Key types / functions / endpoints
- Keep simple; do not over-engineer

## Dependencies `[SA]`

- Blocked by: #T0, #T3 (or "None")
- Blocks: #T5, #T7

## Out of scope `[PM]`

- Something that does not belong here, moved to #TASK-NUMBER

## Constraints `[SA]`

- Files this should stay inside
- Libraries to use
- Guidelines to follow

## Definition of Done `[SA template; PM issue-specific]`

- [ ] All acceptance criteria pass
- [ ] Backend tests pass
- [ ] Frontend tests pass (if applicable)
- [ ] No lint errors
- [ ] Manual verification completed (if applicable)

---

## Frontmatter (before all sections)

```
---
id: T1
title: ...
depends: [T0]
platform_issue: null
---
```

## Section ownership summary

| Section | Owner |
|---|---|
| Frontmatter (id, title, depends, platform_issue) | SA |
| Metadata | SA |
| Goal | SA |
| Context | PM |
| Acceptance criteria | SA draft, PM refine |
| Test requirements | SW |
| Implementation notes | SW |
| Dependencies | SA |
| Out of scope | PM |
| Constraints | SA |
| Definition of Done (template) | SA |
| Definition of Done (issue-specific) | PM |

## PM note

After grooming, add label `groomed` to the Platform Issue.