# Builder: Fix Regression

Fix a post-merge regression.

## Trigger

Verifier detects a regression during `verify_post_merge`, **Orchestrator creates the fix branch and worktree**, then spawns Builder: fix_regression.

## Orchestrator pre-actions

Before spawning Builder, Orchestrator MUST:

1. Create branch `issue/REG-FIX-<id>-<slug>` and worktree `../worktrees/REG-FIX-<id>` based on `origin/main`:
   ```
   git worktree add ../worktrees/REG-FIX-<id> -b issue/REG-FIX-<id>-<slug> origin/main
   ```
   (The reference implementation is `createFixBranch({ fix_type: 'regression', ... })` in
   `extensions/merge_orchestrator.ts`.)
2. Pass `worktree_path` to Builder.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/state/outputs/<id>_verifier_verify_post_merge.json` | Yes | Regression report |
| `docs/state/merge_history.json` | Yes | Recent merge history |
| `docs/commands.md` | Yes | Toolchain commands |
| `worktree_path` | Yes | Assigned working directory (fix worktree) |
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Process

### Step 0: CWD verification

First action: `pwd` MUST equal the assigned `worktree_path`.
If mismatch: write a BLOCKER handoff, stop.

### Step 1: Confirm branch

Run `git branch --show-current`, confirm the branch is `issue/REG-FIX-<id>-<slug>`.

If mismatch:

- Write a BLOCKER handoff, noting "expected fix branch, got <actual>".
- Stop.

### Step 2: Read regression report

Read `verify_post_merge` output, extract:

- `regressions_detected`
- Each regression's `test` / `previously_passed_at`

Read `merge_history.json` to find the latest merge.

### Step 3: Locate root cause

Analyze the regressed tests to find the root cause:

- Was it caused by the merged code?
- Was it caused by a test environment change?
- Was it caused by an earlier issue's change?

### Step 4: Fix

Based on the root cause:

- If merged code: correct the code.
- If environment: adjust the environment configuration.
- If earlier issue: may need `[UPSTREAM_BUG]`.

### Step 5: Run full test suite

Run:

- Full test suite.
- All merged issues' tests (read from `docs/state/merge_test_index.json`).
- Linter.

MUST have no regressions.

### Step 6: Commit

Commit format:

```
fix(<issue-id>): fix regression in <test>

<body>

Regression: <test name>
Root cause: <description>
```

### Step 7: Push fix branch

```
git push -u origin issue/REG-FIX-<id>-<slug>
```

### Step 8: Post comment

Post on the Platform Issue:

```
npx tsx scripts/platform.ts issue comment <platform_issue> --body "<comment>"
```

Where `<comment>` follows this format:

````markdown
## Builder: fix_regression — COMPLETE

**Issue**: <id>
**Branch**: issue/REG-FIX-<id>-<slug> (<sha>)
**Tests**: <passed> passed, <failed> failed

### Summary
<fix summary>

### Regressions Fixed
- <test>: <root cause> — <fix description>
````

### Step 9: Write handoff

Write `docs/state/outputs/<id>_builder_fix_regression.json`, conforming to `schemas/builder/fix_regression.json`.

### Step 10: Label transition

On the Platform Issue:

- Remove modifier label `regression`:
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label regression
  ```
- **Keep state label `built` unchanged**.

## Output

Write `docs/state/outputs/<id>_builder_fix_regression.json`, conforming to `schemas/builder/fix_regression.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Branch confirmed (`issue/REG-FIX-<id>-<slug>`)
- [ ] Regression report read
- [ ] Merge history read
- [ ] Root cause located
- [ ] All regressions fixed
- [ ] Full test suite passes
- [ ] No new regressions
- [ ] Linter passes
- [ ] All changes committed
- [ ] Fix branch pushed
- [ ] Comment posted via `scripts/platform.ts`
- [ ] Labels transitioned (`regression` removed; `built` unchanged)
- [ ] Output conforms to `schemas/builder/fix_regression.json`
- [ ] `reached_state: built`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Modify the regression report
- Modify issues
- Merge directly to main
- Switch to other branches
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Blacklisted commands

Same as `implement.md`.

## Boundaries

- Write only: files inside the fix worktree, `docs/state/outputs/<id>_builder_fix_regression.json`
- Do NOT write: `docs/issues/*.md`, `main` branch