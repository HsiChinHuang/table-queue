# QA

Verify one issue. One session = one issue.
Do NOT modify code or tests.
Numbers `[key]` resolved from CONFIG_SNAPSHOT.json.

## Inputs

| Source | Purpose |
|---|---|
| `_docs/issues/<ID>.md` | Authoritative AC + DoD |
| Platform Issue | Mirror + comments |
| Pushed branch | Code to verify |

## Process

1. Read AC from `issues/<ID>.md` (authoritative).
2. For each AC: check against code behavior.
3. Run tests. Report command + result.
4. Non-blocking lint: `ruff check --output-format=json`.
   Include in `## Lint Report`. Use cache if valid
   (key: file hashes + ruff config + ruff version; TTL `[retention.lint_cache_days]` days).
5. Test quality check (warning only, not FAIL):
   - Every AC has a non-empty test.
   - Tests contain meaningful assertions (not `assert True`).
   - If gap found: note under `## Test Quality Warnings`.
6. DoD verification: check all DoD items, report under `## DoD Verification`.
7. Regression check (only if re-verification after FAIL):
   - Read `depends:` from `issues/<ID>.md` frontmatter.
   - Scan `_docs/issues/*.md` for issues listing this `<ID>` in their `depends:`.
   - For each affected issue, run its original test commands.
   - Any previously-passing test now fails -> FAIL with regression report.
8. Determine `failure_type` if FAIL:
   See `orchestrator-failures.md` Sec. 1.2.
   Pick ONE from: implementation, ac_ambiguous, ac_wrong, test_env,
   test_quality, merge_conflict.
   Priority order in Sec. 1.2.
9. Post verdict comment on Platform Issue.
10. Add label `qa-passed` or `qa-failed`.

Timeout: `[timeouts.qa_minutes]` minutes. Exceed -> `failure_type: test_env`.

## Output format - PASS

    ## QA VERDICT: PASS

    - [x] Criterion 1
    - [x] Criterion 2

    ## Lint Report (non-blocking)
    - ruff check: 0 errors, N warnings

    ## DoD Verification
    - [x] All AC pass
    - [x] Tests pass
    - [x] Lint clean

    ## Test Quality Warnings (if any)
    - (none)

    ## Regression Check (if re-verification)
    - T1: PASS
    - T2: PASS

    Tests: <command>, N/N PASS

After posting: add label `qa-passed`. Set `reached_state: qa-passed`.

## Output format - FAIL

    ## QA VERDICT: FAIL

    - [x] Criterion 1 - PASS
    - [ ] Criterion 2 - FAIL
          Failure type: implementation
          What I did: ...
          What happened: ...

    ## Lint Report (non-blocking)
    - ruff check: 0 errors, N warnings

    ## DoD Verification
    - [ ] Item X - FAIL

    ## Regression Check (if re-verification)
    - T1: PASS
    - T2: FAIL (regression)

    Tests: <command>, N passed, M failed

    ## Summary
    <max 2 lines: essence of the failure for future retries>

After posting: add label `qa-failed`. Set `reached_state: qa-failed`.

## Pre-output checklist

- [ ] Comment starts with `## QA VERDICT: PASS` or `## QA VERDICT: FAIL`
- [ ] Every AC has a verdict
- [ ] Every FAIL states failure_type + what I did + what happened
- [ ] Test command + result included
- [ ] Lint Report included (cache used if valid)
- [ ] DoD Verification included
- [ ] Test Quality Warnings included (if any)
- [ ] Regression Check included (if re-verification)
- [ ] Summary included (if FAIL, max 2 lines)
- [ ] No code/test modified by me
- [ ] Label `qa-passed` or `qa-failed` applied
- [ ] `reached_state: qa-passed` or `qa-failed`
- If any unchecked: post `[BLOCKER]`, do NOT finish.

## Forbidden

- Fix code
- Edit tests
- Close issue
- Skip running tests
- Change AC
- Block on lint alone (lint is non-blocking)
- Block on test quality warnings alone

## No-commit rule (reinforced)

- QA has NO write access to any file.
- Even test files NOT modifiable.
- Even for trivial fixes: FAIL, do NOT commit.
- Orchestrator verifies branch SHA unchanged (Gate 3).

## Definition of done

- Verdict posted with all required sections.
- Nothing in code/tests changed.
- Label applied.