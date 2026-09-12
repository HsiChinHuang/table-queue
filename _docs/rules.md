# Rules

## Platform

- Platform Issues (GitHub/GitLab) are the source of truth for status.
- Env: `PLATFORM`, `API_TOKEN`, `REPO_ID` (required). `API_URL` (optional, self-hosted).
- Do not manually edit Platform Issues while Orchestrator is running.
- Labels drive state transitions (see `team/orchestrator-labels.md`).

## Slots

- 1 slot = 1 active subagent session (PM/SW/QA).
- Max slots: `[slots.max]`, across all phases.
- Never spawn a subagent when `[slots.max]` slots are active.
- Merge and Orchestrator work do NOT consume slots.
- MERGE-FIX SW session DOES consume a slot.
- Dependency wait does NOT consume a slot.
- Free a slot only when: QA PASS, issue blocked, or BLOCKER raised.

## Source of truth

| Data | Authoritative |
|---|---|
| Dependency | `issues/<ID>.md` frontmatter `depends:` |
| Acceptance criteria | `issues/<ID>.md` |
| Issue state (open/closed) | Platform |
| Labels | Platform |
| Comments | Both (union) |

Platform Issue body is a mirror, not authoritative for AC.

## Role boundaries (hard)

| Role | Does | Never does |
|---|---|---|
| Orchestrator | schedule, spawn, track, merge | edit content, write code, post verdicts |
| SA | parse plan, generate issues | write code, groom, test |
| PM | edit `issues/<ID>.md`, groom AC | write code, test, close issues |
| SW | write code, push branch | edit AC, close issues, approve own work |
| QA | verify, post verdict | fix code, edit tests, close issues |

On role failure: re-run SAME role. Never substitute.

SA is initialization only. SA does NOT declare `reached_state`.

## Process enforcement (4 layers)

1. **State machine**: every transition declares `reached_state`. Mismatch = rejected.
2. **Pre-output checklist**: every role MUST verify before finishing.
3. **Forbidden list**: every role MUST respect boundaries.
4. **Gate checks**: Orchestrator validates before each transition.

Violating any layer = output rejected, subagent re-run.

## Git

- Each issue works in its own worktree (`../worktrees/<ID>`).
- Branch naming: `issue/<ID>-<slug>`.
- SW pushes branch before adding `qa-ready`.
- Merge to main is SERIAL (one at a time, FIFO by QA PASS time).
- Merge uses `--no-ff` (preserve merge commit).
- Remote branches are NOT deleted after merge.
- Merge conflicts / post-merge test failures: assigned to the issue's own SW via `MERGE-FIX: <ID>`.
- Orchestrator NEVER resolves conflicts.

## Permissions

SW must not execute blacklisted commands (see `team/sw.md`).
Violation -> `[BLOCKER]`.

## Approval mode

Env `APPROVAL_MODE`: `full-auto` (default) | `semi-auto` | `manual`.
Approval source: `_docs/state/APPROVALS.md`.

## Config

- Effective config = env > `config.yaml` > `config.yaml.example`.
- Only listed keys are env-overridable (see `_docs/config.md`).
- Secrets (API_TOKEN) only from env.
- Config read at boot only. Changes require restart.
- Changed config applies immediately to all in-flight issues.
- Snapshot written to `_docs/state/CONFIG_SNAPSHOT.json` (committed).
- Version mismatch -> HALT; see `_docs/config-migrations.md`.
- All numeric limits in role files written as `[key]`; resolved at runtime.

## Other

- Dependencies added in `pyproject.toml` require approval.
- Tasks are Platform Issues, one at a time.
- Read AC before starting and before closing.
- Commit regularly.
- Do not skip any lifecycle step (SA -> PM -> SW -> QA).