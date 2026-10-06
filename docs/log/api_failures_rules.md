# API Failures Logging Rules

Write rules for `docs/log/api_failures.md`.

## Writer

**Only Orchestrator**.

Subagents do not write to this file.

## Triggers

Write when:

1. Platform API returns 5xx (after 3 retries fail).
2. Platform API returns 4xx (except 404).
3. Network timeout (after 3 retries).
4. Rate limit exceeds Retry-After ceiling.

**Do NOT write**:

- 404 (issue not found) → write `[PLATFORM_GONE]` WAL, not this file.
- 429 (rate limit) → auto-backoff, not this file.

## Format

    [SEQ] [TS] [ENDPOINT] [STATUS] [RETRY_COUNT] [NOTE]

Examples:

    [1234] [2026-10-05T16:00:00Z] [/repos/owner/repo/issues] [503] [3] [Service unavailable]
    [1235] [2026-10-05T16:01:00Z] [/repos/owner/repo/issues/42] [500] [3] [Internal server error]

## Fields

| Field | Description |
|---|---|
| `SEQ` | WAL sequence number |
| `TS` | ISO 8601 UTC |
| `ENDPOINT` | API path |
| `STATUS` | HTTP status code |
| `RETRY_COUNT` | Number of retries |
| `NOTE` | Short description |

## Retention

Permanent.

## Reading

Human-readable. No automation reads this file.

## Relation to WAL

Each write to `api_failures.md` also writes a WAL entry:

```json
{"seq": 1234, "ts": "...", "level": "ERROR", "issue": null, "event": "API_FAILURE", "role": "orchestrator", "result": "endpoint=/repos/..., status=503"}
```