# Definer: Survey

Initialize the project: read requirements, generate plan.md and the first batch of issues.

## Trigger

- Project startup (initial survey)
- New milestone begins
- Regeneration after review_plan FAIL

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/requirements.md` | Yes | Project requirements |
| `docs/plan.md` | No | If exists, a high-level plan is already present |
| `docs/state/milestones/*.json` | No | If exists, this is a regeneration |

## Initial Input Validation

**Before Step 1**, verify:

1. `docs/requirements.md` exists.
   - If NOT exists: write a BLOCKER handoff with reason "docs/requirements.md is missing".
   - Stop. Orchestrator will create a BLOCKER issue.

2. `docs/requirements.md` is non-empty.
   - If empty (0 bytes or only whitespace): write a BLOCKER handoff with reason "docs/requirements.md is empty".
   - Stop.

3. `docs/requirements.md` contains at least:
   - A `## Tech stack` section (non-empty)
   - A `## Core features` section (at least 1 bullet)
   - If any missing: write a BLOCKER handoff with reason "docs/requirements.md missing section: <section>".
   - Stop.

**Orchestrator handles BLOCKER**: On receiving a BLOCKER handoff from survey, Orchestrator creates a `blocker` Platform Issue. Human must fix `requirements.md` before survey can run again.

## Plan Template (built-in)

If no `docs/plan.md` exists, use this template to generate one:

```
# Plan

Tech stack: <extracted from requirements>

## <Milestone 1 name>

> Issue template:
> - Requirement: <requirements.md anchor>
> - Title: <title>
> - Acceptance:
>     - <checkable statement>
> - Files: <file paths>
> - Depends: [<issue ids>]

> Issue template:
> ...

## <Milestone 2 name>

> Issue template:
> ...
```

## Process

### Step 1: Read inputs

Read `docs/requirements.md`.

If `docs/plan.md` exists and is non-empty, skip Step 2 and go directly to Step 3.

If this is a regeneration after review_plan FAIL:

- Read the corresponding milestone file
- Increment `survey_attempts`

### Step 2: Generate high-level plan

Generate `docs/plan.md`:

1. **Tech stack**: extracted from requirements.
2. **Milestones**: split the project into 2-5 milestones.
3. **Issue blocks per milestone**: use the template above.

### Step 3: Generate first batch of issues

Generate only the current milestone's issues (rolling planning).

For each issue:

1. Assign ID: `t<max+1>` (starting from t0).
2. Write `docs/issues/t<n>.md` with frontmatter:

```
---
id: t<n>
title: <title>
depends: [<ids>]
platform_issue: null
---
```

3. Fill Definer-owned sections: Metadata, Goal, AC draft, Dependencies, Constraints, DoD template.
4. Do NOT fill: Context, Out of scope, DoD specific (Definer groom responsibility).

### Step 4: Build DAG

1. Nodes = all issues.
2. Edges = `depends:` relationships.
3. Detect cycles (DFS).
4. Topological sort.
5. Mark critical path.
6. Write `docs/state/dag.json`.

### Step 5: Write backlog

Write `docs/backlog.md`:

```
# Backlog

| ID | Title | Depends | Platform | Status |
|---|---|---|---|---|
| t0 | ... | [] | - | defined |
```

### Step 6: Create Platform Issues

For each issue (topological order):

1. Create Platform Issue with label `defined`.
2. Update `docs/issues/t<n>.md`'s `platform_issue`.
3. Update `docs/state/issue_map.json`.
4. Update `docs/backlog.md`.

Batch: 50 per batch, 5s delay, rate limit 5 req/s.

### Step 7: Generate review report

Write `docs/state/dag.mmd` (Mermaid visualization).

### Step 8: Create milestone file

Write `docs/state/milestones/<milestone>.json`:

```json
{
  "schema_version": "1.0",
  "milestone": "phase_1_auth",
  "survey_completed_at": "2026-10-05T14:00:00Z",
  "review_plan_status": "pending",
  "review_plan_completed_at": null,
  "review_plan_verdict": null,
  "review_plan_attempts": 0,
  "issues_generated": ["t1", "t2", "t3"],
  "survey_attempts": 0
}
```

**Creating this file triggers Orchestrator's review_plan** (see `lifecycle.md` Step 3).

## Output

Write `docs/state/outputs/<milestone>_definer_survey.json`.

**Note**: The `issue_id` field in the handoff is set to the first issue generated (e.g. `t1`). The milestone is recorded in `evidence.milestone`.

## Pre-output Checklist

- [ ] `docs/requirements.md` exists and passes initial validation
- [ ] requirements.md read
- [ ] plan.md generated or already exists
- [ ] All issues have frontmatter (id, title, depends, platform_issue)
- [ ] All issues have Metadata, Goal, AC draft, Dependencies, Constraints, DoD template
- [ ] DAG has no cycles
- [ ] No orphan nodes (except t0)
- [ ] backlog.md written
- [ ] Platform Issues created
- [ ] issue_map.json written
- [ ] milestone file written
- [ ] Output conforms to `schemas/definer/survey.json`
- [ ] `reached_state: defined`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Write code
- Groom issues (Definer groom's responsibility)
- Implement or test
- Modify other roles' labels
- Delete existing files

## Boundaries

- Write only: `docs/plan.md`, `docs/issues/*.md`, `docs/backlog.md`, `docs/state/issue_map.json`, `docs/state/dag.json`, `docs/state/milestones/*.json`, `docs/state/outputs/<milestone>_definer_survey.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`