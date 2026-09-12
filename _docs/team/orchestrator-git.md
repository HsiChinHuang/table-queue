# Git Lifecycle

Master spec for git operations: worktree, branch, merge, rollback.
Read on: merge, rollback, worktree creation/cleanup.

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## 1. Default branch

- Preflight detects: `git symbolic-ref refs/remotes/origin/HEAD`.
- Store as `state/default_branch.txt`.
- All references to "main" use this value.
- Env override: `DEFAULT_BRANCH`.

## 2. Worktree lifecycle

### 2.1 Create

Trigger: Orchestrator at SW stage.

    git worktree add ../worktrees/<ID> -b issue/<ID>-<slug>

Retry policy:
- 3 attempts, backoff 5s/15s/45s.
- On persistent fail: fallback path `../worktrees/<ID>-alt`.
- If alt also fails: BLOCKER `[WORKTREE_CREATE_FAIL]`.

CWD verification:
- Orchestrator passes absolute path to SW.
- SW first action: `pwd` check.
- Mismatch: `[BLOCKER] wrong cwd`, stop.

### 2.2 Reuse

- SW retries: reuse existing worktree.
- MERGE-FIX: reuse worktree, new branch (see Sec. 6).
- Never recreate if exists and matches.

### 2.3 Removal

Trigger: after clean merge.

    git worktree remove ../worktrees/<ID>

Pre-checks:
- `git status --porcelain` inside worktree.
- If dirty: log `[DIRTY_WORKTREE_ON_MERGE]`, do NOT remove, BLOCKER.
- If clean: remove.

Never force-remove. Never delete uncommitted work.

### 2.4 Orphan detection

On boot:
- Scan `../worktrees/`.
- For each:
  - If issue closed: remove.
  - If issue active + branch matches: keep.
  - If no matching issue: log `[ORPHAN_WORKTREE]`, remove.
  - If branch mismatch: log `[STALE_WORKTREE]`, BLOCKER.

### 2.5 Lock detection

On git op failure with `.git/index.lock` or `Permission denied`:
- Retry 3x, 5s gap.
- Persistent: `[BLOCKER] worktree locked`.
- Never delete lock file.
- Human inspects.

### 2.6 Isolation

Each worktree:
- Own branch.
- Shared git object store (git handles).
- Own test DB: `test_<ISSUE_ID>`.
- Own test port: `5000 + (hash(ISSUE_ID) % 1000)`.
- Own temp: `/tmp/agent-<ISSUE_ID>/`.

### 2.7 Large diff splitting

- If diff > `[output.diff_split_lines]` lines:
  - Orchestrator splits into sub-sessions.
  - Each session handles subset.
  - Same worktree, sequential.

## 3. Branch lifecycle

### 3.1 Naming

Format: `issue/<ID>-<slug>`.

Collision handling:
- First attempt: base name.
- If exists: `-v2`, `-v3`, ..., max `-v5`.
- Beyond: BLOCKER `[BRANCH_VERSION_EXHAUSTED]`.

### 3.2 Push

SW pushes: `git push -u origin issue/<ID>-<slug>`.

Retry:
- 3x, backoff [git.push_backoff_seconds].
- Persistent: log `[PUSH_FAIL]`, BLOCKER.

### 3.3 Retain

After merge: branch retained on remote (audit trail).
Never auto-delete.

### 3.4 Missing branch recovery

Detect: `git ls-remote origin issue/<ID>-<slug>` empty.

Actions:
- Local branch exists: re-push (SW authority).
- Local branch missing: BLOCKER `[BRANCH_LOST]`.

Re-push flow:
- Re-spawn SW with context: "branch missing, re-push only".
- SW: `git push -u origin issue/<ID>-<slug>`.
- If fails: BLOCKER.

### 3.5 Force-push detection

Every fetch:
- Compare local tracking SHA vs remote.
- If remote not ancestor of local: `[FORCE_PUSH_DETECTED]`.
- Actions:
  - BLOCKER.
  - Pause merge queue.
  - Human reviews.

## 4. Merge flow

### 4.1 Serial guarantee

- One merge at a time. FIFO.
- Tie-break: smaller local ID.
- Never parallel.

### 4.2 Checkpoints

Checkpoint file: `state/merge-cp.json`.
Written after each step (atomic).

    {
      "issue": "T42",
      "step": 1-7,
      "state": "fetched|reset|merged|tested|pushed|closed",
      "sha": "<commit>",
      "timestamp": "<UTC>"
    }

Steps and checkpoints:

| Step | Action | Checkpoint |
|---|---|---|
| 1 | fetch origin | fetched |
| 2 | reset main to origin | reset |
| 3 | merge --no-ff | merged |
| 4 | conflict check | (abort on conflict) |
| 5 | test suite | tested |
| 6 | push origin main | pushed |
| 7 | closure (close issue, archive, cleanup) | closed |

### 4.3 Atomicity and replay

On boot, read merge-cp.json:
- Step 1: re-run from 2.
- Step 2: re-run from 3.
- Step 3: if local main has merge but not pushed: resume from 5.
- Step 5: if tests passed: resume from 6.
- Step 6: if origin == local: resume from 7.
- Step 7: done.

Each step begins with idempotency check.

### 4.4 Commit message

Format:

    <ID>: <title>

    Issues: <ID>, <conflicting_IDs>
    QA-PASS: <timestamp>
    Test-suite: <full|affected>
    Depends-merged: T1, T2
    Unblocks: T5, T7

Max size: `[merge.commit_message_max]` chars.
Truncate beyond with `[...]`.

### 4.5 Dry-run

Before actual merge:
- `git merge --no-commit --no-ff`.
- If conflicts: abort, create MERGE-FIX.
- Else: complete merge.
- Config: `merge.dry_run`.

### 4.6 Fast path

If branch diff < `[merge.fast_path_lines]` lines AND single file:
- Skip full suite; run smoke only.
- Log `[FAST_MERGE]`.

### 4.7 EOL and whitespace

Preflight:
- `core.autocrlf` same across machines. If not: HALT.
- `.gitattributes` with `* text=auto`. If missing: warn.

On conflict:
- Try `git merge -Xignore-all-space` first.
- If succeeds: use result.
- Else: normal conflict.

### 4.8 Binary conflicts

Detection: git reports `CONFLICT (binary)`.

Actions:
- Abort merge.
- Create `MERGE-FIX: <ID>` with note "binary conflict".
- SW chooses: keep-ours / keep-theirs / regenerate.
- Human approval required.
- Log `[BINARY_CONFLICT] <file>`.

### 4.9 Cumulative conflicts (hot files)

Track: `state/merge-conflicts.json`:
`{file: [issue_ids that merged]}`.

On merge: append issue to file's list.
If file has 3+ merged issues and still active:
- Log `[HOT_FILE] <file> <n>`.
- Prefer serial for future issues touching it.

### 4.10 Pre-merge dirty check

Before merge:
- `git status --porcelain` on main.
- If dirty: log `[DIRTY_MAIN]`, abort.
- Human decides.

### 4.11 Concurrent human push

Before push:
- `git fetch origin`.
- Verify origin SHA unchanged since step 1.
- If changed: abort, re-run merge cycle.
- Never force-push.

### 4.12 Queue dependencies

Before merge: verify all depends are merged.
If not: defer (do not skip).
Re-check next iteration.

### 4.13 Queue starvation

Track queue wait per issue.
If wait > `[timeouts.merge_starvation_hours]`:
- Log `[MERGE_STARVATION]`.
- Signal, not BLOCKER.

## 5. MERGE-FIX flow

### 5.1 Trigger

- Merge conflict (text, binary, or whitespace).
- Post-merge test failure.
- External close with unmerged branch.

### 5.2 Queue impact

- Merge queue STOPPED until MERGE-FIX passes.
- Other QA-PASS issues stay queued.
- FIFO preserved on resume.

### 5.3 Issue creation

    Title: MERGE-FIX: <ID>
    Label: blocker
    Assignee: <ID>'s original SW
    AC: union of all conflicting issues' ACs

### 5.4 Worktree

- Reuse original worktree `../worktrees/<ID>`.
- New branch: `issue/MERGE-FIX-<ID>-<slug>`.
- Base: current origin/main.
- Apply T5's changes on top.
- Resolve conflicts in place.

### 5.5 Flow

- PM (light): fills Goal, AC, Constraints only.
- SW: fixes. Runs FULL test suite of ALL involved issues.
- QA: verifies ALL involved ACs pass on merged branch.
- On PASS: enqueue for merge.
- On FAIL: back to SW (max `[sw_retry.per_issue]`).

MERGE-FIX SW session consumes a slot.

### 5.6 Recursion limit

- Level 1: direct fix.
- Level 2: if MERGE-FIX-1 conflicts.
- Level 3: if MERGE-FIX-2 conflicts.
- Level 3 conflict: BLOCKER `[CASCADE_CONFLICT]`.
- Max level: `[git.merge_fix_max_level]`.

### 5.7 Flaky test handling

On test failure:
- Re-run failed tests once.
- If pass on 2nd: log `[FLAKY_TEST]`, proceed with merge.
- If fail: rollback + MERGE-FIX.

Track flaky rate. If > `[git.flaky_high_pct]`%:
- Log `[FLAKY_HIGH]`, alert human.

### 5.8 QA PASS invalidation

On merge failure:
- Remove `qa-passed`, add `qa-failed`.
- Set `failure_type=merge_conflict`.
- Create MERGE-FIX issue.
- Issue re-enters queue after MERGE-FIX passes.

## 6. Rollback

### 6.1 Trigger

Human creates Platform Issue: `ROLLBACK: <commit>` with label `ROLLBACK`.

### 6.2 Preconditions

- Commit exists in main.
- Method specified: `revert` or `reset`.

### 6.3 Merge-rollback race

Priority: ROLLBACK > merge.
- If ROLLBACK detected mid-merge:
  - Complete current merge (atomic).
  - Then process ROLLBACK.
- Log `[ROLLBACK_DEFERRED]`.

### 6.4 Revert flow

    git checkout main
    git revert <commit> --no-edit
    git push origin main

Non-destructive.

### 6.5 Reset flow

Requires:
- `APPROVALS.md` entry: `reset:<commit>: approved <ts>`.
- Additional: `reset-confirm:<commit>: approved <ts>`.
- Only allowed in `manual` APPROVAL_MODE.

    git checkout main
    git reset --hard <commit>~1
    git push origin main --force-with-lease

Before reset:
- `git fetch origin`.
- Verify origin/main hasn't moved.

### 6.6 Non-latest reset

If commit not latest merge:
- Require additional approval: `reset-non-latest:<commit>`.
- Otherwise HALT.

### 6.7 Reopening original issue

1. Identify issue from commit message.
2. Remove label `closed`, add `groomed`.
3. Move `issues/closed/<ID>.md` back to `issues/<ID>.md`.
4. Update `backlog.md`.
5. Comment: `Reopened due to rollback of <commit>`.
6. Issue re-enters normal flow.

### 6.8 Partial rollback (optional)

Human may specify: `ROLLBACK: <commit> --file <path>`.
- Revert only specific files.
- Safer for partial fixes.
- Default: full rollback.

### 6.9 Human manual revert detection

On boot:
- Compare main SHA to `state/last-known-main.txt`.
- If difference is a revert commit:
  - Log `[HUMAN_REVERT] <sha>`.
  - Identify reverted issues.
  - Reopen.
- If unclear: BLOCKER.

## 7. Safety and audit

### 7.1 Default branch protection

Preflight:
- GitHub: GET `/repos/{REPO_ID}/branches/{default}/protection`.
- If protected: log `[PROTECTED_BRANCH]`.
- Default: HALT unless PR-flow configured.
- Human disables protection OR configures PR flow.

### 7.2 Remote URL drift

Track: `state/origin-url.txt`.
Preflight: compare current URL.
If changed:
- Log `[ORIGIN_CHANGED] <old> -> <new>`.
- HALT: verify intent.

### 7.3 Main history tracking

Track every main SHA in `state/main-history.txt` (append-only).
On boot: verify SHA chain intact.
Any gap: BLOCKER `[HISTORY_GAP]`.

Config: `git.main_history_track`.

### 7.4 Merge audit

Append to `state/merge-history.json` on each merge:

    {
      "issue": "T42",
      "merge_sha": "...",
      "parent_shas": ["...", "..."],
      "timestamp": "...",
      "merge_type": "clean|merge-fix",
      "test_suite": "affected|full|fast"
    }

Permanent. Never deleted.

### 7.5 Audit chain (optional)

Each merge-history entry: include `sha256(entry)` chain.
Chain: `prev_hash -> current_hash`.
Verify on boot. Detects tampering.

Config: `audit.chain`.

### 7.6 Signed commits

Preflight: check `git config commit.gpgsign`.
If repo requires GPG but not configured: warn.
If required and Orchestrator cannot sign: BLOCKER.

### 7.7 Commit authorship

- SW commits: SW's git identity.
- Merge commit: Orchestrator's git identity.
- Preflight: warn if `user.name` / `user.email` unset.

### 7.8 GDPR / deletion

- Orchestrator does NOT rewrite history.
- Human uses `git filter-repo` if required.
- Document in `docs/compliance.md` (optional).

### 7.9 CI integration

After push:
- Wait for CI result up to `[timeouts.ci_wait_minutes]`.
- On fail: BLOCKER `[CI_FAIL]`.
- On timeout: log `[CI_TIMEOUT]`, proceed (advisory).
- Skip: env `SKIP_CI=true`.

### 7.10 Git hooks

- Hooks run normally.
- SW: fix and retry.
- Orchestrator (merge): BLOCKER, never bypass.
- Never use `--no-verify` unless human approves.

### 7.11 Large repo handling

- Shallow clone: `--depth 100`.
- Merge may need `--unshallow`.
- Preflight: detect, warn.
- Merge queue: limit to 1 concurrent.

### 7.12 Worktree pool (optional)

- Maintain N warm worktrees.
- Assign to issue on spawn.
- Reset after merge.
- Config: `worktree.pool_size` (0 = disabled).