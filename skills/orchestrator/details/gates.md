# Gates

Gate checks. Run before each state transition.

## Two Independent Retry Mechanisms

Orchestrator uses **two independent** retry counters:

| Type | Config | Trigger | Counter | Limit |
|---|---|---|---|---|
| **Schema retry** | `schema.max_retries` | handoff JSON violates schema | `schema_retry_count` | default 3 |
| **Role retry** | `roles.<role>.max_retries` | Business logic failure (Gate failure, Verifier FAIL) | `retry_count` | per role |

**The two are calculated independently and do not affect each other.**

### Flow

```
Role completes
  |
  v
Schema validation
  |- PASS -> enter Gate check
  '- FAIL -> schema_retry_count += 1
       |- < schema.max_retries -> re-run same role (with schema errors)
       '- >= schema.max_retries -> BLOCKER
  |
  v
Gate check
  |- PASS -> proceed to next step
  '- FAIL -> retry_count += 1
       |- < roles.<role>.max_retries -> re-run same role (with rejection reason)
       '- >= roles.<role>.max_retries -> BLOCKER
```

### Key Rules

1. **Schema retry is technical**: JSON format, missing fields, type errors. Not business logic.
2. **Role retry is business**: AC not satisfied, tests failing, Gate conditions not met.
3. **After a successful schema retry, `retry_count` is unchanged** (continues from previous value).
4. **After a successful role retry, `schema_retry_count` resets to 0.**

### Example

Scenario: Builder: implement produces invalid JSON on the first attempt, then fails a business check on the second attempt.

```
Attempt 1:
  -> JSON missing evidence_type
  -> Schema FAIL
  -> schema_retry_count = 1
  -> retry_count = 0

Attempt 2:
  -> JSON valid
  -> Schema PASS
  -> schema_retry_count = 0 (reset)
  -> Gate check failed (tests did not pass)
  -> retry_count = 1

Attempt 3:
  -> JSON valid
  -> Schema PASS
  -> Gate check failed
  -> retry_count = 2
  ...
```

## Gate 1: After Definer: groom

Before spawning Builder: implement, check:

- [ ] Issue has label `groomed`
- [ ] Issue has complete definition (Context, AC, Out of scope, DoD specific)
- [ ] AC count within `limits.issue_granularity.max_acs`
- [ ] File count within `limits.issue_granularity.max_files`
- [ ] All automatable AC have verification commands
- [ ] `verification_commands` written to `docs/issues/<id>.md`
- [ ] Platform Issue body matches local

Failure -> re-run Definer: groom (`retry_count += 1`)

## Gate 2: After Builder: implement

Before spawning Verifier: verify_issue, check:

- [ ] Issue has label `built`
- [ ] Branch pushed
- [ ] Builder reports tests pass
- [ ] `branch_sha` recorded
- [ ] `branch_sha` matches `git rev-parse`

Failure -> re-run Builder (`retry_count += 1`)

## Gate 3: After Verifier: verify_issue

Before spawning Verifier: verify_pre_merge, check:

- [ ] Verifier verdict is PASS
- [ ] `ac_results` all PASS or SKIP
- [ ] `verification_commands_source` present
- [ ] No `regressions_detected`

Failure -> re-run Verifier (`retry_count += 1`)

## Gate 4: After Verifier: verify_post_merge

After merge, check:

- [ ] `verify_post_merge` PASS
- [ ] No `regressions_detected`
- [ ] main SHA recorded

Failure -> rollback + Builder: fix_regression

## Gate Failure Handling

1. Record reason.
2. Re-run same role (with rejection reason).
3. `retry_count += 1`.
4. If `retry_count >= roles.<role>.max_retries` -> BLOCKER.

## Branch SHA Verification

Each Gate check:

- Read `branch_sha` from `docs/state/snapshot.json`
- Verify `git rev-parse <branch>` matches
- If mismatch -> `[BRANCH_TAMPER]`, BLOCKER

## Drift Check

Run before every spawn:

- [ ] Platform labels match local
- [ ] Platform issue state (open/closed) matches local
- [ ] AC hash matches

If drift:

- Record `[DRIFT] <issue> <layer>`
- Auto-sync local (if AC change < `ac_change_blocker_pct`)
- Create human_review (if AC change >= `ac_change_blocker_pct`)

## API Query Policy

Default queries only:

- `state` (open/closed)
- `labels` (array)
- `updated_at`

Do NOT query:

- Issue body (AC is local-authoritative)
- Comment history (only latest 1 if needed)

Full body or comments:

- Only when explicitly needed
- Result externalized immediately

## Label Categories

Two categories of labels:

### State labels (mutually exclusive; exactly one per issue)

| Label | Added by | Removed by |
|---|---|---|
| `defined` | Definer: survey | Definer: groom |
| `groomed` | Definer: groom / re_groom | Builder: implement |
| `built` | Builder: implement / fix_qa / fix_merge / fix_regression | Verifier: verify_issue (PASS) or Orchestrator: merge |
| `verified` | Verifier: verify_issue (PASS) | Orchestrator: merge |
| `closed` | Orchestrator: merge | (terminal) |

**Invariant**: At any time, exactly one state label is present.

### Modifier labels (stackable)

| Label | Added by | Removed by |
|---|---|---|
| `verifier_failed` | Verifier: verify_issue (FAIL) | Builder: fix_qa completion |
| `merge_conflict` | Orchestrator (on conflict detected) | Builder: fix_merge completion |
| `regression` | Orchestrator (on regression detected) | Builder: fix_regression completion |
| `blocker` | Orchestrator | Human `[RESOLVED]` |
| `isolated` | Orchestrator (Level 4) | Human `[RESOLVED]` |
| `human_review` | Orchestrator | Orchestrator closes the issue |
| `known_limitation` | Orchestrator (Level 3) | Human |
| `stale` | Orchestrator (human_review timed out) | Human response / auto-close |
| `auto_closed` | Orchestrator (auto-closed) | (terminal) |

**Invariant**: Any number of modifier labels may be present.

### Label Transition Table (per role)

| Role | Add state | Remove state | Add modifier | Remove modifier |
|---|---|---|---|---|
| Definer: survey | `defined` | — | — | — |
| Definer: groom | `groomed` | `defined` | — | — |
| Definer: re_groom | `groomed` | `built` | — | `verifier_failed` |
| Builder: implement | `built` | `groomed` | — | — |
| Builder: fix_qa | `built` (unchanged) | — | — | `verifier_failed` |
| Builder: fix_merge | `built` (unchanged) | — | — | `merge_conflict` |
| Builder: fix_regression | `built` (unchanged) | — | — | `regression` |
| Verifier: verify_issue (PASS) | `verified` | `built` | — | — |
| Verifier: verify_issue (FAIL) | — | — | `verifier_failed` | — |
| Orchestrator: merge | `closed` | `verified` | — | — |
| Orchestrator: conflict | — | — | `merge_conflict` | — |
| Orchestrator: regression | — | — | `regression` | — |
| Orchestrator: BLOCKER | — | — | `blocker` | — |
| Orchestrator: Level 3 | — | — | `known_limitation` | — |
| Orchestrator: Level 4 | — | — | `blocker`, `isolated` | — |

**Note**: `Builder: fix_qa` keeps the state label `built` (unchanged). The issue remains in `built` state, with the `verifier_failed` modifier removed after a successful fix.