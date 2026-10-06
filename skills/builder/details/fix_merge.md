# Builder: Fix Merge

Resolve a merge conflict.

## Trigger

Orchestrator detects a conflict during merge, **creates the fix branch and worktree**, then spawns Builder: fix_merge.

## Orchestrator pre-actions

Before spawning Builder, Orchestrator MUST:

1. Call `createFixBranch({ fix_type: 'merge', ... })`.
2. Create branch `issue/MERGE-FIX-<id>-<slug>`.
3. Create worktree `../worktrees/MERGE-FIX-<id>` based on `origin/main`.
4. Pass `worktree_path` to Builder.

**If Orchestrator has not created the branch, Builder's first action will fail.**

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Issue definitions of the conflicting sides |
| `docs/state/merge_cp.json` | Yes | Merge checkpoint |
| `docs/state/outputs/<id>_builder_implement.json` | Yes | Original implementation output |
| `worktree_path` | Yes | Assigned working directory (fix worktree) |

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

- Write a BLOCKER handoff, noting "binary conflict".
- Stop, wait for human.

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

<!-- HANDOFF_JSON
{ ... }
-->
````

### Step 9: Write handoff

Write `docs/state/outputs/<id>_builder_fix_merge.json`, conforming to `schemas/builder/fix_merge.json`.

### Step 10: Label transition

On the Platform Issue:

- Remove label `merge_conflict`
- Add label `built`

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
- [ ] Comment posted
- [ ] Labels transitioned (`merge_conflict` -> `built`)
- [ ] Output conforms to `schemas/builder/fix_merge.json`
- [ ] `reached_state: built`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Decide binary conflicts unilaterally (MUST be BLOCKER)
- Modify issues
- Merge directly to main
- Modify the original branch
- Switch to other branches

## Blacklisted commands

Same as `implement.md`.

## Boundaries

- Write only: files inside the fix worktree, `docs/state/outputs/<id>_builder_fix_merge.json`
- Do NOT write: `docs/issues/*.md`, `main` branch, the original branch