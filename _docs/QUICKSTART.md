# Quickstart

One-page guide for humans. Full specs in `_docs/team/`.

## 1. First-time setup

    cp .env.example .env
    # Edit .env: PLATFORM, API_TOKEN, REPO_ID
    chmod 600 .env

    cp _docs/config.yaml.example _docs/config.yaml  # optional

    # Write your requirements
    cp _docs/requirements.md.example _docs/requirements.md
    # Edit: replace with your project description

## 2. Start

    # External launcher runs:
    #   orchestrator with role file _docs/team/orchestrator.md

Orchestrator auto-runs:
  preflight -> SA generates plan.md + issues/ -> Lifecycle begins.

## 3. Monitor

Read these files anytime:

| File | Shows |
|---|---|
| `_docs/state/STATUS.md` | Current state, active slots, queue |
| `_docs/log/YYYY-MM-DD.md` | Today's events (machine) |
| `_docs/log/YYYY-MM-DD-human.md` | Today's events (readable) |
| `_docs/backlog.md` | All issues + status |
| `_docs/state/COMPLETE.md` | Set when project done |

## 4. Control

### Pause / Resume

    touch _docs/state/PAUSE     # pause
    rm _docs/state/PAUSE        # resume

### Restart (clean session)

    touch _docs/state/RESTART

### Cancel one subagent

    touch _docs/state/CANCEL_T42

### Reset (full restart)

    touch _docs/state/RESET _docs/state/RESET_APPROVED

## 5. Approvals (semi-auto / manual)

If `APPROVAL_MODE != full-auto`, Orchestrator waits for approval.

    # Add to _docs/state/APPROVALS.md:
    merge:T42: approved 2026-09-12 14:30

Formats:
  merge:<id>
  deps:add:<pkg>
  delete:<path>
  ci:<type>
  reset:<commit>

## 6. Handle BLOCKERs

When Orchestrator cannot proceed:

1. Read the BLOCKER issue on platform.
2. Fix the underlying problem.
3. Comment on BLOCKER issue:

    [RESOLVED] <what you did>

## 7. Common markers (comment in platform issue)

| Marker | Effect |
|---|---|
| `[RESOLVED] <how>` | Clear BLOCKER |
| `[OVERRIDE_QA_PASS] <why>` | Force QA PASS |
| `[SKIP_PM] <why>` | Skip PM (not recommended) |
| `[ANALYZE]` | Trigger L3/L4 analysis |
| `[NEW_REQUIREMENT] <text>` | Create pending issue |
| `[DAG_EXPORT]` | Export DAG to Mermaid |
| `[FORCE_MERGE] <why>` | Force merge (manual mode) |

## 8. When something breaks

| Symptom | Check |
|---|---|
| Orchestrator HALT | `_docs/state/PREFLIGHT_FAIL.md` |
| Stuck issue | `_docs/state/STATUS.md` |
| Slot crash | `_docs/log/` for `[SLOT_STALE]` |
| Config error | `_docs/state/PREFLIGHT_FAIL.md` |
| Secret leak | Rotate `API_TOKEN`, restart |
| Disk full | Free space, restart |

## 9. Completion

When all issues close:
  - Orchestrator writes `_docs/state/COMPLETE.md`
  - Stops

To resume:
    rm _docs/state/COMPLETE.md
    # Restart Orchestrator

## 10. Key files to know

| File | Purpose |
|---|---|
| `_docs/requirements.md` | Your project description (input) |
| `_docs/plan.md` | Structured plan (auto-generated) |
| `_docs/issues/` | One file per issue |
| `_docs/backlog.md` | All issues index |
| `_docs/team/` | Role specs (rarely read by humans) |
| `_docs/state/` | Runtime state |
| `_docs/log/` | Event history |

## 11. Defaults (per config.yaml.example)

| Setting | Default |
|---|---|
| Parallel slots | 3 |
| SW retry per round | 25 |
| SW retry per issue | 100 |
| PM retry per issue | 4 |
| QA timeout | 30 min |
| Session restart | 20 transitions or 1 hour |
| Approval mode | full-auto |

Change in `_docs/config.yaml`, then restart.

## 12. More info

| Topic | File |
|---|---|
| Full lifecycle | `_docs/team/orchestrator.md` |
| Git operations | `_docs/team/orchestrator-git.md` |
| Failures | `_docs/team/orchestrator-failures.md` |
| Human controls | `_docs/team/orchestrator-human.md` |
| Special mechanisms | `_docs/team/orchestrator-special.md` |
| Config details | `_docs/config.md` |
| Hard rules | `_docs/rules.md` |