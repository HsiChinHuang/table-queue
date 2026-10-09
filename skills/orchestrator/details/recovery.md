# Recovery

Recovery flow when Orchestrator boots.

## Authority Model

Priority during recovery (high to low):

1. **Platform State** — issue open/closed follows the platform
2. **`docs/state/snapshot.json`** — slot / queue state
3. **`docs/state/seq.txt`** — sequence number
4. **`docs/state/merge_cp.json`** — merge checkpoint

**Principle**: Platform is most authoritative; local state files are next.

## Trigger

Orchestrator Boot when `snapshot.json` is non-empty.

## Recovery Steps

### Step 0: Attempt schema migration

Before reading or validating any state file, the Orchestrator runs a
**lossless schema migration** on every state file that carries a
`schema_version`:

```
For each of (snapshot, merge_cp, idempotency):
  If file exists:
    Read raw JSON.
    If schema_version == current: skip.
    Else:
      migrated = migrate(raw, from, to)
      Write migrated back (atomic).
      Log [SCHEMA_MIGRATION] <file> <from> -> <to>
On failure:
  Log [SCHEMA_MIGRATION_FAIL] <file> reason=<message>
  Continue (the later validation step will catch the problem)
```

`migrate` is defined in `extensions/schema_migrations.ts`.

### Step 1: Read state files

```
Read docs/state/snapshot.json
Read docs/state/seq.txt
Read docs/state/merge_cp.json (if exists)
Read docs/state/idempotency.json
Read docs/state/launcher_checkpoint.json
```

### Step 2: Validate schema

```
Validate snapshot.json against schemas/state/snapshot.json
Validate merge_cp.json against schemas/state/merge_cp.json (if exists)
Validate idempotency.json against schemas/state/idempotency.json (if exists)

On failure -> see Failure Handling below.
```

### Step 3: Verify consistency

```
If seq.txt != snapshot.last_seq:
  Use snapshot.last_seq
  Overwrite seq.txt
  Log [DRIFT] seq
```

### Step 4: Reconcile with Platform State

```
# Fetch the set of open Platform issues once:
npx tsx scripts/platform.ts issue list --state open
-> Let OPEN_PLATFORM = { issue.number for each returned issue }

# Read docs/state/issue_map.json to map t<n> -> <number>.
# For each t<n> tracked locally:
For each issue_id (t<n>) in snapshot.active_issues:
  number = issue_map[issue_id]
  If number not in OPEN_PLATFORM:
    -> the Platform considers this issue closed (or it is missing)
    -> remove issue_id from snapshot.active_issues
    -> remove any slot with this issue_id from snapshot.slots
    -> Log [DRIFT] <issue_id> platform=closed snapshot=active

# For each slot whose issue is not on Platform at all (no mapping):
For each slot in snapshot.slots:
  If issue_map[slot.issue_id] is undefined:
    -> release the slot
    -> Log [DRIFT] <issue_id> not_on_platform
```

**Note**: Reconciliation uses Platform `state` (open/closed), NOT labels.
Labels are local routing hints; Platform `state` is authoritative. An
issue may carry a `closed` label while remaining `open` on the Platform
(historical inconsistency); recovery trusts the Platform.

**Note**: `scripts/platform.ts issue list --state open` returns ALL open
issues in the repo. Filter to those whose `number` appears in
`docs/state/issue_map.json` values before comparing with
`snapshot.active_issues`.

### Step 5: Recover merge checkpoint

```
If merge_cp.json does not exist -> skip

Based on merge_cp.state:
  fetched -> restart from step 2
  reset -> restart from step 3
  merged -> if local main has the merge, restart from step 5; otherwise abort
  tested -> if tests passed, restart from step 6; otherwise rollback
  pushed -> if origin == local, restart from step 7
  closed -> delete merge_cp.json, done

Log [MERGE_RESUME] <issue> from_step=<n>
```

### Step 6: Recover slots

```
For each slot in snapshot.slots:
  If worktree missing -> release slot
  Log [SLOT_RELEASED] <issue> reason=worktree_missing

For each slot:
  If last_activity_at is stale beyond orchestrator.liveness.stale_minutes
     -> release slot
  Log [SLOT_RELEASED] <issue> reason=activity_stale
```

**Note**: `last_activity_at` is synced from pi-subagents `status.json`
(`lastActivityAt`). It is the authoritative liveness signal; there is no
subagent-side heartbeat file.

### Step 7: Write recovery-complete marker

```
Write snapshot.json (atomic)
Write seq.txt
Log [RECOVERY_OK] slots=<n> queue=<m>
```

## Failure Handling

If a state file fails schema validation **after** the migration attempt
(Step 2), the Orchestrator does **not** attempt a lossy rebuild. A state
file that cannot be migrated or validated is a signal that a human must
inspect the file; guessing at its contents risks corrupting the project's
authoritative state.

1. Log `[RECOVER_FAIL] <file>`.
2. Write `docs/state/PREFLIGHT_FAIL.md` with the failure reason.
3. Create a BLOCKER Platform Issue:
   ```
   npx tsx scripts/platform.ts issue create \
     --title "BLOCKER: state file corrupted" \
     --body "<file>: <reason>" \
     --labels "blocker"
   ```
4. HALT this boot. The Launcher will retry up to
   `launcher.max_restart_attempts` times.

**Why no lossy rebuild**: The Orchestrator has no way to determine whether
a partially corrupted state file represents "empty project" or "mid-flight
project with data lost". A wrong guess could either (a) re-spawn subagents
whose slots are actually live, or (b) drop active issues silently. Both
are worse than a HALT.

**Migration is different from rebuild**: Migration (Step 0) transforms
**known** schema versions into the current version, preserving all data.
Rebuild would discard data. Only migration is attempted automatically.

## Scheduled Restart Recovery

Scheduled restart (`orchestrator.scheduled_restart_enabled`) is **mostly the same** as crash recovery, with these differences:

### Pre-actions before scheduled restart

Before `exit(42)`, Orchestrator MUST:

1. Stop spawning new subagents.
2. Wait for active slots to complete (timeout `orchestrator.liveness.stale_minutes` minutes).
3. On timeout -> mark `[INTERRUPTED]`, write orphan outputs.
4. Write `snapshot.json` (with current slot state).
5. Write `seq.txt`.
6. Write `merge_cp.json` (if merge in progress).
7. Write `launcher_checkpoint.json` (`completed: false`).
8. Log `[ORCH_RESTART]` WAL.
9. `exit(42)`.

**Key**: Wait for active slots to complete before writing state. This ensures slots are empty and no stale slots exist after restart.

### Recovery after scheduled restart

Launcher receives `exit(42)` -> restarts Orchestrator immediately.

Orchestrator Boot:

1. Run Preflight (Stages 0-8).
2. Stage 5 recovery:
   - `snapshot.json` slots should be empty (waited before restart).
   - If slots exist, recover normally.
   - If `merge_cp.json` exists, recover normally.
3. Enter Lifecycle.

**Difference from crash recovery**:

| Aspect | Crash recovery | Scheduled restart recovery |
|---|---|---|
| Slot state | May have stale slots | Usually empty |
| Context | May be corrupted | Clean |
| `merge_cp.json` | May exist | May exist |
| Recovery complexity | High | Low |

### Scheduled restart trigger

```
If orchestrator.scheduled_restart_enabled:
  Check:
    - transitions count >= scheduled_restart_transitions
    - OR elapsed time >= scheduled_restart_hours
    - OR docs/state/restart file exists

  If any true -> run scheduled restart
```

### Scheduled restart log

```
[SEQ] [TS] [INFO] [ORCH_RESTART] role=orchestrator result="reason=transitions, transitions=20"
[SEQ] [TS] [INFO] [SHUTDOWN] role=orchestrator result="graceful, slots_empty=true"
```

### If wait times out

If waiting for active slots exceeds `orchestrator.liveness.stale_minutes`:

1. Force-terminate all subagents.
2. Mark in-progress issues as `[INTERRUPTED]`.
3. Write outputs to `docs/state/outputs/orphan_<ts>/`.
4. Log `[SLOT_FORCE_RELEASED]` WAL.
5. Continue normal restart flow.

## Idempotency Guarantee

| Operation | Idempotency guarantee |
|---|---|
| Read state | Read-only |
| Write state | Atomic write (`.tmp` + `mv`) |
| Release slot | Check if slot exists |
| Replay merge | Check `merge_cp.json` state |
| Query Platform | Read-only |

## Conflict Handling

| Conflict | Resolution |
|---|---|
| Platform says closed, local says active | Platform wins |
| snapshot says slot occupied, seq says released | snapshot wins |
| merge_cp says merging, main already merged | git state wins |

## Log Format

All recovery events write to structured WAL:

```json
{"seq": 1234, "ts": "...", "level": "INFO", "issue": null, "event": "RECOVERY_START", "role": "orchestrator", "result": "startMode=RESUME"}
{"seq": 1235, "ts": "...", "level": "WARN", "issue": "t42", "event": "DRIFT", "role": null, "result": "platform=closed, snapshot=active"}
{"seq": 1236, "ts": "...", "level": "INFO", "issue": null, "event": "RECOVERY_OK", "role": "orchestrator", "result": "slots=2, queue=1"}
```