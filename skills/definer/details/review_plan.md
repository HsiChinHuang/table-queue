# Definer: Review Plan

Review the generated plan and issues for correctness; find gaps or problems.

## Trigger

Orchestrator detects a milestone with `review_plan_status == "pending"` (see `lifecycle.md` Step 3).

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/requirements.md` | Yes | Original requirements |
| `docs/plan.md` | Yes | Generated plan |
| `docs/issues/*.md` | Yes | Generated issues |
| `docs/state/dag.json` | Yes | DAG |
| `docs/state/milestones/<milestone>.json` | Yes | Milestone info |
| `milestone` (arg) | Yes | Passed by Orchestrator on spawn |

## Process

### Step 1: Coverage check

For each requirement in `requirements.md`:

- Find the corresponding issue.
- If none -> record `coverage_gap` finding.

### Step 2: Granularity check

For each issue:

- Count ACs, files, estimated diff lines.
- If exceeds thresholds (`limits.issue_granularity.*`) -> record `granularity_too_large` finding.
- If AC count is 1 and file count is 0 -> record `granularity_too_small` finding.

### Step 3: Dependency check

- Check that `depends:` references exist.
- Check for cycles.
- Check for orphan nodes (except t0).
- If found -> record `dependency_error` / `cycle` / `orphan` finding.

### Step 4: Duplicate and contradiction check

- Check for two issues with identical AC -> `duplicate_ac`.
- Check for two issues with contradictory AC -> `contradictory_ac`.

### Step 5: Generate verdict

- All findings are `warning` -> `PASS_WITH_WARNINGS`
- Any `error` -> `FAIL`
- No findings -> `PASS`

### Step 6: Update milestone file

Write `docs/state/milestones/<milestone>.json`:

- Update `review_plan_status` (`passed` or `failed`)
- Update `review_plan_completed_at`
- Update `review_plan_verdict`
- Increment `review_plan_attempts`

## Output

Write `docs/state/outputs/<milestone>_definer_review_plan.json`.

**Note**: The `issue_id` field in the handoff is set to the first issue of the milestone. The milestone is recorded in `evidence.milestone`.

## Pre-output Checklist

- [ ] Coverage check complete
- [ ] Granularity check complete
- [ ] Dependency check complete
- [ ] Duplicate and contradiction check complete
- [ ] Verdict determined
- [ ] Findings listed
- [ ] Milestone file updated
- [ ] Output conforms to `schemas/definer/review_plan.json`
- [ ] `reached_state: defined`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Directly modify issues (review is read-only)
- Write code
- Modify DAG

## Boundaries

- Read only
- Write only: `docs/state/milestones/<milestone>.json`, `docs/state/outputs/<milestone>_definer_review_plan.json`

## FAIL Routing

If verdict is `FAIL`:

1. Orchestrator sets `review_plan_status` to `failed`.
2. Orchestrator spawns Definer: survey (regenerate).
3. If `survey_attempts >= 3` -> BLOCKER.

See `skills/orchestrator/details/failures.md`.