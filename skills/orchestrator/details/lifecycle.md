# Lifecycle

Orchestrator's main loop. Executed once per iteration.

## Boot Prerequisites

After Orchestrator Boot:
1. Read `AGENTS.md`.
2. Read `skills/orchestrator/SKILL.md`.
3. Run Preflight (config, environment, references, recovery).
4. Enter Lifecycle.

## Each Iteration

### Step 0: First-run initialization

This step runs **before all others**, and only until the project is initialized.

```
If docs/state/initialized exists:
  -> initialization complete, proceed to Step 1

If docs/state/initialized does NOT exist:
  If docs/requirements.md does NOT exist:
    -> HALT, write docs/state/PREFLIGHT_FAIL.md
    -> Create BLOCKER with message "docs/requirements.md is missing"
    -> Skip remaining steps this iteration

  If docs/plan.md does NOT exist or is empty:
    -> spawn Definer: survey (initial survey)
    -> the survey will create docs/plan.md and milestones
    -> after survey completes, review_plan triggers (Step 3)
    -> go to Step 8 (wait for completion)
    -> skip remaining steps this iteration

  If docs/plan.md exists AND docs/state/initialized does NOT exist:
    -> check all milestones' review_plan_status
    -> if all are "passed":
        -> wait for human to create docs/state/initialized
        -> log [AWAITING_INITIALIZED] once
        -> skip remaining steps this iteration
    -> otherwise:
        -> Step 3 will handle pending review_plan
        -> proceed to Step 1
```

**Note**: `docs/state/initialized` is created by a human after reviewing the generated `plan.md` and issues.

### Step 1: Check control files

```
if docs/state/pause exists:
  finish current action
  wait (do not spawn)
  skip remaining steps this iteration

if docs/state/reset and docs/state/reset_approved exist:
  run RESET flow (see recovery.md)
  skip remaining steps this iteration
```

### Step 2: Check human_review label

```
Query Platform for all issues labeled human_review
For each issue:
  if human posted a new comment:
    parse comment, run action
    mark issue resolved
    record [HUMAN_REVIEW_RESOLVED] <issue>
```

### Step 3: Check milestone review_plan

```
Scan docs/state/milestones/*.json

For each milestone:
  if review_plan_status == "pending":
    -> set to in_progress
    -> reserve slot
    -> spawn Definer: review_plan (with milestone argument)
    -> go to Step 8 (wait for completion)
```

**Note**: After survey completes, Orchestrator creates the milestone file with `review_plan_status` set to `pending`. This step triggers review_plan automatically.

**Argument passing**: Orchestrator passes `milestone` as a spawn argument. The handoff's `issue_id` field is set to the first issue of the milestone (e.g. `t1`); the milestone is recorded in `evidence.milestone`.

### Step 4: Query ready issues

```
Query Platform: state label in {defined, groomed, built, verified}
Filter: deps closed (read docs/issues/<id>.md frontmatter)
Filter: not in active_issues
```

**Note**:

- Query for **state labels** only, not modifier labels.
- If the current milestone's review_plan has not passed, do NOT spawn that milestone's issues (wait for review).

### Step 5: Drift check

```
For each candidate issue:
  Query Platform issue
  Compare local vs Platform AC hash
  If different:
    < ac_change_blocker_pct -> auto-sync local
    >= ac_change_blocker_pct -> create human_review, skip this issue
```

### Step 6: Assign slot

```
If active_slots < slots.max:
  Sort ready issues by priority (see slots.md)
  Pick next
  Reserve slot
```

**Priority order**:

1. `review_plan` (milestone-triggered, higher than normal issues)
2. `fix_merge` (avoid merge queue deadlock)
3. `verify_issue`
4. `implement` / `fix_qa` / `fix_regression`
5. `groom` / `re_groom`
6. `verify_pre_merge` / `verify_post_merge`

### Step 7: Spawn role

Based on issue state and modifier labels:

| State label | Modifier labels | Role: Mode |
|---|---|---|
| `defined` | (no `groomed`) | Definer: groom |
| `groomed` | — | Builder: implement |
| `built` | `merge_conflict` | Builder: fix_merge |
| `built` | `regression` | Builder: fix_regression |
| `built` | `verifier_failed` | Builder: fix_qa |
| `built` | (none) | Verifier: verify_issue |
| `verified` | — | Verifier: verify_pre_merge |

**Priority order within `built`**:

1. `merge_conflict` (highest, avoids merge queue deadlock)
2. `regression`
3. `verifier_failed`
4. (none, normal)

**Special case**: Milestone-triggered -> spawn Definer: review_plan.

Pass:

- `issue_id`
- `milestone` (required for review_plan)
- `mode` (determined by state)
- `worktree_path` (Builder/Verifier)
- `candidate_branch` / `merge_sha` (Verifier)
- `failure_history` (if fix)
- `memory_paths` (if retry >= 2)
- `retry_count`

### Step 8: Wait for role

```
Wait until the role writes the handoff JSON or times out
On timeout -> see failures.md
```

### Step 9: Schema validation

```
Read handoff JSON
Validate against schemas/<role>/<phase>.json
If invalid -> re-run same role (up to schema.max_retries times)
```

### Step 10: Process verdict

```
Based on handoff.status:
  COMPLETE -> go to Step 11
  FAIL -> see failures.md
  BLOCKER -> create BLOCKER issue
```

**Special case**: after review_plan completes:

```
If review_plan_verdict == "PASS" or "PASS_WITH_WARNINGS":
  -> milestone.review_plan_status = "passed"
  -> the milestone's issues become eligible for Lifecycle
  -> if all milestones passed AND docs/state/initialized does NOT exist:
       -> log [AWAITING_INITIALIZED]
If review_plan_verdict == "FAIL":
  -> milestone.review_plan_status = "failed"
  -> spawn Definer: survey (regenerate)
  -> if survey_attempts >= 3 -> BLOCKER
```

### Step 11: Update state

```
Update docs/state/snapshot.json (atomic write)
Increment docs/state/seq.txt
Write WAL log
Update docs/state/status.md (only on spawn / complete / slot-release / BLOCKER)
Update docs/state/metrics/status_metrics.json (every iteration)
Release slot
```

### Step 12: Merge check

```
If issue state is verified:
  Add to merge_queue
  Trigger merge flow (see merge.md)
```

### Step 13: Completion check

Two-phase check:

```
Phase 1: verify all completion conditions
Wait 60 seconds
Phase 2: re-verify
Both pass -> write complete.md, stop
```

Completion conditions:

- All issues with state labels {defined, groomed, built, verified} closed
- `docs/issues/pending/` empty
- No open `blocker` label
- Merge queue empty
- All milestones have `review_plan_status == "passed"`

### Step 14: Scheduled restart check

```
If orchestrator.scheduled_restart_enabled:
  Check transitions count or hours elapsed
  If threshold reached -> run scheduled restart (exit 42)
```

### Step 15: Context refresh

Every `orchestrator.context.refresh_interval_iterations` iterations (default 10):

```
Re-read AGENTS.md
Re-read skills/orchestrator/SKILL.md
Clean closed-issue info from context
Write [CONTEXT_REFRESH] WAL
```

**Purpose**: Prevent Orchestrator context from accumulating stale info.

### Step 16: Sleep

```
If no ready issues and slots not full:
  Sleep idle_sleep_seconds
```

## State Transition Summary

```
(new) --[Definer: survey]--> defined
defined --[Definer: groom]--> groomed
groomed --[Builder: implement]--> built
built --[Verifier: verify_issue]--> verified
verified --[Orchestrator: merge]--> closed

Modifier-only transitions (state unchanged):
built (+ verifier_failed) --[Builder: fix_qa]--> built
built (+ merge_conflict) --[Builder: fix_merge]--> built
built (+ regression) --[Builder: fix_regression]--> built

State-reverting transitions:
built (+ verifier_failed) --[Definer: re_groom]--> groomed

Milestone path:
survey --[Orchestrator creates milestone]--> review_plan pending
review_plan --[PASS]--> passed (issues become eligible)
review_plan --[FAIL]--> failed (re-survey)

Initialization path:
survey --[plan.md + milestones created]--> awaiting human review
all review_plan passed --[human creates initialized]--> Lifecycle active
```