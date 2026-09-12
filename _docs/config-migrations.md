# Config Migrations

Tracks changes to `config.yaml` schema.

## Current version

`config_version: 1`

## How to migrate

1. Read the "Migration" section for your source version.
2. Edit `config.yaml`.
3. Bump `config_version`.
4. Restart Orchestrator.

## Version history

### v1 (initial)

No migration needed. Baseline.

## Future migrations

Append here when schema changes.

Template:

    ### vN -> vN+1

    - Renamed: `<old>` -> `<new>`
    - Added: `<key>` (default: `<value>`)
    - Removed: `<key>`
    - Semantics: <what changed>