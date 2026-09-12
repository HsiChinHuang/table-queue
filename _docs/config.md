# Config

## Files

| File | Purpose | Secrets? |
|---|---|---|
| `.env` | Runtime env (secrets + overrides) | Yes |
| `_docs/config.yaml` | Numeric limits and timeouts | No |
| `_docs/config.yaml.example` | Template with defaults | No |
| `_docs/state/CONFIG_SNAPSHOT.json` | Effective values at boot | No (committed) |

## Precedence (high to low)

1. Command-line arg (if any)
2. Environment variable
3. `config.yaml`
4. `config.yaml.example` default

Only the highest-precedence source for a key is used.

## Required env vars

| Var | Required | Format |
|---|---|---|
| `PLATFORM` | yes | `github` or `gitlab` |
| `API_TOKEN` | yes | non-empty string |
| `REPO_ID` | yes | GitHub: `owner/repo`; GitLab: numeric |
| `API_URL` | no | URL |
| `APPROVAL_MODE` | no | `full-auto` (default) / `semi-auto` / `manual` |

## Overridable keys (env -> yaml)

Only these may be set via env:

| Env | YAML |
|---|---|
| `MAX_SLOTS` | `slots.max` |
| `SW_RETRY_PER_ROUND` | `sw_retry.per_round` |
| `SW_RETRY_PER_ISSUE` | `sw_retry.per_issue` |
| `PM_RETRY_PER_ISSUE` | `pm_retry.per_issue` |
| `QA_TIMEOUT_MINUTES` | `timeouts.qa_minutes` |
| `ORCH_RESTART_HOURS` | `timeouts.orch_restart_hours` |
| `ORCH_RESTART_TRANSITIONS` | `timeouts.orch_restart_transitions` |

Retention, memory, output, limits: NOT overridable via env.

## Ranges

| Key | Min | Max |
|---|---|---|
| `slots.max` | 1 | 10 |
| `sw_retry.per_round` | 1 | 200 |
| `sw_retry.per_issue` | 1 | 1000 |
| `pm_retry.per_issue` | 1 | 50 |
| `timeouts.qa_minutes` | 1 | 480 |
| `timeouts.orch_restart_transitions` | 1 | 10000 |
| `timeouts.orch_restart_hours` | 1 | 72 |
| `timeouts.recovery_minutes` | 1 | 60 |
| `timeouts.heartbeat_stale_minutes` | 1 | 60 |
| `timeouts.slot_wait_minutes` | 1 | 60 |
| `timeouts.auto_commit_minutes` | 1 | 60 |
| `timeouts.idle_sleep_seconds` | 5 | 300 |
| `memory.read_max` | 1 | 10 |
| `memory.promote_count` | 1 | 20 |
| `memory.fail_delete_threshold` | 1 | 20 |
| `output.externalize_lines` | 10 | 10000 |
| `output.externalize_tokens` | 100 | 100000 |
| `output.request_max_lines` | 10 | 5000 |
| `output.diff_split_lines` | 100 | 50000 |
| `retention.*` | 1 | 3650 |
| `limits.dep_chain_warn` | 1 | 100 |
| `limits.dep_chain_halt` | 1 | 200 |
| `limits.comments_keep` | 1 | 100 |
| `limits.analysis_max_per_day` | 0 | 100 |
| `log.tail_lines` | 10 | 10000 |
| `merge.full_suite_every` | 1 | 1000 |
| `retry.subagent.*` | 0 | 20 |
| `limits.total_retry_warn` | 100 | 100000 |
| `limits.blocker_fatigue_count` | 1 | 100 |
| `limits.stale_block_days` | 1 | 365 |
| `limits.long_wait_ready_hours` | 1 | 720 |
| `limits.process_anomaly_pct` | 1 | 100 |
| `limits.process_anomaly_window` | 5 | 1000 |
| `limits.plan_quality_threshold` | 1 | 100 |
| `limits.oscillation_alternations` | 1 | 10 |
| `limits.qa_misjudgment_threshold` | 1 | 10 |
| `limits.similar_failures_threshold` | 1 | 100 |
| `limits.correlation_window_minutes` | 1 | 60 |
| `limits.concurrent_failure_threshold` | 1 | 100 |
| `limits.starvation_warn_hours` | 1 | 720 |
| `limits.starvation_blocker_hours` | 1 | 1440 |
| `limits.backlog_drift_log` | 1 | 100 |
| `limits.backlog_drift_blocker` | 1 | 1000 |
| `limits.ac_change_blocker_pct` | 1 | 100 |
| `limits.api_confirm_retries` | 0 | 10 |
| `limits.api_confirm_gap_seconds` | 1 | 60 |
| `limits.failure_pattern_threshold` | 1 | 100 |
| `limits.config_suspect_threshold` | 1 | 100 |
| `limits.slot_stale_multiplier` | 2 | 10 |
| `limits.recovery_attempt_threshold` | 1 | 10 |
| `limits.blocker_create_retry` | 1 | 10 |
| `limits.approval_delete_files` | 1 | 100 |
| `limits.approval_issue_count` | 1 | 1000 |
| `limits.similarity_threshold` | 0 | 1 |
| `limits.git_retry_max` | 1 | 10 |
| `merge.dry_run` | false | true |
| `merge.queue_priority_by_dependents` | false | true |
| `merge.fast_path_lines` | 0 | 1000 |
| `merge.commit_message_max` | 100 | 50000 |
| `timeouts.ci_wait_minutes` | 0 | 120 |
| `timeouts.merge_starvation_hours` | 1 | 720 |
| `git.push_retry` | 1 | 10 |
| `git.merge_fix_max_level` | 1 | 5 |
| `git.flaky_rerun` | 0 | 5 |
| `git.flaky_high_pct` | 1 | 100 |
| `git.worktree_retry` | 1 | 10 |
| `git.worktree_lock_backoff_seconds` | 1 | 60 |
| `git.force_push_check` | false | true |
| `git.autocrlf_uniform` | false | true |
| `git.ignore_all_space_first` | false | true |
| `git.binary_conflict_human_required` | false | true |
| `git.main_history_track` | false | true |
| `git.require_gpg` | false | true |
| `worktree.pool_size` | 0 | 10 |
| `audit.chain` | false | true |
| `memory.write_after_retries` | 1 | 100 |
| `memory.pattern_threshold` | 1 | 100 |
| `memory.similarity_dedupe` | 0 | 1 |
| `memory.max_size_kb` | 1 | 100 |
| `memory.max_candidates` | 10 | 1000 |
| `memory.retention_days` | 7 | 3650 |
| `memory.verified_retention_days` | 30 | 3650 |
| `ac.materiality_threshold_pct` | 1 | 100 |
| `timeouts.suggestion_pm_wait_hours` | 1 | 168 |
| `timeouts.suggestion_timeout_hours` | 2 | 336 |
| `limits.history_max_lines` | 100 | 100000 |
| `limits.pending_stale_days` | 1 | 90 |
| `sa.batch_size` | 10 | 500 |
| `sa.batch_delay_seconds` | 0 | 60 |
| `sa.rate_limit_per_second` | 1 | 100 |
| `sa.max_minutes` | 5 | 480 |
| `sa.output_language` | (enum) | en/zh/ja/... |
| `dag.max_depth_warn` | 1 | 1000 |
| `dag.max_depth_halt` | 1 | 2000 |
| `dag.hub_file_threshold` | 2 | 100 |
| `dag.hub_file_human_escalate` | 2 | 1000 |
| `timeouts.approval_warn_hours` | 1 | 720 |
| `timeouts.approval_max_hours` | 2 | 1440 |
| `timeouts.pause_stale_days` | 1 | 365 |
| `timeouts.completion_verify_delay_seconds` | 10 | 600 |
| `retention.approval_keep_days` | 1 | 365 |
| `completion.auto_restart` | false | true |
| `log.line_max_chars` | 100 | 5000 |
| `log.rotation_buffer_lines` | 100 | 100000 |
| `log.report_delay_hours` | 1 | 48 |
| `retention.daily_log_days` | 7 | 3650 |
| `retention.monthly_summary_days` | 30 | 3650 |
| `retention.quarterly_archive_days` | 90 | 3650 |
| `retention.compliance_years` | 1 | 10 |
| `disk.warn_mb` | 100 | 100000 |
| `disk.halt_mb` | 10 | 10000 |
| `disk.force_archive_mb` | 50 | 50000 |
| `disk.archive_free_ratio` | 1.0 | 10.0 |
| `backlog.active_max_rows` | 100 | 10000 |
| `api.page_size` | 10 | 1000 |
| `api.cache_ttl_minutes` | 1 | 60 |
| `dag.hub_scan_interval_hours` | 1 | 168 |
| `dag.hub_scan_lock_timeout_seconds` | 10 | 300 |
| `priority.human_override_max` | 1 | 10 |
| `priority.boost_value` | 10 | 1000 |

Out of range -> HALT.

## Validation

Orchestrator validates at boot. On failure:

Write `_docs/state/PREFLIGHT_FAIL.md`:

    File: <path>
    Key: <dotted.key>
    Expected: <rule>
    Got: <value>

HALT.

## Env parsing rules (.env)

- `#` at line start = comment, ignored.
- `KEY=value`, no spaces around `=`.
- Values with special chars must be single- or double-quoted.
- No escape sequences inside quotes.
- No multi-line, no variable expansion, no command substitution.
- Blank lines ignored.
- Malformed line: skip + warn.
- All lines malformed: HALT.
- Token with quotes: base64-encode and decode by Orchestrator.

## Type conversion

Env values are strings. Orchestrator converts per schema:

- Integer keys: parse as int. Failure -> PREFLIGHT_FAIL.
- URL keys: must be valid URL.
- Enum keys: must be in allowed set.

## Platform URL

| Platform | Default |
|---|---|
| GitHub public | `https://api.github.com` |
| GitHub Enterprise | `https://<host>/api/v3` |
| GitLab public | `https://gitlab.com/api/v4` |
| GitLab self-hosted | `https://<host>/api/v4` |

Override via `API_URL`. Orchestrator pings it at boot.

## Timezone

- `timezone` key sets the base for `LOCAL_TS` in log lines.
- Default: `UTC`.
- `UTC_TS` is always UTC, regardless of this setting.
- Valid values: any IANA timezone name (e.g., `Asia/Taipei`, `America/New_York`).
- If unset or invalid: falls back to `UTC`.
- Used only for human-readable timestamps; all comparisons use `UTC_TS`.

## Snapshot

After preflight passes, before Lifecycle begins:

- Merge all sources (env > yaml > default).
- Write `_docs/state/CONFIG_SNAPSHOT.json`:

    {
      "timestamp": "...",
      "config_version": 1,
      "values": {...},
      "sources": {"key": "env|yaml|default"}
    }

- Committed to Git.
- Kept history: latest 10 in `_docs/state/history/config-<ts>.json`, older archived.

## Config changes at runtime

- Config is read **only at boot**.
- Changes require Orchestrator restart.
- On next boot, compare to snapshot; log `[CONFIG_CHANGED] <key> <old> -> <new>` per key.
- Changed config applies **immediately to all in-flight issues** (no per-issue pinning).

## Missing config.yaml

If `config.yaml` missing: use `config.yaml.example` defaults.
Log `[CONFIG_DEFAULT] using example defaults`.
Do NOT HALT.

## Unknown keys

- Unknown key in `config.yaml`: warn, log `[CONFIG_UNKNOWN_KEY] <key>`.
- Near-miss key (edit distance <= 2 from known): HALT, likely typo.

## Secrets

- `API_TOKEN` only from env, never yaml.
- On boot, load token value into redaction dictionary.
- All log lines and comments pass through redaction.

## File permissions

- `.env`: 600 (owner only). World-readable -> warn.
- `config.yaml`: 644 acceptable.
- `CONFIG_SNAPSHOT.json`: 644 (no secrets).

## YAML rules

- YAML 1.2.
- Booleans: `true` / `false` only (no `yes` / `no`).
- UTF-8 no BOM.
- Anchors and aliases: allowed but discouraged.

## Change audit

- `config.yaml` header may contain change-log comments.
- On boot, if snapshot differs from prior, log `[CONFIG_CHANGED]` per changed key.
- No approval required for config changes.