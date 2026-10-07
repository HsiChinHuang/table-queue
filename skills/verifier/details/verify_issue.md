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
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Permissions

- **Write scope**: your own handoff JSON only, at `docs/state/outputs/<id>_verifier_verify_issue.json`.
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
`UV_PROJECT_ENVIRONMENT` redirects `uv run` to the shared venv, and
`PYTHONPATH` makes the worktree's own code take precedence over any
stale editable install.

**Note**: This step is only meaningful for Python projects. For other
tech stacks (e.g. Node.js), the environment variables are simply absent
and the step is a no-op.

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

Priority (when multiple match):

1. `ac_wrong`
2. `ac_ambiguous`
3. `test_env`
4. `test_quality`
5. `implementation` (default)

**Note**: `merge_conflict` and `regression` are NOT set by Verifier. They are determined by Orchestrator during the merge phase.

### Step 7: Post comment

Post a verdict comment on the Platform Issue:

```
npx tsx scripts/platform.ts issue comment <platform_issue> --body "<verdict>"
```

**PASS verdict**:

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

**FAIL verdict**:

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

- PASS: swap state label `built` → `verified`:
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label built
  npx tsx scripts/platform.ts label add <platform_issue> --label verified
  ```
- FAIL: keep state label `built` unchanged; add modifier label `verifier_failed`:
  ```
  npx tsx scripts/platform.ts label add <platform_issue> --label verifier_failed
  ```

**Note**: On FAIL, the issue remains in `built` state. The `verifier_failed` label routes the issue to Builder: fix_qa.

## Output

Write `docs/state/outputs/<id>_verifier_verify_issue.json`, conforming to `schemas/verifier/verify_issue.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Shared venv confirmed (or `[VENV_UNAVAILABLE]` logged)
- [ ] All inputs read
- [ ] `## Verification commands` read
- [ ] `branch_sha` matches assignment
- [ ] `ac_mapping` matches `## Verification commands` (or mismatch recorded)
- [ ] Every AC has a verdict
- [ ] Every FAIL has `failure_type` + `what I did` + `what happened`
- [ ] Lint Report included
- [ ] DoD Verification included
- [ ] Test Quality Warnings included (if any)
- [ ] Handoff JSON written under `docs/state/outputs/` only
- [ ] Comment posted via `scripts/platform.ts`
- [ ] Labels transitioned:
  - PASS: `built` removed, `verified` added
  - FAIL: `built` unchanged, `verifier_failed` added
- [ ] Output conforms to `schemas/verifier/verify_issue.json`
- [ ] `reached_state: verified` (if PASS) or `unchanged` (if FAIL)
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify code
- Modify tests
- Modify issues
- Modify other `docs/state/` files
- Close issue
- Skip running tests
- Modify AC
- FAIL solely due to lint (lint is non-blocking)
- FAIL solely due to test quality warnings
- Run `git checkout` or any state-changing git command
- **Substitute commands in `## Verification commands`**
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Read: `docs/issues/<id>.md`, `docs/state/outputs/<id>_builder_implement.json`, `docs/commands.md`, `docs/state/config_snapshot.json`, source files, test files
- Write only: `docs/state/outputs/<id>_verifier_verify_issue.json`