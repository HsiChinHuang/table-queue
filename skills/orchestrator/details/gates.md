# Gates

Gate checks. Run before each state transition.

## Platform API Convention

Every "Platform query" or "Platform operation" in this document means a
call to `npx tsx scripts/platform.ts`. See `docs/commands.md` § Platform
API. `<number>` is the Platform issue number (see `docs/state/issue_map.json`
for the `t<n>` → `<number>` mapping).

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

- [ ] Issue has label `groomed`:
      ```
      npx tsx scripts/platform.ts issue get <number>
      ```
      The returned `labels` array MUST contain `groomed` and MUST NOT contain `defined`.
- [ ] Issue has complete definition:
      `docs/issues/<id>.md` contains non-empty `## Context`,
      `## Acceptance criteria`, `## Out of scope`, `## Definition of Done`.
- [ ] AC count within `limits.issue_granularity.max_acs`:
      read `evidence.ac_count` from the groom handoff.
- [ ] File count within `limits.issue_granularity.max_files`:
      count the `Files:` entries in the issue's `## Constraints` section.
- [ ] All automatable AC have verification commands:
      each `ac<N>` in `evidence.verification_commands` is either a runnable
      command or the literal string `manual`.
- [ ] `verification_commands` written to `docs/issues/<id>.md`:
      the `## Verification commands` section exists and lists one entry per AC.
- [ ] Platform Issue body was synced in groom Step 6:
      groom's handoff `status == "COMPLETE"` and `error == null`. This confirms
      the `issue update --body` call in groom Step 6 succeeded. The Gate does
      NOT re-fetch the Platform body; the sync is guaranteed by groom's own
      successful completion (see `groom.md` Step 6).

Failure -> re-run Definer: groom (`retry_count += 1`)

## Gate 2: After Builder: implement

Before spawning Verifier: verify_issue, check:

- [ ] Issue has label `built`:
      ```
      npx tsx scripts/platform.ts issue get <number>
      ```
      The returned `labels` array MUST contain `built` and MUST NOT contain `groomed`.
- [ ] Branch pushed: verify the branch exists on origin:
      ```
      git ls-remote --heads origin issue/<id>-<slug>
      ```
      MUST return a non-empty SHA.
- [ ] Builder reports tests pass:
      `evidence.test_summary.failed == 0`.
- [ ] `branch_sha` recorded in the handoff:
      `evidence.branch_sha` is a 7–40 hex string.
- [ ] `branch_sha` matches `git rev-parse`:
      ```
      git rev-parse origin/issue/<id>-<slug>
      ```
      MUST equal `evidence.branch_sha`.

Failure -> re-run Builder (`retry_count += 1`)

## Gate 3: After Verifier: verify_issue

Before spawning Verifier: verify_pre_merge, check:

- [ ] Verifier verdict is PASS.
- [ ] `ac_results` all `PASS` or `SKIP`.
- [ ] `verification_commands_source` present in evidence.
- [ ] No `regressions_detected`.

Failure -> re-run Verifier (`retry_count += 1`)

## Gate 4: After Verifier: verify_post_merge

After merge, check:

- [ ] `verify_post_merge` PASS.
- [ ] No `regressions_detected`.
- [ ] main SHA recorded in `evidence.merge_sha`.

Failure -> rollback + Builder: fix_regression

## Gate Failure Handling

1. Record reason.
2. Re-run same role (with rejection reason).
3. `retry_count += 1`.
4. If `retry_count >= roles.<role>.max_retries` -> create a BLOCKER Platform Issue:
   ```
   npx tsx scripts/platform.ts issue create \
     --title "BLOCKER: gate failure on <issue>" \
     --body "<gate name>: <errors>" \
     --labels "blocker"
   ```

## Branch SHA Verification

Each Gate check that involves a branch:

- Read `branch_sha` from the role's handoff `evidence.branch_sha`
- Run:
  ```
  git rev-parse origin/<branch>
  ```
- If mismatch -> `[BRANCH_TAMPER]` WAL + create a BLOCKER Platform Issue:
  ```
  npx tsx scripts/platform.ts issue create \
    --title "BLOCKER: branch SHA mismatch on <issue>" \
    --body "expected=<branch_sha> actual=<git sha>" \
    --labels "blocker"
  ```

## Drift Check

Run before every spawn:

```
For each candidate issue (local id t<n>, platform number <number>):
  npx tsx scripts/platform.ts issue get <number>
  Compare:
    - Platform `state`     vs local issue state (from docs/state/snapshot.json)
    - Platform `labels`    vs local labels
    - Platform `updated_at` vs local issue file mtime
```

If drift is detected:

- Record `[DRIFT] <issue> <layer>` WAL.
- If drift is limited to non-authoritative metadata (labels, timestamps)
  and the AC hash is unchanged -> auto-sync local.
- If the AC hash differs by >= `ac_change_blocker_pct` -> create a
  human_review Platform Issue (see `human_review.md`); skip this issue
  for the current iteration.

**Platform `state` is authoritative for `open`/`closed`.** If the Platform
says an issue is `closed` while local says active -> Platform wins;
remove from local active set. The reverse (Platform `open`, local
`closed`) -> log `[DRIFT]` and route to reconcile (see `recovery.md`).

## API Query Policy

Default query:

- `npx tsx scripts/platform.ts issue get <number>` (single issue)
- `npx tsx scripts/platform.ts issue list --labels <l> --state <s>` (set)

The `issue get` response includes: `number`, `title`, `state`, `labels`,
`updated_at`. It does NOT include the issue body or comments (see
`docs/commands.md` § Platform API for the full output shape).

Do NOT query:

- Issue body (AC is local-authoritative; body sync is guaranteed by
  groom Step 6, see Gate 1).
- Comment history (only the latest comment when needed, via
  `issue latest-comment <number>`).

Full body or comments:

- Only when explicitly needed.
- Result externalized immediately (write to a file, do not embed in
  context).

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

**Note**: `Builder: fix_qa` keeps the state label `built` (unchanged). The
issue remains in `built` state, with the `verifier_failed` modifier
removed after a successful fix.

### Transition Commands

Each transition is executed with `scripts/platform.ts`. The current state
label is removed and the next one is added; modifier labels are added or
removed independently.

**State label transitions** (mutually exclusive):

| From | To | Command |
|---|---|---|
| (none) | `defined` | `npx tsx scripts/platform.ts label add <number> --label defined` |
| `defined` | `groomed` | `npx tsx scripts/platform.ts label remove <number> --label defined` then `npx tsx scripts/platform.ts label add <number> --label groomed` |
| `groomed` | `built` | `npx tsx scripts/platform.ts label remove <number> --label groomed` then `npx tsx scripts/platform.ts label add <number> --label built` |
| `built` | `verified` | `npx tsx scripts/platform.ts label remove <number> --label built` then `npx tsx scripts/platform.ts label add <number> --label verified` |
| `verified` | `closed` | `npx tsx scripts/platform.ts label remove <number> --label verified` then `npx tsx scripts/platform.ts label add <number> --label closed` |
| `built` | `groomed` (via re_groom) | `npx tsx scripts/platform.ts label remove <number> --label built` then `npx tsx scripts/platform.ts label add <number> --label groomed` |

The order matters only for the Platform UI; the API accepts both label
operations in any order. The safe pattern is remove-then-add (avoids a
transient state where both old and new labels exist).

**Modifier label add/remove**:

| Action | Command |
|---|---|
| Add modifier | `npx tsx scripts/platform.ts label add <number> --label <mod>` |
| Add two modifiers | `npx tsx scripts/platform.ts label add <number> --labels "<mod1>,<mod2>"` |
| Remove modifier | `npx tsx scripts/platform.ts label remove <number> --label <mod>` |

### Execution

Run the gate via:

    npx tsx scripts/gate_check.ts <role> <phase> <handoff_path> <current_state>

Parse the JSON output. If `passed: false`, follow "Gate Failure Handling".