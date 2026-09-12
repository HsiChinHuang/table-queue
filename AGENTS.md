# AGENTS

## Hard rules (apply to ALL roles)

1. Read your role file before doing anything. Role files: `_docs/team/<role>.md`.
2. Do NOT perform other roles' work.
3. Declare `reached_state` in output (except SA; see its role file).
4. Never skip your Pre-output checklist.
5. If a rule is unclear: post BLOCKER, do not guess.

## Pointers

- Role files: `_docs/team/<role>.md`
- Shared rules: `_docs/team/_shared.md`
- Hard rules: `_docs/rules.md`
- Commands: `_docs/commands.md`

Note: `_docs/team/orchestrator*.md` are for Orchestrator only. Do NOT read them.

Note: `orchestrator*.md` files are split by topic
(orchestrator-git, orchestrator-failures, orchestrator-human,
orchestrator-special, orchestrator-logging, orchestrator-slots,
orchestrator-boundaries, orchestrator-authority, orchestrator-labels,
orchestrator-merge, orchestrator-preflight, orchestrator-rollback).
These are for Orchestrator only; subagents do NOT read them.