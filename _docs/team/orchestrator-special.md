# Special Mechanisms

Unified spec for four cross-cutting mechanisms:
1. AC SUGGESTION
2. CONSTRAINT VIOLATION REQUEST
3. Memory system
4. Comment archiving
5. Pending issues

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.
Routing overlaps: see `orchestrator-failures.md`.

## 1. AC SUGGESTION

### 1.1 Trigger

SW detects during implementation:
- AC wrong / impossible / unclear.
- AC contradicts plan.md.

SW posts: `[AC SUGGESTION] <id>: <text>` (one per line if multiple).

### 1.2 SW behavior

- Non-blocking by default.
- Continue other ACs.
- If ALL ACs affected: wait for PM.
- Never modify AC directly.

### 1.3 Orchestrator handling

On detection:
1. Hash suggestion text (`sha256`).
2. Dedupe: compare to last 5 suggestions per issue.
   - Duplicate: log `[DUPLICATE_SUGGESTION]`, skip.
3. Batch multiple suggestions in one comment.
4. Insert PM task: re-groom with suggestion.
5. Track age: if > `[timeouts.suggestion_pm_wait_hours]`: log `[SUGGESTION_STALE]`.
6. If > `[timeouts.suggestion_timeout_hours]`: BLOCKER `[SUGGESTION_TIMEOUT]`.

Race with QA FAIL:
- QA FAIL takes priority.
- Suggestion handled next grooming round.
- Log `[SUGGESTION_QA_RACE]`.

### 1.4 PM decision

Read suggestion. Compare to current AC.
If suggestion references stale AC text:
- Comment `[STALE_SUGGESTION]`.
- SW re-reads AC.
- Not counted as failure.

Decide: accept / reject / modify.

Response format (multi-suggestion):

[SUGGESTION RESPONSE]

- <id1>: accepted
- <id2>: rejected: <reason>
- <id3>: modify: <alt>

### 1.5 Materiality

On accept:
- Compute AC diff ratio.
- If ratio >= `[ac.materiality_threshold_pct]`%:
  - Invalidate SW partial work.
  - Reset SW to start (branch preserved).
  - Restart SW session.
- Else:
  - SW continues.
  - Adjust as needed.

### 1.6 Downstream impact

On material change:
1. Scan dependents (direct + transitive).
2. Comment `[UPSTREAM_AC_CHANGED] <T5>` on each.
3. Do NOT auto-invalidate their ACs.
4. Log `[DOWNSTREAM_IMPACT] <list>`.
5. Human decides downstream re-groom.

### 1.7 Failure metrics

Track (optional):
- suggestions proposed / accepted / rejected.
- Aggregate to `state/metrics/suggestions.json`.
- Human reviews.

## 2. CONSTRAINT VIOLATION REQUEST

### 2.1 Trigger

SW detects need to modify files outside Constraints.
SW posts: `[CONSTRAINT VIOLATION REQUEST] <files> <reason>`.
- Batch: one line per file.

### 2.2 SW behavior

- Do NOT modify out-of-scope files.
- Continue in-scope work.
- Wait for PM approval.

### 2.3 Orchestrator handling

On detection:
1. Check file ownership against active issues' Constraints.
2. If file owned by another issue:
   - Log `[OWNERSHIP_CONFLICT] <file> <other_issue>`.
   - Escalate to BLOCKER unless both PMs agree.
3. Insert PM task (with ownership context).

### 2.4 PM decision

Per-file decision allowed:
- Accept: <file1>, <file2>
- Reject: <file3>: <reason>

On accept:
- Update Constraints (local + platform).

On reject:
- Comment reason.
- SW complies.

### 2.5 Post-facto modification

If git status shows out-of-scope changes:
- If request posted: PM decides keep/revert.
- If no request: `[SCOPE_VIOLATION]`, BLOCKER.
- Auto-revert only if PM rejects AND SW confirms.

## 3. Memory system

### 3.1 Write

Trigger: SW retry > `[memory.write_after_retries]`.
Additional: 3+ same failure_type (`[memory.pattern_threshold]`).

Action: SW writes to `_docs/memory/candidates/<uuid>.md`.

Deduplication:
- Compute similarity to existing memories.
- If > `[memory.similarity_dedupe]`: update existing (append source_issue).
- Else: create new.

Size limit: single memory ≤ `[memory.max_size_kb]` KB.
If exceeded: reject, SW splits.

Candidates total cap: `[memory.max_candidates]` files.
If exceeded: block new writes, alert human.

Recommendation (optional):
- On write, Orchestrator computes similarity to existing.
- If > 0.7: alert SW "Related: <uuid>".
- SW decides: dedupe or proceed.

### 3.2 Read

Trigger: SW retry >= 2.

**Layer 1: Orchestrator pre-check (before passing to SW)**:
- Match memories by issue tags.
- Select up to `[memory.read_max]` files.
- Deduplicate (similarity `[memory.similarity_dedupe]`).
- Check `memory/conflicts/` history:
  - Skip known conflicting pairs.
- Pass paths to SW.

**Layer 2: SW conflict check (after reading, before implementing)**:
- Cross-check passed memories for contradictions.
- If found: post `[MEMORY CONFLICT]`, skip conflicting ones.
- Continue implementation.

**Conflict history**:
- Store resolved conflicts: `memory/conflicts/<pair>.md`.
- Format:

      source_a: <uuid>
      source_b: <uuid>
      resolved_by: human
      resolution: <how>
      applies_to: <scope>

- Future reads skip known conflicts.
- Log `[MEMORY_CONFLICT_KNOWN]` if skipped.

Empty match:
- SW proceeds without.
- Log `[NO_MEMORY]`.
- Not a failure.

### 3.3 Promote

- Applied + QA PASS: `verified_count += 1`.
- When `verified_count >= [memory.promote_count]`: move to verified/.

Distinct issues required: 2 (not same twice).
No `[FAILED USE]` in last 3 uses.

On promote: log `[MEMORY_PROMOTED] <uuid>`.

### 3.4 Demote

- Applied + QA FAIL: `verified_count -= 1`, mark `[FAILED USE]`.
- `[memory.fail_delete_threshold]` consecutive fails: delete.

### 3.5 Conflict

- SW posts `[MEMORY CONFLICT]`.
- Orchestrator creates BLOCKER.
- Human merges manually.
- Orchestrator does NOT auto-merge.

### 3.6 Scope

- `project`: this repo only.
- `language`: any repo using this language.
- `universal`: any repo.

SW reads by scope match.

### 3.7 Expiry

- `expires_hint` checked by SW on read.
- Mismatch: mark `[STALE]`, skip.
- Orchestrator on boot: scan for `[STALE]` markers.
- If 5+ stale: alert human.

### 3.8 Human override

- Human edits directly.
- `human_override: true` disables auto promote/demote/delete.

### 3.9 Usage audit

In memory file, `Verification` section:
- `source_issue`: original.
- `applied_by`: [T42, T55, T78].
- `failed_by`: [T99].

Updated by Orchestrator on QA verdict.

### 3.10 Retention

- Candidates: `[memory.retention_days]` days unused → archive.
- Verified: `[memory.verified_retention_days]` days unused → archive.
- Archive: `_docs/memory/archive/`.
- Never auto-delete.
- Human review monthly.

### 3.11 Index maintenance

`_docs/memory/index.md` updated by Orchestrator (no LLM):
- New candidate: add row.
- Promote: move row.
- Delete: remove row.

Format:

    | Topic | Scope | Tags | Verified | Confidence |

On crash mid-update: rebuild on next boot from files.

## 4. Comment archiving

### 4.1 Trigger

On writing new comment to platform:
- If count > `[limits.comments_keep]`: archive oldest.

### 4.2 Atomic order

1. Write to `_docs/issues/<ID>-history.md`:
   `[SEQ:<n>] [<UTC_TS>] [<author>] <content>`.
2. Verify write succeeded.
3. Then delete from platform.
4. If delete fails: retry 3x, then BLOCKER.

Crash between 1 and 2: history has, platform has.
Recovery: dedupe by seq, delete platform duplicate.

### 4.3 Attachments

- Move to `_docs/issues/<ID>-attachments/`.
- history records relative path.

### 4.4 References

- Never reference by platform comment ID.
- Content-based references only.

### 4.5 Read-back

- Post `[REQUEST_OUTPUT] <history.md> <line-range>`.
- Max `[output.request_max_lines]` lines per request.

### 4.6 Growth control

- history.md: append-only.
- If > `[limits.history_max_lines]` lines:
  - Split: `<ID>-history-1.md`, `<ID>-history-2.md`.
  - index.md tracks split.
- Oldest archived to `issues/closed/<ID>-history/`.

### 4.7 Dual format

- `history.md`: machine format (seq-based).
- `history-human.md`: markdown-formatted, by date.
- Auto-generated on archive.

### 4.8 Summary

- Per batch: `[SUMMARY] <n> comments archived at <ts>`.
- Helps human navigate.

### 4.9 Partial failure

- Write history: success.
- Delete platform: fail (network).
- Log `[ARCHIVE_PARTIAL]`.
- Retry on next loop.
- Persist > 1h: BLOCKER.

Log retention and archiving: `orchestrator-logging.md` Sec. 4.

## 5. Pending issues

### 5.1 Who writes

- SW discovers need during implementation.
- Human via `[NEW_REQUIREMENT]` marker.
- PM via Out of scope → follow-up.

### 5.2 Format

`_docs/issues/pending/<uuid>.md`:

title: <title>
acceptance: <acceptance>
files: <files>
depends: [T42]
reason: <reason>
priority: high | normal | low # optional, default normal

### 5.3 Processing

Orchestrator scans (Stage 6 + each loop):
1. Validate format.
2. Validate `depends` refs (must exist).
3. Check title for duplicates.
4. Assign new ID: `T<max+1>`.
5. Move to `issues/T<new>.md`.
6. Update frontmatter (add id, platform_issue).
7. Create platform issue.
8. Update `backlog.md`, `issue-map.json`.
9. Remove from `pending/`.

### 5.4 DAG update

- New issue added to DAG.
- Recompute topological order.
- Update `backlog.md` entirely.
- Dependents of new issue stay blocked longer.
- Dependencies of new issue must be merged first.

### 5.5 Collision handling

- ID exists: re-assign to max+1.
- Title duplicate: log `[DUPLICATE_TITLE]`, delete pending.
- Bad ref (unknown depends ID): log `[PENDING_BAD_REF]`, keep file, human fixes.
- Invalid format: log `[PENDING_INVALID]`, keep, human fixes.

### 5.6 SA interaction

- SA ignores `pending/`.
- Orchestrator handles after SA completes (Stage 6).
- During SA: pending waits. Log `[PENDING_QUEUED]`.

### 5.7 Priority

- `high`: prioritized in slot assignment.
- `normal`: default.
- `low`: deprioritized.

### 5.8 Staleness

- Pending older than `[limits.pending_stale_days]`: log `[PENDING_STALE]`.
- 2x: BLOCKER.
- Human reviews.