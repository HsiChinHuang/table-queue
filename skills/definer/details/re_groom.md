# Definer: Re-groom

Correct an issue's AC after a Verifier FAIL.

## Trigger

Verifier returns `failure_type` of `ac_ambiguous` or `ac_wrong`.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Current issue |
| `docs/plan.md` | Yes | Project plan |
| `docs/state/outputs/<id>_verifier_verify_issue.json` | Yes | Verifier FAIL report |
| `docs/backlog.md` | Yes | DAG context |

## Process

### Step 1: Read inputs

Read all inputs. If the Verifier FAIL report does not exist -> write a BLOCKER handoff.

### Step 2: Analyze failure

Read `failure_type` and `failed_acs`:

- `ac_ambiguous`: AC semantics unclear, needs clarification.
- `ac_wrong`: AC contradicts plan.md, needs correction.

### Step 3: Correct AC

Based on the failure:

- Clarify: rewrite vague AC as concrete behavior.
- Correct: rewrite wrong AC to match plan.md.
- Remove: delete ACs that cannot be implemented.
- Add: add missing ACs.

Each correction MUST be recorded in `changes_made`.

### Step 4: Redefine verification commands

For modified ACs, redefine verification commands.

Write to `docs/issues/<id>.md`'s `## Verification commands` section (overwrite previous content).

### Step 5: Compute materiality

Compute the ratio of AC changes:

```
materiality_pct = (changed_acs / total_acs) * 100
```

### Step 6: Sync Platform

Update the Platform Issue body.

### Step 7: Label transition

On the Platform Issue:

- Remove label `built` or `qa_failed`
- Add label `groomed`

## Output

Write `docs/state/outputs/<id>_definer_re_groom.json`, conforming to `schemas/definer/re_groom.json`.

## Pre-output Checklist

- [ ] Verifier FAIL report read
- [ ] failure_type confirmed
- [ ] failed_acs analyzed
- [ ] AC corrected
- [ ] `verification_commands` updated
- [ ] `materiality_pct` computed
- [ ] `changes_made` recorded
- [ ] Platform Issue body synced
- [ ] Labels transitioned (`built` / `qa_failed` -> `groomed`)
- [ ] Output conforms to `schemas/definer/re_groom.json`
- [ ] `reached_state: groomed`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Write code
- Modify files outside the issue
- Modify the Verifier FAIL report
- Modify Test requirements, Implementation notes

## Boundaries

- Write only: `docs/issues/<id>.md`, Platform Issue body, `docs/state/outputs/<id>_definer_re_groom.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`

## Downstream Routing

Orchestrator decides the next step based on `materiality_pct`:

- `>= ac_change_blocker_pct`: discard the original branch, spawn Builder: implement
- `< ac_change_blocker_pct`: keep the original branch, spawn Builder: fix_qa