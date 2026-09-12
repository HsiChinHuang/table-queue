# Failures

Unified failure taxonomy, routing, and recovery.
Replaces scattered failure logic across files.

## 1. Failure taxonomy

### 1.1 Three layers

| Layer | Values |
|---|---|
| Source | SW, PM, QA, Subagent, Orchestrator, Environment |
| Type | see tables below |
| Severity | Retry, Escalate, Blocker |

### 1.2 Issue-level failure_type

| Type | Source | Severity | Action |
|---|---|---|---|
| `implementation` | QA | Retry | SW |
| `ac_ambiguous` | QA | Escalate | PM |
| `ac_wrong` | QA | Escalate | PM |
| `test_env` | QA | Retry | SW + env note |
| `test_quality` | QA | Retry | SW |
| `merge_conflict` | Orchestrator | Escalate | MERGE-FIX |

Priority (when multiple match):
1. merge_conflict
2. ac_wrong
3. ac_ambiguous
4. test_env
5. test_quality
6. implementation (default)

QA MUST pick ONE. If unsure: implementation.

### 1.3 Subagent-level failure (subtype)

| Subtype | Detection | Retry | Backoff | Escalate |
|---|---|---|---|---|
| `timeout` | > `[timeouts.qa_minutes]` + 5 min | 3 | immediate | BLOCKER |
| `crash` | API 5xx | 5 | 1/2/4/8/16s (+ jitter) | BLOCKER |
| `format_error` | missing `reached_state` | 3 | immediate + hint | BLOCKER |
| `empty_output` | no comment | 3 | immediate | BLOCKER |
| `refused` | refusal pattern | 0 | -- | BLOCKER + needs-human |

Counters: `state/retry-subagent.json`.

## 2. Counters and limits

### 2.1 Issue-level (retry.json)

| Counter | Limit | On exceed |
|---|---|---|
| `sw` (total) | `[sw_retry.per_issue]` | BLOCKER |
| `sw_round` | `[sw_retry.per_round]` | escalate or BLOCKER |
| `pm` (total) | `[pm_retry.per_issue]` | BLOCKER |
| `pm_round` | same as `pm` | -- |

Escalation:
- `sw_round` >= limit:
  - If any `ac_*` failure in round: escalate to PM.
  - Else: BLOCKER.
- `sw` >= limit: BLOCKER.
- `pm` >= limit: BLOCKER.

### 2.2 Subagent-level

Per type per issue: see 1.3.

### 2.3 Global (optional)

- Total retries > [limits.total_retry_warn] across project: log `[HIGH_RETRY_PROJECT]`.
- Not BLOCKER. Signal for human review.

## 3. Routing

### 3.1 On QA FAIL

1. Read `failure_type` from QA comment.
2. Increment issue counters.
3. Route:
   - `implementation` → SW (same round).
   - `ac_ambiguous` → PM.
   - `ac_wrong` → PM.
   - `test_env` → SW + env note.
   - `test_quality` → SW.
   - `merge_conflict` → MERGE-FIX flow.
4. Check limits. BLOCKER if hit.
5. Spawn appropriate role.

### 3.2 On Subagent failure

1. Classify subtype.
2. Increment subagent counter.
3. Retry per type limits.
4. If limit hit: BLOCKER.

## 4. Retry backoff

| Type | Backoff |
|---|---|
| Issue-level (QA FAIL) | none (semantic) |
| Subagent timeout | immediate |
| Subagent crash | 1/2/4/8/16s (+ jitter ±30%) |
| Subagent format_error | immediate |
| Subagent empty | immediate |
| Subagent refused | no retry |
| API rate limit | Retry-After header (max 300s) |

## 5. Failure history

### 5.1 Retention

- Per issue: `_docs/issues/<ID>-history.md`.
- Platform comments: kept up to `[limits.comments_keep]`.
- Archived beyond that.
- On close: history moves to `issues/closed/`.

### 5.2 Passed to SW on retry

- Last 3 FAIL summaries (max 2 lines each).
- Latest full FAIL comment.

## 6. Recovery (idempotent)

### 6.1 Idempotency boundary

Idempotent (safe retry):
- Reads.
- Local writes with atomic mv.
- Git commits.
- API reads.

Non-idempotent (guard):
- Issue creation: idempotency key `<issue>-<role>-create`.
- Branch push: check remote first.
- Comment: dedupe by content hash.

Guard pattern:
1. Check if done.
2. Perform with key.
3. Log `[IDEMPOTENT_OK]`.
4. On duplicate: `[DEDUPED]`.

### 6.2 WAL-snapshot mismatch

Recovery precedence:
1. Platform state (issue state: open/closed).
2. Platform comments (contain `reached_state`?).
3. Log lines (transitions).
4. Snapshot (slots/queue).

Per-issue reconciliation:
- Platform comment has `reached_state`:
  - Treat as completed transition.
  - Append log `[RECOVERED_FROM_PLATFORM]`.
- Platform comment exists but no `reached_state`:
  - Partial write. Re-spawn role.
- Platform state changed but no comment:
  - Log anomaly, trust platform.
- Log has transition, snapshot lacks:
  - Replay transition (idempotent).
- Snapshot has, log lacks:
  - Log anomaly, trust snapshot.

Never assume completion without `reached_state`.

### 6.3 Recovery loop

- Counter: `state/recovery-attempts.json`.
- [limits.recovery_attempt_threshold] attempts without OK: BLOCKER + pause auto-recovery.
- Human clears via `[RECOVERY_OK]`. Counter reset.

### 6.4 Recovery slot semantics

- On boot: slots empty.
- After recovery: repopulate from platform state.
- In-flight issues: re-spawn per snapshot.
- Respect `[slots.max]`.

## 7. Failure propagation

- Issue in retry: dependents stay blocked.
- Issue in BLOCKER: dependents blocked + comment `[UPSTREAM_BLOCKER] <T5>`.
- Upstream resolved: dependents re-eligible.

## 8. Partial success

- SW restarts fresh.
- Prior work preserved in worktree.
- SW reads FAIL history + git log.
- SW decides continue or rebuild.
- Not Orchestrator's decision.

## 9. Failure correlation

- Same failure_type + overlapping files + similar output: log `[CORRELATED_FAILURES]`.
- Do NOT merge retries.
- Flag for human.

## 10. Concurrent failures

- Independent counters.
- [limits.concurrent_failure_threshold]+ within [limits.correlation_window_minutes] min: log `[CONCURRENT_FAILURES]`.
- Root cause investigation: API outage, shared dep, config.

## 11. Failure patterns (learning)

- [limits.failure_pattern_threshold]+ same failure_type per issue: log `[FAILURE_PATTERN]`.
- Trigger: L3 analysis + memory candidate.
- Not blocking.

## 12. Similar failures (fuzzy)

- Cosine similarity of QA Summary lines.
- [limits.similar_failures_threshold]+ > [limits.similarity_threshold]: log `[SIMILAR_FAILURES]`.
- L3 analysis + memory candidate.

## 13. Oscillation

- Track last 5 failure_types per issue.
- Pattern ABAB: log `[OSCILLATION]`.
- [limits.oscillation_alternations] alternations: BLOCKER + L3 analysis.

## 14. QA misjudgment

- SW cannot reproduce QA's failure:
  - Post `[QA_MISJUDGMENT] <reason>`.
- Orchestrator: route to PM for third-party check.
- PM independent verification:
  - Comment: `Third-party check: QA correct | QA false positive | unclear`.
  - PM does NOT modify labels.

- Orchestrator action based on PM result:
  - `QA correct`: route back to SW with PM finding.
  - `QA false positive`:
    - Create BLOCKER `[QA_FALSE_POSITIVE]`.
    - Await human `[OVERRIDE_QA_PASS]`.
    - On human approval: force `qa-passed`, enqueue merge.
    - **Not auto-resolved**.
  - `unclear`: BLOCKER `[QA_UNRESOLVED]`.

- Counter: `state/metrics/misjudgments.json`.
  - Every `[QA_MISJUDGMENT]` → PM check.
  - 2 misjudgments on same issue: L3 analysis.
  - 3 misjudgments on same issue: BLOCKER.

## 15. Impossible AC

- SW posts `[AC_IMPOSSIBLE] <reason>`.
- Route to PM.
- PM: rewrite AC OR mark won't-fix.
- If won't-fix: close as `closed` with note.
- If PM disagrees: BLOCKER.

## 16. Upstream failure discovered

- SW identifies upstream issue as root cause:
  - Post `[UPSTREAM_BUG] <T2>`.
- Stop current issue retry.
- Orchestrator creates `FIX: <T2>`, label `blocker`.
- Assign to T2's original SW.
- Flow: PM (light) → SW → QA.
- If upstream bug requires branch fix:
  - See `orchestrator-git.md` Sec. 3.5, Sec. 5 (MERGE-FIX flow).

## 17. Shared code changes

- SW modifies file: Orchestrator records file → issue mapping.
- On issue PASS: check overlap with active issues.
- If overlap: comment `[SHARED_FILE_CHANGED] <file>`.
- Affected: re-verify on next QA.
- No auto-invalidate.

## 18. Human override

### 18.1 QA override
- Human comments `[OVERRIDE_QA_PASS] <reason>`.
- Force `qa-passed`. Log `[HUMAN_OVERRIDE]`.

### 18.2 Skip step
- Human comments `[SKIP_PM] <reason>`.
- Force `groomed`. Log `[HUMAN_SKIP]`.
- Not allowed for SW, QA.

## 19. Structural failures

### 19.1 Process anomaly
- PASS rate < [limits.process_anomaly_pct]% over last [limits.process_anomaly_window] attempts in any stage:
  - Log `[PROCESS_ANOMALY] <stage>`.
  - BLOCKER.

### 19.2 Plan quality
- > [limits.plan_quality_threshold] `ac_wrong` for same plan section:
  - Log `[PLAN_QUALITY] <section>`.
  - BLOCKER.

### 19.3 Config suspect
- [limits.config_suspect_threshold]+ consecutive format_errors across unrelated issues:
  - Log `[CONFIG_SUSPECT]`.
  - Pause spawns. BLOCKER.

## 20. BLOCKER management

See `orchestrator-human.md` Sec. 4.

Summary:
- Idempotency key: `<issue>-blocker`.
- Retry `[limits.blocker_create_retry]` times.
- Resolve via `[RESOLVED]` marker.
- Aggregation at `[limits.blocker_fatigue_count]` in 24h.
- Priority: RESET > PAUSE > BLOCKER.

## 21. Failure audit

- After project complete: `log/failure-audit.md`.
- Contents:
  - Top 10 issues by retry count.
  - Failure type distribution.
  - Mean retries to PASS.
  - BLOCKER count.
  - Time in retry vs implement.

## 22. Export

- Command: `orchestrator export-failures`.
- Output: `log/failures-export-<ts>.json`.
- Contents: retry counts, types, subagent history.

## 23. STATUS.md failure section

    ## Failure hotspots
    - Top 3 issues by retries: ...
    ## Recent BLOCKERs
    - T12: 2h ago (QA refused)
    - T13: 5h ago (API unstable)

## 24. Failure handling priority

1. Structural (process, plan, config): human.
2. Oscillation: L3.
3. Budget exceeded: review.
4. Individual: per routing.

## 25. Meta-failures

### 25.1 Transition atomicity
- WAL = "attempted", snapshot = "confirmed".
- Mismatch: replay (idempotent).

### 25.2 Recovery failure modes
- Counter: [limits.recovery_attempt_threshold] attempts without OK: BLOCKER.
- Human clears via `[RECOVERY_OK]`.

## 26. Time semantics

- Counters: integers, no time logic.
- Starvation: UTC timestamps.
- Tolerance: ±60s.
- Subagent backoff: local monotonic.
- Retry counters: no time-based decay.

## 27. Long-stale

- Blocked > [limits.stale_block_days] days: log `[STALE_BLOCK]`.
- If upstream BLOCKER > 7 days: escalate.
- No auto-close.

## 28. Stale dependency

- Waited > [limits.long_wait_ready_hours]h on dependency: on ready, force fresh QA.
- Even if prior QA PASS.

## 29. Orchestrator tool failures

- All git ops: retry [git.push_retry]x with backoff.
- Details: `orchestrator-git.md` Sec. 2.5 (worktree lock), Sec. 3.2 (push), Sec. 4.11 (concurrent).
- Critical (merge, fetch, push): BLOCKER.
- Non-critical (status, ls-remote): log + continue.

## 30. Log write

See `orchestrator-logging.md` Sec. 1-3.

Summary:
- Single-threaded Orchestrator.
- All logs via Orchestrator.
- O_APPEND mode.
- Partial write: skip last malformed line on recovery.
- Redaction before write.
- Disk full: emergency archive + BLOCKER.