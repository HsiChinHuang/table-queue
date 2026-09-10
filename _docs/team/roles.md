# Roles

- Orchestrator - `_docs/team/orchestrator.md`
- SA - `_docs/team/sa.md`
- PM - `_docs/team/pm.md`
- SW - `_docs/team/sw.md`
- QA - `_docs/team/qa.md`

## Subagents

- All roles except Orchestrator are transient subagents.
- Fresh session per call. No memory carried between calls.
- Orchestrator passes role file path explicitly. Subagent reads it + `AGENTS.md`.
- Subagent output MUST declare `reached_state`.

## Process is mandatory

- Every issue MUST pass SA → PM → SW → QA. No step may be skipped.
- Orchestrator enforces gate checks at each transition.
- Each role file contains a Pre-output checklist and a Forbidden list. Both are binding.