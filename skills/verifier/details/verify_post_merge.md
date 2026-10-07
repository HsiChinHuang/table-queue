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
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Permissions

- **Write scope**: your own handoff JSON only, at `docs/state/outputs/<id>_verifier_verify_post_merge.json`.
- **Allowed tools**: `read`, `bash`, `grep`, `find`, `write`.
- **Forbidden tools**: `edit`.
- **Forbidden writes**: `src/`, `tests/`, `docs/issues/`, and all other files under `docs/state/`.
- **Forbidden actions**: `git checkout` or any state-changing git command.

## Process

### Step 0: CWD verification

First action: confirm the current directory is correct.
If mismatch: write a BLOCKER handoff, stop.

### Step 0.5: Confirm shared venv (Orchestrator-provided)

The Orchestrator sets two environment variables before spawning a Verifier:

- `UV_PROJECT_ENVIRONMENT` — the hash-bucketed shared venv path
- `PYTHONPATH` — the current worktree path

Confirm both are non-empty. If either is empty, log `[VENV_UNAVAILABLE]`
and proceed; the per-worktree `uv sync` will be used instead. This is a
WARN, not a failure.

Run all verification commands as-is. Do NOT modify command strings.

**Note**: This step is only meaningful for Python projects.

### Step 1: Read smoke test list

Read the smoke test list from `docs/plan.md`'s `## Smoke tests` section.

If `## Smoke tests` does not exist in `docs/plan.md`, fall back to smoke commands in `docs/commands.md`.

### Step 2: Verify current HEAD

**Note**: The main branch is already checked out by Orchestrator before spawning Verifier.
**Do NOT run `git checkout main`** (Orchestrator prepared the worktree).

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
npx tsx scripts/platform.ts issue comment <platform_issue> --body "<verdict>"
```

**PASS verdict**:

````markdown
## MERGE VERDICT: PASS

## Phase
post-merge

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Merge SHA
<sha>
````

**FAIL verdict**:

````markdown
## MERGE VERDICT: FAIL

## Phase
post-merge

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Regressions Detected
- <test>: previously passed at <timestamp>

## Merge SHA
<sha>
````

### Step 6: Write handoff

Write `docs/state/outputs/<id>_verifier_verify_post_merge.json`, conforming to `schemas/verifier/verify_post_merge.json`.

## Output

Write `docs/state/outputs/<id>_verifier_verify_post_merge.json`, conforming to `schemas/verifier/verify_post_merge.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Shared venv confirmed (or `[VENV_UNAVAILABLE]` logged)
- [ ] Smoke test list read
- [ ] HEAD SHA matches `merge_sha`
- [ ] All smoke tests run
- [ ] Regressions recorded (if any)
- [ ] Handoff JSON written under `docs/state/outputs/` only
- [ ] Comment posted via `scripts/platform.ts`
- [ ] Output conforms to `schemas/verifier/verify_post_merge.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Modify issues
- Roll back merge (Orchestrator's responsibility)
- Modify other `docs/state/` files
- Skip running tests
- Run `git checkout` or any state-changing git command
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Read: `docs/plan.md`, `docs/commands.md`, source files, test files
- Write only: `docs/state/outputs/<id>_verifier_verify_post_merge.json`

## Difference from Pre-Merge

| Aspect | Pre-Merge | Post-Merge |
|---|---|---|
| Test scope | Cumulative tests + smoke tests | Smoke tests only |
| Duration | Long (may take minutes) | Short (< 1 minute) |
| Purpose | Confirm merge safety | Confirm merge did not break main |
| Failure handling | Block merge | Trigger rollback |