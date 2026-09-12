# Orchestrator Merge

Read before any merge action.
Full git spec: `orchestrator-git.md`.

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## Scope

This file: merge-specific orchestration.
Not: git commands (see `orchestrator-git.md`), failure routing (see `orchestrator-failures.md`).

## Serial guarantee

- One merge at a time. FIFO by QA PASS timestamp.
- Tie-break: smaller local ID.
- Never parallel.

## Slot interaction

- Merge does NOT consume a slot.
- QA PASS releases slot before merge starts.
- MERGE-FIX SW session DOES consume a slot.
- While merge runs, other slots continue.

## Preconditions

Before any merge:
- Issue has label `qa-passed`.
- AC hash at QA PASS unchanged.
- Feature branch pushed.
- All depends merged.
- Not already merged (idempotency).

## Execution

Steps: see `orchestrator-git.md` Sec. 4.2 (checkpoints).
Commit format: see `orchestrator-git.md` Sec. 4.4.
Dry-run: Sec. 4.5.
Fast path: Sec. 4.6.
Conflict handling: Sec. 4.7-4.9.

## Conflict → MERGE-FIX

On conflict:
- Abort merge.
- Create `MERGE-FIX: <ID>`, label `blocker`.
- Queue STOPPED.
- Details: `orchestrator-git.md` Sec. 5.

## Failure routing

On merge test failure:
- Invalidate QA PASS.
- Route to MERGE-FIX.
- See `orchestrator-git.md` Sec. 5.7-5.8.

## Rollback

See `orchestrator-git.md` Sec. 6.

## Approval integration

When `APPROVAL_MODE != full-auto`:
- Merge requires approval.
- Source: `state/APPROVALS.md`.
- Format: `merge:<ID>: approved <UTC>`.
- Missing: pause, log `[AWAITING_APPROVAL]`.
- Detection: `orchestrator-gates.md`.

## Pre-output checklist

- [ ] Only one merge active
- [ ] FIFO respected
- [ ] Depends verified merged
- [ ] Checkpoint written per step
- [ ] On conflict: MERGE-FIX created
- [ ] On failure: rollback + MERGE-FIX
- [ ] On success: platform closed, labels updated, worktree removed
- [ ] Merge audit logged
- [ ] WAL log written
- [ ] Approval obtained (if required)