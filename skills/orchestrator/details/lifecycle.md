# Lifecycle

Orchestrator's main loop. Executed once per iteration.

## Boot Prerequisites

After Orchestrator Boot:
1. Read `AGENTS.md`.
2. Read `skills/orchestrator/SKILL.md`.
3. Run Preflight (config, environment, references, recovery).
4. Enter Lifecycle.

## Platform API Convention

Every "Platform query" or "Platform operation" in this document means a
call to the unified CLI:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

The CLI reads `.env` (`PLATFORM`, `API_TOKEN`, `REPO_ID`), normalizes
`REPO_ID`, and prints JSON to stdout. See `docs/commands.md` § Platform API
for the full command reference. Do NOT call the Platform API directly via
`curl`; always use `scripts/platform.ts`.

`<number>` in this document is the Platform issue number (the `number`
field in `scripts/platform.ts` output). The local issue ID (`t<n>`) maps
to it via `docs/state/issue_map.json`.

## Each Iteration

### Step 0: First-run initialization

This step runs **before all others**, and only until the project is initialized.

```
If docs/state/initialized exists:
  -> initialization complete, proceed to Step 1

If docs/state/initialized does NOT exist:
  If docs/requirements.md does NOT exist:
    -> HALT, write docs/state/PREFLIGHT_FAIL.md
    -> Create a BLOCKER Platform Issue:
         npx tsx scripts/platform.ts issue create \
           --title "BLOCKER: docs/requirements.md is missing" \
           --body "The project cannot start without requirements.md." \
           --labels "blocker"
    -> Stop this boot; the Launcher will retry up to
       launcher.max_restart_attempts times

  If docs/plan.md does NOT exist or is empty:
    -> spawn Definer: survey (initial survey)
       - Before spawn: generate factpack
         `npx tsx scripts/generate_factpack.ts phase_1_init survey`
         The milestone name is provisional at this point; use "phase_1_init"
         as the placeholder subject_id. The real milestone ID is created by
         survey itself; the factpack file for survey is transient and will be
         overwritten if survey runs again.
       - Timeout: when N (issue count) is unknown, fall back to
         roles.definer.timeout_minutes (60).
    -> the survey will create docs/plan.md and milestones
    -> after survey completes, review_plan triggers (Step 3)
    -> go to Step 8 (wait for completion)
    -> skip remaining steps this iteration

  If docs/plan.md exists AND docs/state/initialized does NOT exist:
    -> check all milestones' review_plan_status
    -> if NOT all "passed":
        -> Step 3 will handle pending review_plan
        -> proceed to Step 1
    -> if all "passed":
        -> Orchestrator creates docs/state/initialized
        -> log [AUTO_INITIALIZED] once
        -> proceed to Step 1
```

**Note**: `docs/state/initialized` marks the point where the initial plan is finalized. The Orchestrator creates it automatically after all `review_plan` runs pass. No human gate.

**Note on requirements.md HALT**: `docs/requirements.md` is a project-level precondition. If it is missing, no plan can be produced, and no issue can be generated. This is one of the few cases where a full HALT is correct. The Launcher will restart up to `launcher.max_restart_attempts` times; if `requirements.md` is still missing, the Launcher eventually gives up. The same HALT applies when a BLOCKER handoff from survey reports the missing precondition (see `survey.md`).

**Note on factpack for survey**: The survey factpack uses a placeholder milestone ID (`phase_1_init`) because the real milestone is not known until survey completes. This is intentional; the factpack is regenerated on any subsequent survey.

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
Run:
  npx tsx scripts/platform.ts issue list --labels human_review --state open

For each returned issue (each has fields: number, title, state, labels, updated_at):
  - Read the latest comment:
      npx tsx scripts/platform.ts issue latest-comment <number>
  - If the latest comment starts with "[RESPONSE]" and has not been processed:
      - Parse response and run the corresponding action (see human_review.md)
      - Update docs/state/questions.md
      - Remove the human_review label:
          npx tsx scripts/platform.ts label remove <number> --label human_review
      - Close the Platform Issue:
          npx tsx scripts/platform.ts issue close <number>
      - Record [HUMAN_REVIEW_RESOLVED] <issue>
```

See `human_review.md` for the full protocol.

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

**Note**: review_plan does NOT receive a factpack. Its inputs (requirements, plan, issues, dag, milestone file) are read directly.

**Note**: After survey completes, Orchestrator creates the milestone file with `review_plan_status` set to `pending`. This step triggers review_plan automatically.

**Argument passing**: Orchestrator passes `milestone` as a spawn argument. The handoff's `issue_id` field is set to the first issue of the milestone (e.g. `t1`); the milestone is recorded in `evidence.milestone`.

### Step 4: Query ready issues

```
For each state label in {defined, groomed, built, verified}:
  npx tsx scripts/platform.ts issue list --labels <label> --state open

Merge all results into one candidate set (dedupe by `number`).
```

Then filter:

```
Filter: deps closed (read docs/issues/<id>.md frontmatter)
Filter: not in active_issues (docs/state/snapshot.json)
Filter: not isolated (`isolated` label not in the returned labels)
```

**Note**:

- Query for **state labels** only, not modifier labels. State labels are mutually exclusive; each issue appears once in the union.
- If the current milestone's review_plan has not passed, do NOT spawn that milestone's issues (wait for review).
- Issues with the `isolated` label are excluded from ready-issue queries. They remain isolated until a human posts `[RESOLVED]` on the BLOCKER issue.
- Map local issue ID (`t<n>`) to Platform number using `docs/state/issue_map.json`.

### Step 5: Drift check

```
For each candidate issue:
  Run: npx tsx scripts/platform.ts issue get <number>
  Compare the returned labels/state to the local view:
    - Local state label from docs/issues/<id>.md frontmatter
    - Local status from docs/state/snapshot.json
  If drift detected:
    - Record [DRIFT] <issue> <layer>
    - Auto-sync local (for non-fatal drift)
    - Create human_review (for drift that affects AC, see human_review.md)
```

See `gates.md` § Drift Check for the full policy.

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

**Survey timeout computation**:

For Definer: survey, the effective timeout is:

```
timeout_minutes = timeout_base_minutes + timeout_per_issue_minutes × N
```

Where:

- `timeout_base_minutes` = `roles.definer.phases.survey.timeout_base_minutes` (default 15)
- `timeout_per_issue_minutes` = `roles.definer.phases.survey.timeout_per_issue_minutes` (default 2)
- `N` = number of issues in the current milestone

`N` is determined as follows:

- **Initial survey** (no plan yet): `N` unknown -> fall back to `roles.definer.timeout_minutes` (60).
- **Regeneration after review_plan FAIL**: `N` = count of issues in the milestone being regenerated (read from the milestone file).
- **New milestone begins**: `N` = count of issues planned for the milestone (from plan.md).

If `N` is known and the formula yields a value, use the formula; otherwise use the fixed `roles.definer.timeout_minutes`.

Example: N = 15 → 15 + 2×15 = 45 minutes.

All other phases use the fixed `roles.<role>.timeout_minutes`.

**Factpack generation (Definer only)**:

Before spawning a Definer in `groom` or `re_groom`, generate the factpack:

```
npx tsx scripts/generate_factpack.ts <issue_id> <phase>
```

Where `<phase>` is `groom` or `re_groom`. On failure (exit code != 0), log `[FACTPACK_FAIL]` and continue the spawn without the factpack (the Definer falls back to reading files directly).

Factpacks are NOT generated for Builder or Verifier; their inputs are minimal and phase-specific.

**Shared venv preparation (Verifier only)**:

Before spawning a Verifier in `verify_issue`, `verify_pre_merge`, or
`verify_post_merge`, prepare the hash-bucketed shared venv and inject
environment variables into the spawn:

1. Compute the shared venv path:

   ```
   python scripts/venv_path.py --root <worktree_path>
   ```

2. Branch on the result:

   - **Exit code 1** (no `pyproject.toml` or `uv.lock`):
     Log `[VENV_UNAVAILABLE] reason=no_dependency_spec`. Spawn the Verifier
     WITHOUT `UV_PROJECT_ENVIRONMENT` / `PYTHONPATH`. The Verifier falls
     back to per-worktree `uv sync`.

   - **Exit code 0 and path does not exist**:
     Run `python scripts/venv_path.py --root <worktree_path> --create`
     (1–3 minutes; runs in the Orchestrator's own time, not inside a slot).
     If `--create` fails (exit code 2), log
     `[VENV_UNAVAILABLE] reason=create_failed` and proceed as in exit code 1.

   - **Exit code 0 and path exists**:
     Spawn the Verifier with these additional environment variables:
     - `UV_PROJECT_ENVIRONMENT` = the shared venv path
     - `PYTHONPATH` = the Verifier's worktree path

   When `venv.enabled: false` in config, always take the exit-code-1 branch
   (skip shared venv entirely).

**Why this works without touching commands**: `UV_PROJECT_ENVIRONMENT`
redirects `uv run` to the shared venv; `PYTHONPATH` makes the worktree's
own code take precedence over any stale editable install. Verifier runs
command strings unchanged. See `docs/commands.md` § Shared venv.

Pass:

- `issue_id` (local, e.g. `t42`)
- `platform_issue` (the number from `scripts/platform.ts` output)
- `milestone` (required for review_plan)
- `mode` (determined by state)
- `worktree_path` (Builder/Verifier)
- `candidate_branch` / `merge_sha` (Verifier)
- `failure_history` (if fix)
- `memory_paths` (if retry >= 2)
- `retry_count`
- `factpack_path` (Definer only; `docs/state/factpack/<subject_id>.json`)

### Step 8: Wait for role

```
Wait until the role writes the handoff JSON or times out
On timeout -> see failures.md
```

### Step 9: Schema validation and gate check

```
Read handoff JSON

# 9a: Schema validation
Validate against schemas/<role>/<phase>.json
If invalid:
  schema_retry_count += 1
  If schema_retry_count < schema.max_retries:
    re-run same role (with schema errors)
  Else:
    create a BLOCKER Platform Issue:
      npx tsx scripts/platform.ts issue create \
        --title "BLOCKER: schema validation failed for <issue_id>" \
        --body "<schema errors>" \
        --labels "blocker"

# 9b: Gate check
Run: npx tsx scripts/gate_check.ts <role> <phase> <handoff_path> <current_state>
Parse the JSON output.

On exit code != 0:
  - exit code 2 -> usage error in Orchestrator code, create a BLOCKER as above
  - exit code 1 -> gate failed or args mismatch
    retry_count += 1
    If retry_count < roles.<role>.max_retries:
      re-run same role (with rejection reason)
    Else:
      create a BLOCKER as above

See gates.md for full Gate Failure Handling.
```

**Note**: The two retry counters (`schema_retry_count` and `retry_count`) are independent. See `gates.md`.

### Step 10: Process verdict

```
Based on handoff.status:
  COMPLETE -> go to Step 11
  FAIL -> see failures.md
  BLOCKER -> see failures.md § Builder BLOCKER routing
             (for verifier BLOCKER, create a BLOCKER Platform Issue
              via scripts/platform.ts and isolate the issue)
```

**Special case**: after review_plan completes:

```
If review_plan_verdict == "PASS" or "PASS_WITH_WARNINGS":
  -> milestone.review_plan_status = "passed"
  -> the milestone's issues become eligible for Lifecycle
  -> Step 0 will handle initialization on the next iteration
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

- No open issue with state labels {defined, groomed, built, verified}:
  ```
  For each of {defined, groomed, built, verified}:
    npx tsx scripts/platform.ts issue list --labels <label> --state open
    MUST return an empty array
  ```
- `docs/issues/pending/` empty
- No open `blocker` label:
  ```
  npx tsx scripts/platform.ts issue list --labels blocker --state open
  MUST return an empty array
  ```
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
survey --[plan.md + milestones created]--> review_plan pending
all review_plan passed --[Orchestrator creates initialized]--> Lifecycle active
```

**Note on factpack cleanup**: factpacks under `docs/state/factpack/` are transient and gitignored. They are overwritten on each spawn of the same subject and phase. No explicit cleanup is required.

**Note on venv cleanup**: shared venv buckets under `.pi-agent/venvs/` are gitignored and never auto-cleaned. Use `python scripts/venv_cleanup.py --delete` periodically to remove buckets older than `venv.cleanup_after_days`.