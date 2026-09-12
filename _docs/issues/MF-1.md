---
id: MF-1
title: MERGE-FIX: B-10 (main.py mount sequence + issue-mirror conflict with main)
depends: [B-10]
platform_issue: 60
---

# MERGE-FIX: B-10

Orchestrator dry-run of the serial merge (B-10 is `qa-passed` at
`7d22c02332534c325f79e42f7a631bda5cde10e2`, QA round 3) hit a real text conflict against
`origin/main`. Measured twice, not inferred: `git merge-tree --write-tree origin/main
origin/issue/B-10-admin-settings` exits 1, and `git merge-file --diff3` against the merge base
`f39cbf884396193896b58a86add5e69ddd6f66da` reproduces the hunks below. Per
`_docs/team/orchestrator-git.md` Sec. 5 the merge queue STOPS until the issue's own SW resolves this.

## Conflicted files (exactly two)

### 1. `backend/app/main.py` - 1 hunk, at merged-file line 429 (the `mount()` sequence)

Both sides edited the same block after the merge base.

- `origin/main` side (15 lines): keeps `admin_router.configure_limiter(limiter)` +
  `mount(admin_router.router)` and ADDS B-08's staff surface (`staff_router.configure_limiter` +
  `mount(staff_router.router)`) with its comment block.
- branch side (41 lines): REPLACES the single admin mount with TWO mounts
  (`mount(admin_router.settings_router)` + `mount(admin_router.tables_router)`, deliberately NOT
  limiter-configured) and adds the settings guest-budget exemption block plus its assert.

Required resolution is a UNION, not a pick: main's staff pair stays as-is; the single
`mount(admin_router.router)` becomes the branch's two mounts; the branch's exemption lines are kept.
B-10's own ACs pin which admin routes are reachable and that neither settings operation is subject
to the 10/min guest budget - so the branch's mount pair and exemption are load-bearing and main's
`mount(admin_router.router)` line must not be resurrected blindly. Verify the resulting route table,
do not eyeball the hunk.

### 2. `_docs/issues/B-10.md` - 3 hunks (merged-file lines 37, 241, 5690)

This is a mirror-vs-adopted-groom collision, not two different features:

- `origin/main` holds the R2 groom mirror (synced at `9125edf` from the Platform body): 2,576 lines,
  142,523 bytes, **14** AC headings, 14 graded ```bash blocks.
- The branch adopted the R2a groom (`c2f7da1` from `205788a`) and then added round notes: 3,236 lines,
  211,653 bytes, **15** AC headings, 15 graded ```bash blocks.

Resolution direction: the BRANCH revision wins the file, because every verdict B-10 carries
(SW round 3, QA round 3) was graded against the branch's 15 graded blocks and QA round 3 independently
re-derived them byte-identical to groom `205788a`. 364 lines present in main are absent from the
branch; each one must be checked, not bulk-discarded - if any is R2-only contract text that R2a
legitimately revised, say so in the deliverable instead of silently dropping it.

## Deliverable

On a branch off CURRENT `origin/main`, produce a tree where:

1. `runacs.py _docs/issues/B-10.md --cwd .` reports `== green=15 [...]` / `== red=0 []` and
   `accheck.py _docs/issues/B-10.md` reports `== 0 finding(s)`.
2. `cd backend && .venv/bin/python -m pytest tests/test_admin_settings.py -q` is green (QA round 3
   baseline: `83 passed, 2 warnings in 8.87s`).
3. `from app.main import app` imports and the resolved route table contains BOTH admin settings
   operations and main's staff table operations; assert it, do not assume it.
4. `ruff check .` clean (baseline: `All checks passed!`).
5. Whole-suite: B-17 is NOT merged yet, so `27 failed` in B-06's two public files is the PRE-EXISTING
   `origin/main` baseline. Attribute it, reproduce it on pristine `origin/main` to prove it is not
   yours, and DO NOT fix it - that is B-17's scope and B-17 is in QA right now.

## Constraints

- Resolve the two files only. No behaviour change, no AC text edits, no AC box ticking.
- Do NOT apply or remove labels; the Orchestrator owns `qa-passed` / `qa-failed` / `closed`.
- Do NOT merge to `main`, do NOT push to `main`.
- Do NOT edit `_docs/issue-map.json`.
- One pytest/python process at a time. Another QA run is active in this session right now
  (B-17 round 6, `/home/te/tq/qa-B-17-r6`); if a suite is already running, finish your own edits and
  measurement turns and only THEN run yours - never two suites at once, never `uv run --with`, never
  `-n auto`, never pipe a pytest run to `tail`/`head`, always wrap in `timeout`.
- Quote 40-hex SHAs only from your own `rev-parse` output.

## Why this happened (Orchestrator attribution)

The R2 groom was mirrored into the tracked file at `9125edf`, then the R2a groom was adopted onto the
feature branch instead of onto `main`, so the tracked mirror and the branch diverged by design and
nothing detected it until merge time. Follow-up worth its own ticket: the branch file is 211,653
bytes, above the 200,000-byte Platform body ceiling, so the Platform body for #36 cannot be brought
into sync with it - the mirror gap must be closed by a size repair, not by `set-body`.
