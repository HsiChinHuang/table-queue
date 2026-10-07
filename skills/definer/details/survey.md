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
| `factpack_path` | No | Path to factpack JSON (injected by Orchestrator) |

**Note on factpack**: When `factpack_path` is provided by Orchestrator, prefer its content over reading `docs/commands.md`, `docs/coding_standards.md`, and `docs/state/config_snapshot.json` directly. The factpack contains the full text of those files plus a relevant config subset and the current issue_map.

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API for the full command reference.

## Generation Discipline

**This mode MUST generate content in small batches, not in a single large generation.**

Rationale: with local slow models (Qwen3.8-27B), a single 6+ minute generation block risks being cut off by timeout, discarding all prior thinking. Batching ensures:

- Each batch completes in **~3-5 minutes** of generation
- Each batch is **persisted immediately** before the next batch starts
- A crash loses at most one batch (not the entire survey)
- The model gets a "breath" between batches, preventing over-long generations

**Batch size** = `min(5, max(1, ceil(N / 3)))`, where N is the total number of issues in the current milestone.

Examples:

| N | batch_size | batches |
|---|---|---|
| 3 | 1 | 3 |
| 8 | 3 | 3 |
| 15 | 5 | 3 |
| 30 | 5 | 6 |

**The batching is REQUIRED, not optional.** Do NOT generate all issues in one pass.

**Tool constraint**: The Pi Agent `write` tool accepts exactly one `{path, content}` pair per call. There is no batch-write API. Each file requires its own `write` call. Within a batch, the calls are independent and MAY be issued sequentially or in parallel in the same turn; all writes of a batch MUST complete before the next batch starts.

## Initial Input Validation

**Before Step 1**, verify:

1. `docs/requirements.md` exists.
   - If NOT exists: write a BLOCKER handoff with reason "docs/requirements.md is missing".
   - Stop.

2. `docs/requirements.md` is non-empty.
   - If empty (0 bytes or only whitespace): write a BLOCKER handoff with reason "docs/requirements.md is empty".
   - Stop.

3. `docs/requirements.md` contains at least:
   - A `## Tech stack` section (non-empty)
   - A `## Core features` section (at least 1 bullet)
   - If any missing: write a BLOCKER handoff with reason "docs/requirements.md missing section: <section>".
   - Stop.

**Orchestrator handles BLOCKER**: `docs/requirements.md` is a project-level precondition. Any failure in the initial validation above makes the whole project unable to proceed. On receiving a BLOCKER handoff from survey, the Orchestrator writes `docs/state/PREFLIGHT_FAIL.md`, creates a BLOCKER Platform Issue via `scripts/platform.ts`, and HALTs. The Launcher retries up to `launcher.max_restart_attempts` times; if the input remains invalid, the Launcher eventually gives up. There is no "isolate and continue" path for this case because no milestone can be planned without valid requirements.

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

If `factpack_path` was provided by Orchestrator:

- Read the factpack JSON.
- Use `facts.tech_stack` (or fall back to reading `requirements.md` if null).
- Use `facts.commands_md` instead of reading `docs/commands.md`.
- Use `facts.coding_standards_md` instead of reading `docs/coding_standards.md`.
- Use `facts.config_subset` for `contract_first.*` and `limits.issue_granularity.*`.
- Use `facts.issue_map.mappings` as the current local-to-platform mapping.

If `factpack_path` was NOT provided (fallback path):

- Read `docs/commands.md`.
- Read `docs/coding_standards.md`.
- Read `docs/state/config_snapshot.json` (extract relevant keys).
- Read `docs/state/issue_map.json`.

If `docs/plan.md` exists and is non-empty, skip Step 2 and go directly to Step 3.

If this is a regeneration after review_plan FAIL:

- Read the corresponding milestone file
- Increment `survey_attempts`

### Step 2: Generate high-level plan

**This step produces a single file (`docs/plan.md`).** Generate its full content in memory, then write it in ONE `write` tool call.

Generate `docs/plan.md`:

1. **Tech stack**: extracted from requirements.
2. **Milestones**: split the project into 2-5 milestones.
3. **Issue blocks per milestone**: use the template above.

**Estimate N** = total number of issues planned for the current milestone. Record this estimate; it drives the initial batch size for Step 3. The exact count is confirmed during Step 3 as issues are actually generated.

### Step 3: Generate first batch of issues (BATCHED)

Generate only the current milestone's issues (rolling planning).

**If the actual issue count differs from the Step 2 estimate**, recompute `batch_size = min(5, max(1, ceil(N / 3)))` before writing the first batch. `N` here is the actual count you are about to generate.

**REQUIRED batching discipline**:

```
N = actual number of issues in this milestone (may differ from Step 2 estimate)
batch_size = min(5, max(1, ceil(N / 3)))
total_batches = ceil(N / batch_size)

For each batch b in [1 .. total_batches]:
  1. Generate the content for the issues in this batch (in memory)
     - Each issue: ~1 minute of thinking + generation
     - Target: the whole batch in ~3-5 minutes
  2. Write each file in its own `write` tool call
     - Each call: {path: docs/issues/t<n>.md, content: <full file content>}
     - The Pi Agent `write` tool accepts exactly one file per call
     - Within a batch, the calls are independent and MAY be issued
       sequentially or in parallel in the same turn
     - Wait for all writes in the batch to complete before starting the next batch
  3. Confirm all writes of the batch succeeded, then move to next batch

Do NOT concatenate all batches into one large generation.
Do NOT defer writes to the end of Step 3.
```

For each issue, the content written MUST include:

1. Assign ID: `t<max+1>` (starting from t0).
2. Frontmatter:

```
---
id: t<n>
title: <title>
depends: [<ids>]
platform_issue: null
---

3. Definer-owned sections: Metadata, Goal, AC draft, Dependencies, Constraints, DoD template.
4. Do NOT fill: Context, Out of scope, DoD specific (Definer groom responsibility).

### Step 4: Build DAG

**Single-file step.** Generate `docs/state/dag.json` in memory, write in ONE tool call.

1. Nodes = all issues.
2. Edges = `depends:` relationships.
3. Detect cycles (DFS).
4. Topological sort.
5. Mark critical path.
6. Write `docs/state/dag.json`.

### Step 5: Write backlog

**Single-file step.** Generate `docs/backlog.md` in memory, write in ONE tool call.

Write `docs/backlog.md`:

```
# Backlog

| ID | Title | Depends | Platform | Status |
|---|---|---|---|---|
| t0 | ... | [] | - | defined |
```

### Step 6: Create Platform Issues

**API step, not a generation step.** For each issue in topological order:

1. Create the Platform Issue via the CLI:
   ```
   npx tsx scripts/platform.ts issue create \
     --title "<title>" \
     --body "<Definer-owned sections: Metadata, Goal, AC draft, Dependencies, Constraints, DoD template>" \
     --labels "defined"
   ```
   The returned JSON contains `number`. Record it.

2. Update `docs/issues/t<n>.md`'s frontmatter `platform_issue` to the returned `number`.

3. Update `docs/state/issue_map.json`: add an entry `{ "t<n>": <number> }`.

4. Update `docs/backlog.md` Platform column.

**Throttling**: max 5 requests/second. Send requests in batches of 50 with
per-request pacing (200ms between requests within a batch). Sleep 5s
between batches.

**Note**: This step involves tool calls but minimal generation. Do NOT batch generation here.

### Step 7: Generate review report

**Single-file step.** Write `docs/state/dag.mmd` (Mermaid visualization) in ONE tool call.

### Step 8: Create milestone file

**Single-file step.** Write `docs/state/milestones/<milestone>.json` in ONE tool call:

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

### Step 9: Write handoff

**Single-file step.** Write `docs/state/outputs/<milestone>_definer_survey.json` in ONE tool call, conforming to `schemas/definer/survey.json`.

## Output

Write `docs/state/outputs/<milestone>_definer_survey.json`.

**Note**: The `issue_id` field in the handoff is set to the first issue generated (e.g. `t1`). The milestone is recorded in `evidence.milestone`.

## Pre-output Checklist

- [ ] `docs/requirements.md` exists and passes initial validation
- [ ] requirements.md read
- [ ] factpack read (if `factpack_path` provided)
- [ ] N (actual issue count) determined
- [ ] `batch_size = min(5, max(1, ceil(N / 3)))` computed
- [ ] All `ceil(N / batch_size)` batches completed
- [ ] Each file was written in its own `write` tool call
- [ ] plan.md generated or already exists
- [ ] All issues have frontmatter (id, title, depends, platform_issue)
- [ ] All issues have Metadata, Goal, AC draft, Dependencies, Constraints, DoD template
- [ ] DAG has no cycles
- [ ] No orphan nodes (except t0)
- [ ] backlog.md written
- [ ] Platform Issues created via `scripts/platform.ts`
- [ ] `platform_issue` recorded in each issue frontmatter
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
- **Generate all issues in a single large pass** (batching is REQUIRED)
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Write only: `docs/plan.md`, `docs/issues/*.md`, `docs/backlog.md`, `docs/state/issue_map.json`, `docs/state/dag.json`, `docs/state/milestones/*.json`, `docs/state/outputs/<milestone>_definer_survey.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`