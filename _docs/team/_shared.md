# Shared Rules (all roles)

Inherit these. Role files add role-specific rules.
Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## Output protocol

Every output MUST declare:

    reached_state: <state>

If output cannot reach target state: post `[BLOCKER] <reason>` and stop.

## Standard markers

| Marker | Posted by | Purpose |
|---|---|---|
| `[BLOCKER]` | any role | Stuck, needs human |
| `[AC SUGGESTION] <text>` | SW | Propose AC change |
| `[CONSTRAINT VIOLATION REQUEST] <files> <reason>` | SW | Need to touch files outside Constraints |
| `[REQUEST_OUTPUT] <file> <start>-<end>` | any | Request externalized output range |
| `[MEMORY CONFLICT]` | SW | Two memories contradict |
| `[KEEP]` | human | Keep externalized output permanently |
| `[RESOLVED] <how>` | human | BLOCKER resolved |
| `[RECOVERY_OK]` | human | Recovery blocking cleared |
| `[ANALYZE]` | human | Trigger L3/L4 analysis |
| `[CONFIG_CHANGED_OK]` | human | Approve config change with in-flight issues |
| `[DEEP_CHAIN_OK]` | human | Allow deep dependency chain |

## Token discipline

- Single output > `[output.externalize_lines]` lines OR > `[output.externalize_tokens]` tokens: externalize.
- Externalize to `_docs/state/outputs/<issue>-<step>-<seq>.md`.
- Inline only: first 20 lines + last 20 lines + file path.
- Mark truncation: `[TRUNCATED: lines 1-20, 480-500 of 500]`.
- To read more: post `[REQUEST_OUTPUT] <file> <start>-<end>`.
- Max `[output.request_max_lines]` lines per request.

## Boundary reminder

- Read ONLY files in your role's allowed list.
- Write ONLY to files in your role's allowed list.
- Report by comment; do NOT fix others' work.
- If you see a secret in output: redact to `[REDACTED]` immediately.
- If you need a forbidden file: post `[BLOCKER]`, do NOT read it.

## CWD verification (SW/QA only)

- First action: `pwd` MUST equal your assigned worktree.
- If mismatch: post `[BLOCKER] wrong cwd`, stop.

## Universal Pre-output checklist (every role, in addition to role-specific)

- [ ] `reached_state` declared
- [ ] No other roles' work performed
- [ ] No blacklisted commands executed
- [ ] No secret leaked (tokens, keys, passwords)
- [ ] Role-specific checklist completed
- If any unchecked: post `[BLOCKER]`, do NOT finish.