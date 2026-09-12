# Orchestrator Labels

Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## Label definitions

| Label | Set by | Meaning |
|---|---|---|
| `backlog` | SA | From plan.md, initial state |
| `groomed` | PM | AC refined, ready for SW |
| `qa-ready` | SW | Code pushed, ready for QA |
| `qa-passed` | QA | Verification passed |
| `qa-failed` | QA | Verification failed |
| `blocker` | Orchestrator | Needs human |
| `closed` | Orchestrator | Merged to main |
| `needs-human` | Orchestrator | Human action required |
| `recovery` | Orchestrator | Recovery blocked |
| `optimization` | Judge (if enabled) | Follow-up optimization |
| `ROLLBACK` | Human | Rollback request |

## Mutex rules

- At most ONE of: `backlog`, `groomed`, `qa-ready`, `qa-passed`, `qa-failed`, `closed`.
- `blocker` / `needs-human` / `recovery` may stack with any state.
- When spawning a new role, remove stale state labels first.

Transitions:
- PM: remove `backlog`, add `groomed`.
- SW: remove `groomed` / `qa-failed`, add `qa-ready`.
- QA: remove `qa-ready`, add `qa-passed` or `qa-failed`.
- Orchestrator on merge success: remove `qa-passed`, add `closed`.

## Issue closure + archive

On `closed`:
1. Move `_docs/issues/<ID>.md` -> `_docs/issues/closed/<ID>.md`.
2. Add `closed_at: <UTC_TS>` to frontmatter.
3. Update `_docs/issues/closed/index.md`:

    | ID | Title | Closed At | Retries | Merge Commit |
    |---|---|---|---|---|
    | T42 | ... | 2026-09-12 | 3 | abc123 |

4. Update `backlog.md`: mark row as `closed` (do NOT delete).
5. Move row from active to archived section.

## Comment archiving

See `orchestrator-special.md` Sec. 4.

Summary:
- Trigger: count > `[limits.comments_keep]`.
- Order: history first, platform delete after.
- Retry 3x on delete fail, then BLOCKER.
- Growth control: split at `[limits.history_max_lines]`.
- Dual format: machine + human-readable.

Full archiving spec: `orchestrator-logging.md` Sec. 4.

## Output directory cleanup

`_docs/state/outputs/`:
- Issue closed: keep `[retention.output_keep_days]` days.
- Then move to `outputs/archive/<YYYY-MM>/`.
- Archive retained `[retention.output_archive_days]` days.
- Files marked `[KEEP]`: permanent.

Retention rules: `orchestrator-logging.md` Sec. 4.1.

## Config snapshot history

`_docs/state/history/`:
- Keep latest `[retention.config_history_keep]` config snapshots.
- Older moved to `state/history/archive/`.

## Backlog.md growth control

- Active section: only non-closed issues.
- On close: move row to bottom `## Closed` section (or separate file `backlog-closed.md`).
- `issue-map.json`: retains all IDs (small file).

## Label color conventions (optional, for humans)

| Label | Suggested color |
|---|---|
| `backlog` | gray |
| `groomed` | blue |
| `qa-ready` | yellow |
| `qa-passed` | green |
| `qa-failed` | red |
| `blocker` | dark red |
| `closed` | purple |