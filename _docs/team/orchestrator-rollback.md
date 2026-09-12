# Orchestrator Rollback

Human-initiated rollback of merged code.
Full procedure: `orchestrator-git.md` Sec. 6.

## Trigger

Human creates Platform Issue: `ROLLBACK: <commit>` with label `ROLLBACK`.

## Preconditions

- Commit exists in main.
- Method specified in issue body: `revert` or `reset`.

## Scope

- Non-destructive (`revert`): allowed in any APPROVAL_MODE.
- Destructive (`reset`): only `manual` + double approval.

## Flow

See `orchestrator-git.md` Sec. 6.4 (revert), Sec. 6.5 (reset).

Summary:
1. Pause merge queue.
2. Execute revert or reset.
3. Reopen original issue.
4. Issue re-enters normal flow.
5. Resume merge queue.

## Safety

- Never without human's ROLLBACK issue.
- Never `reset` without APPROVALS.md entry (×2).
- Non-latest commit reset: additional approval.
- Merge-rollback race: complete merge first.

## Partial rollback (optional)

`ROLLBACK: <commit> --file <path>`: revert only that file.

## Log

All actions prefixed `[ROLLBACK]`.