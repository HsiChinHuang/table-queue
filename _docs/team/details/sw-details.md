# SW Details

Rarely read. Referenced from `sw.md` for edge cases.

## Large diff splitting example

Issue T42: Files = `a.py, b.py, c.py, d.py, e.py`.
Estimated diff > [output.diff_split_lines] lines.

Orchestrator splits:
- Session 1: a.py, b.py -> commit
- Session 2: c.py, d.py -> commit
- Session 3: e.py -> commit
- Session 4: run tests, post comment, label `qa-ready`.

Each session is a fresh SW subagent.

## Memory reading (when `read_memory: true`)

Inputs:
- `memory_paths: [list of file paths]`

Process:
1. Read each file.
2. If two memories contradict: post `[MEMORY CONFLICT]`.
3. Apply only relevant ones.
4. In final comment: list applied memory IDs.

## Memory lifecycle

- Applied + QA PASS -> orchestrator increments `verified_count`.
- Applied + QA FAIL -> orchestrator decrements, marks `[FAILED USE]`.
- 3 consecutive FAILED USE -> deleted by orchestrator.
- Not applied: no change.

## FAIL history usage

Input:
- `failure_history: {recent_summaries: [...], latest_full: "..."}`

Process:
1. Read latest full FAIL first.
2. Read recent summaries to avoid repeating mistakes.
3. Comment must state: `Addressed prior FAIL: <what>`.

## Permission violation examples

If you see yourself about to run:
- `sudo ...` -> STOP
- `rm -rf /` or `rm -rf ~` -> STOP
- `cat ~/.ssh/id_rsa` -> STOP
- `env` or `printenv` -> STOP
- `git push --force` -> STOP
- `curl http://...` (non-platform) -> STOP

Instead: post `[BLOCKER] <reason>`.

## Output externalization examples

Trigger:
- Diff > 50 lines.
- Test output > 50 lines.
- Full reasoning > 1000 tokens.

Action:
- Write full to `_docs/state/outputs/<ID>-sw-<seq>.md`.
- Comment includes:
  - First 20 lines
  - Last 20 lines
  - `[TRUNCATED: lines 1-20, 480-500 of 500]`
  - Path to file.

To request more later: `[REQUEST_OUTPUT] <file> <start>-<end>`.

## Test quality minimum

Per AC: ≥ 1 test with meaningful assertion.

Bad:
```
def test_user(): assert True
```

Good:
```
def test_user_email_unique():
    User.objects.create(email="a@x.com")
    with pytest.raises(IntegrityError):
        User.objects.create(email="a@x.com")
```

## Common pitfalls

| Pitfall | Avoid |
|---|---|
| Editing AC | Only PM edits AC |
| Closing issue | Only Orchestrator closes |
| Skipping tests | Every AC needs a test |
| Pushing to main | Push only own branch |
| Reading `_docs/state/` | Forbidden |

## When AC is impossible

Post `[AC SUGGESTION]` with reasoning.
Do NOT block. Continue implementing your best interpretation.
Do NOT silently change AC.