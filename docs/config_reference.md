# Config Reference

Complete reference for every key in `docs/config.yaml`.

## Status Legend

| Status | Meaning |
|---|---|
| **Implemented** | Key is read and acted upon by code (extensions / launcher) or a skill |
| **Referenced** | Key is mentioned in skills but not yet read by code |
| **Reserved** | Key is defined but not yet used anywhere |

## `config_version`

| Key | Status | Used by |
|---|---|---|
| `config_version` | Implemented | Preflight Stage 0 Step 4 |

## `timezone`

| Key | Status | Used by |
|---|---|---|
| `timezone` | Implemented | Logging (`logging.md`) for `LOCAL_TS` |

## Launcher

| Key | Status | Used by |
|---|---|---|
| `launcher.auto_restart` | Implemented | `launcher/index.ts`, `launcher/config_loader.ts`, `durable.md` |
| `launcher.max_restart_attempts` | Implemented | `launcher/index.ts`, `launcher/config_loader.ts` |
| `launcher.backoff_seconds` | Implemented | `launcher/restart_handler.ts` (`DEFAULT_POLICY`) |
| `launcher.reset_on_scheduled_restart` | Implemented | `launcher/restart_handler.ts` (`shouldResetCounter`) |

## Orchestrator

| Key | Status | Used by |
|---|---|---|
| `orchestrator.scheduled_restart_enabled` | Implemented | `lifecycle.md` Step 14, `recovery.md`, `config_loader.ts` |
| `orchestrator.scheduled_restart_transitions` | Implemented | `lifecycle.md` Step 14, `recovery.md`, `config_loader.ts` |
| `orchestrator.scheduled_restart_hours` | Implemented | `lifecycle.md` Step 14, `recovery.md`, `config_loader.ts` |
| `orchestrator.context.refresh_interval_iterations` | Referenced | `lifecycle.md` Step 15, `logging.md` |
| `orchestrator.context.refresh_files` | **Reserved** | Not yet read by code (list used in `lifecycle.md` Step 15 is hardcoded) |

**Note**: `orchestrator.context.refresh_files` is currently reserved. `lifecycle.md` Step 15 hardcodes the list (`AGENTS.md`, `skills/orchestrator/SKILL.md`). Future implementation should read this key.

## Slots

| Key | Status | Used by |
|---|---|---|
| `slots.max` | Implemented | `slots.md`, `lifecycle.md`, `config_loader.ts` |
| `slots.pause_threshold` | Implemented | `slots.md`, `lifecycle.md` |
| `slots.pause_threshold_min` | Implemented | `slots.md`, `slot_manager.ts` (`adjustPauseThreshold`) |
| `slots.pause_threshold_max` | Implemented | `slots.md`, `slot_manager.ts` (`adjustPauseThreshold`) |

## Roles

| Key | Status | Used by |
|---|---|---|
| `roles.<role>.default_thinking` | Referenced | `config.yaml` only; the actual thinking level per phase is defined below |
| `roles.<role>.max_retries` | Implemented | `gates.md`, `failures.md` |
| `roles.<role>.timeout_minutes` | Implemented | `failures.md` |
| `roles.<role>.phases.<phase>.thinking` | Referenced | `config.yaml`; spawn code should pass to Pi Agent |
| `roles.<role>.phases.<phase>.max_retries` | Implemented | `gates.md`, `failures.md` |

**Note**: `<role>` in `{definer, builder, verifier}`. `<phase>` in `{survey, review_plan, groom, re_groom, implement, fix_qa, fix_merge, fix_regression, verify_issue, verify_pre_merge, verify_post_merge}`.

**Note**: `roles.<role>.default_thinking` is the fallback when a phase-specific `thinking` is not set.

## Heartbeat

| Key | Status | Used by |
|---|---|---|
| `heartbeat.interval_seconds` | Referenced | `slots.md` |
| `heartbeat.stale_minutes` | Implemented | `slots.md`, `recovery.md`, `preflight.md`, `recovery.ts` (`loadHeartbeatConfig`) |
| `heartbeat.force_release_multiplier` | Implemented | `slots.md`, `slot_manager.ts` (`checkHeartbeats`), `recovery.ts` (`loadHeartbeatConfig`) |

## Schema Validation

| Key | Status | Used by |
|---|---|---|
| `schema.strict` | Referenced | `config.yaml`; `schema_validator.ts` uses strict `additionalProperties` per schema |
| `schema.max_retries` | Implemented | `gates.md`, `schema_validator.ts` (`validateAndReport`) |
| `schema.validator_timeout_seconds` | **Reserved** | Not yet implemented (no timeout in `schema_validator.ts`) |

**Note**: `schema.strict` semantics: when `true`, handoff JSON with extra properties is rejected. This is enforced per-schema via `additionalProperties: false`, not via a global Ajv option.

**Note**: `schema.validator_timeout_seconds` is reserved. Future implementation should abort validation if it exceeds this duration.

## Merge

| Key | Status | Used by |
|---|---|---|
| `merge.dry_run` | Implemented | `merge.md` Step 3, `merge_orchestrator.ts` |
| `merge.full_suite_every` | Referenced | `merge.md` |
| `merge.fast_path_lines` | Implemented | `merge.md` |
| `merge.commit_message_max` | **Reserved** | Not yet implemented (no truncation in `merge_orchestrator.ts`) |
| `merge.transactional` | Implemented | `merge.md`, `merge_orchestrator.ts` |
| `merge.smoke_tests_min` | Referenced | `verify_pre_merge.md` |
| `merge.smoke_tests_max` | Referenced | `verify_pre_merge.md` |

**Note**: `merge.commit_message_max` is reserved. Future implementation should truncate commit messages exceeding this length.

## Git

| Key | Status | Used by |
|---|---|---|
| `git.push_retry` | Referenced | `implement.md` (3 times, matches default) |
| `git.push_backoff_seconds` | Referenced | `implement.md` (5/15/45, matches default) |
| `git.merge_fix_max_level` | Referenced | `failures.md` (Level 3 cascade limit) |
| `git.force_push_check` | Referenced | `role_boundaries.ts` (blocks force push) |
| `git.worktree_retry` | **Reserved** | Not yet implemented |
| `git.worktree_lock_backoff_seconds` | **Reserved** | Not yet implemented |
| `git.main_history_track` | **Reserved** | Not yet implemented |
| `git.require_gpg` | Referenced | `preflight.md` Stage 3 |
| `git.autocrlf_uniform` | Referenced | `preflight.md` Stage 3 |

## Memory

| Key | Status | Used by |
|---|---|---|
| `memory.read_max` | Implemented | `memory/readme.md`, `memory/rules.md` |
| `memory.promote_count` | Implemented | `memory/rules.md` |
| `memory.fail_delete_threshold` | Implemented | `memory/rules.md` |
| `memory.write_after_failures` | Implemented | `memory/rules.md` |
| `memory.pattern_threshold` | Referenced | `failures.md` |
| `memory.similarity_dedupe` | Implemented | `memory/readme.md`, `memory/rules.md` |
| `memory.max_size_kb` | Referenced | `memory/readme.md` |
| `memory.max_candidates` | Referenced | `memory/readme.md` |
| `memory.retention_days` | Referenced | `memory/readme.md`, `memory/rules.md` |
| `memory.verified_retention_days` | Referenced | `memory/rules.md` |

## Failure Patterns

| Key | Status | Used by |
|---|---|---|
| `failure_patterns.enabled` | Referenced | `failures.md` |
| `failure_patterns.similarity_threshold` | Referenced | `failures.md` |
| `failure_patterns.min_occurrences` | Implemented | `failures.md` |

## Contract-First

| Key | Status | Used by |
|---|---|---|
| `contract_first.enabled` | Referenced | `groom.md` |
| `contract_first.require_for` | Implemented | `groom.md` |
| `contract_first.allow_natural_for` | Implemented | `groom.md` |

## Output

| Key | Status | Used by |
|---|---|---|
| `output.externalize_lines` | Implemented | `_shared.md`, `implement.md` |
| `output.externalize_tokens` | Implemented | `_shared.md` |
| `output.request_max_lines` | Implemented | `_shared.md` |
| `output.diff_split_lines` | Referenced | `implement.md` |

## Logging

| Key | Status | Used by |
|---|---|---|
| `log.tail_lines` | Referenced | `logging.md` |
| `log.line_max_chars` | Referenced | `logging.md` |
| `log.rotation_time_utc` | Referenced | `logging.md` |
| `log.dual_format_daily` | Referenced | `logging.md` |
| `log.compress_after_days` | Referenced | `logging.md` |
| `log.monthly_after_days` | Referenced | `logging.md` |
| `log.quarterly_after_days` | Referenced | `logging.md` |
| `log.report_delay_hours` | Referenced | `logging.md` |
| `log.structured_wal` | Referenced | `logging.md` |

## Retention

| Key | Status | Used by |
|---|---|---|
| `retention.output_keep_days` | Referenced | `merge.md`, `logging.md` |
| `retention.output_archive_days` | Referenced | `merge.md`, `logging.md` |
| `retention.log_keep_days` | Referenced | `logging.md` |
| `retention.daily_log_days` | Referenced | `logging.md` |
| `retention.monthly_summary_days` | Referenced | `logging.md` |
| `retention.quarterly_archive_days` | Referenced | `logging.md` |
| `retention.config_history_keep` | Implemented | `preflight.md` Stage 0 Step 9 |
| `retention.approval_keep_days` | Referenced | `recovery.md` |
| `retention.merge_history_days` | Referenced | `logging.md` |
| `retention.failure_audit_days` | Referenced | `logging.md` |
| `retention.metrics_days` | Referenced | `logging.md` |
| `retention.status_metrics_days` | Referenced | `logging.md` |
| `retention.idempotency_days` | Referenced | `logging.md` |
| `retention.lint_cache_days` | Implemented | `verify_issue.md` Step 3 |

## Limits

| Key | Status | Used by |
|---|---|---|
| `limits.dep_chain_warn` | Referenced | `survey.md` |
| `limits.dep_chain_halt` | Referenced | `survey.md` |
| `limits.comments_keep` | Referenced | `logging.md` |
| `limits.history_max_lines` | Referenced | `logging.md` |
| `limits.pending_stale_days` | Referenced | `failures.md` |
| `limits.stale_block_days` | Referenced | `failures.md` |
| `limits.blocker_fatigue_count` | Referenced | `failures.md` |
| `limits.approval_delete_files` | Referenced | `gates.md` (approval detection) |
| `limits.approval_issue_count` | Referenced | `gates.md` (approval detection) |
| `limits.similarity_threshold` | Referenced | `failures.md` |
| `limits.ac_change_blocker_pct` | Implemented | `gates.md`, `human_review.md`, `lifecycle.md` |
| `limits.analysis_max_per_day` | Referenced | `failures.md` |
| `limits.issue_granularity.max_acs` | Implemented | `gates.md`, `review_plan.md` |
| `limits.issue_granularity.max_files` | Implemented | `gates.md`, `review_plan.md` |
| `limits.issue_granularity.max_diff_lines` | Referenced | `review_plan.md` |
| `limits.issue_granularity.warn_only` | **Reserved** | Not yet read by code |

## Priority

| Key | Status | Used by |
|---|---|---|
| `priority.human_override_max` | Referenced | `slots.md` |
| `priority.boost_value` | Referenced | `slots.md` |
| `priority.starvation_warn_hours` | Implemented | `slots.md`, `slot_manager.ts` |
| `priority.starvation_blocker_hours` | Implemented | `slots.md`, `slot_manager.ts` |

## Human Review

| Key | Status | Used by |
|---|---|---|
| `human_review.stale_days` | Implemented | `human_review.md` |
| `human_review.poll_interval_iterations` | **Reserved** | Not yet read by code |
| `human_review.auto_close_after_days` | Implemented | `human_review.md` |

## Approval

| Key | Status | Used by |
|---|---|---|
| `approval.mode` | Implemented | `preflight.md`, `recovery.md` |
| `approval.warn_hours` | Referenced | `recovery.md` |
| `approval.max_hours` | Referenced | `recovery.md` |
| `approval.pre_authorized` | **Reserved** | Not yet implemented |

## Automation

| Key | Status | Used by |
|---|---|---|
| `automation.auto_recovery.enabled` | Referenced | `failures.md` |
| `automation.auto_recovery.level` | Implemented | `failures.md` (Level 1-4 routing) |
| `automation.auto_recovery.max_consecutive_failures` | Referenced | `failures.md` |
| `automation.auto_skip_blocked` | Implemented | `failures.md` |
| `automation.auto_learn` | Referenced | `failures.md` |
| `automation.stall_detection.enabled` | Referenced | `failures.md` |
| `automation.stall_detection.iterations_threshold` | Implemented | `failures.md` |
| `automation.stall_detection.action` | **Reserved** | Not yet implemented (always `write_report`) |
| `automation.infinite_loop_detection.enabled` | Referenced | `failures.md` |
| `automation.infinite_loop_detection.max_same_failure` | Implemented | `failures.md` |

## Disk

| Key | Status | Used by |
|---|---|---|
| `disk.warn_mb` | Referenced | `logging.md` |
| `disk.halt_mb` | Referenced | `logging.md` |
| `disk.force_archive_mb` | Referenced | `logging.md` |
| `disk.archive_free_ratio` | Referenced | `logging.md` |

## API

| Key | Status | Used by |
|---|---|---|
| `api.page_size` | Referenced | `preflight.md`, `logging.md` |
| `api.cache_ttl_minutes` | Referenced | `logging.md` |
| `api.cache_force_on_error` | Referenced | `logging.md` |
| `api.confirm_retries` | Implemented | `preflight.md` Stage 5 (recovery) |
| `api.confirm_gap_seconds` | Implemented | `preflight.md` Stage 5 (recovery) |

## Status Summary

| Status | Count |
|---|---|
| **Implemented** | ~62 |
| **Referenced** | ~53 |
| **Reserved** | 8 |

### Reserved Keys (not yet implemented)

| Key | Reason |
|---|---|
| `orchestrator.context.refresh_files` | Lifecycle hardcodes the list |
| `schema.validator_timeout_seconds` | No timeout in `schema_validator.ts` |
| `merge.commit_message_max` | No truncation in `merge_orchestrator.ts` |
| `git.worktree_retry` | Worktree retry not implemented |
| `git.worktree_lock_backoff_seconds` | Worktree lock backoff not implemented |
| `git.main_history_track` | Main history tracking not implemented |
| `limits.issue_granularity.warn_only` | Granularity checks not yet enforced |
| `human_review.poll_interval_iterations` | Polling not yet implemented |
| `approval.pre_authorized` | Pre-authorization not yet implemented |
| `automation.stall_detection.action` | Only `write_report` implemented |

**Note**: Reserved keys are tracked for future implementation. When implementing, update both this file and the relevant skill/code.