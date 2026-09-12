# Changelog

## v1.0 (2026-09-13) - Initial design

### Summary

Complete multi-agent orchestration system for software projects.
- 5 roles: Orchestrator, SA, PM, SW, QA
- 4-layer enforcement: state machine, checklist, forbidden, gates
- Parallel implementation (3 slots), serial merge
- 120+ config keys
- Platform-agnostic (GitHub / GitLab)

### Design process

Systematic deep-dive across 9 topic groups:

| Group | Topic | Issues addressed |
|---|---|---|
| G1 | Authority chain | 60 |
| G2 | Role boundaries | 50 |
| G3 | Slot scheduling | 35 |
| G4 | Failure taxonomy | 126 |
| G5 | Merge + Git | 121 |
| G6 | Special mechanisms | 86 |
| G7 | SA + DAG | 77 |
| G8 | Human interaction | 67 |
| G9 | Logging + scale | 66 |

Total: ~688 issues analyzed.

### Verification

- 12 core scenarios simulated (Batch 1: 5 happy-path; Batch 2: 6 recovery; Batch 3: 5 boundary; plus 3 runtime controls).
- 8 scenarios re-verified after fixes.
- 1 post-verification fix applied.

### Key design decisions

| Decision | Rationale |
|---|---|
| Platform is source of truth | Audit trail |
| Dependencies local-only | Platform can't express DAG |
| Fresh session per subagent | Avoid context pollution |
| Slot = subagent session | Prevent over-scheduling |
| Serial merge | Deterministic history |
| Failure taxonomy 3-layer | Clear routing |
| Memory 2-layer (candidates/verified) | Quality control |
| Human markers via comments | No custom UI needed |

### Known limitations

- GitLab path not fully tested (GitHub primary).
- Hub file splitting requires human judgment.
- Dry-run scope limited to local files.
- Encrypted secret scanning not implemented.
- Multi-language testing templates (only Python).

### Files

Total ~50 markdown files + config + scripts.

### Change log

- 2026-09-13: Initial v1.0