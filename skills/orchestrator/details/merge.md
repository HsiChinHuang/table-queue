# Merge

Merge flow. Transactional merge + verification.

## Trigger

Issue state is `verified` and passes Gate 3.

## Preconditions

- [ ] Issue has state label `verified`
- [ ] AC hash matches groom time
- [ ] Branch pushed
- [ ] All dependencies merged
- [ ] No in-progress merge
- [ ] `merge_queue` correctly sorted

## Merge Queue

- FIFO by Verifier PASS timestamp
- Tie-break: smaller local ID
- Dependency priority: if depends not merged -> defer, do not skip
- Isolated issues (`isolated` label) are skipped, not blocked

## Transactional Merge

### Step 1: fetch origin

```
git fetch origin
```

### Step 2: reset main to origin

```
git checkout main
git reset --hard origin/main
```

### Step 3: dry-run merge

```
git merge --no-commit --no-ff issue/<id>-<slug>
```

On conflict -> abort, go to "Conflict Handling".

### Step 4: actual merge

```
git merge --no-ff issue/<id>-<slug>
```

Commit message format:

```
<id>: <title>

Issues: <id>
VERIFIER-PASS: <timestamp>
Test-suite: <full|affected>
```

### Step 5: run tests

Run full test suite (or affected suite).

On failure -> rollback + go to "Regression Handling".

### Step 6: push origin main

```
git push origin main
```

### Step 7: closure

Run these steps **in order**. Local state updates come first; the Platform
Issue is closed **last**, so that a failure partway through does not leave
a Platform Issue marked closed while local state is inconsistent.

1. Update labels on the Platform Issue:
   - `npx tsx scripts/platform.ts label remove <id> --label verified`
   - `npx tsx scripts/platform.ts label add <id> --label closed`
2. Move `docs/issues/<id>.md` to `docs/issues/closed/<id>.md`
3. Update `docs/issues/closed/index.md`
4. Update `docs/backlog.md`
5. Update `docs/state/merge_test_index.json` (append this issue's `## Verification commands`)
6. Clean up worktree
7. Remove from `docs/state/snapshot.json`
8. Write `docs/state/merge_history.json`
9. **Close the Platform Issue** (final step):
   ```
   npx tsx scripts/platform.ts issue close <id>
   ```
   The `closed` label added in step 1 marks the local state; the API call
   in this step makes the Platform authoritative state `closed`. Both are
   required. `recovery.md` reconciles against Platform state, not labels.

**Note**: Step 1 through step 8 are implemented by `closure()` in
`extensions/merge_orchestrator.ts` (reference implementation). The
Orchestrator performs the equivalent operations using bash + the
`platform.ts` CLI. Step 9 is a `platform.ts` call that the Orchestrator
must execute explicitly; it is NOT part of `closure()`.

**Why step 9 matters**: Without it, a merged issue remains `open` on
GitHub/GitLab, which breaks `recovery.md` Step 4 (Platform is the
authority for `open`/`closed`) and pollutes the Platform issue list.
The `closed` label alone is not sufficient.

## Checkpoint

Write `docs/state/merge_cp.json` after every step:

```json
{
  "issue_id": "t42",
  "step": 5,
  "state": "tested",
  "timestamp": "...",
  "pre_merge_sha": "...",
  "merge_sha": "...",
  "test_result": { "total": 20, "passed": 20, "failed": 0 }
}
```

Recovery after crash: see `recovery.md`.

## Verifier Worktree Preparation

**Before spawning any Verifier, Orchestrator MUST prepare a worktree**:

### For `verify_pre_merge`

1. Create worktree if missing: `../worktrees/verify-<id>`
2. In the worktree, checkout the candidate branch: `git -C ../worktrees/verify-<id> checkout <candidate_branch>`
3. Pass `worktree_path` to Verifier
4. Pass `candidate_branch` to Verifier

### For `verify_post_merge`

1. Create worktree if missing: `../worktrees/verify-<sha>`
2. In the worktree, checkout main: `git -C ../worktrees/verify-<sha> checkout main`
3. Pass `worktree_path` to Verifier
4. Pass `merge_sha` to Verifier

**Reason**: Verifier is read-only and does NOT run `git checkout`. Orchestrator prepares the environment.

## Conflict Handling

On conflict:

### Step C0: Add modifier label

**Before creating the fix branch**, add `merge_conflict` label:

```
npx tsx scripts/platform.ts label add <id> --label merge_conflict
```

This marks the issue for `fix_merge` routing in Lifecycle Step 7.

### Step C1: Create fix branch

Create a fix branch and worktree based on `origin/main`:

```
git worktree add ../worktrees/MERGE-FIX-<id> -b issue/MERGE-FIX-<id>-<slug> origin/main
```

Result:

- Branch: `issue/MERGE-FIX-<id>-<slug>`
- Worktree: `../worktrees/MERGE-FIX-<id>`

The reference implementation is `createFixBranch()` in
`extensions/merge_orchestrator.ts`.

### Step C2: Continue merge queue

- Keep other `verified` issues in the queue.
- The conflicting issue is temporarily deferred; other issues merge normally.

### Step C3: Spawn Builder: fix_merge

Pass:

- `issue_id`
- `worktree_path: ../worktrees/MERGE-FIX-<id>`
- `merge_cp_path: docs/state/merge_cp.json`

### Step C4: Wait for result

- If fix_merge COMPLETE -> Builder removes `merge_conflict` label; the issue re-enters the merge queue.
- If fix_merge BLOCKER -> create BLOCKER issue (issue remains in `built` state).

### Binary conflict

Binary conflicts cannot be resolved automatically. The issue is **isolated** and the merge queue continues.

1. Add labels:
   ```
   npx tsx scripts/platform.ts label add <id> --labels "blocker,isolated"
   ```
2. Create a BLOCKER Platform Issue referencing the conflict:
   ```
   npx tsx scripts/platform.ts issue create \
     --title "BLOCKER: binary merge conflict on <id>" \
     --body "<context>" \
     --labels "blocker"
   ```
3. **Resume the merge queue**: the isolated issue is skipped; other
   `verified` issues continue merging.
4. Log `[ISOLATED] <issue> reason=binary_conflict`.

The isolated issue is not resolved automatically. When a human posts
`[RESOLVED] <how>` on the BLOCKER issue, the Orchestrator removes the
`blocker` and `isolated` labels and re-enqueues the issue.

**Key**: binary conflict does NOT pause the whole merge queue.

## Regression Handling

If post-merge tests fail (Step 5):

### Step R0: Add modifier label

Add the `regression` label:

```
npx tsx scripts/platform.ts label add <id> --label regression
```

This marks the issue for `fix_regression` routing in Lifecycle Step 7.

### Step R1: Rollback merge

```
git reset --hard <pre_merge_sha>
git push origin main --force-with-lease
```

### Step R2: Create fix branch

```
git worktree add ../worktrees/REG-FIX-<id> -b issue/REG-FIX-<id>-<slug> origin/main
```

- Branch: `issue/REG-FIX-<id>-<slug>`
- Worktree: `../worktrees/REG-FIX-<id>`

The reference implementation is `createFixBranch({ fix_type: 'regression', ... })`.

### Step R3: Spawn Builder: fix_regression

Pass:

- `issue_id`
- `worktree_path: ../worktrees/REG-FIX-<id>`
- `verify_post_merge_path: docs/state/outputs/<id>_verifier_verify_post_merge.json`

### Step R4: Wait for result

- If fix_regression COMPLETE -> Builder removes `regression` label; re-enter merge flow.
- If fix_regression BLOCKER -> create BLOCKER issue.

## Fast Path

If branch diff < `merge.fast_path_lines` and single file:

- Skip full suite, run smoke tests only
- Record `[FAST_MERGE]`

## Post-Merge Verification

After merge completes:

1. Prepare worktree `../worktrees/verify-<sha>` (see "Verifier Worktree Preparation")
2. Spawn Verifier: verify_post_merge
3. If PASS -> continue next iteration
4. If FAIL -> go to "Regression Handling"

## Merge History

Write to `docs/state/merge_history.json` on every merge:

```json
{
  "issue_id": "t42",
  "merge_sha": "...",
  "pre_merge_sha": "...",
  "timestamp": "...",
  "merge_type": "clean|merge-fix",
  "test_suite": "full|affected|fast"
}
```

## Fix Branch Naming Summary

| Situation | Branch name | Worktree |
|---|---|---|
| Merge conflict | `issue/MERGE-FIX-<id>-<slug>` | `../worktrees/MERGE-FIX-<id>` |
| Post-merge regression | `issue/REG-FIX-<id>-<slug>` | `../worktrees/REG-FIX-<id>` |

**Creator**: Orchestrator (via bash commands; reference implementation in
`createFixBranch()`).
**Cleaner**: Orchestrator (via bash commands; reference implementation in
`cleanupFixBranch()`).