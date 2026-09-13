---
id: MF-2
title: MERGE-FIX: B-14 (testing.md test-file listing conflict with the merged T7)
depends: [B-14, T7]
platform_issue: 63
---

# MERGE-FIX: B-14

## Metadata

- **Phase**: phase-2-backend
- **Type**: chore
- **Area**: docs+tests
- **Size**: S
- **Milestone**: Phase 2 - Backend tests

## Goal

Land B-14 on `main` with a content-resolved `_docs/testing.md` that keeps BOTH sides of the one
colliding region: T7's 19-name `### Structure` tree (the disk truth T7 AC-3 verified) and B-14's
new `### Test-file inventory` flat list, with the fictional `test_state_machine.py` present in no
listing. When this is done, the merged tree's doc<->disk and doc<->collected belts are all green at
the same time - a claim neither side proves alone - the serial merge queue (5.2) restarts, and the
merge commit carries B-14's green gate with it. This is a resolution task, not a product task: no
behaviour, no test file and no other document changes; the only new claim is that both sides'
substantive content survives together.
## Context

B-14 is `qa-failed` by merge-conflict invalidation (5.8, comment 5650196274 at #40), NOT by a
verdict reversal — QA round 1's PASS 8/8 at tip `04291af70d39d123351ed4fc7531359cea3c95da` stands
as the content judgment. The serial merge queue is stopped (5.2) until this issue passes.
This is a resolution task, not a product task: everything is already proved on one side; the only
new claim is that both sides survive together.

- Related: #40 (B-14), #59 (T7, closed, merged at 50012be01b258fa63d57724d384095a2bfe75dda), precedent MF-1 #60
- Worktree per 5.4: `/home/te/tq/sw-B-14-r1` REUSED (verified clean porcelain=0, tip 04291af); new branch `issue/MERGE-FIX-B-14-testing-md` cut at origin/main AT LANE START (currently 292adcc — MUST contain merged T7); B-14's commits apply on top (`git merge issue/B-14-backend-tests` or cherry-pick 080ba69..04291af, lane's choice, then resolve).
- B-14 branch retained untouched on remote per 3.3; never force-push.

## Conflicted files (exactly one)

`_docs/testing.md`. Measured twice: dry-run `git merge --no-commit --no-ff 04291af` at main 292adcc
-> `CONFLICT (content)`; 4.7 whitespace retry `-Xignore-all-space` -> same conflict. `merge-file
--diff3` reproduces EXACTLY ONE HUNK at the `## Structure` tree listing (measured file sizes:
base 21,330 B @08dfebc; main-side 21,585 B @292adcc (+12/−3, T7's 19-name real listing);
B-14-side 24,170 B @04291af (+54/−10, a new `### Test-file inventory` section AND an 8-name tree)).

The hunk (diff3: ours=main/T7 | base | theirs=B-14):

```text
<<<<<<< ours (main, merged T7 — 16 visible entries of the 19-name listing)
├── test_staff_waitlist.py
├── test_staff_tables.py
├── test_admin_settings.py
├── test_admin_tables.py
├── test_admin_reset.py
├── test_seed.py
├── test_staff_dashboard.py
├── test_config.py
├── test_dependencies.py
├── test_errors.py
├── test_health.py
├── test_middleware.py
├── test_models.py
├── test_schemas.py
├── test_startup.py
└── test_startup_bootstrap_settings.py
||||||| base (08dfebc — 7 entries incl. the FICTIONAL test_state_machine.py)
├── test_staff_waitlist.py
├── test_staff_tables.py
├── test_staff_dashboard.py
├── test_admin_settings.py
├── test_admin_tables.py
├── test_state_machine.py
└── test_seed.py
=======
(theirs, B-14: 8-entry alphabetical tree — test_public_waitlist/schemas/seed/staff_dashboard/
 staff_tables/staff_waitlist/startup/startup_bootstrap_settings; exact bytes at
 /home/te/tq/boot5/mf-evidence/hunk.diff3)
>>>>>>> theirs (B-14)
```

Resolution background (Orchestrator's measured view, PM may re-rule):

1. Post-merge reality is EXACTLY 19 real `test_*.py` files — B-14 added no new file (QA measured
   258 collected across 19 modules at the tip); `test_state_machine.py` stays FICTIONAL by the B-14
   round-4 ruling (Out of scope; AC-7's internal guard fires the moment it is collected).
2. T7's merged listing is the 19-name truth T7 AC-3 verified against disk; B-14's new
   `### Test-file inventory` flat list already names all 19 (the tree hunk is its stale 8-entry
   half). Keeping BOTH sides' substantive content plausibly means: T7's tree listing + B-14's new
   inventory section, and dropping the fictional name. QA's AC-4 both-direction `comm` proof at the
   tip used the doc's flat list vs the collected set; the merged doc must keep BOTH belts green:
   T7 AC-3 ('testing.md names exactly the 19 test_*.py files present') AND B-14 AC-4
   (every collected module named, every named file collected).
3. Do NOT touch: `_docs/issues/T7.md` or `closed/T7.md` (T7's frozen gates), `backend/app/main.py`
   (3rd-entry HOT_FILE per 4.9 — this conflict has nothing to do with it), `_docs/issues/B-14.md`
   except its Test requirements report sections, `_docs/testing.md` content OUTSIDE the
   inventory/Structure region (B-17 #58 owns the plugin-removal paragraph; both sides already
   agree on it — measured: that region auto-merged).

## Acceptance criteria

Per 5.3 this set is the union of the conflicting issues' relevant gates - the ones that MUST be
green on the merged tree: B-14 AC-1 (full suite) -> AC-1 here; B-14 AC-4 (doc<->collected, both
directions) -> AC-2 here; T7 AC-3 (testing.md names exactly the files on disk) -> AC-3 here; the
kept-content half of the resolution (inventory section + full tree, fictional name in no listing)
-> AC-4 here; B-14 AC-3 (ruff clean) -> AC-5 here. T7 AC-8 is NOT applicable to this lane: it
audits paths, and this lane exists to change `testing.md`'s inventory region, which its own scope
statement excludes.

Every block is a gate per `_docs/testing.md` section 9: Rule 1 (exactly one verdict token, PASS and
FAIL branches both print), Rule 2 (each guard can reach the path it names) and Rule 3 (the wrapped
tool's exit status is captured, not inferred). No block sets `-e` or `-o pipefail`: a SIGPIPE
through a truncating consumer yields a false FAIL exit code. Where a block pipes a run into
`tail`, it writes the full output to a log first and reads `RC=${PIPESTATUS[0]}` in its own
statement (section 9, Anti-pattern 3).

**Groom-branch state, stated honestly.** AC-1, AC-3 and AC-5 are green right now at plain `main`
`4f5070b`, measured under each block. AC-2 and AC-4 go green only on the **resolved merged tree**,
which is SW's deliverable; at plain `main` their blocks print FAIL **by construction** (main names
the fictional `test_state_machine.py` in section 8, so AC-2's `named-not-collected` arm is
necessarily non-empty; main has no inventory section, so AC-4's arm (a) is necessarily red). That
red on this groom branch is the accepted B-14 round-4 precedent, not a defect of this groom, and QA
must not read it as one.
- [ ] **AC-1** The whole backend suite is green on the merged tree with the ordering pin the
  Ordering-pin section demands: a suite-wide run that names no path, run as
  `backend/.venv/bin/python -m pytest -q -p no:randomly`, exits 0 and reports **258 passed**. 258 is
  what QA measured for B-14 at tip `04291af` and what this groom measures at plain `main` `4f5070b`;
  B-14 adds no test file, so the merge must not move the number in either direction. The exit status
  is captured and branched on, not inferred from the summary line. Green = `PASS AC-1`.

  Measured today (at `4f5070b`, gate env, TMPDIR=/home/te/tq/pm-MF-2-r1, TZ=UTC): the block prints
  `PASS AC-1: full suite green, 258 passed (expected 258)`; the raw tail of the same run is
  `258 passed, 3 warnings in 63.76s (0:01:03)`.

  ```bash
  OUT=$(backend/.venv/bin/python -m pytest -q -p no:randomly 2>&1 | tee /tmp/mf2-ac1.log | tail -3); RC=${PIPESTATUS[0]}
  COUNT=$(printf '%s\n' "$OUT" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+')
  if [ "$RC" -eq 0 ] && [ "${COUNT:-0}" -eq 258 ]; then
    echo "PASS AC-1: full suite green, ${COUNT} passed (expected 258)"
  else
    echo "FAIL AC-1: rc=${RC} passed=${COUNT:-none}; expected rc=0 and 258 passed - full output at /tmp/mf2-ac1.log"
  fi
  ```

- [ ] **AC-2** B-14's doc<->collected belt holds on the merged doc in BOTH directions, the way QA
  proved it at B-14's tip: every `test_*.py` module that
  `backend/.venv/bin/python -m pytest --collect-only -q -p no:randomly` collects is named in
  `_docs/testing.md`, and every `test_*.py` name `_docs/testing.md` carries is collected. Both
  `comm` halves must be empty, and a `doc_named >= 10` guard rides along so a doc that names nothing
  cannot pass vacuously. The doc set is every `test_*.py` token anywhere in the file (both the
  `### Structure` tree and the `### Test-file inventory` list), because the merged doc must agree
  with the collected set everywhere it names a file - which is precisely why main is red today and
  why B-14's round-4 rewrite of section 8 matters: at `4f5070b` section 8 still contains the command
  line `uv run pytest tests/test_state_machine.py -v`, a whole-token mention of the FICTIONAL module
  outside any listing section. The resolution must land a doc that names exactly the collected 19
  and nothing else; B-14's side already does it that way (measured below).
  Green = `PASS AC-2`, carrying both counts; red names which direction drifted.

  Measured today (at `4f5070b`, plain `main`, before any merge; the block's own arms, not a
  paraphrase): `collect_rc=0`, collected stems 19, `doc_named=20`, and the block prints
  `FAIL AC-2: collected-not-named=0: ; named-not-collected=1: state_machine ; doc_named=20`.
  Expected red at plain main, by construction: main names 19 real modules plus the fictional one.
  Green-capability preflight (so the block is known able to pass before SW touches anything), the
  same block with the doc argument pointed at B-14's own `_docs/testing.md` (the `04291af` blob,
  measured 24,170 bytes) against this worktree's collected set, prints
  `PASS AC-2: both directions empty - collected=19 modules, doc_named=19 names`.
  Falsification controls (section 9 Rule 2): (1) with the doc set taken from the conflict's
  ours-plus-base hunk text (the `hunk.diff3` sides measured, 17 distinct stems after the block's own
  regex), both drift directions report at once:
  `FAIL AC-2: collected-not-named=3: auth public_board public_waitlist ; named-not-collected=1: state_machine ; doc_named=17`;
  (2) the vacuity guard fires on its own for a 3-name doc:
  `FAIL AC-2: doc set too small to prove anything - doc_named=3, requires >= 10 (collected=19)`.
  Control docs were scratch files inside this worktree, deleted before the commit.

  ```bash
  backend/.venv/bin/python -m pytest --collect-only -q -p no:randomly > /tmp/mf2ac2-collected.txt 2>&1; RC=$?
  if [ "$RC" -ne 0 ]; then
    echo "FAIL AC-2: pytest --collect-only exit=${RC} - see /tmp/mf2ac2-collected.txt"
    exit 0
  fi
  grep -oE 'test_[A-Za-z0-9_]+\.py' /tmp/mf2ac2-collected.txt | sed 's#^test_##; s#\.py$##' | sort -u > /tmp/mf2ac2-collected.names
  python3 - "${1:-_docs/testing.md}" > /tmp/mf2ac2-doc.names <<'PY'
  import io, re, sys
  t = io.open(sys.argv[1], encoding='utf-8').read()
  print('\n'.join(sorted(set(re.findall(r'test_([A-Za-z0-9_]+)\.py', t)))))
  PY
  DOC=$?
  if [ "$DOC" -ne 0 ]; then
    echo "FAIL AC-2: the testing.md name probe could not run (exit ${DOC})"
    exit 0
  fi
  COL_N=$(grep -c . /tmp/mf2ac2-collected.names); DOC_N=$(grep -c . /tmp/mf2ac2-doc.names)
  A_N=$(comm -23 /tmp/mf2ac2-collected.names /tmp/mf2ac2-doc.names | grep -c .)
  B_N=$(comm -13 /tmp/mf2ac2-collected.names /tmp/mf2ac2-doc.names | grep -c .)
  A=$(comm -23 /tmp/mf2ac2-collected.names /tmp/mf2ac2-doc.names | tr '\n' ' ')
  B=$(comm -13 /tmp/mf2ac2-collected.names /tmp/mf2ac2-doc.names | tr '\n' ' ')
  if [ "$DOC_N" -lt 10 ]; then
    echo "FAIL AC-2: doc set too small to prove anything - doc_named=${DOC_N}, requires >= 10 (collected=${COL_N})"
  elif [ "$A_N" -eq 0 ] && [ "$B_N" -eq 0 ]; then
    echo "PASS AC-2: both directions empty - collected=${COL_N} modules, doc_named=${DOC_N} names"
  else
    echo "FAIL AC-2: collected-not-named=${A_N}: ${A}; named-not-collected=${B_N}: ${B}; doc_named=${DOC_N}"
  fi
  ```

- [ ] **AC-3** T7's belt, restated here as an executable check: `_docs/testing.md`'s
  `### Structure` listing for `backend/tests/` names **exactly** the `test_*.py` files present in
  that directory - count equality AND name equality, red in both drift directions
  (listed-but-absent, present-but-unnamed). The block hardcodes no count; 19 is what it reports when
  the two sets agree. SW must ALSO re-run T7 AC-3 verbatim from the frozen
  `_docs/issues/closed/T7.md` copy as cross-check, so this restatement cannot silently weaken it.
  Green = `PASS AC-3`.

  Measured today (at `4f5070b`): the block prints
  `PASS AC-3: testing.md names exactly the 19 test_*.py files present in backend/tests, no more and no less`.
  Falsification control (section 9 Rule 2), same block run against a doc whose `### Structure`
  region is replaced by the 8-entry tree half of the hunk - the base-minus-hunk construction, i.e.
  main's doc with only that region swapped for the theirs side measured at
  `/home/te/tq/boot5/mf-evidence/hunk.diff3`: it prints
  `FAIL AC-3: testing.md names 8 test files and backend/tests holds 19; present but not named: test_admin_reset, test_admin_settings, test_admin_tables, test_auth, test_config (+6 more); named but absent from backend/tests: none`.
  The block is the T7 AC-3 block (identical probe, identical verdict strings); note T7's frozen copy
  carries a duplicated `def head` line, harmless and left as frozen. Run the probe with
  `python3 - <<'PY'`, not `python3 -c`.

  ```bash
  python3 - <<'PY' || echo "FAIL AC-3: the testing.md list probe could not run"
  import io, os, re
  src = io.open('_docs/testing.md', encoding='utf-8').read().replace('\r\n', '\n')
  sec = re.search(r'(?m)^### Structure\s*$(.*?)(?=^#{2,3} |\Z)', src, re.S)
  if not sec:
      print('FAIL AC-3: testing.md has no Structure section to compare against the disk')
      raise SystemExit
  listed = set(re.findall(r'(test_\w+)\.py', sec.group(1)))
  on_disk = set(f[:-3] for f in sorted(os.listdir('backend/tests')) if re.fullmatch(r'test_\w+\.py', f))
  missing = sorted(listed - on_disk)
  unnamed = sorted(on_disk - listed)
  def head(names):
      return 'none' if not names else ', '.join(names[:5]) + (' (+' + str(len(names) - 5) + ' more)' if len(names) > 5 else '')
  bad = []
  if missing:
      bad.append('listed but absent from backend/tests: ' + head(missing))
  if unnamed:
      bad.append('present but not named in the listing: ' + head(unnamed))
  print('FAIL AC-3: testing.md names ' + str(len(listed)) + ' test files and backend/tests holds '
        + str(len(on_disk)) + '; present but not named: ' + head(unnamed)
        + '; named but absent from backend/tests: ' + head(missing) if bad else
        'PASS AC-3: testing.md names exactly the ' + str(len(on_disk))
        + ' test_*.py files present in backend/tests, no more and no less')
  PY
  ```

- [ ] **AC-4** The resolution kept BOTH sides' substantive additions and nothing fictional. Four
  arms, each named in the FAIL line so a reader can see which side was dropped:
  (a) `_docs/testing.md` contains a heading matching `^### Test-file inventory` - B-14's flat list,
  the half a wholesale `--ours` would destroy; note B-14 ships that heading with a suffix
  (`### Test-file inventory (mirrors the collected set)`, measured in the `04291af` blob), which is
  why the arm is a prefix match and not an exact-string match;
  (b) that inventory names exactly the `test_*.py` files on disk;
  (c) the `### Structure` tree names exactly the `test_*.py` files on disk - T7's half, which a
  wholesale `--theirs` would destroy;
  (d) the FICTIONAL `test_state_machine.py` appears in NEITHER listing section (arm (a)'s inventory
  arm is skipped, not silently passed, when the section is absent).
  Green = `PASS AC-4`.

  Measured today (at `4f5070b`, plain `main`): the block prints
  `FAIL AC-4: inventory heading MISSING (arm a: no line matching ^### Test-file inventory - B-14's flat list was dropped or renamed)`,
  and the arm values behind it are `tree names 19 of 19 on disk (arm c green on main); fictional in
  structure=False; fictional anywhere in the doc=True - section 8's command line, which arm (d)
  deliberately does not read`. Expected red at plain main, by construction: main has no inventory.
  Controls (section 9 procedure: one red tree, one green tree, all scratch files inside this worktree
  and deleted before the commit):
  (1) green-capability, run against B-14's `_docs/testing.md` as a blob (the `04291af` side, fetched
  byte-identical from `/home/te/tq/boot5/mf-evidence/testing.b14.md`, measured 24,170 bytes, matching
  this worktree's 19 `backend/tests` entries) - its inventory heading is the suffixed
  `### Test-file inventory (mirrors the collected set)`, which is exactly why arm (a) is a prefix
  match - and the block prints
  `PASS AC-4: inventory section present with exactly the 19 files on disk; the structure tree names the same 19; test_state_machine.py appears in neither listing`
  - B-14's side alone already satisfies AC-4's four arms, so the merge only has to not destroy it;
  (2) can-fail, run against a doc holding the hunk's 8-entry tree plus a 3-name inventory: all three
  content arms report at once, `FAIL AC-4: arm b: inventory names 3 files, disk holds 19;
  missing=...; extra=none; arm c: structure names 9 of the 19 files on disk; missing=...;
  extra=test_state_machine.py; arm d: test_state_machine.py still listed in structure`;
  (3) the same verdict strings reproduce on a fabricated T7-tree + 19-name-inventory doc as the
  `PASS AC-4` line above.

  ```bash
  python3 - <<'PY' || echo "FAIL AC-4: the kept-content probe could not run"
  import io, os, re
  src = io.open('_docs/testing.md', encoding='utf-8').read().replace('\r\n', '\n')
  on_disk = set(f for f in sorted(os.listdir('backend/tests')) if re.fullmatch(r'test_\w+\.py', f))
  def heading(pat):
      m = re.search(r'(?m)^' + pat + r'[^\n]*\n', src)
      return m.group(0) if m else None
  def body(open_line):
      start = src.index(open_line) + len(open_line)
      m = re.compile(r'(?m)^#{2,3} ').search(src, start)
      return src[start:m.start() if m else len(src)]
  inv_head = heading(r'### Test-file inventory')
  tree_head = heading(r'### Structure')
  inv = body(inv_head) if inv_head else None
  tree = body(tree_head) if tree_head else None
  bad = []
  if inv is None:
      bad.append('inventory heading MISSING (arm a: no line matching ^### Test-file inventory - B-14\'s flat list was dropped or renamed)')
  else:
      inv_files = set(re.findall(r'(test_\w+\.py)', inv))
      if inv_files != on_disk:
          bad.append('arm b: inventory names ' + str(len(inv_files)) + ' files, disk holds ' + str(len(on_disk))
                     + '; missing=' + (','.join(sorted(on_disk - inv_files)) or 'none')
                     + '; extra=' + (','.join(sorted(inv_files - on_disk)) or 'none'))
  if tree is None:
      bad.append('arm c: Structure section MISSING')
  else:
      tree_files = set(re.findall(r'(test_\w+\.py)', tree))
      if tree_files != on_disk:
          bad.append('arm c: structure names ' + str(len(tree_files)) + ' of the ' + str(len(on_disk))
                     + ' files on disk; missing=' + (','.join(sorted(on_disk - tree_files)) or 'none')
                     + '; extra=' + (','.join(sorted(tree_files - on_disk)) or 'none'))
  fictional = [n for n, b in (('inventory', inv), ('structure', tree))
               if b is not None and 'test_state_machine.py' in b]
  if fictional:
      bad.append('arm d: test_state_machine.py still listed in ' + ','.join(fictional))
  print('FAIL AC-4: ' + '; '.join(bad) if bad else
        'PASS AC-4: inventory section present with exactly the ' + str(len(on_disk))
        + ' files on disk; the structure tree names the same ' + str(len(on_disk))
        + '; test_state_machine.py appears in neither listing')
  PY
  ```

- [ ] **AC-5** Lint is clean on the merged tree: `backend/.venv/bin/python -m ruff check backend`
  exits 0 and its last line is literally `All checks passed!` - 0 errors, 0 warnings. The exit status
  is captured per section 9 Rule 3 and the token is matched with `grep -qx` per Rule 1, so neither
  the verdict nor the count is eyeballed. A docs-only merge must not move ruff in either direction.
  Green = `PASS AC-5`.

  Measured today (at `4f5070b`): the block prints
  `PASS AC-5: ruff check backend exit=0, last line 'All checks passed!'`; the raw command prints
  `All checks passed!` with rc=0.

  ```bash
  OUT=$(backend/.venv/bin/python -m ruff check backend 2>&1); RC=$?
  LAST=$(printf '%s\n' "$OUT" | tail -1)
  if [ "$RC" -eq 0 ] && printf '%s' "$LAST" | grep -qx 'All checks passed!'; then
    echo "PASS AC-5: ruff check backend exit=0, last line '$LAST'"
  else
    echo "FAIL AC-5: ruff exit=${RC}, last line='${LAST}', expected exit=0 and 'All checks passed!'"
  fi
  ```

**Cross-check duty for SW** (the 5.3 union duty, not a sixth AC): re-run `runacs` over BOTH
`_docs/issues/B-14.md` and `_docs/issues/closed/T7.md` on the resolved tree, and re-run T7 AC-3 from
the frozen `_docs/issues/closed/T7.md` copy rather than only from the AC-3 restatement above.
## Constraints

Non-negotiables. A violation of any forbidden item below is a `[BLOCKER]` raised to the
Orchestrator, not something the lane may fold into the merge commit.

**Forbidden**

- **Wholesale `git checkout --ours` / `--theirs` of `_docs/testing.md`**, and the equivalent
  `-X ours` / `-X theirs` / `-Xignore-all-space` strategy flags for that path. The single diff3 hunk
  at the `## Structure` `backend/tests/` listing is resolved **by content**: T7's 19-name tree plus
  B-14's `### Test-file inventory`, fictional name in no listing. Either flag deletes one side's
  substantive addition silently, which is exactly what AC-4 exists to catch.
- **Force-push in any form**, `--force-with-lease` included. B-14's branch stays untouched on the
  remote per 3.3; the merge commit is added, never rewritten onto someone else's tip.
- **Any edit to `backend/app/main.py`.** It is the 3rd-entry HOT_FILE per 4.9 and this conflict has
  nothing to do with it. This lane changes zero code.
- **Any edit to `_docs/issues/T7.md` or `_docs/issues/closed/T7.md`.** Those are T7's frozen gates;
  AC-3 is re-run *from* the frozen copy, never rewritten here.
- **Any edit to B-14's AC text** in `_docs/issues/B-14.md`.
- **Any edit to the B-17 (#58) plugin-removal paragraph**, or to any other `_docs/testing.md` region
  outside the `### Structure` / `### Test-file inventory` area. B-17 owns that text and both sides of
  this conflict already agree on it (measured: that region auto-merges).
- **Creating `test_state_machine.py`**, in `backend/tests/` or anywhere else. It stays FICTIONAL by
  the B-14 round-4 ruling, it exists in no tree on disk, and B-14's own internal guard fires the
  moment it is collected. The fix is to remove the name from the doc, never to add the file.

**Required environment for every gate run** (WAL 303; each arm was measured the hard way)

- `TMPDIR` off `/mnt/c`: drvfs breaks pytest's capture (`FileNotFoundError` in `snap()`).
- Run from a worktree **without** the orchestrator `.env` (pydantic `extra=forbid`).
- No `set -e` and no `set -o pipefail` around an AC block, and no truncating consumer such as `head`
  on a state-changing script: SIGPIPE yields a false FAIL exit code.
- Gate env for suite and collection runs, with interpreter `backend/.venv/bin/python` (`uv` is not
  on PATH; `uv run pytest` in a command line is documentation, not the gate's command):
  `export DATABASE_URL="sqlite:////home/te/tq/<lane>/_gate.db" JWT_SECRET=<lane secret> STAFF_PIN=0000 ENV=test TMPDIR=/home/te/tq/<lane> TZ=UTC`
- TZ note: run the gate while the host calendar date equals the UTC date unless B-14's date fix is
  already in the tree.
- Every suite-wide claim carries `-p no:randomly` in the command line that makes the claim
  (`### Ordering pin for suite-wide claims`). `pytest-randomly` stays installed; do not remove it and
  do not pin it away in `addopts`.
- Scratch and gate-db files live inside the lane worktree only and are deleted before the commit;
  `_gate.db` and any `/tmp/mf2*` capture are not commit candidates.

**Scope**

- Files this lane may change: `_docs/testing.md`, and within it only the
  `### Structure` / `### Test-file inventory` region plus any section 8 command line that still
  names the fictional module (AC-2's `named-not-collected` arm cannot go green otherwise, and
  B-14's own `04291af` blob already reads that section the B-14 round-4 way).
- Not touched: `backend/`, `frontend/`, every other `_docs/issues/*` file, `_docs/state/*`,
  `issue-map.json` (MF-2 = #63 is already mapped).
- Merge is `--no-ff` and serial (rules: Git section); the branch is cut at origin/main at lane start
  and that tip must contain merged T7.

## Test requirements

## Implementation notes

## Dependencies

## Out of scope

## Definition of Done
