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
| `factpack_path` | No | Path to factpack JSON (injected by Orchestrator) |
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

**Note on factpack**: When `factpack_path` is provided, prefer its content over reading `docs/commands.md`, `docs/coding_standards.md`, and `docs/state/config_snapshot.json` directly. The factpack contains the full text of those files plus a relevant config subset.

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Process

### Step 1: Read inputs

Read all inputs. If the Verifier FAIL report does not exist -> write a BLOCKER handoff.

If `factpack_path` was provided by Orchestrator:

- Read the factpack JSON.
- Use `facts.tech_stack` (fall back to `docs/plan.md` if null).
- Use `facts.commands_md` instead of reading `docs/commands.md`.
- Use `facts.coding_standards_md` instead of reading `docs/coding_standards.md`.
- Use `facts.config_subset` for `contract_first.*` and `limits.issue_granularity.*`.

If `factpack_path` was NOT provided (fallback path):

- Read `docs/commands.md`.
- Read `docs/coding_standards.md`.
- Read `docs/state/config_snapshot.json` (extract relevant keys).

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

Guard: if `total_acs == 0` (all ACs were removed), set `materiality_pct = 100` to force a fresh implementation rather than a fix_qa.

### Step 6: Sync Platform body

Read the full content of `docs/issues/<id>.md`, then push it to the Platform:

```
npx tsx scripts/platform.ts issue update <platform_issue> \
  --body "<full content of docs/issues/<id>.md>"
```

If the update fails (non-zero exit): retry once; if still failing, write a
BLOCKER handoff with reason `platform_body_sync_failed` and stop.

### Step 7: Label transition

On the Platform Issue:

- Remove state label `built`:
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label built
  ```
- Remove modifier label `verifier_failed` (if present):
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label verifier_failed
  ```
- Add state label `groomed`:
  ```
  npx tsx scripts/platform.ts label add <platform_issue> --label groomed
  ```

## Output

Write `docs/state/outputs/<id>_definer_re_groom.json`, conforming to `schemas/definer/re_groom.json`.

## Pre-output Checklist

- [ ] Verifier FAIL report read
- [ ] factpack read (if `factpack_path` provided)
- [ ] failure_type confirmed
- [ ] failed_acs analyzed
- [ ] AC corrected
- [ ] `verification_commands` updated
- [ ] `materiality_pct` computed
- [ ] `changes_made` recorded
- [ ] Platform Issue body synced via `issue update`
- [ ] Labels transitioned (`built` removed, `verifier_failed` removed, `groomed` added)
- [ ] Output conforms to `schemas/definer/re_groom.json`
- [ ] `reached_state: groomed`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Write code
- Modify files outside the issue
- Modify the Verifier FAIL report
- Modify Test requirements, Implementation notes
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Write only: `docs/issues/<id>.md`, Platform Issue (via `scripts/platform.ts`), `docs/state/outputs/<id>_definer_re_groom.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`

## Downstream Routing

Orchestrator decides the next step based on `materiality_pct`:

- `>= ac_change_blocker_pct`: discard the original branch, spawn Builder: implement
- `< ac_change_blocker_pct`: keep the original branch, spawn Builder: fix_qa