# Builder: Fix QA

Fix the implementation based on a Verifier FAIL report.

## Trigger

Verifier returns `failure_type` of `implementation`, `test_env`, or `test_quality`. Orchestrator routes the issue to Builder: fix_qa when the issue has state label `built` and modifier label `verifier_failed`.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Authoritative AC + Verification commands |
| `docs/state/outputs/<id>_verifier_verify_issue.json` | Yes | Verifier FAIL report |
| `docs/coding_standards.md` | Yes | Coding standards |
| `docs/commands.md` | Yes | Toolchain commands |
| `docs/state/config_snapshot.json` | Yes | Config snapshot |
| `failure_history` | Yes | Last 3 FAIL summaries + latest full FAIL |
| `memory_paths` | No | Relevant memories |
| `worktree_path` | Yes | Assigned working directory |

## Process

### Step 0: CWD verification

First action: `pwd` MUST equal the assigned `worktree_path`.
If mismatch: write a BLOCKER handoff, stop.

### Step 1: Read FAIL report

Read the Verifier FAIL report, extract:

- `failure_type`
- `failed_acs`
- Each failed AC's `verdict` / `command` / `exit_code` / `output_path` / `note` (from `evidence.ac_results.<ac>`)

Read `failure_history`:

- Read the latest full FAIL first.
- Then read the last 3 summaries to avoid repeating mistakes.

### Step 1.5: Read verification commands

Read each AC's verification command from `docs/issues/<id>.md`'s `## Verification commands` section.

**This is the authoritative source.** For each `failed_acs`, confirm the corresponding verification command.

If a `failed_ac` has no corresponding command and is not `manual`:

- Write a BLOCKER handoff, noting "missing verification command for <ac_id>".
- Stop.

### Step 2: Check memories (if `memory_paths` is non-empty)

Read each memory file.
If two memories conflict: write `[MEMORY CONFLICT]` in `evidence.notes`.
List the actually applied memory IDs in the final handoff (`evidence.memory_applied`).

### Step 3: Analyze failure

Based on `failure_type`:

- `implementation`: code behavior does not match AC.
- `test_env`: test environment issue (e.g. database, port).
- `test_quality`: test quality insufficient (e.g. `assert True`).

### Step 4: Fix

Based on the analysis:

- `implementation`: modify code to match the AC.
- `test_env`: adjust test environment (isolate DB, ports, etc.).
- `test_quality`: rewrite tests with meaningful assertions.

If the failure cannot be reproduced:

- Write `[VERIFIER_MISJUDGMENT] <reason>` in `evidence.notes`, and set `evidence.reported_issue: "VERIFIER_MISJUDGMENT"`.
- Continue implementing the reasonable scope.
- The Orchestrator will route this to Definer for a third-party check (see `failures.md` § Verifier misjudgment routing).

If the AC is impossible to implement:

- Write `[AC_IMPOSSIBLE] <reason>` in `evidence.notes`, and set `evidence.reported_issue: "AC_IMPOSSIBLE"`.
- Continue implementing the reasonable scope.

If an upstream issue is the root cause:

- Write `[UPSTREAM_BUG] <id>` in `evidence.notes`, and set `evidence.upstream_bug_id: "<id>"`.
- Continue implementing the reasonable scope.

### Step 5: Run tests

Run:

- **Each command in `## Verification commands`.**
- Full test suite (because this is a fix).
- Linter.

If any command fails after fixing, apply the same 3-attempt + self-diagnosis cascade as `implement.md` Step 5.

MUST have no regressions.

### Step 6: Commit

Commit format:

```
fix(<issue-id>): address Verifier failure in <ac>

<body>

Addresses: <failed_acs>
```

### Step 7: Push branch

Push the fix to the **same branch**.

### Step 8: Post comment

````markdown
## Builder: fix_qa — COMPLETE

**Issue**: <id>
**Branch**: issue/<id>-<slug> (<sha>)
**Tests**: <passed> passed, <failed> failed
**Lint**: <status>

### Summary
<fix summary>

### Addressed Failures
- ac2: <fix description> — <verification command> PASS

### Addressed prior FAIL
<how the previous failure was addressed>

<!-- HANDOFF_JSON
{ ... }
-->
````

### Step 9: Write handoff

Write `docs/state/outputs/<id>_builder_fix_qa.json`, conforming to `schemas/builder/fix_qa.json`.

### Step 10: Label transition

On the Platform Issue:

- Remove modifier label `verifier_failed`
- **Keep state label `built` unchanged**

**Note**: After this transition, the issue is back to `built` state with no modifier labels. Lifecycle Step 7 will route it to Verifier: verify_issue.

## Output

Write `docs/state/outputs/<id>_builder_fix_qa.json`, conforming to `schemas/builder/fix_qa.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Verifier FAIL report read
- [ ] failure_history read
- [ ] `## Verification commands` read
- [ ] Failure analyzed
- [ ] All failed_acs addressed
- [ ] Full test suite passes
- [ ] No regressions
- [ ] Linter passes
- [ ] All changes committed
- [ ] Branch pushed
- [ ] Comment posted
- [ ] Memory IDs listed (if used)
- [ ] Modifier label removed (`verifier_failed`)
- [ ] State label unchanged (`built`)
- [ ] Output conforms to `schemas/builder/fix_qa.json`
- [ ] `reached_state: built`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

Same as `implement.md`.

## Blacklisted commands

Same as `implement.md`.

## Boundaries

- Write only: files inside the worktree, `docs/state/outputs/<id>_builder_fix_qa.json`
- Do NOT write: `docs/issues/*.md`, other files under `docs/state/`, other branches