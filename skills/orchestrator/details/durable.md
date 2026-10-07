# Pi Durable Integration

Integration spec between Pi Durable and this system.

## Role of Pi Durable

Pi Durable is Pi Agent 1.0's built-in checkpoint mechanism. It:

- Periodically saves checkpoints during task execution
- Supports resuming from a checkpoint
- Distinguishes idempotent from non-idempotent operations

**In this system, Pi Durable plays an auxiliary role.** Our state files are the authoritative source of business logic.

## Three Checkpoint Types

| Type | Triggered by | Saved content | Location |
|---|---|---|---|
| Pi Durable checkpoint | Pi Agent (automatic) | Pi Agent internal state | Managed by Pi Agent |
| Launcher checkpoint | Launcher | Completion status | docs/state/launcher_checkpoint.json |
| Orchestrator state | Orchestrator | Slots / Queue / Seq | docs/state/*.json |

## Startup Flow

```
Launcher starts
  |
  v
Read docs/state/launcher_checkpoint.json
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
  |- Read snapshot.json
  |   |- Empty -> brand-new project
  |   '- Non-empty -> run recovery
  '- Enter Lifecycle
```

**Note**: The config snapshot path is resolved by the Orchestrator itself during Preflight Stage 0, not passed on the CLI. Launcher does NOT pass `--config`.

**Note**: Orchestrator determines the start mode by reading `launcher_checkpoint.json` itself. Launcher does NOT pass `--mode`.

## Why We Do Not Depend on Pi Durable

1. **Business logic independence** — Pi Durable only manages Pi Agent's internal state, not business logic.
2. **Degradable** — Even if Pi Durable is unavailable, recovery from state files still works.
3. **Auditable** — Our state files are plain JSON, easy to audit.
4. **Predictable** — Recovery logic is code, not LLM judgment.

## Integration with Launcher

Launcher is responsible for:

- Reading `launcher_checkpoint.json`
- Recording `orchestrator_pid` while Orchestrator runs
- Clearing `orchestrator_pid` after Orchestrator exits
- Marking `completed: true` after normal completion

Launcher does NOT directly read or write Pi Durable checkpoints.

## Integration with Orchestrator

Orchestrator is responsible for:

- Rebuilding state from state files
- NOT directly reading or writing Pi Durable checkpoints
- Using Pi Durable's context-restore API if available (optional)

## Degradation Strategy

If Pi Durable is unavailable:

1. Launcher depends only on `launcher_checkpoint.json`.
2. Orchestrator depends only on state files.
3. Recovery logic is unchanged.

## Checkpoint Write Timing

### Launcher checkpoint

- Orchestrator completes normally -> `completed: true`
- Orchestrator scheduled restart -> unchanged
- Launcher startup -> create if absent
- Orchestrator spawn success -> write `orchestrator_pid`
- Orchestrator exit -> clear `orchestrator_pid`

### Orchestrator state

- After every transition (atomic write)
- After every slot change
- After every merge step (`merge_cp.json`)

### Pi Durable checkpoint

Managed automatically by Pi Agent; this system does not interfere.