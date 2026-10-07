# Verifier: Verify Pre-Merge

Pre-merge cumulative test verification.

## Trigger

Orchestrator spawns Verifier before merge.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/state/merge_test_index.json` | Yes | Cumulative test index |
| `docs/issues/<id>.md` | Yes | Current issue |
| `docs/commands.md` | Yes | Toolchain commands |
| `docs/plan.md` | Yes | Smoke test list |
| `candidate_branch` | Yes | Candidate branch name |
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Permissions

- **Write scope**: your own handoff JSON only, at `docs/state/outputs/<id>_verifier_verify_pre_merge.json`.
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

### Step 1: Read cumulative test index

Read `docs/state/merge_test_index.json`.

Format:

```json
{
  "schema_version": "1.0",
  "updated_at": "...",
  "tests": [
    { "issue_id": "t1", "command": "uv run pytest tests/test_auth.py" },
    { "issue_id": "t2", "command": "uv run pytest tests/test_models.py" }
  ]
}
```

### Step 2: Switch to candidate branch

**Note**: The candidate branch is provided by Orchestrator via spawn argument.
**Do NOT run `git checkout`** (Orchestrator prepared the worktree).

Verify the current branch is the candidate branch:

```
git branch --show-current
```

If the current branch does not match `candidate_branch`: write a BLOCKER handoff, stop.

### Step 3: Run cumulative tests

For each test command in the index:

1. Run the command.
2. Record exit code.
3. If failed, record in `failed_tests`.

### Step 4: Run smoke tests

Read the smoke test list from `docs/plan.md`'s `## Smoke tests` section.

Run each smoke test (at least `merge.smoke_tests_min`, at most `merge.smoke_tests_max`).

If `## Smoke tests` does not exist in `docs/plan.md`, fall back to smoke commands in `docs/commands.md`.

### Step 5: Determine verdict

- All cumulative + smoke tests pass -> PASS
- Any failure -> FAIL, record `failed_tests`

### Step 6: Post comment

Post on the Platform Issue:

```
npx tsx scripts/platform.ts issue comment <platform_issue> --body "<verdict>"
```

**PASS verdict**:

````markdown
## MERGE VERDICT: PASS

## Phase
pre-merge

## Cumulative Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>
````

**FAIL verdict**:

````markdown
## MERGE VERDICT: FAIL

## Phase
pre-merge

## Cumulative Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Failed Tests
- <test>: <error summary>
````

### Step 7: Write handoff

Write `docs/state/outputs/<id>_verifier_verify_pre_merge.json`, conforming to `schemas/verifier/verify_pre_merge.json`.

## Output

Write `docs/state/outputs/<id>_verifier_verify_pre_merge.json`, conforming to `schemas/verifier/verify_pre_merge.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Shared venv confirmed (or `[VENV_UNAVAILABLE]` logged)
- [ ] Cumulative test index read
- [ ] Candidate branch confirmed
- [ ] All cumulative tests run
- [ ] Smoke tests run
- [ ] Failed tests recorded (if any)
- [ ] Handoff JSON written under `docs/state/outputs/` only
- [ ] Comment posted via `scripts/platform.ts`
- [ ] Output conforms to `schemas/verifier/verify_pre_merge.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Modify issues
- Modify cumulative test index (Orchestrator's responsibility)
- Modify other `docs/state/` files
- Skip running tests
- Run `git checkout` or any state-changing git command
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Read: `docs/state/merge_test_index.json`, `docs/issues/<id>.md`, `docs/commands.md`, `docs/plan.md`, source files, test files
- Write only: `docs/state/outputs/<id>_verifier_verify_pre_merge.json`