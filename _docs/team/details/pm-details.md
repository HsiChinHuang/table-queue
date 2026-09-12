# PM Details

Rarely read. Referenced from `pm.md` for edge cases.

## Example: refined AC

Before (SA draft):
- [ ] User can signup.

After (PM refined):
- [ ] POST /signup with valid data creates User + redirects to /dashboard.
- [ ] POST /signup with duplicate email returns 400 + shows inline error.
- [ ] POST /signup with missing field returns 400 + lists missing fields.
- [ ] Empty / loading / error UI states are visible.

## Common grooming mistakes

| Mistake | Fix |
|---|---|
| AC uses vague words ("robust", "good") | Replace with checkable behavior |
| AC has no error cases | Add failure-path ACs |
| AC has no edge cases | Add empty/loading/error |
| Goal describes implementation | Move to Context |
| Out of scope lists things already done | Remove or move to follow-up |

## Handling dependency unmet

- Add under `Out of scope`:
  - `- Blocked by #42 (T5): <reason>`
- Do NOT remove the AC. Do NOT re-scope.
- PM continues grooming.

## Trigger: AC SUGGESTION

SW comment format:
```
[AC SUGGESTION] Change AC2 from "X" to "Y" because <reason>.
```

PM decision options:
- Accept: update AC in both files. Comment with rationale.
- Reject: comment with rationale. SW continues original AC.
- Modify: propose alternative in comment. Requires SW agreement (SW re-confirms).

## Trigger: CONSTRAINT VIOLATION REQUEST

SW comment:
```
[CONSTRAINT VIOLATION REQUEST] Need to change files: users/views.py
Reason: <reason>
```

PM decision:
- Accept: update `Constraints` in both files.
- Reject: comment with rationale. SW must stay within original.

## Trigger: QA FAIL with ac_ambiguous / ac_wrong

1. Read failing AC.
2. Read original plan.md entry for this issue.
3. Clarify (if ambiguous) OR correct (if wrong).
4. Update both files.
5. Comment: `Re-groomed: <change>. Reason: <QA failure summary>`.
6. Reset state.

## Section ownership reminders

PM MUST NOT fill:
- `Test requirements` (SW)
- `Implementation notes` (SW)

PM MUST fill:
- `Context`
- `Acceptance criteria` (refined)
- `Out of scope`
- `Definition of Done` (issue-specific parts)

## Out of scope → follow-up issue

When moving something out:
1. Create pending request: `_docs/issues/pending/<uuid>.md`.
2. In `Out of scope`: `- <item> -> pending/<uuid>`.
3. Orchestrator will formalize into a new issue.