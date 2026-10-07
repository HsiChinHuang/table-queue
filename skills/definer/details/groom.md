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
| `factpack_path` | No | Path to factpack JSON (injected by Orchestrator) |
| `platform_issue` | Yes | Platform issue number (from `docs/state/issue_map.json`) |

**Note on factpack**: When `factpack_path` is provided, prefer its content over reading `docs/commands.md`, `docs/coding_standards.md`, and `docs/state/config_snapshot.json` directly. The factpack contains the full text of those files plus a relevant config subset.

## Platform API

All Platform operations in this document use:

```
npx tsx scripts/platform.ts <resource> <action> [options]
```

See `docs/commands.md` § Platform API.

## Process

### Step 1: Read inputs

Read all input files. If the issue does not exist -> write a BLOCKER handoff.

If `factpack_path` was provided by Orchestrator:

- Read the factpack JSON.
- Use `facts.tech_stack` (fall back to `docs/plan.md` if null).
- Use `facts.commands_md` instead of reading `docs/commands.md`.
- Use `facts.coding_standards_md` instead of reading `docs/coding_standards.md`.
- Use `facts.config_subset` for `contract_first.*` and `limits.issue_granularity.*`.

If `factpack_path` was NOT provided (fallback path):

- Read `docs/commands.md`.
- Read `docs/coding_standards.md`.
- Read `docs/state/config_snapshot.json` (extract relevant keys).

### Step 2: Refine AC

Refine the AC draft (from survey) into checkable statements:

- Each AC MUST describe an observable behavior.
- Include error cases, empty states, loading states.
- Avoid vague words (robust, good, nice, proper).

### Step 3: Define verification commands (contract-first)

For each automatable AC (types in `contract_first.require_for`):

- Define an executable command.
- Format: `<command>`, e.g. `uv run pytest tests/test_auth.py::test_signup_duplicate`.
- The command MUST be executable locally and deterministic, and MUST produce a clear pass/fail exit code (0 = pass, non-zero = fail).

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

### Step 6: Sync Platform body

Read the full content of `docs/issues/<id>.md` (the entire file, including
frontmatter). Then push it to the Platform Issue body:

```
npx tsx scripts/platform.ts issue update <platform_issue> \
  --body "<full content of docs/issues/<id>.md>"
```

The `<platform_issue>` is the number from the input (`platform_issue`).
On success, the returned JSON's `number` equals `<platform_issue>`.

If the update fails (non-zero exit):

- Retry once. If still failing, write a BLOCKER handoff with reason
  `platform_body_sync_failed` and stop.

**Note**: The Platform Issue body is a mirror of the local file. The local
file remains authoritative. The Gate 1 check (see `gates.md`) relies on
this step's success to confirm body sync; a COMPLETE handoff with no
error implies the sync succeeded.

### Step 7: Label transition

On the Platform Issue:

- Remove state label `defined`:
  ```
  npx tsx scripts/platform.ts label remove <platform_issue> --label defined
  ```
- Add state label `groomed`:
  ```
  npx tsx scripts/platform.ts label add <platform_issue> --label groomed
  ```

## Output

Write `docs/state/outputs/<id>_definer_groom.json`, conforming to `schemas/definer/groom.json`.

## Pre-output Checklist

- [ ] All inputs read
- [ ] factpack read (if `factpack_path` provided)
- [ ] Each AC is checkable
- [ ] Error cases covered
- [ ] Automatable AC have verification commands
- [ ] `verification_commands` written to `docs/issues/<id>.md`
- [ ] Context, AC, Out of scope, DoD specific filled
- [ ] Platform Issue body synced via `issue update`
- [ ] Labels transitioned (`defined` removed, `groomed` added)
- [ ] Output conforms to `schemas/definer/groom.json`
- [ ] `reached_state: groomed`
- If any unchecked: write a BLOCKER handoff, do NOT complete

## Forbidden

- Write code
- Modify Test requirements, Implementation notes (Builder's responsibility)
- Modify files outside the issue
- Modify `plan.md`
- **Call the Platform API directly via `curl`**; always use `scripts/platform.ts`

## Boundaries

- Write only: `docs/issues/<id>.md`, Platform Issue (via `scripts/platform.ts`), `docs/state/outputs/<id>_definer_groom.json`
- Do NOT write: `src/`, `tests/`, other files under `docs/state/`