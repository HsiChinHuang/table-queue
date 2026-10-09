# Tooling contract: ready.py readiness computation

Tooling note for the out-of-repo readiness tool at
`../.tq-orchestrator/ready.py` (sibling of the repo root).

**Status (2026-10-09):** the `.tq-orchestrator/` directory is ABSENT on this
host (verified by recursive search). The ready.py patch is DEFERRED to an
operator follow-up item; this document pins the contract so that patch is
mechanical. Tracked by issue t28 (platform #83).

## Algorithm (normative)

Given:

- `issue-map.json` — maps local issue id → platform issue number
  (repo copy: `_docs/issue-map.json`).
- platform state — platform issue number → `open` | `closed`.
- dep-map — local issue id → list of dependency ids.

1. **closed-set** = { id | id is in `issue-map.json` AND the platform state of
   `issue-map[id]` is `closed` }. This is the ONLY source of "closed".
2. Readiness is NEVER computed from issue titles: no title regex, no
   bracket/`[x]` parsing, no title-derived state of any kind.
3. For every id not in closed-set:
   - if any dependency is missing from the dep-map (or its state is
     unresolvable), report that single issue as `UNKNOWN-deps` and CONTINUE —
     all other issues keep evaluating. A dep-map gap must never abort the
     whole run.
   - otherwise the issue is `READY` iff all its dependencies are in
     closed-set, else `WAITING`.

## Regression scenario (observed reopens)

The old title-regex implementation listed these issues as ready while they
were closed on the platform (SA-era unbracketed titles defeated the regex):

| id   | platform # | platform state | old tool output |
|------|-----------|----------------|-----------------|
| B-15 | #47       | closed         | ready (WRONG)   |
| F-16 | #48       | closed         | ready (WRONG)   |
| P0-16| #49       | closed         | ready (WRONG)   |
| P0-13| #46       | closed         | ready (WRONG)   |

Under this contract all four are in closed-set and can never appear as ready,
regardless of title.

## Verification

Self-contained offline fixture (Python 3 stdlib only):

```
python3 tests/ready_contract/ready_fixture.py --case closed-bare-title
python3 tests/ready_contract/ready_fixture.py --case dep-gap
python3 tests/ready_contract/ready_fixture.py --case all
```

Exit 0 = contract holds; non-zero = violation.
