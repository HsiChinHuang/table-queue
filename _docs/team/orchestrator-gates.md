# Orchestrator Gates

Read before every Gate check. Run checks in order; on first failure, act.
Numbers `[key]` resolved from `CONFIG_SNAPSHOT.json`.

## Gate 1: Before PM -> SW

- [ ] Issue has label `groomed`
- [ ] `issues/<ID>.md` contains all sections from `task-template.md`
- [ ] Platform Issue body matches local
- [ ] `reached_state == groomed`

On failure: re-run PM with rejection reason.

## Gate 2: Before SW -> QA

- [ ] Issue has label `qa-ready`
- [ ] Feature branch pushed to remote (`issue/<ID>-<slug>`)
- [ ] SW reported FULL test suite (or affected suite) passes locally
- [ ] `reached_state == qa-ready`

On failure: re-run SW with rejection reason.

## Gate 3: Before QA -> closed

- [ ] QA comment starts with `## QA VERDICT: PASS`
- [ ] All AC items marked `[x]`
- [ ] Label `qa-passed` applied
- [ ] Local issue and Platform Issue are in sync
- [ ] `reached_state == qa-passed`

On failure: re-run QA with rejection reason.

## Gate 3 (enhanced): branch SHA check

- [ ] Branch HEAD SHA == SHA recorded at Gate 2 (SW completion).
- If changed: log `[QA_COMMIT_DETECTED]`, BLOCKER, re-run QA.

## On any Gate failure

1. Record reason.
2. Re-spawn SAME role. Pass rejection reason.
3. Do NOT edit anything yourself.
4. Repeat until Gate passes or retry limit hit.

## Slot priority

See `orchestrator-slots.md` for full algorithm.

Formula:
    priority = direct_blocked * 2 + transitive_blocked * 1 + critical_path_bonus

Recomputed: before each spawn.
Tie-break: FIFO → Size → local ID.

## Drift detection

Run before each spawn AND every Lifecycle loop.
Full procedure: `orchestrator-authority.md`.

This file: quick reference only.

Quick check:
- Labels: platform authoritative.
- State: platform authoritative.
- AC: platform authoritative (local mirror).
- Depends: local authoritative (platform ignores).

On conflict: resolve per layer.
On AC change >= [limits.ac_change_blocker_pct]%: BLOCKER.

## Failure routing

See `orchestrator-failures.md` Sec. 3 (Routing).
See Sec. 1.2 for failure_type list.
See Sec. 2 for counters and limits.

## Output request routing

If subagent output contains `[REQUEST_OUTPUT] <file> <start>-<end>`:
- Read file (max `[output.request_max_lines]` lines).
- Inject content into next spawn of same role.
- Strip the request from visible comment.

## AC SUGGESTION routing

See `orchestrator-special.md` Sec. 1.
Insert PM task; does NOT block SW; occupies slot when PM runs.

## CONSTRAINT VIOLATION routing

See `orchestrator-special.md` Sec. 2.
Same as AC SUGGESTION; check file ownership first.

## Approval detection

Orchestrator detects these events and requires approval when
`APPROVAL_MODE != full-auto`:

| Event | Detection |
|---|---|
| Merge | Before entering merge queue |
| Deps add | SW diff touches `pyproject.toml` / `package.json` dependency sections |
| Delete > [limits.approval_delete_files] file | Diff has >1 `D`-status file |
| CI change | Diff touches `.github/`, `.gitlab-ci.yml`, or CI dirs |
| > [limits.approval_issue_count] issues | SA run generates > [limits.approval_issue_count] issues |

Approval source: `state/APPROVALS.md`.
Approval line format: `<action>:<id>: approved <UTC_TS>`.

Missing approval -> pause action, log `[AWAITING_APPROVAL]`, wait.