# Slot Scheduling & Fairness

Slot = one active subagent session. Max = `[slots.max]`.

## Slot assignment

Trigger: each Lifecycle loop iteration.

Algorithm:
1. Query platform: ready issues (deps closed).
2. Filter: not in-flight, not blocked, not waiting.
3. Sort by priority (see below).
4. While active_slots < `[slots.max]`:
   a. Pick top issue.
   b. Reserve slot.
   c. Spawn appropriate role (PM if label `backlog`; SW if `groomed`; QA if `qa-ready`).

## Priority

    priority(issue) =
        direct_blocked(issue) * 2
      + transitive_blocked(issue) * 1
      + (is_critical_path ? 1 : 0)

Sort: descending.
Tie-break:
  1. Older creation ts (FIFO).
  2. Smaller Size (S > M > L).
  3. Smaller local ID.

`is_critical_path`: marked by SA at generation (longest chain).

### Human priority override

Trigger: human comments `[PRIORITY HIGH]` on issue.

Effect:
- Add `[priority.boost_value]` to priority score.
- Max `[priority.human_override_max]` HIGH issues at once.
- Exceeding: ignore extra, log `[PRIORITY_OVERRIDE_EXCEEDED]`.

Lifecycle:
- Boost persists until issue closed OR human posts `[PRIORITY NORMAL]`.
- On close: override cleared automatically.

Log: `[PRIORITY_OVERRIDE] <issue> HIGH`.

## Slot release

Release on:
- QA PASS (issue enqueued for merge).
- BLOCKER raised.
- Issue externally closed.
- Slot crash (heartbeat timeout).

NOT released on:
- QA FAIL (retry continues).
- Waiting on dependency.
- Waiting on approval.

## Slot crash detection

Heartbeat mechanism:
- Subagent writes `state/heartbeat-<session_id>.txt`:
  - Content: `<UTC_TS>`.
  - Frequency: every 2 min.
  - Format: single line.
- Orchestrator checks on each loop:
  - Read heartbeat file.
  - If `now - ts` > `[timeouts.heartbeat_stale_minutes]` min:
    - Log `[SLOT_STALE] <issue> <role>`.
  - After `[limits.slot_stale_multiplier]x` threshold:
    - Force release.
    - Log `[SLOT_FORCE_RELEASED]`.
    - Mark issue `[INTERRUPTED]`.
    - Re-spawn per snapshot.

Subagent responsibility:
- Update heartbeat at start.
- Every 2 min during work.
- Final update before comment.
- Delete on clean exit.

No `[LONG_RUNNING]` marker needed. Heartbeat is sufficient.

## Starvation detection

Check every Lifecycle loop:
- For each ready issue not yet spawned:
  - wait_time = now - became_ready_ts.
  - If > [limits.starvation_warn_hours]: log `[STARVATION_WARN] <issue> <wait>`.
  - If > [limits.starvation_blocker_hours]: BLOCKER + needs-human.

## Idle behavior

If active_slots < `[slots.max]` AND no ready issues:
- Sleep [timeouts.idle_sleep_seconds]s (configurable: `[timeouts.idle_sleep_seconds]`).
- On wake, check:
  - Pending issues to formalize.
  - L3 analysis opportunities (rate-limited).
  - Orphan worktree cleanup.
- Do NOT busy-spin.

## Merge interaction

- Merge does NOT consume a slot.
- MERGE-FIX SW session DOES consume a slot.
- Merge queue is separate from slot pool.

## Approval interaction

- Waiting for approval: slot RELEASED.
- Issue marked `[AWAITING_APPROVAL]`.
- On approval: re-queue for spawn.

## Fairness metrics

Recorded to `state/STATUS.md` each loop:
- Active slots: N / `[slots.max]`
- Avg wait time (ready → spawn)
- Max wait time (issue ID)
- Starvation events (24h)
- Force-released slots (24h)
- Slot utilization (active / capacity)

## Slot state in snapshot.json

    {
      "slots": [
        {
          "issue_id": "T5",
          "role": "SW",
          "spawn_ts": "...",
          "last_action_ts": "...",
          "worktree": "../worktrees/T5"
        }
      ],
      "max_slots": 3
    }

## Slot-state invariants

- len(slots) <= max_slots.
- No issue appears twice.
- All slots have valid spawn_ts.
- Force-release logs before state update.

## Long-wait escalation

If issue waits > [limits.starvation_blocker_hours]h:
1. Log `[STARVATION_BLOCKER]`.
2. Create BLOCKER issue.
3. Reason: no slot availability.
4. Human may:
   - Increase `slots.max`.
   - Reduce other issues' priority.
   - Investigate root cause.