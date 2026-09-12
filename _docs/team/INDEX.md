# Team File Index

Quick guide to `_docs/team/` files.

## Role files (read by subagents)

| File | Read by | Purpose |
|---|---|---|
| `_shared.md` | all roles | Common rules, markers |
| `sa.md` | SA | Plan generation, state detection |
| `sa-dag.md` | SA | DAG, depth, file conflicts (referenced) |
| `pm.md` | PM | Grooming |
| `sw.md` | SW | Implementation |
| `qa.md` | QA | Verification |

## Orchestrator files (read by Orchestrator only)

| File | When read | Purpose |
|---|---|---|
| `orchestrator.md` | boot | Main entry, Lifecycle |
| `orchestrator-preflight.md` | boot | Startup checks |
| `orchestrator-gates.md` | Gate checks | Validation |
| `orchestrator-slots.md` | scheduling | Slot algorithm |
| `orchestrator-authority.md` | drift check | Source of truth |
| `orchestrator-boundaries.md` | every spawn | Role boundaries |
| `orchestrator-failures.md` | on FAIL | Taxonomy, routing |
| `orchestrator-git.md` | merge/rollback | Git lifecycle |
| `orchestrator-merge.md` | merge | Merge orchestration |
| `orchestrator-rollback.md` | rollback | Rollback entry |
| `orchestrator-labels.md` | labels | Label rules, archive |
| `orchestrator-human.md` | human actions | PAUSE/RESET/Approval |
| `orchestrator-special.md` | special triggers | AC/Memory/Pending |
| `orchestrator-logging.md` | logging | Log/archive/scale |

## Details (rarely read)

| File | Purpose |
|---|---|
| `details/sa-details.md` | SA edge cases |
| `details/pm-details.md` | PM edge cases |
| `details/sw-details.md` | SW edge cases |
| `details/qa-details.md` | QA edge cases |
| `details/orchestrator-details.md` | Orchestrator edge cases |

## Reading order

**Subagent**: `AGENTS.md` → `_shared.md` → own role file.

**Orchestrator boot**: `AGENTS.md` → `orchestrator.md` → `orchestrator-preflight.md`.

**Orchestrator runtime**: pulls specific files on demand (see "When read" column).

## File size guide

| Category | Typical |
|---|---|
| Role files | 100~200 lines |
| Orchestrator core | ~200 lines |
| Orchestrator topic files | 80~150 lines |
| Details | 100~200 lines |

## Do NOT read

- Subagents: any `orchestrator*.md`
- Orchestrator: role files during scheduling (only pass paths)
- Anyone: files in other roles' allowed lists