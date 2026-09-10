# Process

This file is a reference for the Orchestrator. Subagents do NOT read it.

## Concurrency

- Implementation: up to 3 issues in parallel (Mode X).
- Merge: SERIAL, one at a time (never parallel).

## Worktrees

- Path: `../worktrees/<ID>`
- Branch: `issue/<ID>-<slug>`
- Created by Orchestrator on entering SW stage.
- Removed after merge to main.

## Lifecycle (mandatory, no step may be skipped)

1. SA: requirements.md -> plan.md -> issues/*.md -> backlog.md -> Platform Issues
2. PM: groom issue -> update `_docs/issues/<ID>.md` + Platform Issue -> label `groomed`
3. SW: create worktree -> implement -> push branch -> label `qa-ready`
4. QA: verify -> label `qa-passed` or `qa-failed`
5. FAIL: goto 3 (max 100). PASS: enqueue for merge.
6. Orchestrator merges serially (FIFO) -> close issue -> label `closed`

## Env vars

| Var | Purpose |
|---|---|
| `PLATFORM` | `github` or `gitlab` |
| `API_TOKEN` | Access token |
| `REPO_ID` | GitHub: `owner/repo`; GitLab: numeric project ID |
| `API_URL` | Optional, for self-hosted |