# Documents

## Read by Orchestrator only

- `_docs/process.md`
- `_docs/team/orchestrator.md`
- `_docs/team/roles.md`
- `_docs/orchestrator-playbook.md` (operating knowledge: AC authoring, rulings, harness traps)

## Read by specific roles (per role file)

- SA (read): `_docs/requirements.md`, `_docs/plan.md.example`
- SA (read+write): `_docs/design-system.md`, `_docs/plan.md`, `_docs/issues/<ID>.md`, `_docs/backlog.md`, `_docs/issue-map.json`
- PM: `_docs/issues/<ID>.md`, `_docs/task-template.md`
- SW: `_docs/issues/<ID>.md`, `_docs/testing-guidelines.md`, `_docs/commands.md`, `_docs/design-system.md`
- QA: `_docs/issues/<ID>.md`, `_docs/testing-guidelines.md`, `_docs/commands.md`

## Generated (runtime)

- `_docs/plan.md` (SA)
- `_docs/issues/<ID>.md` (SA, enriched by PM)
- `_docs/backlog.md` (SA)
- `_docs/issue-map.json` (SA)

## Universal

- `_docs/rules.md` (all roles may read)
- `_docs/requirements.md` (project requirements this guide summarizes; SA reads in full, all roles may consult)
- `_docs/AGENTS.md` (all roles must read first)