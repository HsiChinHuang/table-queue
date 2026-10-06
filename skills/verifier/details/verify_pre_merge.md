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

## Permissions

- **Read-only**: MUST NOT write any file.
- **Allowed tools**: `read`, `bash`, `grep`, `find`.
- **Forbidden tools**: `edit`, `write`.

## Process

### Step 0: CWD verification

First action: confirm the current directory is correct.
If mismatch: write a BLOCKER handoff, stop.

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
**Do NOT run `git checkout`** (Verifier is read-only).

Orchestrator has already prepared the worktree with the candidate branch checked out. Verify that the current branch is the candidate branch:

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
## MERGE VERDICT: PASS

## Phase
pre-merge

## Cumulative Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Smoke Tests
- Total: <n>, Passed: <n>, Failed: <n>
```

Or:

```
## MERGE VERDICT: FAIL

## Phase
pre-merge

## Cumulative Tests
- Total: <n>, Passed: <n>, Failed: <n>

## Failed Tests
- <test>: <error summary>
```

### Step 7: Write handoff

Write `docs/state/outputs/<id>_verifier_verify_pre_merge.json`, conforming to `schemas/verifier/verify_pre_merge.json`.

## Output

Write `docs/state/outputs/<id>_verifier_verify_pre_merge.json`, conforming to `schemas/verifier/verify_pre_merge.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Cumulative test index read
- [ ] Candidate branch confirmed
- [ ] All cumulative tests run
- [ ] Smoke tests run
- [ ] Failed tests recorded (if any)
- [ ] No file modified
- [ ] Comment posted
- [ ] Output conforms to `schemas/verifier/verify_pre_merge.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Modify cumulative test index (Orchestrator's responsibility)
- Skip running tests
- Run `git checkout` or any state-changing git command

## Boundaries

- Read only
- Write only: `docs/state/outputs/<id>_verifier_verify_pre_merge.json`