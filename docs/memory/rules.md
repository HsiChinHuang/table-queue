# Memory Rules

Promote, demote, and delete rules for the Memory system.

## States

- `candidate` — unverified, in `candidates/`
- `verified` — validated, in `verified/`
- `archived` — archived, in `archive/`

## Write

Trigger: Any role fails >= `memory.write_after_failures` (default 3) times consecutively.

Process:

1. Role generates memory content.
2. Generate ID: `<type>_<scope>_<primary_tag>_<secondary_tag>_<short_hash>`.
3. Compute similarity to existing memories.
4. If similarity > `memory.similarity_dedupe` (default 0.85) → update existing.
5. Otherwise → write to `candidates/`.
6. Update `index.json` and `index.md`.

## Read

Trigger: Role retry >= 2.

Process:

1. Match memories by current issue's `tags` and `scope`.
2. Select up to `memory.read_max` (default 3).
3. Dedupe (similarity `memory.similarity_dedupe`).
4. Check `docs/memory/conflicts/` history, skip known conflicts.
5. Pass memory paths to the role.

## Promote (candidate → verified)

Conditions (all must be true):

1. `verified_count >= memory.promote_count` (default 2).
2. Applied by at least 2 **distinct** issues.
3. No `[FAILED USE]` in last 3 uses.
4. `human_override` is `false`.

Process:

1. Move file: `candidates/<id>.json` → `verified/<id>.json`.
2. Update `index.json` state to `verified`.
3. Log `[MEMORY_PROMOTED] <id>`.

## Demote (verified → archived)

Conditions:

1. `failed_count` increases `memory.fail_delete_threshold` (default 3) times consecutively.
2. `human_override` is `false`.

Process:

1. Move file: `verified/<id>.json` → `archive/<id>.json`.
2. Update `index.json` state to `archived`.
3. Log `[MEMORY_DEMOTED] <id>`.

## Delete

Conditions:

1. `failed_count` increases `memory.fail_delete_threshold * 2` times consecutively.
2. `human_override` is `false`.

Process:

1. Delete file.
2. Remove from `index.json`.
3. Log `[MEMORY_DELETED] <id>`.

## Human Override

Set `human_override: true` to disable auto promote/demote/delete.

Human may edit memory files directly.

## Retention

- Candidates: `memory.retention_days` (default 90) days unused → archive.
- Verified: `memory.verified_retention_days` (default 365) days unused → archive.
- Archive: permanent.

## Conflict Handling

If two memories conflict:

1. Role detects during read → writes `[MEMORY CONFLICT]`.
2. Orchestrator creates a human_review.
3. Human decides:
   - Merge into one
   - Delete one
   - Mark as applicable to different scope
4. After resolution, write `docs/memory/conflicts/<id_a>_<id_b>.json`.
5. Future reads skip known conflicts.