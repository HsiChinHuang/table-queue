# Memory System

Long-term knowledge base. Records problems and solutions for future agents.

## Quick Reference

| Item | Value |
|---|---|
| Write trigger | Any role fails 3+ times consecutively |
| Read trigger | Role retry >= 2 |
| Read limit | `memory.read_max` (default 3) |
| Promote threshold | `memory.promote_count` (default 2) |
| Demote threshold | `memory.fail_delete_threshold` (default 3) |
| Scope | project / language / universal |
| Max file size | `memory.max_size_kb` (default 10 KB) |
| Max candidates | `memory.max_candidates` (default 100) |
| Retention | `memory.retention_days` (default 90) |

## Directory Structure

```
docs/memory/
├── readme.md
├── rules.md               (promote/demote rules)
├── index.json             (machine-readable index)
├── index.md               (human-readable index)
├── candidates/            (unverified)
├── verified/              (validated)
├── patterns/              (common failure patterns)
├── anti_patterns/         (known anti-patterns)
├── conflicts/             (known conflict pairs)
└── archive/               (expired or demoted)
```

## File Format

Each memory is a JSON file conforming to `schemas/memory/memory.json`.

## ID Format

```
<type>_<scope>_<primary_tag>_<secondary_tag>_<short_hash>
```

Examples:

- `sol_lang_django_migrat_a1b2`
- `anti_univ_test_assert_c3d4`

### ID Conflict Handling

`short_hash` is the first 4 hex chars of `sha256(problem + solution)`. If two memories have identical IDs (rare):

1. **Append a sequence number**: `sol_lang_django_migrat_a1b2_2`
2. **Sequence starts at 2**.
3. **Do NOT append `_1`** (first conflict uses `_2`).

Examples:

- First created: `sol_lang_django_migrat_a1b2`
- If conflict: `sol_lang_django_migrat_a1b2_2`
- If conflict again: `sol_lang_django_migrat_a1b2_3`

### Dedupe Priority

**Before** generating an ID, compute similarity to existing memories:

- If `similarity > memory.similarity_dedupe` (default 0.85) → update existing memory, do not create new.
- Otherwise → generate new ID. On conflict, append sequence.

## State Transitions

```
candidate → verified → archived
```

- candidate → verified: `verified_count >= promote_count` and at least 2 distinct issues applied.
- verified → archived: `failed_count` increases `fail_delete_threshold` times consecutively.

Detailed rules in `rules.md`.

## Human Override

Edit the memory file, set `human_override: true` to disable auto promote/demote/delete.

## Conflict Handling

If two memories conflict:

1. Role detects during read → writes `[MEMORY CONFLICT]`.
2. Orchestrator creates a human_review.
3. Human decides:
   - Merge into one
   - Delete one
   - Mark as applicable to different scope
4. After resolution, write `conflicts/<id_a>_<id_b>.json`.
5. Future reads skip known conflicts.