# Documents

## Read by Orchestrator only

- `_docs/team/orchestrator.md` (Orchestrator's own brief; it names `AGENTS.md` and `_docs/task-template.md`, and is the only role file that names `_docs/process.md` at all, which is why that document keeps no read row here: root `AGENTS.md` forbids every other role from reading it)
- `_docs/team/roles.md` (read by the Orchestrator; the other role files name each other only as the role-to-file map)
- `_docs/orchestrator-playbook.md` (operating knowledge: AC authoring, rulings, harness traps)

## Read by specific roles (per role file)

- SA (read): `_docs/requirements.md`, `_docs/plan.md.example`, `_docs/task-template.md`, `_docs/design-system.md`, `_docs/plan.md`, `_docs/backlog.md`, `_docs/issue-map.json` (`_docs/issues/<ID>.md` files are written here by SA and are not named as reads by the SA role file)
- PM: `_docs/issues/<ID>.md`, `_docs/task-template.md`
- SW: `_docs/issues/<ID>.md`
- QA: `_docs/issues/<ID>.md`

## Generated (runtime)

- `_docs/plan.md` (SA)
- `_docs/issues/` (SA, enriched by PM)
- `_docs/backlog.md` (SA)
- `_docs/issue-map.json` (SA)

## Universal

- `_docs/team/sw.md` (root `AGENTS.md` section 3 requires every subagent to read its own role file, and every role brief under `_docs/team/` names `_docs/team/<role>.md` as the one file the Orchestrator passes; the row registers the three transient-role briefs)
- `_docs/team/qa.md` (same section-3 requirement)
- `_docs/team/pm.md` (same section-3 requirement)
- `_docs/rules.md` (all roles may read; the Orchestrator must not pass it directly)
- `_docs/requirements.md` (project requirements this guide summarizes; SA reads in full, all roles may consult)
- `_docs/requirements.md.example` (template every checkout carries; `_docs/requirements.md` is generated from it)
- `_docs/api-examples.md` (worked API examples behind `_docs/openapi.yaml`)
- `_docs/specs.md` (root `AGENTS.md` section 3: full specification)
- `_docs/ui.md` (root `AGENTS.md` section 3: UI guide)
- `_docs/openapi.yaml` (root `AGENTS.md` section 3: API contract)
- `_docs/testing.md` (root `AGENTS.md` section 3: testing guide)
- `_docs/deployment.md` (deployment guide; not in section 3, listed here so the index reaches it)
- `AGENTS.md` (all roles must read first)
- `CONTRIBUTING.md` (root `AGENTS.md` section 3: issue and PR workflow)
- `_docs/project-guide.md` (project content map and frozen archive of the old `AGENTS.md` sections)
