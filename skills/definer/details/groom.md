# Definer: Groom

Refine a single issue's AC and define verification commands.

## Trigger

Orchestrator spawns Definer for an issue in state `defined` that has NOT been groomed.

## Inputs

| File | Required | Purpose |
|---|---|---|
| `docs/issues/<id>.md` | Yes | Current issue |
| `docs/plan.md` | Yes | Project plan |
| `docs/requirements.md` | Yes | Requirements |
| `docs/coding_standards.md` | Yes | Coding standards |
| `docs/backlog.md` | Yes | DAG context |

## Process

### Step 1: Read inputs

Read all input files. If the issue does not exist -> write a BLOCKER handoff.

### Step 2: Refine AC

Refine the AC draft (from survey) into checkable statements:

- Each AC MUST describe an observable behavior.
- Include error cases, empty states, loading states.
- Avoid vague words (robust, good, nice, proper).

### Step 3: Define verification commands (contract-first)

For each automatable AC (types in `contract_first.require_for`):

- Define an executable command.
- Format: `<command>`, e.g. `uv run pytest tests/test_auth.py::test_signup_duplicate`.
- The command MUST run in CI.

For non-automatable AC (types in `contract_first.allow_natural_for`):

- Do NOT force a command.
- Mark as `"manual"` in `verification_commands`.

### Step 4: Write verification commands to the issue file

Write `verification_commands` to `docs/issues/<id>.md`'s `## Verification commands` section:

```markdown
## Verification commands

- ac1: `uv run pytest tests/test_auth.py::test_signup_valid`
- ac2: `uv run pytest tests/test_auth.py::test_signup_duplicate`
- ac3: `manual`
```

**This section is the authoritative source of verification commands.** Builder and Verifier read from here.

### Step 5: Fill sections

Fill the following sections:

- `Context`: why this issue exists, links to plan.md and design docs.
- `Acceptance criteria`: refined AC list.
- `Out of scope`: content not belonging to this issue, linked to follow-up issues.
- `Definition of Done` (issue-specific): concrete completion criteria.

### Step 6: Sync Platform

Write the updated issue content to the Platform Issue body.

### Step 7: Label transition

On the Platform Issue:

- Remove label `defined`
- Add label `groomed`

## Output

Write `docs/state/outputs/<id>_definer_groom.json`, conforming to `schemas/definer/groom.json`.

## Pre-output Checklist

- [ ] All inputs read
- [ ] Each AC is checkable
- [ ] Error cases covered
- [ ] Automatable AC have verification commands
- [ ] `verification_commands` written to `docs/issues/<id>.md`
- [ ] Context, AC, Out of scope, DoD specific filled
- [ ] Platform Issue body synced
- [ ] Labels transitioned (`defined` -> `groomed`)
- [ ] Output conforms to `schemas/definer/groom.json`
- [ ] `reached_state: groomed`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Write code
- Modify Test requirements, Implementation notes (Builder's responsibility)
- Modify files outside the issue
- Modify `plan.md`

## Boundaries

- Write only: `docs/issues/<id>.md`, Platform Issue body, `docs/state/outputs/<id>_definer_groom.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`