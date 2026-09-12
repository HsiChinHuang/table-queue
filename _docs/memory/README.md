# Memory System

Long-term knowledge base. Only verified solutions.

Full spec: `_docs/team/orchestrator-special.md` Sec. 3.

## Quick reference

| Aspect | Value |
|---|---|
| Write trigger | retry > `[memory.write_after_retries]` |
| Read trigger | retry >= 2 |
| Read limit | `[memory.read_max]` files/session |
| Promote | `verified_count >= [memory.promote_count]` |
| Demote | `[memory.fail_delete_threshold]` fails |
| Scope | project / language / universal |
| Max size | `[memory.max_size_kb]` KB |
| Retention | `[memory.retention_days]` days |

## Structure

    _docs/memory/
    ├── README.md
    ├── index.md
    ├── candidates/      (unverified)
    ├── verified/        (validated)
    └── archive/         (older)

## File format

See `orchestrator-special.md` Sec. 3.1.

## Human override

Edit file; add `human_override: true` to disable auto.