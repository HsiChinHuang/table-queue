# Slots

Slot management and priority.

## Slot Definition

- 1 slot = 1 active subagent session
- Max: `slots.max` (default 3)

## Slot Consumption

| Role | Mode | Consumes slot |
|---|---|---|
| Definer | survey | Yes |
| Definer | review_plan | Yes |
| Definer | groom | Yes |
| Definer | re_groom | Yes |
| Builder | implement | Yes |
| Builder | fix_qa | Yes |
| Builder | fix_merge | Yes |
| Builder | fix_regression | Yes |
| Verifier | verify_issue | Yes |
| Verifier | verify_pre_merge | Yes |
| Verifier | verify_post_merge | Yes |
| Orchestrator | merge | No |

## Slot Lifecycle

- definer survey -> release
- definer review_plan -> release
- definer groom -> release
- definer re_groom -> release
- builder implement -> release
- builder fix_qa -> release
- builder fix_merge -> release
- builder fix_regression -> release
- verifier verify_issue -> release
- verifier verify_pre_merge -> release
- verifier verify_post_merge -> release

Release the slot immediately after each mode completes; do not wait for the next step.

## Priority Order

When multiple tasks compete for slots:

| Priority | Task | Reason |
|---|---|---|
| 1 | `review_plan` (milestone-triggered) | Blocks the whole milestone |
| 2 | `fix_merge` | Avoids merge queue deadlock |
| 3 | `verify_issue` | Frees built issues |
| 4 | `implement` / `fix_qa` / `fix_regression` | Advance new issues |
| 5 | `groom` / `re_groom` | Prepare new issues |
| 6 | `verify_pre_merge` / `verify_post_merge` | Merge verification |

## Role and Mode Determination

Based on state label and modifier labels:

| State label | Modifier labels | Role: Mode |
|---|---|---|
| `defined` | — | definer: groom |
| `groomed` | — | builder: implement |
| `built` | `merge_conflict` | builder: fix_merge |
| `built` | `regression` | builder: fix_regression |
| `built` | `verifier_failed` | builder: fix_qa |
| `built` | (none) | verifier: verify_issue |
| `verified` | — | verifier: verify_pre_merge |

**Priority order within `built`**:

1. `merge_conflict`
2. `regression`
3. `verifier_failed`
4. (none, normal)

**Special case**: milestone's `review_plan_status == "pending"` -> definer: review_plan.

## Priority Sorting (within the same category)

```
priority(issue) =
    direct_blocked(issue) * 2
  + transitive_blocked(issue) * 1
  + (is_critical_path ? 1 : 0)
  + (waiting_time > starvation_warn_hours ? boost : 0)
  + (merge_queue_length > pause_threshold ? verifier_boost : 0)
  - (dependencies_blocked ? penalty : 0)
```

Sort:

1. priority descending
2. earlier creation time (FIFO)
3. smaller Size (S > M > L)
4. smaller local ID

## Dynamic Pause Threshold

- `slots.pause_threshold` (default 2)
- When merge_queue length >= threshold:
  - Pause new Builder spawns
  - Prefer spawning Verifier

Dynamic adjustment:

- 3 consecutive iterations of growing merge_queue -> use `pause_threshold_min`
- 5 consecutive iterations of empty merge_queue -> use `pause_threshold_max`

## Slot Liveness Detection

Liveness detection is provided natively by pi-subagents. The runner tracks
`lastActivityAt` per run and raises a "needs attention" signal when a run
has been idle longer than `needsAttentionAfterMs`.

**No subagent-side heartbeat file is required.** The runner's `status.json`
is the single source of truth.

### Spawn-time configuration

When spawning a subagent, pass:

```
subagent({
  action: "spawn",
  agent: "<role>",
  prompt: "...",
  control: {
    needsAttentionAfterMs: <from config: subagent.watchdog.needs_attention_after_minutes * 60000>
  }
})
```

Default: 900000 ms (15 minutes). Qwen3.8-27B needs 600–900s because its
thinking blocks run 1–5 minutes per turn; the 300s default is too tight.

### In-loop decision protocol

When the Orchestrator session wakes up (completion notification, attention
signal, or user message), it MUST run this protocol for each active slot:

1. Call `subagent({action: "status", id: "<run_id>"})`.
2. Read the returned `state` and `activity` fields.
3. Decide:
   - `state == "complete"` -> consume handoff, proceed.
   - `state == "failed"` -> route per `failures.md` Sec. 3.2.
   - `state == "running"` and `activity` recent -> continue waiting.
   - `state == "running"` and `activity` stale -> revive or interrupt
     (see `failures.md` Sec. 1.3).
   - `state == "paused"` -> user intervention; wait for steer.

The `run_id` is stored in `docs/state/snapshot.json` at spawn time
(`slots[].run_id`) and updated immediately on every revive or re-spawn.

### Out-of-process recovery

When no LLM session is available (e.g. after Orchestrator restart or crash),
use filesystem enumeration. See `scripts/recover_orphans.py`.

This is the fallback for the corner case where the watchdog lived in the
parent process and died with it.

### Threshold tuning

The threshold is a configuration concern, not an implementation concern:

| Model class | Recommended |
|---|---|
| Fast cloud models (Claude, GPT-4) | 300s |
| Local slow models (Qwen3.8-27B Q4) | 600–900s |

Adjust in `docs/config.yaml` (`subagent.watchdog.needs_attention_after_minutes`).

## Slot State

Written to `docs/state/snapshot.json`:

```json
{
  "schema_version": "2.0",
  "slots": [
    {
      "slot_id": "slot_1",
      "issue_id": "t42",
      "role": "builder",
      "phase": "implement",
      "run_id": "b0c73a06",
      "spawn_at": "...",
      "last_activity_at": "...",
      "worktree_path": "../worktrees/t42"
    }
  ],
  "max_slots": 3
}
```

**Note**: `last_activity_at` is synced from `status.json`'s `lastActivityAt`
when the Orchestrator checks liveness. It is NOT written by subagents.
`run_id` is the pi-subagents run identifier and MUST be updated on every
revive or re-spawn.

## Starvation Detection

For each ready issue:

- If wait > `priority.starvation_warn_hours` -> `[STARVATION_WARN]`
- If wait > `priority.starvation_blocker_hours` -> BLOCKER

## Fairness Metrics

Recorded every iteration to `docs/state/metrics/status_metrics.json`:

- Active slots: N / max
- Avg wait time (ready -> spawn)
- Max wait time (issue ID)
- Starvation events (24h)
- Force-released slots (24h)
- Slot utilization