# Verifier: Verify Post-Merge

Post-merge lightweight smoke test verification.

## Trigger

Orchestrator spawns Verifier after a successful merge.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/plan.md` | Yes | Smoke test list |
| `docs/commands.md` | Yes | Toolchain commands |
| `merge_sha` | Yes | Commit SHA after merge |

## Permissions

- **Read-only**: MUST NOT write any file.
- **Allowed tools**: `read`, `bash`, `grep`, `find`.
- **Forbidden tools**: `edit`, `write`.

## Process

### Step 0: CWD verification

First action: confirm the current directory is correct.
If mismatch: write a BLOCKER handoff, stop.

### Step 1: Read smoke test list

Read the smoke test list from `docs/plan.md`'s `## Smoke tests` section.

If `## Smoke tests` does not exist in `docs/plan.md`, fall back to smoke commands in `docs/commands.md`.

### Step 2: Verify current HEAD

**Note**: The main branch is already checked out by Orchestrator before spawning Verifier.
**Do NOT run `git checkout main`** (Verifier is read-only).

Verify the current HEAD SHA matches `merge_sha`:

```
git rev-parse HEAD
```

If the HEAD SHA does not match `merge_sha`: write a BLOCKER handoff, stop.

### Step 3: Run smoke tests

Run each smoke test (lightweight, 10-20 tests).
Record exit code.

### Step 4: Determine verdict

- All smoke tests pass -> PASS
- Any failure -> FAIL, record `regressions_detected`

### Step 5: Post comment

Post on the Platform Issue:

```
## MERGE VERDICT: PASS

## Phase
post-merge

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Merge SHA
<sha>
```

Or:

```
## MERGE VERDICT: FAIL

## Phase
post-merge

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Regressions Detected
- <test>: previously passed at <timestamp>

## Merge SHA
<sha>
```

### Step 6: Write handoff

Write `docs/state/outputs/<id>_verifier_verify_post_merge.json`, conforming to `schemas/verifier/verify_post_merge.json`.

## Output

Write `docs/state/outputs/<id>_verifier_verify_post_merge.json`, conforming to `schemas/verifier/verify_post_merge.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Smoke test list read
- [ ] HEAD SHA matches `merge_sha`
- [ ] All smoke tests run
- [ ] Regressions recorded (if any)
- [ ] No file modified
- [ ] Comment posted
- [ ] Output conforms to `schemas/verifier/verify_post_merge.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Roll back merge (Orchestrator's responsibility)
- Skip running tests
- Run `git checkout` or any state-changing git command

## Boundaries

- Read only
- Write only: `docs/state/outputs/<id>_verifier_verify_post_merge.json`

## Difference from Pre-Merge

| Aspect | Pre-Merge | Post-Merge |
|---|---|---|
| Test scope | Cumulative tests + smoke tests | Smoke tests only |
| Duration | Long (may take minutes) | Short (< 1 minute) |
| Purpose | Confirm merge safety | Confirm merge did not break main |
| Failure handling | Block merge | Trigger rollback |