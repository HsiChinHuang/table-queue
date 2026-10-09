# Checkpoints

Three layers of checkpoint / state storage in this framework.

## Layer Overview

| Layer | Mechanism | Storage | Recovery Decision |
|---|---|---|---|
| 1. Pi Session | Conversation log | `~/.pi/agent/sessions/<project>/*.jsonl` | Not used for recovery |
| 2. Launcher Checkpoint | `launcher_checkpoint.json` | `docs/state/` | FRESH / RESUME |
| 3. Orchestrator State | `snapshot.json`, `merge_cp.json`, `seq.txt` | `docs/state/` | Business logic rebuild |

Each layer has a distinct role. Layer 3 is the authoritative source for
business state; Layers 1 and 2 are auxiliary.

## Layer 1: Pi Session

Pi Agent automatically creates one session per `pi run` invocation,
stored as a JSONL file under `~/.pi/agent/sessions/<project>/*.jsonl`.
Each session is a full conversation transcript.

The Launcher's spawn does NOT pass `--continue` / `--session-id` /
`--session`, so every Launcher restart produces a new session file. This
framework does NOT use Pi Session for recovery. Session files are kept
only as a debug artifact (useful for post-mortem inspection of what the
Orchestrator said in a given run).

## Layer 2: Launcher Checkpoint

The Launcher reads `docs/state/launcher_checkpoint.json` at startup to
decide FRESH vs RESUME:

```
Launcher starts
  |
  v
Read docs/state/launcher_checkpoint.json
  |- Not found -> FRESH
  |- completed: true -> FRESH
  '- completed: false -> RESUME
```

If the checkpoint is missing or `completed: true`, the Launcher treats
the project as fresh. Otherwise, it proceeds in RESUME mode; the
Orchestrator then runs Preflight Stage 5 recovery (see `recovery.md`).

### Write timing

- Orchestrator completes normally -> `completed: true`
- Orchestrator scheduled restart -> unchanged
- Launcher startup -> create if absent
- Orchestrator spawn success -> write `orchestrator_pid`
- Orchestrator exit -> clear `orchestrator_pid`

## Layer 3: Orchestrator State

The Orchestrator reads `docs/state/*.json` during Preflight Stage 5
(Recovery). These files are the authoritative source for business state:

| File | Purpose |
|---|---|
| `snapshot.json` | Active slots, merge queue, active issues |
| `seq.txt` | Monotonic sequence number (must match `snapshot.last_seq`) |
| `merge_cp.json` | In-progress merge checkpoint (Step 1–7) |
| `idempotency.json` | Idempotency keys for Platform operations |

When these files disagree with each other or with the Platform, the
authority order is defined in `recovery.md` § Authority Model.

### Write timing

- After every transition (atomic write)
- After every slot change
- After every merge step (`merge_cp.json`)

## Startup Flow

```
Launcher starts
  |
  v
Read docs/state/launcher_checkpoint.json  (Layer 2)
  |- Not found -> FRESH
  |- completed: true -> FRESH
  '- completed: false -> RESUME
  |
  v
spawn('pi', ['run', '--skill', 'skills/orchestrator/SKILL.md'])
  |
  v
Orchestrator Boot
  |- Preflight
  |    |- Stage 5: Recovery
  |         |- Read docs/state/*.json  (Layer 3)
  |         '- Rebuild business state
  '- Enter Lifecycle
```

**Note**: The config snapshot path is resolved by the Orchestrator
itself during Preflight Stage 0, not passed on the CLI. The Launcher
does NOT pass `--config`.

**Note**: The Orchestrator determines the start mode by reading
`launcher_checkpoint.json` itself. The Launcher does NOT pass `--mode`.