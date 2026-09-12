# Orchestrator Details

Rarely read. Referenced from `orchestrator*.md` for edge cases.

## Recovery: full example

Situation: Orchestrator crashed while 3 issues active.

Snapshot:
```
{
  "slots": [{"id": "T42", "role": "SW"}, {"id": "T55", "role": "QA"}, {"id": "T58", "role": "PM"}],
  "last_seq": 1234,
  "merge_queue": ["T50"]
}
```

Platform state:
- T42: label `qa-ready`
- T55: label `qa-ready`
- T58: label `backlog`
- T50: label `qa-passed`

Reconciliation:
- T42: snapshot said SW; platform says qa-ready -> SW completed. Spawn QA.
- T55: same -> Spawn QA.
- T58: snapshot said PM; platform says backlog -> PM crashed before writing. Re-spawn PM.
- T50: platform says qa-passed -> re-enqueue merge.

Worktrees scan:
- `../worktrees/T42/` exists -> keep (T42 still active).
- `../worktrees/T55/` exists -> keep.
- `../worktrees/T58/` exists but T58 has no SW commit -> `git status` check; if clean, keep; if dirty, log `[DIRTY_WORKTREE]`.

Read log tail ([log.tail_lines] lines) for last `[SHUTDOWN]` or `[ORCH_RESTART]`.

## Session restart timing

Restart triggers:
- [timeouts.orch_restart_transitions] transitions since last restart.
- OR [timeouts.orch_restart_hours] hours elapsed.
- OR `state/RESTART` file.

Precise timing:
- Check at each transition start.
- If due: finish current transition, then restart.
- Never restart mid-merge.
- Never restart with active subagents (wait or timeout).

## Comment archiving: atomicity

Correct order:
1. Write to `issues/<ID>-history.md` (append with seq).
2. Then delete from Platform.
3. On Platform delete failure: retry 3x. If still failing: BLOCKER.

Recovery scenario:
- Crash between 1 and 2: history has comment, platform still has it.
- Recovery: detect duplicate seq, delete platform version.

## Drift detection: example

Platform says AC2 = "returns 404".
Local says AC2 = "returns 400".

Action:
- Overwrite local AC2 to "returns 404".
- Log: `[DRIFT] T42 AC2 platform=404 local=400`.
- If diff > [limits.ac_change_blocker_pct]% of AC text: BLOCKER + needs-human.

## Slot priority: worked example

Ready issues: T60, T62, T65, T66, T70.
Available slots: 3.

Compute:
- T60: direct=2 (T63, T64), transitive=5 -> score = 2*2+5 = 9.
- T62: direct=0, transitive=0 -> 0.
- T65: direct=3, transitive=8 -> 14.
- T66: direct=1, transitive=2 -> 4.
- T70: direct=0, transitive=0 -> 0.

Sort: T65 (14), T60 (9), T66 (4), T62 (0, older), T70 (0, newer).

Pick: T65, T60, T66.

## Blocked issue idle-fill example

Slot 1: T42 in FAIL retry loop (SW).
Slot 2: T55 waiting on merge.
Slot 3: T58 in QA.

Ready pool: T60, T62.

Action: No new spawn (3 slots active).
When T58 completes (PASS), slot 3 freed -> pick T60.

If T58 fails and goes back to SW: slot stays occupied by T58.

## Completed project

Condition:
- All `backlog` label issues closed.
- `issues/pending/` empty.
- No open `blocker` label issues.

Action:
1. Write `state/COMPLETE.md`:
   - completed_at, total_issues, total_retries, total_duration.
2. Keep: snapshot.json, log/, memory/.
3. Delete: orchestrator.lock, retry.json, recovery.log, cache/, retry-subagent.json.
4. Write `log/summary-final.md`.
5. Stop. Do NOT auto-restart.

## Pending new issue: full flow

SW discovers need for new issue:
1. Write `_docs/issues/pending/<uuid>.md`:
```
---
title: Add rate limiting to signup
acceptance: 5 requests/min per IP returns 429
files: users/middleware.py
depends: [T42]
reason: Discovered during T42 implementation
---
```
2. Post comment on T42: `[REQUEST NEW ISSUE] pending/<uuid>`.

Orchestrator:
1. Scan `pending/` at intervals.
2. Assign new ID: `T<max+1>`.
3. Move to `issues/T<new>.md`.
4. Update frontmatter (add id, platform_issue).
5. Create Platform Issue.
6. Update `backlog.md`, `issue-map.json`.
7. Remove from `pending/`.

## Recovery loop detection

`state/recovery.log`:
```
[START] 2026-09-12 14:00
[PHASE 1] ...
[START] 2026-09-12 14:05   <- no OK before
```

Counter: 2 consecutive START without OK.

At [limits.recovery_attempt_threshold]: create BLOCKER, pause auto-recovery, wait human `[RECOVERY_OK]`.