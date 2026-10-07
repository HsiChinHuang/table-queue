# Builder: Fix Merge

Resolve a merge conflict.

## Trigger

Orchestrator detects a conflict during merge, **creates the fix branch and worktree**, then spawns Builder: fix_merge.

## Orchestrator pre-actions

Before spawning Builder, Orchestrator MUST:

1. Create branch `issue/MERGE-FIX-<id>-<slug>` and worktree `../worktrees/MERGE-FIX-<id>` based on `origin/main`:
   ```
   git worktree add ../worktrees/MERGE-FIX-<id> -b issue/MERGE-FIX-<id>-<slug> origin/main
   ```
   (The reference implementation is `createFixBranch()` in
   `extensions/merge_orchestrator.ts`.)
2. Pass `worktree_path` to Builder.

**If Orchestrator has not created the branch, Builder's first action will fail.**

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Issue definitions of the conflicting sides |
| `docs/state/merge_cp.json` | Yes | Merge checkpoint |
| `docs/state/outputs/<id>_builder_implement.json` | Yes | Original implementation output |
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

Run `git branch --show-current`, confirm the branch is `issue/MERGE-FIX-<id>-<slug>`.

If mismatch:

- Write a BLOCKER handoff, noting "expected fix branch, got <actual>".
- Stop.

### Step 2: Read conflict info

Read `merge_cp.json`, extract:

- `issue_id`
- `state` (should be `merged`)
- List of conflicting files

Read both sides' issue definitions to understand their change intents.

### Step 3: Check conflict type

If binary conflict:

- Write a BLOCKER handoff with `error.error_code: BINARY_CONFLICT`.
- Stop. The Orchestrator will isolate this issue (see `failures.md`
  § Builder BLOCKER routing) and continue merging other verified issues.
  The isolated issue remains queued for eventual human review; it does
  NOT block the merge queue.

If pure whitespace conflict:

- Try `git merge -Xignore-all-space`.
- If successful, use the result.

### Step 4: Resolve conflicts

For each conflicting file:

1. Understand both sides' change intents.
2. Choose a strategy:
   - `keep_ours`: keep our changes.
   - `keep_theirs`: keep their changes.
   - `merge_manual`: manually merge both changes.
3. Mark the conflict as resolved in the file.

### Step 5: Run integration tests

Run:

- All tests from both conflicting issues (read from `## Verification commands`).
- Full test suite.

MUST have no regressions.

### Step 6: Commit

Commit format:

```
merge(<issue-id>): resolve merge conflict

Conflicts: <files>
Strategy: <strategy>
```

### Step 7: Push fix branch

```
git push -u origin issue/MERGE-FIX-<id>-<slug>
```

### Step 8: Post comment

Post on the Platform Issue:

```
npx tsx scripts/platform.ts issue comment <platform_issue> --body "<comment>"
```

Where `<comment>` follows this format:

````markdown
## Builder: fix_merge — COMPLETE

**Issue**: <id>
**Branch**: issue/MERGE-FIX-<id>-<slug> (<sha>)
**Conflicts**: <files>
**Tests**: <passed> passed, <failed> failed
**Integration**: PASS

### Summary
<conflict resolution summary>

### Resolved Conflicts
- <file>: <strategy> — <resolution>
````

### Step 9: Write handoff

Write `docs/state/outputs/<id>_builder_fix_merge.json`, conforming to `schemas/builder/fix_merge.json`.

### Step 10: Label transition

On the Platform Issue:

- Remove modifier label `merge_conflict`:
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label merge_conflict
  ```
- **Keep state label `built` unchanged**.

## Output

Write `docs/state/outputs/<id>_builder_fix_merge.json`, conforming to `schemas/builder/fix_merge.json`.

## Pre-output Checklist

- [ ] CWD verification passed
- [ ] Branch confirmed (`issue/MERGE-FIX-<id>-<slug>`)
- [ ] Conflict info read
- [ ] Conflict type confirmed (not binary)
- [ ] All conflicts resolved
- [ ] Integration tests pass
- [ ] No regressions
- [ ] Linter passes
- [ ] All changes committed
- [ ] Fix branch pushed
- [ ] Comment posted via `scripts/platform.ts`
- [ ] Labels transitioned (`merge_conflict` removed; `built` unchanged)
- [ ] Output conforms to `schemas/builder/fix_merge.json`
- [ ] `reached_state: built`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Decide binary conflicts unilaterally (MUST be BLOCKER)
- Modify issues
- Merge directly to main
- Modify the original branch
- Switch to other branches
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Blacklisted commands

Same as `implement.md`.

## Boundaries

- Write only: files inside the fix worktree, `docs/state/outputs/<id>_builder_fix_merge.json`
- Do NOT write: `docs/issues/*.md`, `main` branch, the original branch