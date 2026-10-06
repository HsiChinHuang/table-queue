# Schema Versioning

Versioning rules for all schemas.

## Version Number

Each schema has a `schema_version` field in format `<major>.<minor>`.

Examples: `1.0`, `1.1`, `2.0`.

## Change Rules

### Major version (1.0 -> 2.0)

- **Breaking changes**: removing fields, changing field types, changing field semantics.
- Requires **manual migration**.
- Old data must be converted.

### Minor version (1.0 -> 1.1)

- **Backward-compatible changes**: adding optional fields, loosening constraints.
- No migration required.
- Old data remains valid.

## Migration Flow

### On write

1. Check `schema_version`.
2. If older version -> convert via migration function.
3. Write new version.

### On read

1. Read `schema_version`.
2. If older version -> convert via migration function.
3. Use converted data.

## Migration Functions

Stored in `extensions/schema_migrations.ts`:

```typescript
export const migrations: Record<string, (data: unknown) => unknown> = {
  '1.0->1.1': migrate_1_0_to_1_1,
  '1.1->2.0': migrate_1_1_to_2_0,
};

function migrate_1_0_to_1_1(data: unknown): unknown {
  // Add new field
  if (typeof data !== 'object' || data === null) return data;
  return { ...data, new_field: null, schema_version: '1.1' };
}
```

## Version List

| Schema | Current version | Notes |
|---|---|---|
| `common/handoff.json` | 1.0 | Base envelope for all role outputs |
| `common/error.json` | 1.0 | Structured error |
| `common/evidence.json` | 1.0 | Evidence base |
| `definer/survey.json` | 1.0 | Initial plan generation |
| `definer/review_plan.json` | 1.0 | Plan review |
| `definer/groom.json` | 1.0 | AC refinement |
| `definer/re_groom.json` | 1.0 | AC correction after QA FAIL |
| `builder/implement.json` | 1.0 | AC implementation |
| `builder/fix_qa.json` | 1.0 | QA failure fix |
| `builder/fix_merge.json` | 1.0 | Merge conflict resolution |
| `builder/fix_regression.json` | 1.0 | Post-merge regression fix |
| `verifier/verify_issue.json` | 1.0 | Single-issue verification |
| `verifier/verify_pre_merge.json` | 1.0 | Pre-merge cumulative tests |
| `verifier/verify_post_merge.json` | 1.0 | Post-merge smoke tests |
| `state/snapshot.json` | 1.0 | Slot and merge queue state |
| `state/retry.json` | 1.0 | Issue-level retry counters |
| `state/retry_subagent.json` | 1.0 | Subagent-level retry counters |
| `state/config_snapshot.json` | 1.0 | Effective config snapshot |
| `state/issue_map.json` | 1.0 | Local ID to platform number mapping |
| `state/merge_cp.json` | 1.0 | Merge checkpoint |
| `state/idempotency.json` | 1.0 | Idempotency records |
| `state/launcher_checkpoint.json` | 1.0 | Launcher checkpoint |
| `state/merge_test_index.json` | 1.0 | Cumulative test index |
| `state/merge_history.json` | 1.0 | Merge history |
| `state/token_usage.json` | 1.0 | Token usage per issue |
| `state/misjudgments.json` | 1.0 | QA misjudgment records |
| `state/milestone.json` | 1.0 | Milestone tracking |
| `state/status_metrics.json` | 1.0 | Per-iteration fairness metrics |
| `memory/memory.json` | 1.0 | Single memory entry |
| `memory/index.json` | 1.0 | Memory index |
| `log/wal_entry.json` | 1.0 | WAL entry |

## Example Files

Files ending with `.example` (e.g., `handoff.json.builder_implement.example`) are **illustrative samples**. They are not schemas.

- `*.json.example`: complete valid sample for the schema
- `*.json.<variant>.example`: sample variant (e.g., `error.json.environment_error.example` shows the `context` field for `environment_error`)

Examples are not loaded by `schema_validator.ts`.

## Compatibility Guarantee

- Minor version upgrade: old data needs no modification.
- Major version upgrade: migration function provided.
- Migration failure: HALT + write PREFLIGHT_FAIL.

## Registration

All schemas are registered with Ajv at module load time via `schema_validator.ts`. Registration uses each schema's `$id` field.

`$ref` values in schemas (e.g., `../common/handoff.json`) resolve against `$id` per JSON Schema draft-07 rules.