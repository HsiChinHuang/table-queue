# Process

This file is a reference for the Orchestrator. Subagents do NOT read it.

## Concurrency

- Max 3 active subagent sessions globally (PM + SW + QA combined).
- 1 issue = 1 slot, held from PM start until QA PASS or blocked.
- Merge: SERIAL, one at a time (never parallel).
- Waiting on dependencies: does NOT hold a slot.
- Merge and Orchestrator work do NOT consume slots.
- MERGE-FIX SW session DOES consume a slot.

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
5. FAIL: goto 3 (max 100). PASS: release slot, enqueue for merge.
6. Orchestrator merges serially (FIFO) -> close issue -> label `closed`

## Slot rules

- Never spawn a subagent if 3 slots are active.
- Free a slot only when: QA PASS, issue blocked, or BLOCKER raised.
- If slots full: queue the issue; do not spawn.

## Env vars

| Var | Purpose |
|---|---|
| `PLATFORM` | `github` or `gitlab` |
| `API_TOKEN` | Access token |
| `REPO_ID` | GitHub: `owner/repo`; GitLab: numeric project ID |
| `API_URL` | Optional, for self-hosted |