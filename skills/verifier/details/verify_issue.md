# Verifier: Verify Issue

Verify a single issue's AC.

## Trigger

Orchestrator spawns Verifier for an issue with state label `built` (no modifier labels).

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Authoritative AC + Verification commands + DoD |
| `docs/state/outputs/<id>_builder_implement.json` | Yes | Builder output |
| `docs/commands.md` | Yes | Toolchain commands |
| `docs/state/config_snapshot.json` | Yes | Config snapshot |
| `branch_sha` | Yes | Branch SHA to verify |

## Permissions

- **Read-only**: MUST NOT write any file.
- **Allowed tools**: `read`, `bash`, `grep`, `find`.
- **Forbidden tools**: `edit`, `write`.

## Process

### Step 0: CWD verification

First action: confirm the current directory is correct.
If mismatch: write a BLOCKER handoff, stop.

### Step 1: Read inputs

Read:

- ACs from `docs/issues/<id>.md` (authoritative).
- **`## Verification commands` section from `docs/issues/<id>.md`** (authoritative verification commands).
- Builder output (containing `ac_mapping`, `branch_sha`).
- Test commands from `docs/commands.md`.

Verify `branch_sha` matches the assigned one.
If mismatch: write a BLOCKER handoff, stop.

**Verify `ac_mapping` consistency**:

- Each `test` in `ac_mapping` MUST match the corresponding command in `## Verification commands`.
- If mismatch: record `[BUILDER_COMMAND_MISMATCH]`, use `## Verification commands` as authoritative.

### Step 2: Verify each AC

For each AC:

1. Get the verification command from `## Verification commands`.
2. If the command is `manual`:
   - Read the corresponding test file.
   - Check whether the test has a meaningful assertion.
   - If undecidable: mark `SKIP`, record in `test_quality_warnings`.
3. Otherwise:
   - Run the command.
   - Check exit code:
     - 0 -> PASS
     - non-zero -> FAIL
   - Record `command`, `exit_code`, `output_path` (if output is long).

### Step 3: Lint check

Run the linter (non-blocking):

```
ruff check --output-format=json
```

Record `errors` and `warnings`.

Use cache if valid: key = `sha256(file hashes + ruff config + ruff version)`.
Cache location: `docs/cache/lint/`.
TTL: `retention.lint_cache_days` days.

### Step 4: Test quality check

For each AC:

- Check if a corresponding test exists.
- Check if the test has a meaningful assertion (not `assert True`).
- If quality issues found: add to `test_quality_warnings` (warning only, not FAIL).

### Step 5: DoD verification

Read Definition of Done from `docs/issues/<id>.md`.
For each DoD item:

- Check whether it is satisfied.
- Record in `dod_verified` (boolean).

### Step 6: Determine failure_type (if FAIL)

If any AC fails, determine `failure_type`:

| Situation | failure_type |
|---|---|
| Code behavior does not match AC | `implementation` |
| AC semantics unclear (multiple readings) | `ac_ambiguous` |
| AC contradicts plan.md | `ac_wrong` |
| Passes locally but fails in Verifier | `test_env` |
| Test quality insufficient | `test_quality` |
| Merge failed | `merge_conflict` (determined by Orchestrator) |

Priority (when multiple match):

1. `merge_conflict`
2. `ac_wrong`
3. `ac_ambiguous`
4. `test_env`
5. `test_quality`
6. `implementation` (default)

### Step 7: Post comment

Post a verdict comment on the Platform Issue:

**PASS format**:

````markdown
## VERIFIER VERDICT: PASS

- [x] ac1: <description> — PASS (command: `...`, exit: 0)
- [x] ac2: <description> — PASS (command: `...`, exit: 0)

## Lint Report (non-blocking)
- ruff check: <errors> errors, <warnings> warnings

## DoD Verification
- [x] All AC pass
- [x] Tests pass
- [x] Lint clean

## Test Quality Warnings
- (none)

Tests: <command>, <passed>/<total> PASS
````

**FAIL format**:

````markdown
## VERIFIER VERDICT: FAIL

- [x] ac1: <description> — PASS
- [ ] ac2: <description> — FAIL
      Failure type: <failure_type>
      Command: <verification command>
      Exit code: <code>
      What I did: <action>
      What happened: <result>

## Lint Report (non-blocking)
- ruff check: <errors> errors, <warnings> warnings

## DoD Verification
- [ ] <item> — FAIL

## Summary
<max 2 lines>
````

### Step 8: Write handoff

Write `docs/state/outputs/<id>_verifier_verify_issue.json`, conforming to `schemas/verifier/verify_issue.json`.

**`command` in `ac_results` MUST come from `## Verification commands`.**

### Step 9: Label transition

On the Platform Issue:

- PASS: remove state label `built`, add state label `verified`
- FAIL: keep state label `built`, add modifier label `verifier_failed`

**Note**: On FAIL, the issue remains in `built` state. The `verifier_failed` label routes the issue to Builder: fix_qa.

## Output

Write `docs/state/outputs/<id>_verifier_verify_issue.json`, conforming to `schemas/verifier/verify_issue.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] All inputs read
- [ ] `## Verification commands` read
- [ ] `branch_sha` matches assignment
- [ ] `ac_mapping` matches `## Verification commands` (or mismatch recorded)
- [ ] Every AC has a verdict
- [ ] Every FAIL has `failure_type` + `what I did` + `what happened`
- [ ] Lint Report included
- [ ] DoD Verification included
- [ ] Test Quality Warnings included (if any)
- [ ] No file modified
- [ ] Comment posted
- [ ] Labels transitioned:
  - PASS: `built` -> `verified`
  - FAIL: keep `built`, add `verifier_failed`
- [ ] Output conforms to `schemas/verifier/verify_issue.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Close issue
- Skip running tests
- Modify AC
- FAIL solely due to lint (lint is non-blocking)
- FAIL solely due to test quality warnings
- **Substitute commands in `## Verification commands`**

## Boundaries

- Read only
- Write only: `docs/state/outputs/<id>_verifier_verify_issue.json`