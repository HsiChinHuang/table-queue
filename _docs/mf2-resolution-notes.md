# MF-2 resolution notes (Orchestrator measured evidence, rehearsal scratch)

Issue: MF-2 #63. Not a contract — the AC blocks in MF-2.md govern. This file records what was
MEASURED so the lane does not re-derive it. All commands run in scratch trees; main checkout
untouched (porcelain 0 after every step).

## 1. The real merge produces TWO conflict regions, not one

Self-correction of the scaffold (which showed one diff3 hunk): `git merge --no-commit --no-ff
04291af70d39d123351ed4fc7531359cea3c95da` at main `292adcc` leaves `_docs/testing.md` with
markers at L57-75 **and** L82-92 — `merge-file --diff3` had aligned the two edits into one hunk.
Both regions are inside the `### Structure` tree listing; nothing else conflicts.

## 2. Tree-fact audit (measured)

- `backend/tests/` on disk (both parents identical): `__init__.py`, `conftest.py`,
  `public_fixtures.py`, and exactly **19** `test_*.py` files.
- `factories.py` appears in main's Structure tree and **exists in NO git commit ever**
  (`git log --all --oneline -- backend/tests/factories.py` -> empty). It is the B-17-series
  aspiration; B-14's merged prose paragraph (auto-merged, do not touch) already documents it as
  such ("there is no `factories.py`").
- `test_state_machine.py` — fictional by the B-14 round-4 ruling; in no tree.
- The `<<<<<<< HEAD` side of region 1 carries `factories.py` + non-alphabetical order; the
  `=======` side (B-14) carries `public_fixtures.py` + 4 test names alphabetical.

## 3. Rehearsed resolution — PROVEN GREEN on the resolved merged tree

Union = keep `public_fixtures.py` (real), drop `factories.py` (fiction) from the Structure tree,
list all 19 test files alphabetically (T7 AC-3 requires alphabetical? No — it requires the exact
name set; the merged listing below happens alphabetical, matching both sides' convention):

```text
backend/tests/
├── conftest.py
├── public_fixtures.py
├── test_admin_reset.py
├── test_admin_settings.py
├── test_admin_tables.py
├── test_auth.py
├── test_config.py
├── test_dependencies.py
├── test_errors.py
├── test_health.py
├── test_middleware.py
├── test_models.py
├── test_public_board.py
├── test_public_waitlist.py
├── test_schemas.py
├── test_seed.py
├── test_staff_dashboard.py
├── test_staff_tables.py
├── test_staff_waitlist.py
├── test_startup.py
└── test_startup_bootstrap_settings.py
```

(Exact patch against main: `/home/te/tq/mf2-rehearsal` scratch commit `rehearsal: resolve
testing.md hunk (real-file union)` — scratch is disposable; facts above are the durable record.
`git -C /home/te/tq/mf2-rehearsal show HEAD -- _docs/testing.md` regenerates the diff.)

Measured on the rehearsal tree (B-14's AC file copied from 04291af as `_b14check.md`):

    runacs _b14check.md --only AC-4  -> PASS AC-4: actual=258; every collected ... == green=1 red=0
    runacs closed/T7.md --only AC-3  -> PASS AC-3: testing.md names exactly the 19 ... == green=1 red=0
    runacs _b14check.md (full)       -> == green=8 ['AC-1'..'AC-8'] == red=0 []

Gate env: `TMPDIR=/home/te/tq/pytest_tmp TZ=UTC DATABASE_URL=sqlite:////home/te/tq/mf2r.db
JWT_SECRET=x STAFF_PIN=0000 ENV=test`, interpreter `backend/.venv/bin/python`.

## 4. What "keeping both sides" means here, measured

- B-14's substantive addition is the `### Test-file inventory (mirrors the collected set)` section
  (flat 19-name list) — it sits OUTSIDE the conflicted regions and lands automatically.
- T7's substantive belt is AC-3's exact-19-name equality — satisfied by the listing above.
- The old main-side tree lines the resolution drops (`factories.py`, non-alphabetical order) are
  NOT belt-checked content: AC-3 compares the NAME SET against disk, and `factories.py` is not on
  disk. Dropping fiction from a listing that claims to mirror the tree is the resolution, not a
  side's loss.
