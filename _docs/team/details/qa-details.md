# QA Details

Rarely read. Referenced from `qa.md` for edge cases.

## Failure type decision tree

```
Is code behavior incorrect per AC?
  yes -> implementation
  no  -> Is AC unclear (multiple interpretations)?
           yes -> ac_ambiguous
           no  -> Is AC contradicting plan.md?
                    yes -> ac_wrong
                    no  -> Does test pass locally but fail in QA?
                             yes -> test_env
                             no  -> Check test quality
                                      hollow tests -> test_quality
                                      merge failed -> merge_conflict (Orchestrator only)
```

## Regression check: full example

Issue T55 (re-verification after FAIL).

Step 1: read `issues/T55.md` frontmatter:
```
depends: [T42, T43]
```

Step 2: scan `_docs/issues/*.md` for `depends:` containing `T55`:
- T60 depends on T55.
- T62 depends on T55.

Step 3: affected = [T42, T43, T60, T62].

Step 4: for each, read their AC and run their test commands.

Step 5: any test that previously passed now fails -> FAIL with regression list.

## Lint cache key

```
key = sha256(
  hash(all source files in branch diff)
  + hash(ruff config file)
  + ruff --version
)
```

Cache hit: reuse. Cache miss: run + store.

Cache location: `_docs/cache/lint/<key>.json`.
Cache invalidation: [retention.lint_cache_days] days or key mismatch.

## DoD verification checklist

From `issues/<ID>.md` `Definition of Done`:
- [ ] All AC pass
- [ ] Backend tests pass (`uv run pytest`)
- [ ] Frontend tests pass (`npm run test`)
- [ ] No lint errors
- [ ] PR references issue
- [ ] Manual verification completed

QA verifies each. Report in `## DoD Verification` section.

## Test quality warning examples

Warning 1:
```
def test_signup():
    assert True
```
No assertion against behavior.

Warning 2:
```
def test_signup():
    client.post("/signup", {})  # no assertion
```
Calls but doesn't check.

Warning 3:
```
def test_signup():
    assert client.post("/signup", {}).status_code == 200  # happy path only
```
Missing error path.

These are warnings, not FAILs (unless egregious).

## Output example (PASS, full)

```
## QA VERDICT: PASS

- [x] POST /signup creates user - PASS
- [x] Duplicate email shows error - PASS

## Lint Report (non-blocking)
- ruff check: 0 errors, 2 warnings (unused imports in views.py)

## DoD Verification
- [x] All AC pass
- [x] Tests pass
- [x] Lint clean
- [x] PR references issue

## Test Quality Warnings
- (none)

Tests: `uv run pytest tests/test_auth.py`, 12/12 PASS
```

## Output example (FAIL, full)

```
## QA VERDICT: FAIL

- [x] POST /signup creates user - PASS
- [ ] Duplicate email shows error - FAIL
      Failure type: implementation
      What I did: POSTed existing email
      What happened: 500 error, no visible error message

## Lint Report (non-blocking)
- ruff check: 0 errors, 0 warnings

## DoD Verification
- [x] AC1 pass
- [ ] AC2 fail
- [x] Tests pass

## Regression Check
- T42: PASS
- T43: PASS

Tests: `uv run pytest`, 18 passed, 0 failed

## Summary
Duplicate email not handled; 500 instead of 400.
```

## When to refuse to PASS

- Any AC untested.
- Any AC behavior not matching description.
- Any regression in dependent issues.
- Any DoD item that cannot be verified.