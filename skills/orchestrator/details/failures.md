# Failures

Failure routing.

## Platform API Convention

"Create a BLOCKER Platform Issue" and label operations in this document
mean calls to `npx tsx scripts/platform.ts`. See `docs/commands.md` §
Platform API.

## Failure Classification

### Issue-level failure_type

| Type | Source | Action |
|---|---|---|
| `implementation` | Verifier | Builder: fix_qa |
| `ac_ambiguous` | Verifier | Definer: re_groom |
| `ac_wrong` | Verifier | Definer: re_groom |
| `test_env` | Verifier | Builder: fix_qa |
| `test_quality` | Verifier | Builder: fix_qa |
| `merge_conflict` | Orchestrator | Builder: fix_merge |
| `regression` | Verifier | Builder: fix_regression |

### Milestone-level failure

| Situation | Action |
|---|---|
| `review_plan` verdict FAIL | Definer: survey (regenerate) |
| `review_plan` FAIL 3 times | BLOCKER + human_review (milestone blocked; other milestones continue) |

### Subagent-level failure_type

| Type | Detection | Retry | Escalation |
|---|---|---|---|
| `timeout` | > `roles.<role>.timeout_minutes` | 3 | BLOCKER + isolate |
| `crash` | API 5xx | 5 | BLOCKER + isolate |
| `format_error` | Missing required fields | 3 | BLOCKER + isolate |
| `empty_output` | No output | 3 | BLOCKER + isolate |
| `refused` | Model refusal | 0 | BLOCKER + isolate |
| `schema_violation` | Schema validation failed | 3 | BLOCKER + isolate |
| `self_diagnosis` | Agent self-diagnosis | 1 | BLOCKER + isolate |

**Note**: "isolate" means add `blocker` + `isolated` labels and continue with other issues.

## Routing Logic

## Failure Type Authority

`handoff.evidence.failure_type` is the **sole authority** for business-level
routing. `handoff.error.error_type` describes only the mechanism layer
(e.g. `business_failure`, `timeout`, `crash`).

For any `verifier` `verify_issue` `FAIL`:

- `handoff.evidence.failure_type` MUST be set.
- `handoff.error.error_type` MUST be `business_failure`.
- `handoff.error.context.failure_type` MUST equal `handoff.evidence.failure_type`.
- Mismatch -> `[ROUTE_MISMATCH]` WAL + treat as schema violation.

### Verifier FAIL routing

```
Read handoff.evidence.failure_type (authoritative)
Based on failure_type:
  implementation -> Builder: fix_qa (state label: built unchanged)
  ac_ambiguous -> Definer: re_groom (state label: built -> groomed)
  ac_wrong -> Definer: re_groom (state label: built -> groomed)
  test_env -> Builder: fix_qa (state label: built unchanged)
  test_quality -> Builder: fix_qa (state label: built unchanged)
  merge_conflict -> Builder: fix_merge (state label: built unchanged)
  regression -> Builder: fix_regression (state label: built unchanged)
```

### re_groom downstream routing

After Definer: re_groom completes, based on `materiality_pct`:

```
If materiality_pct >= ac_change_blocker_pct (default 50):
  -> discard the original branch
  -> spawn Builder: implement (state label: groomed -> built)
Otherwise:
  -> spawn Builder: fix_qa (state label: built unchanged)
  -> keep the original branch
```

### review_plan FAIL routing

```
After Definer: review_plan completes:
  If review_plan_verdict == "FAIL":
    -> read milestone.survey_attempts
    -> If < 3:
        -> increment survey_attempts
        -> spawn Definer: survey (regenerate)
    -> If >= 3:
        -> create a BLOCKER Platform Issue:
             npx tsx scripts/platform.ts issue create \
               --title "BLOCKER: review_plan repeated FAIL on <milestone>" \
               --body "<findings>" \
               --labels "blocker"
        -> create a human_review Platform Issue (see human_review.md)
        -> mark milestone as blocked (isolated)
        -> continue other milestones
```

### Verifier misjudgment routing

When a Builder reports `[VERIFIER_MISJUDGMENT]` (in `evidence.reported_issue`):

```
Orchestrator routes to Definer for third-party check:
  Definer posts one of:
    "Third-party check: Verifier correct"
    "Third-party check: Verifier false positive"
    "Third-party check: unclear"
  Definer does NOT modify labels.

Orchestrator action based on Definer's verdict:
  verifier_correct:
    -> route back to Builder with Definer's finding
  verifier_false_positive:
    -> add labels:
         npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: VERIFIER_FALSE_POSITIVE on <issue>" \
           --body "<reason>" \
           --labels "blocker"
    -> isolate the issue (skip it, continue other issues)
    -> on human [OVERRIDE_VERIFIER_PASS]: force `verified` label, enqueue merge
    -> NOT auto-resolved
  unclear:
    -> add labels:
         npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: VERIFIER_UNRESOLVED on <issue>" \
           --body "<context>" \
           --labels "blocker"
    -> isolate the issue, continue other issues

Counter: docs/state/metrics/misjudgments.json
  Every [VERIFIER_MISJUDGMENT] -> Definer check
  2 misjudgments on same issue -> L3 analysis
  3 misjudgments on same issue -> BLOCKER + isolate
```

### Builder BLOCKER routing

When a Builder (any phase) returns a handoff with `status: BLOCKER`:

```
Read handoff.role, handoff.phase, handoff.error.error_code

Based on (role, phase, error_code):
  (builder, fix_merge, BINARY_CONFLICT):
    -> add labels:
         npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: binary merge conflict on <issue>" \
           --body "<conflicts>" \
           --labels "blocker"
    -> resume the merge queue; other verified issues continue merging
    -> Log [ISOLATED] <issue> reason=binary_conflict
    -> The isolated issue is not auto-resolved; a human posts [RESOLVED] later

  (builder, implement, CONSTRAINT_VIOLATION_REQUEST):
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: constraint violation request on <issue>" \
           --body "Requested files: <files>\nReason: <reason>" \
           --labels "blocker"
    -> route to Definer to review the constraints
    -> on Definer's decision, the issue is re-spawned as Builder: implement
       with the updated constraints
    -> Log [BLOCKER_CREATED] <issue> reason=constraint_violation

  (builder, implement, IMPLEMENTATION_STUCK):
    -> add labels:
         npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: implementation stuck on <issue>" \
           --body "<context>" \
           --labels "blocker"
    -> isolate the issue; continue other issues
    -> Log [ISOLATED] <issue> reason=implementation_stuck

  (builder, fix_qa, *):
    -> the fix_qa phase should not emit a BLOCKER; if it does, treat as
       IMPLEMENTATION_STUCK above

  any other (builder, *, *):
    -> add labels:
         npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
    -> create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: <error_code> on <issue>" \
           --body "<error.message>" \
           --labels "blocker"
    -> isolate the issue; continue other issues
    -> Log [ISOLATED] <issue> reason=<error_code>
```

**Key principle**: A Builder BLOCKER never halts the project. The affected
issue is isolated; the rest of the pipeline continues.

### Subagent failure routing

```
Read exit reason
Based on reason:
  timeout -> retry, at limit -> BLOCKER + isolate (see Builder BLOCKER routing)
  crash -> retry (backoff 1/2/4/8/16s)
  format_error -> retry (with hint)
  empty_output -> retry
  refused -> BLOCKER + isolate + human_review
             (BLOCKER via scripts/platform.ts; human_review via human_review.md)
  schema_violation -> retry (with schema errors)
  self_diagnosis -> depends on Level
```

### next_action authority

`next_action` is a **suggestion**, not a command.

- Orchestrator routes based on `failure_type`.
- If `next_action` matches Orchestrator routing -> proceed normally.
- If mismatch -> record `[ROUTE_MISMATCH]` WAL, **Orchestrator's routing wins**.

## Retry Strategy

| Type | Backoff |
|---|---|
| Issue-level (Verifier FAIL) | none (semantic) |
| Subagent timeout | immediate |
| Subagent crash | 1/2/4/8/16s (+ jitter) |
| Subagent format_error | immediate + hint |
| Subagent empty_output | immediate |
| Subagent refused | no retry |
| API rate limit | Retry-After header |

## Self-Diagnosis (Level 1-4)

Controlled by `automation.auto_recovery.level`. Default `level: 4`.

### Level 1: Retry

**Enabled when**: `auto_recovery.level >= 1`

**Behavior**:

- Retry the same operation 3 times (separate from `schema.max_retries` / `roles.<role>.max_retries`).
- 5-second interval between retries.
- Include the previous error summary on retry.

**Use case**:

- Transient network errors.
- Temporary API unavailability.
- Flaky tests.

**Trigger**: `error.retryable == true` and `retry_count < 3`.

### Level 2: Alternate approach

**Enabled when**: `auto_recovery.level >= 2`

**Behavior**:

- After Level 1 fails, try a different approach:
  - Implementation: different algorithm, different file structure.
  - Testing: different strategy (unit -> integration).
  - Fix: different angle.
- Try at most 2 different approaches.

**Use case**:

- Level 1 retry still fails.
- Error indicates "wrong approach" rather than "execution error".

**Trigger**: Level 1 completed and still failing.

**Record**: `[SELF_DIAGNOSIS] level=2 attempt=<n> method=<description>`.

### Level 3: Degrade

**Enabled when**: `auto_recovery.level >= 3`

**Behavior**:

- If an AC cannot be implemented:
  - Add the `known_limitation` label:
    ```
    npx tsx scripts/platform.ts label add <number> --label known_limitation
    ```
  - Builder records `degraded_acs` in the handoff's `evidence`.
  - Continue other ACs.
- If the entire issue cannot complete:
  - Skip the issue.
  - Continue other issues.

**Use case**:

- Requirements self-contradictory (ACs cannot all be satisfied).
- Technical limits (language, framework unsupported).
- Environment limits (missing dependencies).

**Trigger**: Level 2 completed and still failing.

**Record**: `[SELF_DIAGNOSIS] level=3 degraded_acs=<list>`.

**Label management**:

- **Orchestrator** adds the `known_limitation` label after Builder completes with `degraded_acs`.
- The label is informational; no human action is required to continue.

**Limit**: Degraded ACs MUST be re-checked in the final `verify_post_merge`. If a degraded AC fails post-merge verification, the issue is isolated.

### Level 4: Isolate

**Enabled when**: `auto_recovery.level >= 4`

**Behavior**:

- Add labels:
  ```
  npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
  ```
- Create a BLOCKER Platform Issue:
  ```
  npx tsx scripts/platform.ts issue create \
    --title "BLOCKER: <issue> isolated" \
    --body "<context>" \
    --labels "blocker"
  ```
- **Skip the issue, continue other issues**.
- Orchestrator no longer assigns slots to this issue.

**Use case**:

- Levels 1-3 all failed.
- Problem is beyond the agent's capability.
- Human intervention eventually required.

**Trigger**: Level 3 completed and still failing.

**Record**: `[SELF_DIAGNOSIS] level=4 isolated_issue=<id>`.

**Recovery**:

- After human resolves the problem, post `[RESOLVED] <how>` on the BLOCKER issue.
- Orchestrator removes the `isolated` and `blocker` labels, restores the issue:
  ```
  npx tsx scripts/platform.ts label remove <number> --label isolated
  npx tsx scripts/platform.ts label remove <number> --label blocker
  ```

## Relationship Between Levels

```
Failure
  |
  v
Level 1: Retry (3x)
  | failed
  v
Level 2: Alternate approach (2x)
  | failed
  v
Level 3: Degrade
  | failed
  v
Level 4: Isolate
  |
  v
BLOCKER + continue other issues
```

**If `auto_recovery.level < 4`**: After the corresponding level fails, go directly to BLOCKER + isolate (never HALT the whole project).

## Failure Pattern Library

If the same `failure_type` occurs >= `failure_patterns.min_occurrences`:

- Record `[FAILURE_PATTERN] <type>`
- Trigger Definer: survey (to improve issue splitting)
- Write to Memory

## Infinite Loop Detection

If the same issue fails >= `automation.infinite_loop_detection.max_same_failure` times:

- Isolate the issue:
  ```
  npx tsx scripts/platform.ts label add <number> --labels "blocker,isolated"
  ```
- Create a BLOCKER Platform Issue:
  ```
  npx tsx scripts/platform.ts issue create \
    --title "BLOCKER: infinite loop on <issue>" \
    --body "Same failure repeated <n> times." \
    --labels "blocker"
  ```
- Continue other issues

## Stall Detection

If `automation.stall_detection.iterations_threshold` consecutive iterations pass with no progress:

- Write `docs/state/stalled.md`
- Create a human_review Platform Issue (see human_review.md)
- **Do NOT block** other issues

## BLOCKER Management

Creating a BLOCKER:

1. Idempotency key: `<issue>-blocker`
2. Create Platform Issue with label `blocker`:
   ```
   npx tsx scripts/platform.ts issue create \
     --title "BLOCKER: <summary>" \
     --body "<context>" \
     --labels "blocker"
   ```
3. If 3 failures -> write `docs/state/pending_blockers/<issue>.md`

Resolving a BLOCKER:

1. Human posts `[RESOLVED] <how>` on the Platform Issue.
2. Orchestrator detects it, then removes the `blocker` (and `isolated` if present) labels:
   ```
   npx tsx scripts/platform.ts label remove <number> --label blocker
   npx tsx scripts/platform.ts label remove <number> --label isolated
   ```
   Optionally close the BLOCKER issue:
   ```
   npx tsx scripts/platform.ts issue close <number>
   ```
3. Related issue resumes.

## Human Review vs Blocker

| Type | Labels | Blocking? | Purpose |
|---|---|---|---|
| Blocker | `blocker` | No (isolated issue only) | Human action may resolve the isolated issue; other issues continue |
| Blocker + Isolated | `blocker`, `isolated` | No (isolated issue only) | Isolate specific issue; others continue |
| Human Review | `human_review` | No | Raise question without blocking |

**Note**: No label blocks the whole project. The system always continues with other work. `HALT` is reserved for Preflight failures that make the Orchestrator unable to proceed at all.

## Configuration

```yaml
automation:
  auto_recovery:
    enabled: true
    level: 4                    # 1-4
    max_consecutive_failures: 5
  auto_skip_blocked: true       # Always true; do not set to false
  auto_learn: true
  stall_detection:
    enabled: true
    iterations_threshold: 10
    action: write_report        # write_report | escalate | abort
  infinite_loop_detection:
    enabled: true
    max_same_failure: 5
```