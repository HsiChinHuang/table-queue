# SA Details

Rarely read. Referenced from `sa.md` for edge cases.

## Example: plan.md block

```
> Issue template:
> - Title: Create User model
> - Acceptance:
>     - User has email (unique), password_hash, household FK
>     - `uv run pytest tests/test_models.py` passes
> - Files: users/models.py, users/migrations/
> - Depends: []
```

## Example: issue frontmatter

```
---
id: T1
title: Create User model
depends: [T0]
platform_issue: 42
---

## Metadata
- Phase: phase-2
- Type: feature
- Area: backend
- Size: M

## Goal
...

## Acceptance criteria
- [ ] ...

## Constraints
- Files: users/models.py
```

## State detection examples

| Existing | Run |
|---|---|
| req only | P1 + P2 + P2b + P3 |
| req + plan | P2 + P2b + P3 |
| req + plan + issues/ | P2b + P3 |
| req + plan + issues/ + backlog | P3 |
| all | DONE |

## File ownership conflict: example

- T5: Files = `users/models.py, users/views.py`
- T7: Files = `users/models.py, users/forms.py`
- No dependency between T5 and T7.
- Resolution: T7.depends += [T5]. Log warning in plan.md.

## Dependency chain depth

- Depth = longest path from any root to any leaf.
- Warn if > [limits.dep_chain_warn].
- HALT if > [limits.dep_chain_halt] unless `[DEEP_CHAIN_OK]` in plan.md.

## Cycle detection

- Build DAG. Run DFS. If back-edge found: cycle.
- HALT, list the cycle.

## Reference validity

- Every `depends: Txx` must reference an existing ID in the same plan.
- Missing: HALT with list.

## Malformed file handling

- Frontmatter not YAML: HALT.
- Missing `id` or `title`: HALT.
- `depends` not a list: HALT.
- Never auto-repair.

## P2 output: which sections SA fills

| Section | SA |
|---|---|
| frontmatter (id, title, depends, platform_issue) | fills |
| Metadata | fills |
| Goal | fills |
| Context | empty (PM) |
| Acceptance criteria (draft) | fills |
| Test requirements | empty (SW) |
| Implementation notes | empty (SW) |
| Dependencies | fills |
| Out of scope | empty (PM) |
| Constraints | fills |
| Definition of Done (template) | fills |
| Definition of Done (specific) | empty (PM) |