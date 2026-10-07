# Logging

Logging and audit.

## WAL Format

Each line is a standalone JSON:

```json
{"seq": 1234, "ts": "2026-10-05T16:00:00Z", "level": "INFO", "issue": "t42", "event": "TRANSITION", "role": "builder", "from": "defined", "to": "built", "result": "COMPLETE"}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `seq` | integer | Monotonically increasing sequence number |
| `ts` | string | ISO 8601 UTC |
| `level` | string | INFO / WARN / ERROR / CRITICAL |
| `issue` | string\|null | Issue ID (if applicable) |
| `event` | string | Event type |
| `role` | string\|null | Role |
| `from` | string\|null | Source state (TRANSITION only) |
| `to` | string\|null | Target state (TRANSITION only) |
| `result` | string | Result summary |
| `duration_ms` | integer\|null | Duration in milliseconds |
| `extra` | object\|null | Event-specific fields |

## Event Types

### Standard events

- `TRANSITION` — state transition
- `SPAWN` — spawn role
- `COMPLETE` — role completed
- `FAIL` — role failed
- `SLOT_RELEASED` — slot released
- `SLOT_STALE` — slot activity stale
- `SLOT_FORCE_RELEASED` — slot force-released

### Anomaly events

- `BOUNDARY` — role boundary violation
- `SECRET_LEAK` — secret leaked
- `DRIFT` — state drift
- `RECOVER` — recovery started
- `RECOVER_AUTO` — auto-repair of a corrupt state file succeeded
- `RECOVER_FAIL` — auto-repair failed; scope isolated or HALT
- `RECOVERY_OK` — recovery completed
- `INTERRUPTED` — subagent interrupted before completion (scheduled restart or force-terminate)
- `ISOLATED` — issue isolated (`blocker` + `isolated` labels); other work continues
- `ROLLBACK` — rollback
- `PAUSED` / `RESUMED` — pause / resume
- `CONFIG_CHANGED` — config changed
- `CONFIG_DEFAULT` — using default config
- `CONFIG_UNKNOWN_KEY` — unknown config key
- `MERGE_CP` — merge checkpoint
- `REDACT_FAIL` — redaction failed
- `REDACT_FAILURE_SPIKE` — too many redaction failures
- `DISK_FULL` — disk full
- `STALLED` — stalled
- `INFINITE_LOOP` — infinite loop
- `PLAN_EDITED` / `PLAN_MODIFIED` / `REQ_MODIFIED`
- `PLATFORM_GONE` — Platform issue gone
- `PLATFORM_ORPHAN` — orphan issue
- `CLOCK_SKEW` — clock skew
- `ROUTE_MISMATCH` — routing mismatch
- `CONTEXT_REFRESH` — context refresh

### API events

- `API_FAILURE` — API failure (written to `api_failures.md`)

### Schema events

- `SCHEMA_VIOLATION` — schema validation failed
- `SCHEMA_MIGRATION` — schema migration
- `SCHEMA_MIGRATION_FAIL` — schema migration failed
- `BUILDER_COMMAND_MISMATCH` — Builder command differs from verification command

### Merge events

- `MERGE_START` — merge starts
- `MERGE_STEP` — merge step
- `MERGE_OK` — merge succeeded
- `MERGE_FAIL` — merge failed
- `MERGE_ROLLBACK` — merge rolled back
- `MERGE_RESUME` — merge resumed
- `MERGE_ABORT` — merge aborted
- `MERGE_COMPLETE` — merge complete
- `FAST_MERGE` — fast merge

### Milestone events

- `MILESTONE_CREATED` — milestone created
- `MILESTONE_REVIEW_START` — review starts
- `MILESTONE_REVIEW_PASSED` — review passed
- `MILESTONE_REVIEW_FAILED` — review failed

### Human events

- `HUMAN_REVIEW_CREATED` — human_review created
- `HUMAN_REVIEW_RESOLVED` — human_review resolved
- `HUMAN_REVIEW_STALE` — human_review stale
- `HUMAN_REVIEW_AUTO_CLOSED` — human_review auto-closed
- `HUMAN_OVERRIDE` — human override
- `BLOCKER_CREATED` — BLOCKER created
- `BLOCKER_RESOLVED` — BLOCKER resolved

### Memory events

- `MEMORY_PROMOTED` — memory promoted
- `MEMORY_DEMOTED` — memory demoted
- `MEMORY_DELETED` — memory deleted
- `MEMORY_CONFLICT` — memory conflict
- `MEMORY_CONFLICT_KNOWN` — known conflict
- `MEMORY_WRITTEN` — memory written
- `MEMORY_READ` — memory read

### Lifecycle events

- `PREFLIGHT_OK` — preflight passed
- `PREFLIGHT_FAIL` — preflight failed
- `ORCH_RESTART` — Orchestrator restart
- `RESTART_DISABLED` — auto-restart disabled
- `SHUTDOWN` — shutdown

## seq.txt Write Order

`docs/state/seq.txt` is written **after every transition**:

```
1. Write WAL (with new seq)
2. Write snapshot.json (with last_seq)
3. Write seq.txt (matching last_seq)
```

**Order matters**: WAL first, then snapshot, then seq.txt.

If crash between steps 2 and 3:

- WAL has N+1
- snapshot has N+1
- seq.txt has N (stale)

On recovery: snapshot wins; overwrite seq.txt.

## Iteration Frequency

Orchestrator main loop frequency:

| Situation | Interval |
|---|---|
| Ready issue or spawnable task | Immediately proceed to next iteration |
| No ready issue, slots not full | Sleep `idle_sleep_seconds` (default 30s) |
| Slots full | Wait for any slot to complete |

## Control File Polling Frequency

- `docs/state/pause`, `docs/state/reset`: checked **every iteration**.
- `docs/state/cancel_*`: checked **every iteration**.
- Maximum delay is `idle_sleep_seconds`.

## Context Refresh

Every `orchestrator.context.refresh_interval_iterations` iterations (default 10):

1. Re-read `AGENTS.md`.
2. Re-read `skills/orchestrator/SKILL.md`.
3. Clean closed-issue info from context.
4. Write `[CONTEXT_REFRESH]` WAL.

## Dual Format

### Machine format

`docs/log/YYYY_MM_DD.md`: one JSON per line.

### Human format

`docs/log/YYYY_MM_DD_human.md`: Markdown table.

Generated daily at `log.rotation_time_utc` (default 00:05 UTC).

## Redaction

Scan before write:

- `ghp_`, `gho_`, `ghu_`, `ghs_`
- `glpat-`
- `sk-`
- `Bearer ` + 20+ chars
- Actual `API_TOKEN` value
- `-----BEGIN`

Match -> replace with `[REDACTED]`.

Redaction failure:

- Do not write the line
- Write to `docs/log/redaction_failures.md`
- If > 10 in 1 hour -> BLOCKER

## Log Rotation

- Daily rotation (UTC 00:05)
- Over `log.compress_after_days` (7 days) -> gzip
- Over `log.monthly_after_days` (30 days) -> monthly aggregation
- Over `log.quarterly_after_days` (365 days) -> quarterly archive

## Retention

| Type | Retention |
|---|---|
| Daily logs | `retention.daily_log_days` (30 days) |
| Monthly summaries | `retention.monthly_summary_days` (90 days) |
| Quarterly archives | `retention.quarterly_archive_days` (365 days) |
| Merge history | Permanent (`retention.merge_history_days=0`) |
| Failure audit | Permanent (`retention.failure_audit_days=0`) |
| Token usage | `retention.metrics_days` (default 180 days) |
| Misjudgments | `retention.metrics_days` (default 180 days) |
| Status metrics | `retention.status_metrics_days` (default 30 days) |

## Audit Files

### `docs/log/api_failures.md`

Records non-recoverable API failures. Writer: **Orchestrator**.

Triggers:

1. Platform API returns 5xx (after 3 retries fail).
2. Platform API returns 4xx (except 404).
3. Network timeout (after 3 retries).
4. Rate limit exceeds Retry-After ceiling.

Format:

```
[SEQ] [TS] [ENDPOINT] [STATUS] [RETRY_COUNT] [NOTE]
```

Also writes WAL:

```json
{"seq": 1234, "ts": "...", "level": "ERROR", "issue": null, "event": "API_FAILURE", "role": "orchestrator", "result": "endpoint=/repos/..., status=503"}
```

### `docs/log/redaction_failures.md`

Records redaction failures. Writer: Orchestrator.

**This file is ignored by `.gitignore`.**

### `docs/state/merge_history.json`

Permanently retained merge history.

### `docs/state/config_snapshot.json`

Config snapshot.

## Disk Monitoring

Hourly check:

- If available space < `disk.warn_mb` -> WARN
- If available space < `disk.halt_mb` -> HALT
- If `docs/log/` > `disk.force_archive_mb` -> force archive

On disk full:

1. Force-compress oldest logs
2. Move to `docs/log/emergency_archive/`
3. Retry write
4. If still failing -> HALT + BLOCKER

## Git Strategy

- Daily logs: not committed daily
- Weekly commit: `docs/log/weekly_YYYY_WW.md` (summary)
- Monthly summaries: committed
- Raw logs: gitignored from day 8

## Log Queries

- `pi log-tail <n>` — last N lines
- `pi log-for <issue>` — specific issue
- `pi log-since <date>` — from date
- `pi log-search <pattern>` — search

All read-only.