# Human Interaction

PAUSE, RESTART, RESET, Approval, BLOCKER resolution, Completion.
File-based and comment-based commands from humans.

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## 1. PAUSE

### 1.1 Trigger

Human creates `_docs/state/PAUSE` file (any content).

### 1.2 Behavior

On detection (Lifecycle step 1):
- Finish current action (see 1.3 for definition).
- Stop spawning new subagents.
- Wait for active slots to finish (timeout `[timeouts.slot_wait_minutes]`).
- On timeout: force terminate, mark issue `[INTERRUPTED]`.
- Write `[PAUSED]` log.
- Heartbeat continues (log every `[timeouts.auto_commit_minutes]`).
- No API writes.
- Pending files NOT processed. Log `[PENDING_DEFERRED]`.

### 1.3 Current action definition

| Context | "Current action" completes when |
|---|---|
| Subagent session | Subagent posts comment + declares reached_state |
| Merge | push finishes or aborts |
| Per-transition | log + snapshot written |
| SA | all phases done or HALT |

### 1.4 PAUSE during merge

- Merge is atomic; never interrupt.
- If PAUSE detected mid-merge: complete merge first.
- Log `[PAUSE_DEFERRED_MERGE]`.
- After merge: enter pause.

### 1.5 PAUSE during SA

- SA runs to completion (not interruptible).
- PAUSE applies after SA finishes.
- Log `[SA_CONTINUES_DURING_PAUSE]`.
- Reason: SA sets up project state; partial is worse.

### 1.6 Slot state

- Active slots: wait for completion (or timeout).
- On completion: slot freed.
- No new spawns.
- Snapshot updated with slot states.
- On resume: repopulate from snapshot.

### 1.7 Resume

Human deletes `_docs/state/PAUSE`.
On next loop:
- Run drift check for all in-flight.
- Reconcile platform state.
- Resume Lifecycle.
- Log `[RESUMED]`.

### 1.8 Stale

- Paused > `[timeouts.pause_stale_days]`: log `[PAUSE_STALE]`.
- No auto-resume. Human action.

### 1.9 Priority

RESET > RESTART > PAUSE.
- If RESET during PAUSE: run reset.
- If RESTART during PAUSE: complete PAUSE cycle first.

### 1.10 Per-issue pause

Use BLOCKER with `related_issues: [T5]`.
- T5 not scheduled.
- Other issues continue.
- No new file needed.

## 2. Approval

### 2.1 Modes

| Mode | Requires approval |
|---|---|
| `full-auto` | Never |
| `semi-auto` | Merge, deps add, delete >N files, CI change, >N issues |
| `manual` | Every merge + destructive ops |

Set via env: `APPROVAL_MODE`.

### 2.2 Approval file

`_docs/state/APPROVALS.md`.

Format: `<action>:<id>: approved <UTC_TS>`.
Rejected: `<action>:<id>: rejected <UTC_TS>`.

### 2.3 Approval formats

| Action | Format | Example |
|---|---|---|
| merge | `merge:<issue_id>` | `merge:T42` |
| deps add | `deps:add:<package>` | `deps:add:requests` |
| delete | `delete:<path>` | `delete:users/legacy.py` |
| CI | `ci:<change_type>` | `ci:workflow_update` |
| reset | `reset:<commit>` | `reset:abc1234` |
| reset confirm | `reset-confirm:<commit>` | `reset-confirm:abc1234` |
| reset non-latest | `reset-non-latest:<commit>` | `reset-non-latest:abc1234` |
| config change | `config-change:<key>:from=<old>,to=<new>` | `config-change:slots.max:from=3,to=5` |
| force merge | `force-merge:<issue_id>` | `force-merge:T42` |

Config change approval requires `old_value` and `new_value`.
Prevents applying stale approval to a different change.

### 2.4 Waiting

On required approval missing:
- Slot RELEASED.
- Issue marked `[AWAITING_APPROVAL]`.
- Log `[AWAITING_APPROVAL]`.
- Action paused.

### 2.5 Timeout (two thresholds)

| Threshold | Default | Action |
|---|---|---|
| warn | `[timeouts.approval_warn_hours]` (24h) | Log `[APPROVAL_STALE]` |
| max | `[timeouts.approval_max_hours]` (72h) | BLOCKER `[APPROVAL_STUCK]` |

At max: human must decide: approve, reject, or cancel action.

### 2.5.1 Change set semantics

Multiple config changes at same boot:
- All require individual approvals.
- Partial approval: HALT (do not apply any).
- All approved: apply together (atomic).
- Log `[CONFIG_CHANGED_BATCH] <n> keys`.

Approval validity:
- Consumed on next boot.
- Unused > `[retention.approval_keep_days]` days: archive.

### 2.6 Rejected

- Action skipped.
- Issue marked `[REJECTED]`.
- For merge: issue stays queued with `needs-review` label.
- Log `[REJECTED] <action> <id>`.

### 2.7 Stale approval detection

Before using approval:
- Re-verify action still pending.
- If action already done: ignore approval, log `[STALE_APPROVAL]`.
- If issue closed: ignore.

Consumed marking:
- On successful application: mark as `consumed` in APPROVALS.md.
- Format: `config-change:<key>:from=<old>,to=<new>: consumed <ts>`.
- Consumed entries archived to `state/history/approvals-<ts>.md` after `[retention.approval_keep_days]`.
- New change requires new approval.

### 2.8 Detection rules

See `orchestrator-gates.md` for detection events.

## 3. RESET

### 3.1 Trigger

Human creates BOTH:
- `_docs/state/RESET`
- `_docs/state/RESET_APPROVED`

### 3.2 Scope

**Archive** to `state/history/reset-<ts>/`:
- All state files.
- `issues/*` (excluding `closed/`).
- `backlog.md`, `issue-map.json`.

**Clear**:
- `_docs/issues/*` (except `closed/`).
- `_docs/backlog.md`.
- `_docs/issue-map.json`.
- `_docs/state/snapshot*.json`.
- `_docs/state/retry*.json`.
- `_docs/state/seq.txt`.
- `_docs/state/*.lock`.
- `_docs/state/CONFIG_SNAPSHOT.json` (regenerate on next boot).
- `_docs/state/outputs/`, `compressed/`, `pending-blockers/`, `metrics/`.

**Preserve**:
- `_docs/log/`.
- `_docs/memory/` (knowledge asset).
- `_docs/requirements.md`.
- `_docs/config.yaml`.
- `.env`.
- `_docs/issues/closed/` (archive).
- `_docs/state/history/`.

### 3.3 Process

1. Wait for in-flight issues (or timeout).
2. Archive.
3. Clear.
4. Update platform (see 3.4).
5. Cleanup worktrees/branches (see 3.5).
6. Restart SA.

### 3.4 Platform action

Default:
- Close all `backlog`-labeled issues with label `reset-archived`.
- Preserves audit trail.
- Log `[RESET_PLATFORM_CLOSED]`.

Optional (destructive):
- Requires `_docs/state/RESET_PLATFORM_APPROVED` file.
- Delete issues via API.
- Log `[RESET_PLATFORM_DELETED]`.

### 3.5 Worktree and branch cleanup

- Remove all `../worktrees/*` directories.
- Delete local branches `issue/*` (after archive).
- Remote branches: KEEP (audit).
- If dirty worktree: log `[RESET_DIRTY]`, human confirms.

### 3.6 ID continuity

Default: continue from max in `issue-map.json`.
Override: create `_docs/state/RESET_IDS` → restart from T0.

### 3.7 Memory preservation

Memory is NOT reset.
If human wants memory reset: manual `rm -rf _docs/memory/`.
Log `[MEMORY_PRESERVED_ON_RESET]`.

### 3.8 Idempotency

- Archive directory: `reset-<ts>` with timestamp.
- Second RESET: new archive, does not delete old.
- Platform: skip issues already closed with `reset-archived`.
- No side effects on repeat.

### 3.9 State file tampering

On boot:
- Validate state files (JSON parse).
- Malformed: log `[STATE_TAMPERED] <file>`.
- Fallback to backup (`snapshot-1.json`).
- If no backup: HALT, human fixes.
- Never auto-repair JSON.

## 4. BLOCKER management

### 4.1 Creation

- Idempotency key: `<issue>-blocker`.
- `[limits.blocker_create_retry]` fails: write local `state/pending-blockers/<issue>.md`.
- Next boot: process pending.

### 4.2 Resolve

Human comments `[RESOLVED] <how>` on BLOCKER issue.

Detection: first line of comment must start with `[RESOLVED]`.
Optional `<how>` text follows.

On detection:
- Clear blocker state.
- Related issues resume.
- Log `[BLOCKER_RESOLVED] <issue>`.

### 4.3 Close without marker

Human closes BLOCKER issue without `[RESOLVED]`:
- Treat as resolved (human intent).
- Log `[BLOCKER_CLOSED_NO_MARKER]`.

### 4.4 BLOCKER with closed issue

Detect: related issue closed before BLOCKER resolved.

Action:
- Auto-close BLOCKER with comment.
- Log `[BLOCKER_AUTO_CLOSED]`.
- Reason: no longer relevant.

### 4.5 Aggregation (fatigue prevention)

- > `[limits.blocker_fatigue_count]` BLOCKERs in 24h: log `[BLOCKER_FATIGUE]`.
- Same-source BLOCKERs: aggregate into one summary issue.
- Critical (security, data loss): always immediate.

### 4.6 Priority

RESET > PAUSE > BLOCKER.
BLOCKER affects only related_issues.
System-wide: use PAUSE.

### 4.7 Marker ownership

- Human markers: this file Sec. 6.
- Role markers: `_shared.md`.
- No overlap by design.
- Orchestrator acts on human markers only when from human (via specific files or attributed comments).

## 5. Completion

### 5.1 Conditions

- All `backlog`-labeled issues closed.
- `_docs/issues/pending/` empty.
- No open `blocker`-labeled issues.
- Merge queue empty.

### 5.2 Two-phase check

Phase 1: verify all conditions.
Phase 2: sleep `[timeouts.completion_verify_delay_seconds]` (60s), re-verify.
Both pass: write COMPLETE.md.

### 5.3 Race handling

After Phase 1 passes, sleep.
Before Phase 2: re-check all conditions.
If any fails:
- Abort completion.
- Continue Lifecycle.
- Log `[COMPLETION_RACE]`.
- Next check after normal interval.

### 5.4 On complete

1. Write `_docs/state/COMPLETE.md`:

    # Project Complete
    - completed_at: <UTC_TS>
    - total_issues: N
    - total_retries: N
    - total_duration: <duration>
    - final_commit: <SHA>
    - archived_to: state/history/final-<ts>/

2. Archive: `_docs/state/` → `_docs/state/history/final-<ts>/`.
3. Keep: `snapshot.json`, `log/`, `memory/`.
4. Delete: `orchestrator.lock`, `retry.json`, `recovery.log`, `cache/`, `retry-subagent.json`.
5. Cleanup worktrees:
   - Remove `../worktrees/*` (should be empty already).
   - Delete local `issue/*` branches.
   - Keep remote branches.
   - Log `[COMPLETION_WORKTREE_CLEAN]`.
6. Write `_docs/log/summary-final.md`.
7. Stop. Do NOT auto-restart (unless `[completion.auto_restart]`).

### 5.5 Resume after completion

Human deletes `_docs/state/COMPLETE.md`.
On next boot:
- Detect COMPLETE.md missing.
- Read state (may be empty).
- SA runs if needed.
- Lifecycle resumes.

For fresh project: also run RESET.

## 6. Human commands

### 6.1 File-based commands

| File | Action |
|---|---|
| `state/PAUSE` | Global pause |
| `state/RESTART` | Session restart |
| `state/RESET` + `RESET_APPROVED` | Full reset |
| `state/RESET_IDS` | Reset ID to T0 |
| `state/RESET_PLATFORM_APPROVED` | Allow platform deletion |
| `state/initialized` | First-run approval |
| `state/APPROVALS.md` | Approval lines |
| `state/CANCEL_<issue_id>` | Cancel running subagent |

### 6.2 Cancel subagent

Trigger: `state/CANCEL_<issue_id>` file.

Behavior:
- Orchestrator detects on next loop.
- Terminate that subagent session.
- Mark issue `[INTERRUPTED]`.
- Re-spawn on next cycle (or leave for human).
- Log `[CANCELLED] <issue>`.
- Delete cancel file.

### 6.3 Comment-based commands

| Marker | Action |
|---|---|
| `[RESOLVED] <how>` | Resolve BLOCKER |
| `[RECOVERY_OK]` | Clear recovery loop |
| `[CONFIG_CHANGED_OK]` | Approve config with in-flight |
| `[OVERRIDE_QA_PASS] <reason>` | Force QA PASS |
| `[SKIP_PM] <reason>` | Skip PM step |
| `[ANALYZE]` | Trigger L3/L4 |
| `[DEEP_CHAIN_OK]` | Allow deep chain |
| `[HUB_PARALLEL_OK]` | Allow hub parallel |
| `[DAG_EXPORT]` | Generate DAG |
| `[DAG_CHECK]` | Check DAG |
| `[NEW_REQUIREMENT] <text>` | Create pending |
| `[KEEP]` | Keep output |
| `[FORCE_MERGE] <reason>` | Force merge (manual mode + approval) |
| `[PLAN_CHANGE_REQUEST] <text>` | Request plan change |

### 6.4 Marker validation

- Orchestrator scans markers on each loop.
- Malformed marker: log `[MARKER_MALFORMED] <content>`.
- Do NOT act on malformed.
- Human corrects.

### 6.5 Force merge

Requires:
- `APPROVAL_MODE=manual`.
- `APPROVALS.md` entry: `force-merge:<issue>`.
- Human comments `[FORCE_MERGE] <reason>` on issue.

Behavior:
- QA PASS invalidated (label removed).
- Merge proceeds.
- Log `[FORCE_MERGE]`.