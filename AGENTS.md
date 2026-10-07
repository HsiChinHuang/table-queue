# AGENTS

## Hard rules (apply to ALL roles)

1. Read your role skill before doing anything: `skills/<role>/SKILL.md`.
2. Do NOT perform other roles' work.
3. Your output MUST be a JSON handoff conforming to `schemas/<role>/<phase>.json`.
4. Declare `reached_state` in your handoff.
5. If a rule is unclear: write a BLOCKER handoff, do not guess.
6. Never skip your Pre-output checklist.

## Pointers

- Role skills: `skills/<role>/SKILL.md`
- Schemas: `schemas/<role>/<phase>.json`
- Config: `docs/config.yaml`
- Commands: `docs/commands.md`

Note: `skills/orchestrator/` is for Orchestrator only.
Note: `details/` subdirectories are loaded on demand.