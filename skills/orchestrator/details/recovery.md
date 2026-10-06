# Recovery

Recovery flow when Orchestrator boots.

## Authority Model

Priority during recovery (high to low):

1. **Platform State** — issue open/closed follows the platform
2. **`docs/state/snapshot.json`** — slot / queue state
3. **`docs/state/seq.txt`** — sequence number
4. **`docs/state/merge_cp.json`** — merge checkpoint
5. **Pi Durable checkpoint** — auxiliary only

**Principle**: Platform is most authoritative; local state files are next; Pi Durable does not participate in business logic.

## Trigger

Orchestrator Boot when `snapshot.json` is non-empty.

## Recovery Steps

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
Validate idempotency.json against schemas/state/idempotency.json

On failure -> write PREFLIGHT_FAIL.md, HALT
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
Query Platform for all open issues

For each issue in snapshot.active_issues:
  If Platform says closed -> remove from snapshot
  If not found on Platform -> remove from snapshot
  Log [DRIFT] <issue> platform=<state> snapshot=active

For each slot in snapshot.slots:
  If the issue is not on Platform -> release the slot
  Log [DRIFT] <issue> not_on_platform
```

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
  If heartbeat > heartbeat.stale_minutes -> release slot
  Log [SLOT_RELEASED] <issue> reason=heartbeat_stale
```

### Step 7: Write recovery-complete marker

```
Write snapshot.json (atomic)
Write seq.txt
Log [RECOVERY_OK] slots=<n> queue=<m>
```

## Scheduled Restart Recovery

Scheduled restart (`orchestrator.scheduled_restart_enabled`) is **mostly the same** as crash recovery, with these differences:

### Pre-actions before scheduled restart

Before `exit(42)`, Orchestrator MUST:

1. Stop spawning new subagents.
2. Wait for active slots to complete (timeout `heartbeat.stale_minutes` minutes).
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

If waiting for active slots exceeds `heartbeat.stale_minutes`:

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
| Pi Durable conflicts with snapshot | snapshot wins |
| merge_cp says merging, main already merged | git state wins |

## Log Format

All recovery events write to structured WAL:

```json
{"seq": 1234, "ts": "...", "level": "INFO", "issue": null, "event": "RECOVERY_START", "role": "orchestrator", "result": "startMode=RESUME"}
{"seq": 1235, "ts": "...", "level": "WARN", "issue": "t42", "event": "DRIFT", "role": null, "result": "platform=closed, snapshot=active"}
{"seq": 1236, "ts": "...", "level": "INFO", "issue": null, "event": "RECOVERY_OK", "role": "orchestrator", "result": "slots=2, queue=1"}
```