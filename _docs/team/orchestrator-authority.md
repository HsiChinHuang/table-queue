# Authority & Consistency

Defines which source is authoritative for each data layer.

## Authority layers

| Layer | Data | Authoritative source |
|---|---|---|
| State | open/closed, labels | Platform |
| Content | AC, Constraints | Platform (local mirrors) |
| Dependency | `depends:` | Local `issues/<ID>.md` |
| Mapping | local ID ↔ platform number | Local `issue-map.json` |
| Comments | discussion | Both (union) |

When two sources disagree, resolve per layer above.

## Mirror rules

| Local file | Mirrors | Sync direction |
|---|---|---|
| `issues/<ID>.md` AC + Constraints | Platform body | Platform → local |
| `backlog.md` | Platform issue list | Platform → local |
| `issue-map.json` | (no mirror; mapping) | Local-only |

Platform Issue body is a mirror of local `issues/<ID>.md` content,
NOT the other way for dependencies.

## Drift detection

Run timing:
1. Before each subagent spawn (per-issue).
2. Every Lifecycle loop iteration (all active issues).

Detection procedure:
1. Query Platform issue (GET).
2. Read local `issues/<ID>.md`.
3. Compare per layer:
   - State labels: exact set match.
   - AC section: hash match.
   - Constraints section: hash match.
   - State (open/closed): match.

On drift:
- Log `[DRIFT] <ID> <layer> <platform_value> <local_value>`.
- Overwrite local from Platform (for State + Content).
- Never overwrite local depends from Platform.

## Drift severity

| Condition | Action |
|---|---|
| Label difference | Auto-sync local. No BLOCKER. |
| State (open/closed) difference | Follow Platform. |
| AC hash differs, change < [limits.ac_change_blocker_pct]% | Auto-sync local. Log. |
| AC hash differs, change ≥ [limits.ac_change_blocker_pct]% | BLOCKER + needs-human. |
| Local file missing, platform exists | Re-create local from platform. |
| Platform missing, local exists | See "Platform anomalies". |

## Plan.md edits

- plan.md is SA's input, NOT authoritative after issues generated.
- Existing issues: NOT regenerated.
- New issues from plan.md edits: NOT auto-created.
- Detection: hash plan.md each Lifecycle loop.
- On change: log `[PLAN_EDITED]`, update STATUS.md.
- Human creates `pending/` files for new issues.

## Platform anomalies

### Issue deleted (404 confirmed)
- Confirm: retry GET [limits.api_confirm_retries]x, [limits.api_confirm_gap_seconds]s gap.
- If persistent 404:
  - Log `[PLATFORM_GONE] <ID>`.
  - Keep local `issues/<ID>.md` (audit).
  - If issue was in-flight: BLOCKER + needs-human.
  - If closed: mark local as orphan.
- Do NOT auto-recreate.

### Issue closed externally
- Detect: platform state == closed, but no merge logged.
- Check branch:
  - `git merge-base --is-ancestor issue/<ID>-<slug> main`.
  - If ancestor: merged externally. Accept. Archive.
  - If not ancestor: BLOCKER + needs-human (`[UNMERGED_CLOSED]`).
- Read latest comment for rationale:
  - "abandoned" / "wontfix": accept, discard work.
  - No comment: BLOCKER.

### Label modified externally
- Mutex conflict (>1 state label):
  - Keep highest priority per orchestrator-labels.md.
  - Remove lower.
- Human-added `blocker`: pause related issue.
- Human-added `ROLLBACK`: trigger rollback flow.
- Unknown label: log `[UNKNOWN_LABEL]`, keep.

### AC changed post-QA-PASS
- Before merge: compare AC hash vs hash at QA PASS.
- If changed: invalidate QA PASS.
  - Remove `qa-passed`, add `qa-failed` (failure_type: ac_changed_post_qa).
  - Re-run PM → SW → QA.
- If merge already complete:
  - Log `[POST_MERGE_AC_CHANGE]`.
  - New cycle via pending issue.

## Backlog consistency

### Count mismatch
- Compare: backlog.md rows vs platform `backlog`-labeled issues.
- Diff < [limits.backlog_drift_log]: auto-reconcile.
- Diff >= [limits.backlog_drift_log]: log `[BACKLOG_DRIFT_LARGE]`.
- Diff >= [limits.backlog_drift_blocker]: BLOCKER.

### Reconciliation
- Platform new (not in backlog):
  - Read body, extract depends/AC.
  - Add row.
  - Log `[PLATFORM_NEW] <ID>`.
- Local-only (not on platform):
  - Mark row `[ORPHANED]`.
  - Do NOT schedule.
  - If dependency for others: BLOCKER.

## Issue-map consistency

- Rebuild from Platform:
  1. Query all issues (any state, label `backlog` or `closed`).
  2. Match with local `issues/*.md` by exact title.
  3. Build `{local_id: platform_number}`.
  4. Overwrite local `issue-map.json`.
- Mismatch detection: for each entry, GET platform issue, compare title.
- Auto-fix: overwrite with platform-derived map.
- Log `[MAP_REBUILT]` with diff.

## Pending handling

See `orchestrator-special.md` Sec. 5.

Summary:
- Pending files are Orchestrator's domain, NOT SA's.
- SA state detection ignores `pending/`.
- Orchestrator processes after SA complete (Stage 6).
- New requirement in comments: creates pending.

## New requirement in comments

- Human uses `[NEW_REQUIREMENT] <text>` in a comment.
- Orchestrator creates `pending/<uuid>.md` with content.
- Normal pending flow.

## New requirement affecting existing issue

- If human explicitly says "changes T5 AC":
  - Route to PM re-groom (like AC SUGGESTION).
- Otherwise: new issue.