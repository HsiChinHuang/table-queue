# Preflight

Checks run when Orchestrator boots.

## Timing

Every Orchestrator startup (including after a scheduled restart).

## Stage 0: Config load and validation

### Step 1: Load .env

Read `.env` line by line:

- Ignore lines starting with `#`.
- Format: `KEY=value`, no spaces around `=`.
- Values with special chars must be quoted.
- Malformed line: skip + WARN.
- All malformed: HALT.

### Step 2: Load config.yaml

Read `docs/config.yaml`. If missing -> use defaults from `docs/config.yaml.example`, log `[CONFIG_DEFAULT]`.

### Step 3: Apply env overrides

Only keys listed in `config.md` may be overridden by env.

### Step 4: Validate config

- Type check (integer / string / boolean).
- Range check (min/max defined in `config.yaml`).
- Version check (`config_version` must be the currently supported version).
- Unknown key: WARN + log `[CONFIG_UNKNOWN_KEY]`.
- Near-miss key (edit distance <= 2): HALT.
- Out of range: HALT.
- Immutable key that disagrees with the system design: HALT.

**Immutable keys** (must have the documented value; any other value HALT):

| Key | Required value | Reason |
|---|---|---|
| `automation.auto_skip_blocked` | `true` | The system is designed to always isolate blocked issues and continue. Setting it to `false` would make blocked issues pause the whole project, contradicting the no-halt policy. |

Failure -> write `docs/state/PREFLIGHT_FAIL.md`, HALT.

### Step 5: Check .env permissions

- If not 600 -> WARN.

### Step 6: Build redaction dictionary

Built from the `API_TOKEN` value.

### Step 7: Trigger schema migration

**Timing**: before writing `config_snapshot.json`.

Flow:

```
for each data file in docs/state/:
  if file has schema_version field:
    read current version from data
    if current version < schema_version:
      call migrate(data, current_version, schema_version)
      write back
```

**Note**: The actual migration is for **data files** (e.g. `snapshot.json`, `retry.json`), not the schema files themselves.

If migration fails -> log `[SCHEMA_MIGRATION_FAIL]`, HALT.

### Step 8: Write CONFIG_SNAPSHOT

Merge all sources (env > yaml > default), write `docs/state/config_snapshot.json` (committed).

Format:

```json
{
  "schema_version": "1.0",
  "timestamp": "...",
  "config_version": 2,
  "values": {},
  "sources": {"key": "env|yaml|default"}
}
```

### Step 9: Compare with prior snapshot

If a prior snapshot exists:

- Compare each key.
- If different -> log `[CONFIG_CHANGED] <key> <old> -> <new>`.
- Archive prior snapshot to `docs/state/history/config_<ts>.json`.
- Keep the latest `retention.config_history_keep` (default 10).

## Stage 1: Environment checks (HALT on failure)

| Check | Command | Expected |
|---|---|---|
| git installed | `git --version` | >= 2.20 |
| In git repo | `git rev-parse --git-dir` | success |
| origin set | `git remote get-url origin` | non-empty |
| state dir writable | `touch docs/state/.pf && rm docs/state/.pf` | success |
| log dir writable | `touch docs/log/.pf && rm docs/log/.pf` | success |
| issues dir writable | `touch docs/issues/.pf && rm docs/issues/.pf` | success |
| worktree base | `mkdir -p ../worktrees` | success |
| Platform API ping | GET repo metadata | HTTP 200 |
| `PLATFORM` set | env check | `github` or `gitlab` |
| `API_TOKEN` set | env check | non-empty |
| `REPO_ID` set | env check | non-empty |
| Default branch | `git symbolic-ref refs/remotes/origin/HEAD` | non-empty |
| origin URL | compare `docs/state/origin_url.txt` | unchanged |
| Branch protection | GET API /protection | unprotected or PR flow configured |

Failure -> write `docs/state/PREFLIGHT_FAIL.md`, HALT.

## Stage 2: Reference integrity scan

Scan all `docs/**/*.md` for `docs/...` references.

Ignore:

- Dynamic paths: `issues/<id>.md`, `state/outputs/...`, `log/...`, `memory/candidates/...`, `memory/verified/...`
- Examples: `docs/*.example`
- Details files: `skills/*/details/*`

For static references: verify the file exists.

Missing -> write `docs/state/PREFLIGHT_FAIL.md`, HALT.

## Stage 3: Project checks (only if `docs/plan.md` exists)

Read tech-stack.

| Check | Expected |
|---|---|
| Toolchain present | per tech-stack (uv, npm, etc.) |
| Test runner present | per tech-stack |
| Linter present | per tech-stack |
| Platform labels creatable | API |
| `.gitattributes` present | `test -f .gitattributes` |
| autocrlf uniform | `git config core.autocrlf` = `true` or `input` |
| commit.gpgsign | matches repo requirement |
| user.name / email | set |

Failure severity:

- Linter missing: log only, no HALT.
- Test runner missing: BLOCKER.
- Toolchain missing: BLOCKER.
- `.gitattributes` missing: WARN.
- autocrlf not uniform: HALT.
- GPG mismatch: BLOCKER.
- user.name / email unset: WARN.

## Stage 4: Double-instance guard

### Step 1: Check orchestrator.lock

```
Read docs/state/orchestrator.lock
If exists:
  Read PID
  If PID alive -> HALT (another Orchestrator running)
  If PID dead -> overwrite (last crash)
If not exists -> create
```

### Step 2: Write own PID

Write `docs/state/orchestrator.lock`:

```json
{
  "schema_version": "1.0",
  "pid": 12345,
  "boot_at": "2026-10-05T14:00:00Z",
  "boot_count": 1
}
```

## Stage 5: Recovery

See `recovery.md` for the full flow and the auto-repair procedure.

**Failure handling**: If recovery fails:

1. Attempt auto-repair (see `recovery.md` § Auto-Repair).
2. If auto-repair succeeds -> log `[RECOVER_AUTO]`, continue.
3. If auto-repair fails -> write `docs/state/PREFLIGHT_FAIL.md`, create BLOCKER, HALT.

The Launcher will restart the Orchestrator up to `launcher.max_restart_attempts` times. If the failure is persistent, the Launcher eventually gives up.

## Stage 6: Scan pending

Scan `docs/issues/pending/*.md`:

- If Platform has an issue with the same title -> delete pending, log `[RECOVERED]`.
- Otherwise -> normal ID assignment (deferred to Lifecycle).

## Stage 7: Orchestrator liveness baseline

- Verify lock exists.
- Orchestrator liveness = UTC timestamp of the last log line.
- If log stale > `orchestrator.liveness.stale_minutes` -> treat as crashed.

**Note**: This is the **Orchestrator's own** liveness check. It is distinct from subagent watchdog, which is provided by pi-subagents (see `slots.md`).

## Stage 8: Update launcher_checkpoint

Write `docs/state/launcher_checkpoint.json`:

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-10-05T14:00:00Z",
  "last_seq": 0,
  "completed": false,
  "orchestrator_pid": 12345
}
```

## Preflight Complete

All Stages passed -> log `[PREFLIGHT_OK]`, delete `docs/state/PREFLIGHT_FAIL.md`, enter Lifecycle.

## First-Run Handling

After Preflight passes, **before entering the main Lifecycle**:

- If `docs/state/initialized` exists:
  - Proceed directly to Lifecycle Step 1.

- If `docs/state/initialized` does NOT exist:
  - Lifecycle **Step 0** handles initialization. This includes:
    - Checking `docs/requirements.md` exists.
    - Triggering the initial `Definer: survey` if `docs/plan.md` does not exist.
    - After all `review_plan` runs pass, the Orchestrator automatically
      creates `docs/state/initialized` and proceeds.

## Degradable Features (WARN only, no HALT)

| Feature | If missing |
|---|---|
| `docs/memory/` | Skip memory reads/writes |
| `docs/cache/` | Skip caching |
| `docs/log/analysis/` | Skip L3/L4 analysis |