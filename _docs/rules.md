# Rules

## Platform

- Platform Issues (GitHub/GitLab) are the source of truth for status.
- Set `PLATFORM`, `API_TOKEN`, `REPO_ID`. Optional `API_URL`.
- Do not manually edit Platform Issues while Orchestrator is running.
- Labels drive state transitions (see `orchestrator.md`).

## Source of truth (files)

- Dependency source of truth: `_docs/issues/<ID>.md` frontmatter `depends:`.
- Platform Issue body is a mirror, not authoritative.
- AC source of truth: `_docs/issues/<ID>.md`.

## Process enforcement (4 layers)

1. State machine: every transition declares `reached_state`. Mismatch = rejected.
2. Pre-output checklist: every role MUST verify before finishing.
3. Forbidden list: every role MUST respect boundaries.
4. Gate checks: Orchestrator validates before each transition.

Violating any layer = output rejected, subagent re-run.

## Git

- Each issue works in its own worktree (`../worktrees/<ID>`).
- Branch naming: `issue/<ID>-<slug>`.
- SW pushes branch before adding `qa-ready`.
- Merge to main is SERIAL (one at a time, FIFO by QA PASS time).
- Merge uses `--no-ff` (preserve merge commit).
- Remote branches are NOT deleted after merge.
- Merge conflicts / post-rebase test failures: assigned to the issue's own SW via `MERGE-FIX: <ID>` issue.

## Other

- Dependencies are added in `pyproject.toml`. Ask before adding.
- Tasks are Platform Issues, one at a time.
- Read AC before starting and before closing.
- Commit regularly.
- Do not skip any lifecycle step (SA -> PM -> SW -> QA).