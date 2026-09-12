# SA · DAG & Plan Quality

Detailed spec for SA's plan generation and DAG construction.
Referenced from `sa.md`.
Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## 1. Plan generation quality

### 1.1 P1 quality checks

After generating `plan.md`, before P2:

| Check | Rule | On fail |
|---|---|---|
| Block fields | Every block has Title, Acceptance, Files, Depends | HALT |
| Cycle | No cycle in Depends | HALT |
| Reference | All T-IDs exist | HALT |
| AC checkable | No vague words: "robust", "good", "nice", "proper" | WARN |
| AC structure | ≥ 1 verb + object | WARN |
| Tech-stack match | plan.md header == requirements.md | HALT |

On failure: log `[P1_QUALITY_FAIL] <check> <detail>`, list issues, HALT.

### 1.2 Language policy

- `requirements.md`: user's language (any).
- `plan.md`: English (`[sa.output_language]`).
- `issues/*.md`: English.
- Comments: English.
- SA translates on P1.
- Detect non-English in plan: warn.

### 1.3 Non-functional requirements (NFR)

Scan `requirements.md` for:
- Performance (latency, throughput).
- Security (auth, encryption).
- Accessibility (WCAG).
- Compliance (GDPR, HIPAA).

On detection:
- Add to `plan.md` header as global constraints.
- Applies to ALL issues.
- Log `[NFR_DETECTED] <list>`.
- Not mapped to specific issues.

### 1.4 Traceability

Plan block format extended:

    > Issue template:
    > - Requirement: <requirements.md anchor>
    > - Title: ...
    > - Acceptance: ...
    > - Files: ...
    > - Depends: ...

Rules:
- SA must set `Requirement` field.
- Missing: log `[NO_TRACEABILITY]`, warn.
- If `[plan.traceability_required]`: missing → HALT.
- Anchor format: `#section-name` matching requirements.md headers.

### 1.5 Depends semantics

- Default: **AND** (all listed must complete).
- OR semantics: not supported.
- Mixed: human creates separate issues.
- Document in `plan.md` header:
  `# Depends = all listed must complete (AND)`.

## 2. Plan and requirements update

### 2.1 Config snapshot during SA

- SA reads config at start (from `CONFIG_SNAPSHOT.json`).
- Config changes during SA: NOT applied until restart.
- SA uses snapshot, never re-reads.
- Log `[SA_CONFIG_SNAPSHOT] <ts>`.

### 2.2 Plan modified by human

On SA boot:
- Compute plan.md hash.
- If differs from `state/plan-hash.txt`:
  - Log `[PLAN_MODIFIED]`.
  - Do NOT auto-regenerate issues.
  - New blocks: human creates pending.
  - Modified blocks: human updates issues.
  - Deleted blocks: human marks issues `[OBSOLETE]`.

### 2.3 Requirements modified by human

On SA boot:
- Compute requirements.md hash.
- If differs:
  - Log `[REQ_MODIFIED]`.
  - Do NOT auto-regenerate plan.
  - Human decides: RESET flow or manual update.

### 2.4 Plan versioning

- `plan.md` committed to Git.
- Each regeneration: new commit.
- SA logs `[PLAN_GENERATED] <hash>`.
- Human uses `git log plan.md`.
- No internal versioning.

### 2.5 P1 lint report

Output: `state/plan-lint.md`.

Format:
    ## Errors
    - <description>
    ## Warnings
    - <description>

Errors block P2. Warnings log and proceed.

### 2.6 SA decision log

Output: `state/sa-decisions.md`.

Format: `[<phase>] <decision> | <rationale>`

Example:
    [P2c] Detected cycle T5 → T7 → T5 | HALT
    [P2e] File conflict: utils.py (T5, T7) | Serialized T7 after T5
    [P2f] Wrote 15 issues | OK

Human reviews.

## 3. DAG construction

### 3.1 Build

After P2c (block extraction):
1. Nodes = all issues (by ID).
2. Edges = from `depends:`.
3. Detect cycles (see 3.5).
4. Topological sort.
5. Identify critical path.
6. Mark critical path issues: `critical: true`.

### 3.2 Critical path

- Longest path from any root to any leaf.
- Marks used by slot priority (`orchestrator-slots.md`).
- Recompute on DAG change.

### 3.3 Persistence

Cache: `state/dag.json`.

    {
      "nodes": ["T0", "T1", ...],
      "edges": [["T0", "T1"], ...],
      "critical_path": ["T0", "T5", "T12"],
      "hash": "sha256:...",
      "computed_at": "..."
    }

Invalidate on: any `issues/*.md` change.
Rebuild: on boot + on change.
Config: `[dag.cache]`.

### 3.4 Incremental update

Trigger: single issue state change (open→closed).

Algorithm:
1. Mark closed issue's node.
2. For each out-edge: mark target "unblocked".
3. Recompute critical path (may change).
4. Recompute parallelism if needed.
5. Update `backlog.md`.
Complexity: O(degree), not O(n).

Config: `[dag.incremental]`.

### 3.5 Cycle detection

Run on:
- P2 (initial).
- Pending new issue addition.
- Dependency changes.
- Manual `[DAG_CHECK]` marker.

Algorithm: DFS with white/gray/black coloring.
On cycle: HALT, output cycle path.
Config: `[dag.cycle_detection_on_change]`.

### 3.6 Orphan detection

- Node with no in-edges and no out-edges: orphan.
- Exception: T0 is intentionally root.
- Others: log `[ORPHAN_NODE] <ID>`.
- Warn, not HALT.
- Human may need to add dependency.

### 3.7 Parallelism analysis (optional)

Compute maximum antichain size (Dilworth).
Result: theoretical max parallel slots needed.
If > `[slots.max]`: note in plan.md comment.
Not blocking.

### 3.8 Visualization

Mermaid export to `state/dag.mmd`:

    graph TD
      T0 --> T1
      T0 --> T2
      T1 --> T3
      ...

Generated on:
- P2 complete.
- DAG change.
- Human `[DAG_EXPORT]` marker.

ASCII fallback: `state/dag.txt`.
Limit: 100 issues for ASCII.

## 4. Depth analysis

### 4.1 Depth computation

- Depth = longest path from any root to any leaf.
- Computed after DAG construction.
- Warn if > `[dag.max_depth_warn]` (default 10).
- HALT if > `[dag.max_depth_halt]` (default 20) unless `[DEEP_CHAIN_OK]`.

### 4.2 Deep chain report

Written to `plan.md` comment:
- Longest chain: T0 → T5 → T12 → ... → T98 (depth 15).
- Critical path length.
- Suggested parallelization:
  - Which Depends edges to weaken.
  - Which issues to split.
- Config: `[dag.max_depth_warn]`, `[dag.max_depth_halt]`.

## 5. File ownership conflict

### 5.1 Detection

Scan issues' `Files` field:
- Build map: file → [issue_ids].
- For 2+ issues sharing files, no dependency between them:
  - Add serial: later issue's `depends += earlier issue`.
  - Order: topological position in plan.md (earlier wins).
  - Tie-break: smaller local ID.

### 5.2 Re-validation

After adding serial deps:
- Re-run cycle detection.
- If cycle introduced: HALT.

### 5.3 Log

Log conflicts to `plan.md` warning section.
Format: `[FILE_CONFLICT] <file> <issue_a> <issue_b> → serialized`.

### 5.4 Hub file detection

After all issues written:
- For each file with ≥ `[dag.hub_file_threshold]` issues:
  - Log `[HUB_FILE] <file> <n>`.

### 5.5 Hub mitigation

Option 1: Force serial (default).
- Pick "earliest" issue by dependency.
- Add serial dependency to others.
- Ensure no cycles.

Option 2: Split file (preferred).
- Create sub-issues for each section.
- SA generates proposal in plan.md comment.
- Human approves or modifies.
- Split into ceil(N/3) sub-issues.

Option 3: Allow parallel.
- Requires `[HUB_PARALLEL_OK]` in plan.md.
- Expect 30-50% MERGE-FIX rate.
- Log `[HUB_PARALLEL_RISK]`.

Default: option 1.
If ≥ `[dag.hub_file_human_escalate]` issues on same file: escalate.

### 5.6 Hub re-detection

Triggers:
- Initial: on P2 (full scan).
- Incremental: on each pending processing (scan only new issue's Files).
- Periodic: every `[dag.hub_scan_interval_hours]` hours (full scan).

Lock: `state/hub-scan.lock` prevents concurrent scans.

On detection:
- Log `[HUB_FILE] <file> <n>`.
- If n >= `[dag.hub_file_human_escalate]`: escalate to human.
- Else: apply mitigation (serial by default).

Incremental algorithm:
1. Read new issue's Files.
2. For each file: increment count.
3. If crosses threshold: log + mitigate.
4. Does NOT rescan all issues.

Periodic algorithm:
1. Acquire lock.
2. Full scan all issues' Files.
3. Recompute all counts.
4. Log changes.
5. Release lock.

## 6. Batch processing

### 6.1 P3 batching

Create issues in batches of `[sa.batch_size]` (default 50).

Between batches:
- Sleep `[sa.batch_delay_seconds]` (default 5).
- Rate limit: `[sa.rate_limit_per_second]` req/s.

### 6.2 Rate limiting

429 response: backoff 1/2/4/8/16s, max 6 retries.
Persistent 429: HALT, save progress.
Resume: from last created.
Log `[RATE_LIMIT_P3]`.

### 6.3 Partial failure (P3)

Track created IDs in memory.
On resume:
- Skip created, continue next.
- Log `[SA_P3_RESUME] from <last>`.

Idempotency key: `<issue>-create`.
On duplicate: `[DEDUPED]`.

## 7. Recovery

### 7.1 Progress file

`state/sa-progress.json`:

    {
      "phase": "P2",
      "sub_step": "P2d",
      "last_id": "T10",
      "block_hash": "...",
      "timestamp": "..."
    }

### 7.2 P2 partial recovery

Detect: count files vs plan blocks.
If mismatch:
1. Read plan.md blocks.
2. Read existing `issues/*.md`.
3. Missing: generate.
4. Extra: log `[ORPHAN_ISSUE]`, do NOT delete.
5. Resume from P2e (validation).

### 7.3 P3 partial recovery

Detect: count local issues vs platform issues by title.

Reconciliation:
1. For each local issue:
   - Query platform by title.
   - If exists: update `issue-map.json`.
   - If not: create.
2. Orphan platform issues: log `[PLATFORM_ORPHAN]`, human decides.

### 7.4 SA-Orchestrator coordination

- SA runs as a subagent (not a slot).
- Orchestrator waits for SA completion before Lifecycle.
- During SA: no other subagents spawned.
- Reason: issues not yet finalized.
- SA timeout: `[sa.max_minutes]` (default 60).
- On timeout: log `[SA_TIMEOUT]`, HALT.

### 7.5 Dry-run mode

Env: `SA_DRY_RUN=true`.
- P1: generate plan.md.
- P2: generate issues/*.md.
- P2b: generate backlog.md.
- P3: SKIP platform creation.
Human reviews, removes flag, re-runs.
Config: `[sa.dry_run]`.

### 7.6 Multiple requirements files

Config: `[sa.requirements_files]: [req1.md, req2.md]`.
SA reads all, merges.
Order: sorted by filename.
Conflicts: log `[REQ_CONFLICT]`, HALT.
Default: `[_docs/requirements.md]`.