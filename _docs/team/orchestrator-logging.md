# Logging, Archiving, Scale

Master spec for logs, archives, and scale handling.
Referenced from `orchestrator.md`, `orchestrator-labels.md`, `orchestrator-special.md`.

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## 1. Log format

### 1.1 Header

Each daily log starts with: `# LOG FORMAT v1`

Format version independent of config_version.

### 1.2 Line format

    [SEQ] [UTC_TS] [LOCAL_TS] [LEVEL] [<ID>] [<from> -> <to>] [<role>] [<result>]

Levels: INFO | WARN | ERROR | CRITICAL.
Missing level: default INFO + warning.

Line max: `[log.line_max_chars]` chars.
Exceed: truncate + `[...TRUNCATED n chars]`.
Full content: `state/outputs/<issue>-log-<seq>.md`.
Log line includes path reference.

### 1.3 Event types

Standard transitions plus:
[BOUNDARY] [SECRET_LEAK] [DRIFT] [RECOVER] [ROLLBACK]
[PAUSED] [RESUMED] [SLOT_STALE] [MERGE_CP*]
[CONFIG_CHANGED] [PLAN_MODIFIED] [CLOCK_SKEW]
[REDACT_FAIL] [LOG_BACKUP_FAIL] [DISK_FULL]

### 1.4 Dual format

- Machine: `log/YYYY-MM-DD.md` (seq-sorted, single-line).
- Human: `log/YYYY-MM-DD-human.md` (Markdown, generated daily).
- Human file: table format, grouped by issue.
- Generation time: `[log.rotation_time_utc]` (default 00:05 UTC).
- Missed: generated on next boot.

### 1.5 Time consistency

- Primary sort: SEQ (monotonic).
- UTC_TS: reference only.
- LOCAL_TS: human reading.
- Clock skew > 60s: log `[CLOCK_SKEW]`.
- Never sort by timestamp.

## 2. Redaction

### 2.1 Before write

Scan line for:
- `ghp_`, `gho_`, `ghu_`, `ghs_`
- `glpat-`
- `sk-`
- `Bearer ` + 20+ chars
- Literal API_TOKEN value
- `-----BEGIN` (PEM)

Match: replace with `[REDACTED]`.

### 2.2 Redaction failure

If redaction fails (unknown pattern, parse error):
- Do NOT write the line.
- Write fallback: `[SEQ] [TS] [REDACT_FAIL] <original_length>`.
- Log to `log/redaction-failures.md`.
- > 10 failures/hour: BLOCKER `[REDACT_FAILURE_SPIKE]`.

### 2.3 Human log privacy

- Same redaction as machine log.
- Comment contains "PRIVATE": exclude from human log.
- Human may request exclusion: `[NO_LOG]` marker in comment.

## 3. Atomicity and rotation

### 3.1 Write atomicity

- Single-writer: Orchestrator only.
- O_APPEND mode.
- Each line flushed.
- Crash mid-write: skip malformed last line on recovery.

### 3.2 Daily rotation

    Trigger: UTC `[log.rotation_time_utc]` (00:05).
    1. Set marker `state/log-rotating`.
    2. Flush current buffer.
    3. Generate `YYYY-MM-DD-human.md`.
    4. Delete marker.
    5. Resume.
    Missed (Orchestrator off): on next boot.

Buffer during rotation: `[log.rotation_buffer_lines]` lines.
Exceed: BLOCKER.

### 3.3 Rotation and Git

- Rotation: local files only.
- Git commit: weekly (see Sec. 5).
- Rotation does not trigger commit.
- Crash between rotation and next commit: files recoverable from disk.

### 3.4 Format version migration

- Header: `# LOG FORMAT vN`.
- New format: v(N+1).
- Parser handles vN and v(N+1).
- Old logs never re-parsed.
- Archive retains original version.

## 4. Archiving

### 4.1 Retention

| File type | Default | Config key |
|---|---|---|
| Daily logs | 30 days | `retention.daily_log_days` |
| Monthly summaries | 90 days | `retention.monthly_summary_days` |
| Quarterly archives | 365 days | `retention.quarterly_archive_days` |
| Merge history | permanent | `retention.merge_history_days=0` |
| Failure audit | permanent | `retention.failure_audit_days=0` |
| Compliance | `compliance_years` | override |

If `retention.compliance_years` set: quarterly archives kept longer.

### 4.2 Compression

- After `[log.compress_after_days]` (7): gzip daily files → `.md.gz`.
- After `[log.monthly_after_days]` (30): aggregate to monthly, gzip.
- After `[log.quarterly_after_days]` (365): archive quarterly.

### 4.3 Rotation atomicity

月末归档流程：
1. 设置 marker `state/log-rotating`.
2. Flush。
3. Rename `YYYY-MM-DD.md` → `.md.gz`.
4. Delete marker.
5. Resume.

During rotation: writes buffered.
Max buffer: `[log.rotation_buffer_lines]`.
Exceed: BLOCKER.

### 4.4 Archive disk check

Before archive:
- Verify free space > `[disk.archive_free_ratio]` × expected archive size.
- Insufficient: HALT, alert.
- After archive: verify success.

### 4.5 Backlog split atomicity

- Write `backlog-active.md.tmp`, `backlog-closed.md.tmp`.
- Atomic rename both.
- Old `backlog.md` retained as `backlog.md.bak` for 1 day.
- Delete `.bak` after successful next boot.

## 5. Git strategy

### 5.1 Commit strategy

- Daily logs: NOT committed daily.
- Weekly commit: `log/weekly-YYYY-WW.md` (summary).
- Monthly summaries: committed.
- Raw logs: gitignored (day 8 onwards).

### 5.2 Log backup

- Weekly: push to remote branch `logs/weekly-YYYY-WW`.
- Not main (avoid pollution).
- Push fail: log `[LOG_BACKUP_FAIL]`, retry next week.
- S3/backup: out of scope.

### 5.3 .gitignore rules

    # Raw daily logs (uncommitted after week 1)
    _docs/log/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md
    _docs/log/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-human.md
    _docs/log/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md.gz

    # Track summaries and audits
    !_docs/log/weekly-*.md
    !_docs/log/*/summary.md
    !_docs/log/failure-audit*.md
    !_docs/log/index.md
    !_docs/log/archive/**

## 6. Reports

### 6.1 Monthly summary

`log/YYYY-MM/summary.md`:
- Issues: opened / closed / open.
- Retries: total, avg, max.
- BLOCKER count.
- Merge count.
- Avg duration.
- Failure type distribution.

### 6.2 Report accuracy

- Generated at month end + `[log.report_delay_hours]` (12h).
- Reads complete previous month.
- Late data (> 12h): next month's report notes it.
- Idempotent: can regenerate.

### 6.3 Quarterly archive

`log/archive/YYYY-QN/`:
- All months.
- Compressed.
- Index: `log/archive/YYYY-QN/index.md`.

### 6.4 Annual report

`log/annual-YYYY.md`:
- Aggregate stats.
- Top issues by complexity.
- Process improvements.

### 6.5 Failure audit derivation

- Failure audit = aggregate from daily logs + retry.json.
- Generated on completion OR human request.
- Stored: `log/failure-audit-<ts>.md`.
- Not continuously updated.

### 6.6 Metrics vs logs

- Logs: events (append-only).
- Metrics: aggregated stats (updated periodically).
- Derived from logs + state files.
- Stored: `state/metrics/*.json`.

## 7. Disk monitoring

### 7.1 Thresholds

- Preflight: < `[disk.warn_mb]` warn, < `[disk.halt_mb]` halt.
- During: hourly check.
- < `[disk.halt_mb]`: pause operations, alert.

### 7.2 Disk full emergency

Detected: write fail with ENOSPC.

Immediate actions:
1. Force-compress oldest logs.
2. Move to `log/emergency-archive/`.
3. Retry write.
4. If still fail: HALT.

Notify: BLOCKER `[DISK_FULL]`.
Resume: human frees space.

### 7.3 Force archive trigger

- `log/` > `[disk.force_archive_mb]` (500): force archive.
- `log/` > `[disk.warn_mb]` (1000): warn.

## 8. Scale

### 8.1 Backlog split

- `backlog.md`: active issues only.
- `backlog-closed.md`: archived rows.
- Auto-split at `[backlog.active_max_rows]` (500) active rows.
- Config: `[backlog.split_on_exceed]`.

### 8.2 Issue-map

- Single file.
- Pagination not needed (small).
- If > 10K entries: split by range.

### 8.3 API pagination

- Query platform: `[api.page_size]` (100) per page.
- Cache in memory.
- Refresh: `[api.cache_ttl_minutes]` (5 min) OR on transition.

### 8.4 API cache invalidation

- TTL: `[api.cache_ttl_minutes]`.
- Force refresh: on user action, on error, on suspected drift.
- On 404 or 410: immediate invalidate.
- On 429: exponential backoff, keep cache.
- Config: `[api.cache_force_on_error]`.

### 8.5 Cache and drift

- Drift check uses fresh data (bypasses cache).
- Normal queries use cache.
- Force refresh: on drift suspicion.

### 8.6 Priority sort stability

- Primary: priority score (see `orchestrator-slots.md`).
- Tie-break 1: creation timestamp.
- Tie-break 2: Size (S < M < L).
- Tie-break 3: local ID ascending.
- Fully deterministic.

### 8.7 DAG cache invalidation

- Track: `issues/*.md` directory mtime hash.
- On boot: compare.
- Differs: invalidate cache, rebuild.
- On any issue write: invalidate.

### 8.8 Slot priority at 1000+

- Ready issues only.
- 1000+ total: still fast (ready subset typically < 100).
- Sort cost: O(n log n) negligible.

### 8.9 Memory index at scale

- Rebuild from files on boot.
- Cache in memory.
- No persistent index beyond file listing.

## 9. Log queries

### 9.1 Query tools

- `orchestrator log-tail <n>`: last N lines.
- `orchestrator log-for <issue>`: per-issue.
- `orchestrator log-since <date>`: from date.
- `orchestrator log-search <pattern>`: grep.
- All read-only.
- Output to stdout.

### 9.2 Per-issue extraction

Command: `orchestrator log-for <issue>`.
Output: `log/by-issue/<issue>.md`.
Contents: all log lines for that issue.
Generated on demand.

### 9.3 Archive index

`log/index.md`:
- By date: link to daily files.
- By issue: list of issues with log ranges.
- By event type: link to specific events.

Maintenance:
- On each transition: append (cheap).
- Daily end: full rebuild.
- Archive: move entries.

### 9.4 L3 analysis privacy

- Analysis reads redacted logs only.
- Output contains "PRIVATE": exclude.
- Analysis stored: `log/analysis/`.
- Human reviews before external sharing.

## 10. Integration

### 10.1 Log and failure audit

See Sec. 6.5. Failure audit is on-demand, not continuous.

### 10.2 Log and merge history

- Merge history: `state/merge-history.json` (permanent).
- Referenced from daily log lines.
- Both preserved.

### 10.3 Log and memory

- Memory files: `_docs/memory/`.
- Log entries about memory: `[MEMORY_PROMOTED]`, `[MEMORY_FAILED]`.
- Independent storage.

### 10.4 Log and metrics

- Metrics derived from logs.
- Stored separately: `state/metrics/*.json`.
- Logs source of truth for events.