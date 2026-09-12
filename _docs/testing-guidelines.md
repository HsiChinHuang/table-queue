# Testing Guidelines

## Commands

Defaults per tech-stack in `plan.md`.

Python:
- All: `uv run pytest`
- One file: `uv run pytest tests/test_<name>.py`
- One test: `uv run pytest tests/test_<name>.py::<Class>::<test> -v`
- Linter (SW): `ruff check --fix`
- Linter (QA): `ruff check --output-format=json`

## Test structure

- Tests live in `tests/` (or per project convention in `plan.md`).
- One file per module: `test_<module>.py`.
- Group related tests: `class Test<Module>`.
- Test names describe behavior: `test_<action>_<expected>`.

## Per-AC requirement

Every acceptance criterion MUST have ≥ 1 test with a meaningful assertion.

Good:
```
def test_signup_duplicate_email():
    User.objects.create(email="a@x.com")
    with pytest.raises(IntegrityError):
        User.objects.create(email="a@x.com")
```

Bad:
```
def test_signup(): assert True
```

## Isolation (parallel worktrees)

Each worktree uses independent test environment:

| Resource | Pattern |
|---|---|
| Test DB | `test_<ISSUE_ID>` |
| Test port | `5000 + (hash(ISSUE_ID) % 1000)` |
| Temp dir | `/tmp/agent-<ISSUE_ID>/` |

Rationale: 3 parallel SW sessions must not collide.

## Affected-module test selection

For merge-time testing (not QA):

1. Compute branch diff: `git diff main..issue/<ID>-<slug> --name-only`.
2. Identify modules touched.
3. Run tests for those modules + their direct dependents.
4. Plus smoke tests (below).

## Smoke tests

Defined per project. Minimum 10, maximum 20.

Recommended scope:
- Core model creation.
- Critical user paths (signup, login, main action).
- Integration between 2+ modules.

Location: `tests/smoke/` or equivalent.

## Full suite triggers

Run FULL suite when:
- First merge ever.
- Every [merge.full_suite_every]th merge (counter in `state/seq.txt` modulo).
- `plan.md` explicitly requires it.

## Regression testing (QA)

When QA re-verifies after FAIL:
- Read `issues/<ID>.md` frontmatter `depends:`.
- Scan `issues/*.md` for issues that list this ID in their `depends:`.
- Run each affected issue's test commands.
- Any previously-passing test now fails = regression.

## Lint

- Non-blocking for QA verdict.
- Cached with key: `sha256(file hashes + ruff config + ruff version)`.
- Cache location: `_docs/cache/lint/`.
- TTL: [retention.lint_cache_days] days.
- Cache file permissions: read-only after write.

## Coverage

No hard coverage threshold.
Quality over quantity: every AC has a test.

## Common mistakes

| Mistake | Fix |
|---|---|
| Test with `assert True` | Add real assertion |
| Happy path only | Add error path |
| Test hitting external API | Mock or skip |
| Shared DB across worktrees | Use isolated DB |
| Test dependent on order | Use fixtures |