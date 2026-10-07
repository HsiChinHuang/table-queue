# Human Review

The human_review mechanism. Raise questions without blocking.

## Triggers

Create a human_review issue when:

1. Drift check finds AC change >= `ac_change_blocker_pct`
2. Stall detection triggers
3. Infinite loop detection triggers
4. Role cannot decide (e.g. ambiguous AC)
5. Structural problem (multiple failures unresolvable)
6. `review_plan` FAIL 3 times

## Creation Flow

### Step 1: Create Platform Issue

Run:

```
npx tsx scripts/platform.ts issue create \
  --title "[REVIEW] <issue>: <question summary>" \
  --body "<body>" \
  --labels "human_review"
```

Where `<body>` is:

```
## Question
<question description>

## Context
- Issue: <id>
- Raised by: <role> / Orchestrator
- Raised at: <UTC>

## Options
- A: <option 1>
- B: <option 2>
- C: <option 3>

## Related Files
- docs/issues/<id>.md
- docs/state/outputs/<id>_<role>_<phase>.json

## How to Respond
Post a comment on this issue with format:
    [RESPONSE] <option> <extra note>
```

The returned JSON contains the Platform issue `number`.

### Step 2: Write local mirror

Append an entry in `docs/state/questions.md` under `## Open questions`:

```markdown
### Q<n>: <title>

- **Platform Issue**: #<number>
- **Issue ID**: <id>
- **Raised at**: <UTC>
- **Raised by**: <role>
- **Status**: open

#### Question

<question description>

#### Options

- A: <option 1>
- B: <option 2>
- C: <option 3>

#### Human Response

(pending)
```

**`<n>`**: starts at 1, incremented by the current max number in `docs/state/questions.md` + 1.

### Step 3: Log WAL

```json
{"seq": 1234, "ts": "...", "level": "INFO", "issue": "t42", "event": "HUMAN_REVIEW_CREATED", "role": "orchestrator", "result": "platform_issue=#123"}
```

## Non-blocking

After creating a human_review:

- **Does NOT block** any issue
- Continue assigning other issues
- Continue other work

## Synchronization Mechanism

### Platform -> questions.md

**Trigger**: every iteration Step 2 (check human_review label).

Flow:

```
npx tsx scripts/platform.ts issue list --labels human_review --state open
-> For each returned issue:
     - number = issue.number
     - Read the latest comment:
         npx tsx scripts/platform.ts issue latest-comment <number>
     - If the latest comment's `body` starts with "[RESPONSE]" and has not
       been processed yet:
         1. Parse the response.
         2. Run the corresponding action (see `Orchestrator Read` below).
         3. Update docs/state/questions.md:
              - Move the corresponding Q<n> from "Open questions"
                to "Resolved questions"
              - Status: resolved
              - Human Response: <comment body>
              - Resolved at: <UTC>
         4. Remove the human_review label:
              npx tsx scripts/platform.ts label remove <number> --label human_review
         5. Close the Platform Issue:
              npx tsx scripts/platform.ts issue close <number>
         6. Record [HUMAN_REVIEW_RESOLVED] <issue>
```

### questions.md -> Platform

**One-way**. questions.md is a local mirror; it does not sync back to Platform.

**Reason**: Platform is the authoritative source; questions.md is only for quick human viewing.

### Conflict handling

If Platform and questions.md disagree:

- Platform wins.
- Record `[DRIFT] questions.md`.
- Auto-sync questions.md.

## Human Response

Human posts a comment on the Platform Issue:

```
[RESPONSE] A
```

Or:

```
[RESPONSE] B because <reason>
```

## Orchestrator Read

Every iteration:

1. `npx tsx scripts/platform.ts issue list --labels human_review --state open`
2. For each returned issue:
   - `npx tsx scripts/platform.ts issue latest-comment <number>`
   - If `[RESPONSE]` present and not yet processed:
     - Parse response
     - Run corresponding action
     - Update questions.md
     - `npx tsx scripts/platform.ts label remove <number> --label human_review`
     - `npx tsx scripts/platform.ts issue close <number>`
     - Record `[HUMAN_REVIEW_RESOLVED] <issue>`

## Stale Handling

**`stale` and `auto_closed` are Platform labels**, not local-only states.

If a human_review issue exists > `human_review.stale_days` (compare
`issue.updated_at` in the list output to now):

- Add the `stale` label:
  ```
  npx tsx scripts/platform.ts label add <number> --label stale
  ```
- Record `[HUMAN_REVIEW_STALE] <issue>`
- In questions.md, set `Status: stale`

If it exists > `human_review.auto_close_after_days`:

- Add `auto_closed`, remove `human_review`:
  ```
  npx tsx scripts/platform.ts label remove <number> --label human_review
  npx tsx scripts/platform.ts label add <number> --label auto_closed
  ```
- Close the Platform Issue:
  ```
  npx tsx scripts/platform.ts issue close <number>
  ```
- Record `[HUMAN_REVIEW_AUTO_CLOSED] <issue>`
- In questions.md, set `Status: auto_closed`

## Priority

| Type | Priority |
|---|---|
| Blocker | Highest (isolated issue only) |
| Human Review | Medium (non-blocking) |
| Normal Issue | Low |

**Note**: `blocker` and `human_review` are both non-blocking for the project. The difference is:

- `blocker` (typically with `isolated`) freezes a specific issue until a human resolves it; the rest of the project continues.
- `human_review` raises a question without freezing any issue; the related issue continues normally while the question is open.

Neither label pauses the whole project. Only Preflight failure (missing `requirements.md`, unrecoverable state) triggers a full HALT.

## questions.md Format

```markdown
# Questions

Local mirror. Remote counterpart is Platform issues labeled `human_review`.

Last synced: <UTC>

## Open questions

### Q1: T42 AC change too large

- **Platform Issue**: #123
- **Issue ID**: t42
- **Raised at**: 2026-10-05T16:00:00Z
- **Raised by**: orchestrator
- **Status**: open

#### Question

T42's AC was modified 60% after Verifier PASS (> ac_change_blocker_pct).

#### Options

- A: Accept the change, re-verify
- B: Reject the change, keep original AC
- C: Create a new issue for the change

#### Human Response

(pending)

## Resolved questions

### Q0: ...

- **Platform Issue**: #120
- **Issue ID**: t40
- **Raised at**: 2026-10-05T10:00:00Z
- **Raised by**: verifier
- **Status**: resolved
- **Resolved at**: 2026-10-05T11:00:00Z

#### Question

...

#### Options

...

#### Human Response

[RESPONSE] A
```

## Common human_review Scenarios

### Scenario 1: AC change too large

```
## Question
T42's AC was modified 60% after Verifier PASS (> ac_change_blocker_pct).

## Options
- A: Accept the change, re-verify
- B: Reject the change, keep original AC
- C: Create a new issue for the change
```

### Scenario 2: Undecidable AC

```
## Question
T55's AC3 is "the page looks clean", which Verifier cannot judge.

## Options
- A: Accept Verifier's SKIP verdict
- B: Human verifies manually
- C: Rewrite AC into an automatable form
```

### Scenario 3: Structural problem

```
## Question
T78 failed 5 times consecutively, failure_type is always implementation.

## Options
- A: Isolate T78, continue other issues
- B: Redefine T78
- C: Split T78 into smaller issues
```

### Scenario 4: review_plan repeated FAIL

```
## Question
phase_1_auth's review_plan FAILed 3 times consecutively.

## Options
- A: Accept current split, continue
- B: Human manually adjusts plan.md
- C: Redefine requirements.md
```