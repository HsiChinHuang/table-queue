---
id: MF-1
title: MERGE-FIX: B-10 (main.py mount sequence + issue-mirror conflict with main)
depends: [B-10]
platform_issue: 60
---

# MERGE-FIX: B-10

## Metadata

- **Phase**: phase-2-backend
- **Type**: chore
- **Area**: backend
- **Size**: S
- **Milestone**: Phase 2 - Backend surfaces

## Goal

Land B-10 on `main` without losing either side of the conflict: `backend/app/main.py` becomes the
UNION of main's staff mount pair and the branch's two admin mounts plus its budget exemption, and
`_docs/issues/B-10.md` becomes byte-identical to the branch's adopted R2a groom. The merge commit
then carries B-10's own green gate with it.

## Context

B-10 is `qa-passed` but cannot merge cleanly, so the serial merge queue is stopped. This issue is
the resolution task, not a product task: everything it has to prove is already proved on one side or
the other, and the only new claim is that both sides survive together. The conflict report below is
the Orchestrator's measured background and stays as prose.

- Related: #36 (B-10), #55 (B-08, the staff surface on `main`), B-17 (the 27 pre-existing suite failures)
- Plan: `_docs/plan.md`
- Contract: `_docs/specs.md` section 9, `_docs/openapi.yaml`

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

### PM re-check of the 364-line figure (groom round, re-measured here)

The 364 above counts the ENTIRE ours-only side of the three conflict hunks, blank lines included.
Reproducing the same `git merge-file --diff3` against the same merge base today reproduces the three
hunk positions exactly (merged-file lines 37, 241 and 5690) and the same ours-side totals
(95 + 2,354 + 7 = 2,456 lines, of which 122 + 94 + 12 = 228 were also in the merge base). The
non-blank residual is therefore **212**, not 361 or 364: `awk` over the ours-only section counts 97
blank lines inside it, so 309 blanks were never ours-only at all. SW does not need to triage them
line by line, because the disposition below is byte-exact: the branch revision wins the whole file, so
no line is dropped by judgement. What the deliverable DOES owe is the one real contract difference the
branch introduced, named once: the branch splits B-11's admin surface onto `tables_router` so that
B-10's AC-1 can read `settings_router` alone, which is why main's single `mount(admin_router.router)`
line cannot be kept.

### PM groom note: what the deliverable owes, in addition

The report the SW leg posts must name the single contract difference the branch introduced (the
`settings_router` / `tables_router` split of the router B-11 imports) and state that the main-only
B-10 mirror lines are superseded R2 block bodies. It must also say plainly that AC-3 cannot go green on
`origin/main` and why: main carries the fourteen-block R2 mirror, so fifteen greens are unobtainable
there, which is exactly why AC-3 measures the branch's fifteen-block file inside a scratch export of
the union rather than main's own file.

## Deliverable (original Orchestrator brief, kept as background)

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

## Test requirements

SW fills this section. Nothing below is a PM claim: it is the measurement surface this issue's AC
blocks already drive, listed so SW knows what has to be run and where.

- No new test file. MF-1 adds no behaviour, so it adds no test: `backend/tests/test_admin_settings.py`
  (83 tests) and `backend/tests/test_staff_tables.py` are the two suites the union has to satisfy.
- Every AC block below is self-contained and runs from the repo root of the MF-1 branch checkout.
- AC-5 runs B-10's own 15 graded blocks inside a scratch export, which is the only way to measure the
  merged tree without a checkout that already contains it.

## Implementation notes

SW fills this section. Hints, all of them measured today:

- Build the scratch trees the way `merged-runacs.sh` does: `git archive <ref> | tar -x`, then
  `ln -sfn "$TQ_VENV" backend/.venv`. A `git worktree` or plain copy on `drvfs` cannot exec the venv.
- The scratch tree needs `_docs/specs.md`: `app/errors.py` reads the error catalogue from two levels
  above `backend/` at import time and raises `FileNotFoundError` without it.
- Never inherit the developer `.env`: the repo root carries an untracked `.env` whose keys
  (`platform`, `api_token`, ...) the app config rejects with `extra_forbidden`. Use
  `backend/.env.example` or export the four variables the app needs.
- main's staff pair needs three things the B-10 branch never had: `backend/app/routers/staff.py`, its
  two service modules, and main's `from app.routers import staff as staff_router` line. Copying only
  the mount lines gives `NameError: name 'staff_router' is not defined` at import.

## Dependencies

- Blocked by: #36 (B-10, `qa-passed`), and by the merge of #55's staff surface, which is already on
  `origin/main`.
- Blocks: the serial merge of B-17 and every later `qa-passed` issue behind B-10 in the queue.

## Out of scope

- The 27 pre-existing whole-suite failures in `backend/tests/test_public_board.py` and
  `backend/tests/test_public_waitlist.py`: they reproduce on pristine `origin/main`, they are B-17's
  scope, and B-17 is in QA right now. AC-6 only requires that MF-1 adds no new failure.
- B-10's `runacs` green on `origin/main` itself: main holds the superseded R2 mirror (14 graded
  blocks), so a run against main's own file can at best print `green=1 red=14`. AC-5 therefore
  measures the branch's 15-block file inside a scratch export.
- The mirror size repair: the branch's `_docs/issues/B-10.md` is 211,653 bytes, above the 200,000-byte
  Platform body ceiling, so #36's Platform body cannot be brought into sync with it. That is the
  follow-up the attribution section below already names; MF-1 changes no AC text.
- Closing #60 or writing any label: the Orchestrator owns labels and closes.

## Acceptance criteria

Every block runs from the repo root of the MF-1 branch checkout, prints a `PASS AC-n` or `FAIL AC-n`
verdict as its first line, sets no `set -e` and no `set -o pipefail`, pipes no state-changing command
into a truncating consumer, and wraps every subprocess in `timeout`. Two optional environment
variables are honoured: `TQ_VENV` (interpreter with the app's dependencies, default
`/home/te/tq/suite/backend/.venv`) and `TQ_HARNESS` (directory holding `runacs.py`).

Three measured facts explain the shape of the blocks below, and all three are the reason a green here
is a green on the merged tree rather than a green on this checkout:

- **A tree containing the merge does not exist on `main` yet.** AC-3, AC-4, AC-5, AC-7 and AC-8 therefore
  build the resolution THEMSELVES: `backend/app/main.py` and `backend/tests/test_admin_settings.py` are copied
  from this working tree (a scratch fallback to the branch revision lets the same block run in a clean
  checkout), every other file of `backend/app` and `backend/tests` is unioned from
  `origin/issue/B-10-admin-settings` first and `origin/main` second, so main's staff surface joins the
  branch's admin surface, and the result is run in a scratch directory. AC-3 additionally replaces the
  B-10 mirror inside the export with the branch's fifteen-block revision, because that is the file the
  merge is supposed to land.
- **The scratch directory must be outside this repo.** Two of B-10's own gates read every tracked file
  (the whole-tree CJK audit), and `ruff check .` from `backend/` reads anything placed inside the tree,
  so a helper file left in the repo can turn a gate red that this issue did not touch. The scratch
  trees go under `/tmp` or the native worktree root, never under `_docs/state/` either - line 88 of
  `.gitignore` ignores that whole directory, so evidence placed there can never be re-read from a
  checkout.
- **The venv cannot run from this drive.** `drvfs` will not execute the Linux interpreter, so a
  `git worktree` on this mount cannot run a suite; that is why the blocks use `git archive` plus a
  symlinked venv, the same shape the harness's own post-merge scripts use.

The red baseline below is today's checkout, whose `git rev-parse HEAD` and `git rev-parse origin/main`
print the same commit. Two ACs (AC-6, AC-8) are honest PASS-now checks that must STAY green through the
merge; the other eight are red today.

- [ ] **AC-1** `backend/app/main.py` is the union, not a pick

  - the file carries no conflict marker of either family
  - `mount(admin_router.settings_router)` and `mount(admin_router.tables_router)` are both present
  - `staff_router.configure_limiter(limiter)` and `mount(staff_router.router)` are both present
  - `admin_router.configure_limiter(limiter)` and a bare `mount(admin_router.router)` are both ABSENT
  - Green now: no. On today's tree neither admin mount exists and main's own bare admin mount does.

  Measured today: `FAIL AC-1: main.py is not the required union`, from exactly these four findings:
  `mount of admin_router.settings_router is missing`; `mount of admin_router.tables_router is missing`;
  `admin_router.configure_limiter(limiter) must not be restored`;
  `bare mount(admin_router.router) must not be restored`.

  ```bash
  set -u
  f="backend/app/main.py"
  [ -f "$f" ] || { echo "FAIL AC-1: backend/app/main.py is missing"; exit 0; }
  ok=1
  say() { echo "  - $1"; ok=0; }
  [ "$(grep -c '^<<<<<<<' "$f")" -eq 0 ] || say "a conflict marker is left in $f"
  [ "$(grep -c '^>>>>>>>' "$f")" -eq 0 ] || say "a closing conflict marker is left in $f"
  grep -q 'mount(admin_router\.settings_router)' "$f" || say "mount of admin_router.settings_router is missing"
  grep -q 'mount(admin_router\.tables_router)' "$f" || say "mount of admin_router.tables_router is missing"
  grep -q 'staff_router\.configure_limiter(limiter)' "$f" || say "staff_router.configure_limiter(limiter) is missing"
  grep -q 'mount(staff_router\.router)' "$f" || say "mount(staff_router.router) is missing"
  grep -q 'admin_router\.configure_limiter(limiter)' "$f" && say "admin_router.configure_limiter(limiter) must not be restored"
  grep -q 'mount(admin_router\.router)' "$f" && say "bare mount(admin_router.router) must not be restored"
  if [ "$ok" -eq 1 ]; then
      echo "PASS AC-1: main.py is the union with 0 conflict markers left"
  else
      echo "FAIL AC-1: main.py is not the required union"
  fi
  ```

- [ ] **AC-2** the settings guest budget exemption survives the union

  - `backend/app/main.py` is not a byte-for-byte copy of either conflicted side
  - the `exempt_surface(` call appears exactly once and names both settings handler references
  - Green now: no, today's `backend/app/main.py` equals the `origin/main` side and names no exemption.

  This is a structural check. Whether the exemption actually still SHIELDS the two settings operations
  is behavioural, and B-10's own AC-13 owns that proof: two hundred logged GETs and two hundred logged
  PATCHes on the settings path all answering 200. AC-3 runs that block on the merged tree, so this AC
  does not re-implement it.

  Measured today: `FAIL AC-2: main.py is one conflicted side taken whole` - the block's own first check
  fired on the file being byte-identical to `origin/main`, so the three exemption findings below it were
  never reached.

  ```bash
  set -u
  f="backend/app/main.py"
  [ -f "$f" ] || { echo "FAIL AC-2: backend/app/main.py is missing"; exit 0; }
  work="$(mktemp -d /tmp/mf1-ac2-XXXXXX)"
  side() { printf '%s' "$1" | tr -c 'A-Za-z0-9' '_'; }
  n=0
  for ref in origin/main origin/issue/B-10-admin-settings; do
      git show "$ref:$f" > "$work/$(side "$ref").side" 2>/dev/null
      cmp -s "$f" "$work/$(side "$ref").side" && n=$((n + 1))
  done
  if [ "$n" -gt 0 ]; then
      echo "FAIL AC-2: main.py is one conflicted side taken whole"
      rm -rf "$work"
      exit 0
  fi
  ok=1
  say() { echo "  - $1"; ok=0; }
  [ "$(grep -c '^<<<<<<<' "$f")" -eq 0 ] || say "a conflict marker is left in $f"
  [ "$(grep -c '^>>>>>>>' "$f")" -eq 0 ] || say "a closing conflict marker is left in $f"
  [ "$(grep -c 'exempt_surface($' "$f")" -eq 1 ] || say "the exemption call is not present exactly once"
  grep -q 'admin_router\.get_admin_settings,$' "$f" || say "the exemption does not name the GET handler"
  grep -q 'admin_router\.update_admin_settings,$' "$f" || say "the exemption does not name the PATCH handler"
  if [ "$ok" -eq 1 ]; then
      echo "PASS AC-2: the settings budget exemption survived the union in main.py"
  else
      echo "FAIL AC-2: the exemption did not survive the union"
  fi
  rm -rf "$work"
  ```

- [ ] **AC-3** B-10's own gate is green on the merged tree

  - all fifteen of B-10's graded blocks print their own `PASS AC-n` token on the merged tree
  - the gate runs inside a scratch export of the union, because a tree that already contains the merge is
    the thing under construction
  - the `_docs/issues/B-10.md` inside that export is the branch's fifteen-block R2a revision
  - Green now: no. `origin/main` holds the superseded fourteen-block R2 mirror, so the best reading
    obtainable there is one green and fourteen red.

  Measured today: `B10_GATE rc=0 green=1 red=14` then `FAIL AC-3: B-10 gate green=1 red=14 rc=0`, red set
  `['AC-1', 'AC-2', 'AC-3', 'AC-4', 'AC-5', 'AC-6', 'AC-7', 'AC-8', 'AC-9', 'AC-10', 'AC-11', 'AC-13',
  'AC-14', 'AC-15']`. The single green is B-10's own CJK audit, green there only because this checkout's
  uncommitted `T7.md` edit is inherited into the export; nothing else is green.

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/python" ] || { echo "FAIL AC-3: no interpreter at $VENV (set TQ_VENV)"; exit 0; }
  HARNESS="${TQ_HARNESS:-}"
  if [ -z "$HARNESS" ]; then
      for c in "/mnt/c/Users/tw097/Desktop/ai-dev-tools-zoomcamp/.tq-orchestrator" "/home/te/tq/harness"; do
          [ -f "$c/runacs.py" ] && HARNESS="$c" && break
      done
  fi
  [ -n "$HARNESS" ] && [ -f "$HARNESS/runacs.py" ] || { echo "FAIL AC-3: runacs.py not found (set TQ_HARNESS)"; exit 0; }
  work="$(mktemp -d /home/te/tq/mf1-ac3-XXXXXX)"
  [ -d "$work" ] || { echo "FAIL AC-3: cannot create a scratch directory on the native filesystem"; exit 0; }
  export GIT_DIR="$(git rev-parse --git-common-dir)"
  export GIT_WORK_TREE="$PWD"
  { git ls-tree -r --name-only origin/issue/B-10-admin-settings;
    git ls-tree -r --name-only origin/main; } | sort -u > "$work/files.txt"
  while read -r f; do
      mkdir -p "$work/$(dirname "$f")"
      if [ -f "$f" ]; then cp "$f" "$work/$f"
      elif git cat-file -e "origin/issue/B-10-admin-settings:$f" 2>/dev/null; then git show "origin/issue/B-10-admin-settings:$f" > "$work/$f"
      else git show "origin/main:$f" > "$work/$f"; fi
  done < "$work/files.txt"
  git archive origin/issue/B-10-admin-settings _docs | tar -x -C "$work"
  git show origin/issue/B-10-admin-settings:_docs/issues/B-10.md > "$work/_docs/issues/B-10.md"
  ln -sfn "$VENV" "$work/backend/.venv"
  out="$(cd "$work" && timeout 1700 python3 "$HARNESS/runacs.py" _docs/issues/B-10.md --cwd . 2>&1)"; rc=$?
  g="$(printf '%s\n' "$out" | grep -oE '^== green=[0-9]+' | grep -oE '[0-9]+')"
  r="$(printf '%s\n' "$out" | grep -oE '^== red=[0-9]+' | grep -oE '[0-9]+')"
  echo "B10_GATE rc=$rc green=${g:-none} red=${r:-none}"
  printf '%s\n' "$out" | grep -E '^== red=' | head -2
  if [ "$rc" -eq 0 ] && [ "${g:-0}" -eq 15 ] && [ "${r:-1}" -eq 0 ]; then
      echo "PASS AC-3: B-10 gate green 15 red 0"
  else
      echo "FAIL AC-3: B-10 gate green=${g:-none} red=${r:-none} rc=$rc"
  fi
  rm -rf "$work"
  ```

- [ ] **AC-4** the resolved route table answers both surfaces at import time

  - `from app.main import app` imports under the union (main's staff modules, the branch's admin router)
  - the flattened route table serves `/api/v1/admin/settings`, `/api/v1/admin/tables`,
    `/api/v1/staff/tables`, `/api/v1/staff/tables/{id}` and `/api/v1/staff/tables/{id}/release`
  - a hunk picked wrong fails here at import or route level, not by grep alone
  - Green now: no, on today's tree the settings path is absent from the route table.

  Measured today: `FAIL AC-4: route probe exit 1 with 1 MISSING_ROUTE`, first line
  `RESOLVED_ROUTE_PROBE rc=1 missing=1 PATH_COUNT 17 MISSING_ROUTE /api/v1/admin/settings`. The
  `original_router` attribute the probe walks is this FastAPI's own: `main.py`'s own `_reachable_paths`
  helper follows it, and `app.routes` otherwise hides a mounted router inside a container.

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/python" ] || { echo "FAIL AC-4: no interpreter at $VENV (set TQ_VENV)"; exit 0; }
  work="$(mktemp -d /tmp/mf1-ac4-XXXXXX)"
  export GIT_DIR="$(git rev-parse --git-common-dir)"
  export GIT_WORK_TREE="$PWD"
  mkdir -p "$work/backend/app" "$work/_docs"
  cp _docs/specs.md _docs/openapi.yaml _docs/testing.md "$work/_docs/"
  cp backend/.env.example "$work/backend/.env"
  ln -sfn "$VENV" "$work/backend-venv"
  { git ls-tree -r --name-only origin/issue/B-10-admin-settings -- backend/app;
    git ls-tree -r --name-only origin/main -- backend/app; } | sort -u > "$work/files.txt"
  while read -r f; do
      mkdir -p "$work/$(dirname "$f")"
      if [ -f "$f" ]; then cp "$f" "$work/$f"
      elif git cat-file -e "origin/issue/B-10-admin-settings:$f" 2>/dev/null; then git show "origin/issue/B-10-admin-settings:$f" > "$work/$f"
      else git show "origin/main:$f" > "$work/$f"; fi
  done < "$work/files.txt"
  if [ -f backend/app/main.py ]; then cp backend/app/main.py "$work/backend/app/main.py"; else git show origin/issue/B-10-admin-settings:backend/app/main.py > "$work/backend/app/main.py"; fi
  cat > "$work/backend/probe.py" <<'PROBE'
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./tq_mf1.db")
os.environ.setdefault("JWT_SECRET", "mf1-secret")
os.environ.setdefault("STAFF_PIN", "0000")
os.environ.setdefault("ENV", "test")
from app.main import app

paths = set()
stack = list(app.routes)
while stack:
    route = stack.pop()
    path = getattr(route, "path", None)
    if path:
        paths.add(path)
    nested = getattr(route, "original_router", None)
    if nested is not None:
        stack.extend(nested.routes)
print("PATH_COUNT", len(paths))
REQUIRED = ("/api/v1/admin/settings", "/api/v1/admin/tables", "/api/v1/staff/tables",
            "/api/v1/staff/tables/{id}", "/api/v1/staff/tables/{id}/release")
for want in REQUIRED:
    if want not in paths:
        print("MISSING_ROUTE", want)
sys.exit(1 if any(w not in paths for w in REQUIRED) else 0)
PROBE
  out="$(cd "$work/backend" && timeout 300 ../backend-venv/bin/python probe.py 2>&1)"; rc=$?
  m="$(printf '%s\n' "$out" | grep -cE '^MISSING_ROUTE ')"
  echo "RESOLVED_ROUTE_PROBE rc=$rc missing=$m $(printf '%s\n' "$out" | grep -E '^PATH_COUNT|^MISSING_ROUTE' | paste -sd' ' -)"
  if [ "$rc" -eq 0 ] && [ "$m" -eq 0 ]; then
      echo "PASS AC-4: the resolved route table serves both admin and staff surfaces"
  else
      echo "FAIL AC-4: route probe exit $rc with $m MISSING_ROUTE"
  fi
  rm -rf "$work"
  ```

- [ ] **AC-5** the three surfaces the union joins pass TOGETHER in one pytest process

  - on the merged tree, B-10's admin settings suite, B-11's admin tables suite and B-08's staff tables
    suite are passed in a SINGLE `python -m pytest` invocation - `tests/test_admin_settings.py
    tests/test_admin_tables.py tests/test_staff_tables.py` - so the shared limiter, the shared router
    module and the single app import survive the resolution
  - PASS needs that one process to exit `0`, to report zero `FAILED` and zero `ERROR` lines, and to print
    a passed count of at least 98 (the 83 admin settings tests plus the admin/staff table tests)
  - the three suites passing SEPARATELY is explicitly NOT a pass: the proposition AC-5 exists for is
    inter-surface interaction, and a separate-process run cannot see limiter or router state leaking
    across surfaces. The block therefore names all three files in one argv and never loops over them.
  - why the wording is what it is (do not "restore" the old text): the previous revision demanded that
    a bare `pytest -q` over the whole union suite exit `0`, and that demand is unsatisfiable before this
    issue closes - MF-1 gates B-10's merge, the stopped merge queue blocks B-17's merge, and B-17 owns
    the 27 pre-existing failures inside that very suite. AC-5's green would have depended on a merge that
    AC-5's own issue gates: a circular AC, red by construction rather than by defect.
  - AC-8, unchanged, is the whole-suite no-new-failures guard: it compares candidate failure ids against
    a `git archive` baseline computed identically from `origin/main` and needs zero new ids. The 27
    belong to B-17 and stay B-17's; nobody may re-add an exit-0 demand to AC-5 to "prove" them away.
  - Green now: no. The merged tree this block needs lives on branch
    `issue/MF-1-b10-merge-resolution`, not on `main`, so in the main checkout the export has no
    `tests/test_admin_settings.py` and the run cannot even start.

  Measured today: `FAIL AC-5: union triple rc=1 with 68 FAILED or ERROR lines and 30 passed counted`, from the
  block's own report line `UNION_TRIPLE rc=1 counts=68 failed,30 passed 30 counted`, run in the main checkout
  (the export there still gets main's pre-merge `backend/app/main.py`, so the admin surfaces are unreachable). The same block's
  logic was executed against a `git archive` export of
  `origin/issue/MF-1-b10-merge-resolution` at `87d7747616ca3f13bca1fc440d8ec99ac6396e9d`: one process over
  the three files prints `98 passed, 2 warnings in 10.90s`. Whole-suite figures for the record, both
  measured on that branch tip: `UNION_SUITE rc=1 counts=27 failed` (all 27 are B-17's, AC-8's territory)
  and B-10's own gate reads `green=15 red=0`.

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/python" ] || { echo "FAIL AC-5: no interpreter at $VENV (set TQ_VENV)"; exit 0; }
  work="$(mktemp -d /tmp/mf1-ac5-XXXXXX)"
  export GIT_DIR="$(git rev-parse --git-common-dir)"
  export GIT_WORK_TREE="$PWD"
  mkdir -p "$work/backend/tests" "$work/_docs"
  cp _docs/specs.md _docs/openapi.yaml _docs/testing.md "$work/_docs/"
  cp backend/.env.example "$work/backend/.env"
  ln -sfn "$VENV" "$work/backend-venv"
  { git ls-tree -r --name-only origin/issue/B-10-admin-settings -- backend/app backend/tests;
    git ls-tree -r --name-only origin/main -- backend/app backend/tests; } | sort -u > "$work/files.txt"
  while read -r f; do
      mkdir -p "$work/$(dirname "$f")"
      if [ -f "$f" ]; then cp "$f" "$work/$f"
      elif git cat-file -e "origin/issue/B-10-admin-settings:$f" 2>/dev/null; then git show "origin/issue/B-10-admin-settings:$f" > "$work/$f"
      else git show "origin/main:$f" > "$work/$f"; fi
  done < "$work/files.txt"
  [ -f "$work/backend/app/main.py" ] || { echo "FAIL AC-5: no main.py in the union file set"; exit 0; }
  if [ -f backend/app/main.py ]; then cp backend/app/main.py "$work/backend/app/main.py"; else git show origin/issue/B-10-admin-settings:backend/app/main.py > "$work/backend/app/main.py"; fi
  if [ -f backend/tests/test_admin_settings.py ]; then cp backend/tests/test_admin_settings.py "$work/backend/tests/test_admin_settings.py"; fi
  cd "$work/backend"
  missing=0
  for t in tests/test_admin_settings.py tests/test_admin_tables.py tests/test_staff_tables.py; do
      [ -f "$t" ] || { echo "TRIPLE_MISSING $t"; missing=1; }
  done
  [ "$missing" -eq 0 ] || { echo "FAIL AC-5: a surface file is absent from the union"; rm -rf "$work"; exit 0; }
  out="$(timeout 1700 ../backend-venv/bin/python -m pytest tests/test_admin_settings.py tests/test_admin_tables.py tests/test_staff_tables.py -q --no-header -p no:cacheprovider 2>&1)"; rc=$?
  nbad="$(printf '%s\n' "$out" | grep -cE '^(FAILED|ERROR) ')"
  npass="$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+')"
  npass="${npass:-0}"
  echo "UNION_TRIPLE rc=$rc counts=$(printf '%s\n' "$out" | grep -oE '[0-9]+ (passed|failed|errors)' | paste -sd, -) $npass counted"
  printf '%s\n' "$out" | grep -E '^(FAILED|ERROR) ' | head -3
  if [ "$rc" -eq 0 ] && [ "$nbad" -eq 0 ] && [ "$npass" -ge 98 ]; then
      echo "PASS AC-5: three surfaces in one process exit 0 with 0 failed and ${npass} passed"
  else
      echo "FAIL AC-5: union triple rc=$rc with $nbad FAILED or ERROR lines and ${npass} passed counted"
  fi
  rm -rf "$work"
  ```

- [ ] **AC-6** `ruff check .` stays clean from `backend/`

  - the linter runs in `backend/`, the directory holding its own `pyproject.toml`
  - the scratch trees AC-3 to AC-5 build sit under `/tmp` or the native worktree root, never inside this
    repo, so they add no lintable file here
  - Green now: yes, and it must STAY green through the merge.

  Measured today: `PASS AC-6: ruff check . from backend/ prints All checks passed!`

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/ruff" ] || { echo "FAIL AC-6: no ruff at $VENV/bin/ruff (set TQ_VENV)"; exit 0; }
  out="$(cd backend && timeout 300 "$VENV/bin/ruff" check . 2>&1)"
  first="$(printf '%s\n' "$out" | head -1)"
  echo "RUFF says: $first"
  if printf '%s\n' "$out" | grep -q 'All checks passed!' && ! printf '%s\n' "$out" | grep -qE 'Found [0-9]+ error'; then
      echo "PASS AC-6: ruff check . from backend/ prints All checks passed!"
  else
      echo "FAIL AC-6: ruff check . from backend/ is not clean"
      printf '%s\n' "$out" | tail -5
  fi
  ```

- [ ] **AC-7** B-10's own test suite is green inside the merged tree

  - `backend/tests/test_admin_settings.py` runs against the union app and answers `83 passed`
  - the run happens in a scratch export of the union, so it measures the merge and not a stale checkout
  - Green now: no, that file is not tracked on `origin/main` at all.

  Measured today: `FAIL AC-7: B-10 pytest exit 4 with 1 or more FAILED or ERROR lines`, the block's own
  report line being `B10_PYTEST rc=4 counts=none 1 FAILED or ERROR lines` and its only finding line
  `ERROR: file or directory not found: tests/test_admin_settings.py`. On a resolved tree the same block
  prints `83 passed`, which is QA round 3's baseline for B-10's own file.

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/python" ] || { echo "FAIL AC-7: no interpreter at $VENV (set TQ_VENV)"; exit 0; }
  work="$(mktemp -d /tmp/mf1-ac7-XXXXXX)"
  export GIT_DIR="$(git rev-parse --git-common-dir)"
  export GIT_WORK_TREE="$PWD"
  mkdir -p "$work/backend/tests" "$work/_docs"
  cp _docs/specs.md _docs/openapi.yaml _docs/testing.md "$work/_docs/"
  cp backend/.env.example "$work/backend/.env"
  ln -sfn "$VENV" "$work/backend-venv"
  { git ls-tree -r --name-only origin/issue/B-10-admin-settings -- backend/app backend/tests;
    git ls-tree -r --name-only origin/main -- backend/app backend/tests; } | sort -u > "$work/files.txt"
  while read -r f; do
      mkdir -p "$work/$(dirname "$f")"
      if [ -f "$f" ]; then cp "$f" "$work/$f"
      elif git cat-file -e "origin/issue/B-10-admin-settings:$f" 2>/dev/null; then git show "origin/issue/B-10-admin-settings:$f" > "$work/$f"
      else git show "origin/main:$f" > "$work/$f"; fi
  done < "$work/files.txt"
  if [ -f backend/app/main.py ]; then cp backend/app/main.py "$work/backend/app/main.py"; else git show origin/issue/B-10-admin-settings:backend/app/main.py > "$work/backend/app/main.py"; fi
  if [ -f backend/tests/test_admin_settings.py ]; then cp backend/tests/test_admin_settings.py "$work/backend/tests/test_admin_settings.py"; fi
  cd "$work/backend"
  out="$(timeout 900 ../backend-venv/bin/python -m pytest tests/test_admin_settings.py -q --no-header -p no:cacheprovider 2>&1)"; rc=$?
  n="$(printf '%s\n' "$out" | grep -cE '^(FAILED|ERROR) ')"
  p="$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | head -1)"
  echo "B10_PYTEST rc=$rc counts=${p:-none} $n FAILED or ERROR lines"
  printf '%s\n' "$out" | grep -E '^(FAILED|ERROR) ' | head -3
  if [ "$rc" -eq 0 ] && [ "$n" -eq 0 ]; then
      echo "PASS AC-7: B-10 pytest exit 0 with ${p:-no passed count}"
  else
      echo "FAIL AC-7: B-10 pytest exit $rc with $n or more FAILED or ERROR lines"
  fi
  rm -rf "$work"
  ```

- [ ] **AC-8** no new whole-suite failure beyond the 27 B-17 owns

  - both sides are computed identically: `git archive <ref> | tar -x` into a scratch directory, the shared
    venv linked in, then a bare `pytest -q` over the whole `backend/tests` directory
  - BASELINE is `origin/main`, the pre-existing set B-17 owns; CANDIDATE is the B-10 branch revision, the
    stand-in for the MF-1 tree until the merge commit exists
  - PASS needs a baseline whose counted failures equal its counted failure ids, a candidate whose ids are
    counted the same way, and ZERO candidate ids absent from the baseline
  - those 27 failures are B-17's and stay out of MF-1's scope; this AC only forbids making it worse
  - Green now: yes, and it must stay green through the merge.

  Measured today: `PASS AC-8: baseline_failed=27 candidate_failed=27 new_failures=0`, with
  `BASELINE_FAILED_COUNT=27 baseline_ids=27`, `CANDIDATE_FAILED_COUNT=27 candidate_ids=27` and
  `NEW_FAILURE_COUNT=0`; all 27 ids sit in `tests/test_public_board.py` and
  `tests/test_public_waitlist.py` and none of them is a B-10 file.

  ```bash
  set -u
  VENV="${TQ_VENV:-/home/te/tq/suite/backend/.venv}"
  [ -x "$VENV/bin/python" ] || { echo "FAIL AC-8: no interpreter at $VENV (set TQ_VENV)"; exit 0; }
  base="$(mktemp -d /tmp/mf1-ac8-XXXXXX)"
  collect() {
      ref="$1"; run="$base/$2"
      mkdir -p "$run" || { echo 0 > "$run/nfail"; : > "$run/ids.txt"; return; }
      git archive "$ref" | tar -x -C "$run" || { echo 0 > "$run/nfail"; : > "$run/ids.txt"; return; }
      ln -sfn "$VENV" "$run/backend/.venv"
      (cd "$run/backend" && timeout 1700 .venv/bin/python -m pytest -q --no-header -p no:cacheprovider 2>&1) > "$run/report.txt"
      grep -oE '[0-9]+ failed' "$run/report.txt" | head -1 | grep -oE '[0-9]+' > "$run/nfail" || echo 0 > "$run/nfail"
      grep -E '^(FAILED|ERROR) ' "$run/report.txt" | sed -E 's#^(FAILED|ERROR) (tests/[a-z_]+\.py)::#\2::#' | sort -u > "$run/ids.txt"
  }
  collect origin/main main
  collect origin/issue/B-10-admin-settings cand
  m="$(cat "$base/main/nfail")"; b="$(cat "$base/cand/nfail")"
  comm -13 "$base/main/ids.txt" "$base/cand/ids.txt" > "$base/newer.txt"
  nm="$(wc -l < "$base/main/ids.txt")"; nb="$(wc -l < "$base/cand/ids.txt")"; nn="$(wc -l < "$base/newer.txt")"
  echo "BASELINE_FAILED_COUNT=$m baseline_ids=$nm"
  echo "CANDIDATE_FAILED_COUNT=$b candidate_ids=$nb"
  echo "NEW_FAILURE_COUNT=$nn"
  paste -sd, "$base/newer.txt"
  if [ "$m" -gt 0 ] && [ "$nm" -eq "$m" ] && [ "$nb" -eq "$b" ] && [ "$nn" -eq 0 ]; then
      echo "PASS AC-8: baseline_failed=$m candidate_failed=$b new_failures=0"
  else
      echo "FAIL AC-8: baseline_failed=$m candidate_failed=$b new_failures=$nn"
  fi
  rm -rf "$base"
  ```

- [ ] **AC-9** the resolution took nothing wholesale and left nothing conflicted

  - `_docs/issues/B-10.md` on MF-1 is byte-identical to the `origin/issue/B-10-admin-settings` revision,
    compared against the BRANCH ref and never against a possibly stale local `main`
  - `backend/app/main.py` equals neither conflicted side byte for byte
  - neither resolved file carries a conflict marker
  - Green now: no, the mirror is `origin/main`'s R2 revision and differs from the branch's.

  Measured today: `FAIL AC-9: resolution discipline violated`, from
  `_docs/issues/B-10.md is not byte identical to the B-10 branch revision` (`cmp` reports
  `differ: byte 7610, line 115`) plus `backend/app/main.py is the main side taken whole`.

  ```bash
  set -u
  [ -f backend/app/main.py ] || { echo "FAIL AC-9: backend/app/main.py is missing"; exit 0; }
  ok=1
  say() { echo "  - $1"; ok=0; }
  git show origin/issue/B-10-admin-settings:_docs/issues/B-10.md | cmp - _docs/issues/B-10.md 2>/dev/null \
      || say "_docs/issues/B-10.md is not byte identical to the B-10 branch revision"
  git show origin/issue/B-10-admin-settings:backend/app/main.py | cmp - backend/app/main.py 2>/dev/null \
      && say "backend/app/main.py is the branch side taken whole"
  git show origin/main:backend/app/main.py | cmp - backend/app/main.py 2>/dev/null \
      && say "backend/app/main.py is the main side taken whole"
  [ "$(grep -c '^<<<<<<<' backend/app/main.py)" -eq 0 ] || say "a conflict marker is left in backend/app/main.py"
  [ "$(grep -c '^<<<<<<<' _docs/issues/B-10.md)" -eq 0 ] || say "a conflict marker is left in _docs/issues/B-10.md"
  if [ "$ok" -eq 1 ]; then
      echo "PASS AC-9: the mirror matches the branch revision and main.py is neither side whole"
  else
      echo "FAIL AC-9: resolution discipline violated"
  fi
  ```

- [ ] **AC-10** the merge really happened on this branch

  - `git merge-base --is-ancestor` succeeds for BOTH `origin/main` and
    `origin/issue/B-10-admin-settings` against `HEAD`
  - the two refs resolve to different commits, so the check cannot pass by accident of a shared tip
  - Green now: no, `HEAD` equals `origin/main` today and does not contain the B-10 branch.

  Measured today: `FAIL AC-10: HEAD does not descend from both merged sides`, the single finding being
  `origin/issue/B-10-admin-settings is not an ancestor of HEAD` (`git rev-parse HEAD` prints the same
  commit as `git rev-parse origin/main` today, and the ancestry check against the branch ref exits 1).

  ```bash
  set -u
  a="$(git rev-parse origin/issue/B-10-admin-settings)" || { echo "FAIL AC-10: cannot resolve the B-10 branch ref"; exit 0; }
  b="$(git rev-parse origin/main)" || { echo "FAIL AC-10: cannot resolve origin/main"; exit 0; }
  h="$(git rev-parse HEAD)" || { echo "FAIL AC-10: cannot resolve HEAD"; exit 0; }
  [ "$a" != "$b" ] || { echo "FAIL AC-10: the two merged refs resolve to the same commit"; exit 0; }
  ok=1
  say() { echo "  - $1"; ok=0; }
  git merge-base --is-ancestor "$a" "$h" || say "origin/issue/B-10-admin-settings is not an ancestor of HEAD"
  git merge-base --is-ancestor "$b" "$h" || say "origin/main is not an ancestor of HEAD"
  if [ "$ok" -eq 1 ]; then
      echo "PASS AC-10: HEAD descends from both merged sides"
  else
      echo "FAIL AC-10: HEAD does not descend from both merged sides"
  fi
  ```


## Constraints

Writable file set, and nothing else:

- `backend/app/main.py` (the conflict resolution itself, plus main's staff import line)
- `backend/app/routers/staff.py`, `backend/app/services/table_conflict.py`,
  `backend/app/services/table_write.py`, `backend/tests/test_staff_tables.py` - ONLY as the byte-exact
  restoration of the `origin/main` versions they already are
- `_docs/issues/B-10.md` - ONLY as the byte-exact copy of the `origin/issue/B-10-admin-settings` revision

Forbidden, all of them measured as load-bearing this session:

- No behaviour change: no new route, no changed validator, no changed limiter policy, no re-formatting
  of a comment block that the merge did not force.
- No edit of any AC text and no AC box ticking anywhere, in MF-1 or in B-10's mirror. In particular
  AC-3 cannot be satisfied by editing B-10's mirror back toward fourteen blocks, by ticking a box, or by
  pointing the gate at `origin/main`'s superseded mirror: it goes green only when fifteen of the branch's
  own graded blocks each print their own PASS token on the merged tree.
- No `.gitignore` edit: the ignore rules are what make the harness's scratch paths work (line 88
  ignores `_docs/state/`, line 91 ignores `backend/.venv`), and the whole-tree CJK audit an AC runs
  reads every tracked file.
- No apply or remove of labels; labels are the Orchestrator's.
- Never merge or push to `main`; never touch `_docs/issue-map.json`; never edit `T7.md`, `B-10.md`'s
  AC content or `B-17.md`.
- One pytest/python process at a time, never `uv run --with`, never `-n auto`, never pipe a state-
  changing or pytest run into `tail`/`head`, always wrap a suite in `timeout`. None of this issue's AC
  blocks runs under `set -e` or `set -o pipefail`.
- Quote a 40-hex SHA only from your own `rev-parse` output.

Environment variables the AC blocks honour, all optional: `TQ_VENV` (interpreter with the app's
dependencies, default `/home/te/tq/suite/backend/.venv`) and `TQ_HARNESS` (directory holding
`runacs.py`, default the `.tq-orchestrator` directory beside the repo).

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Backend tests pass (AC-5: B-10 settings + B-11 admin tables + B-08 staff tables all pass in ONE
      pytest process on the merged tree, `>=98 passed` and zero FAILED/ERROR lines; AC-7: B-10's own file
      answers 83 passed inside that union; AC-8: the whole-suite run adds no failure id over the
      `origin/main` baseline, whose 27 B-17 owns)
- [ ] Frontend tests pass (if applicable) - not applicable, MF-1 touches no frontend file
- [ ] No lint errors (AC-6: `ruff check .` clean from `backend/`)
- [ ] Manual verification completed (if applicable) - none needed: every gate above is executable

## Issue-specific DoD (PM)

- [ ] The merge commit exists on the MF-1 branch with BOTH `origin/main` and
      `origin/issue/B-10-admin-settings` as ancestors (AC-10)
- [ ] `_docs/issues/B-10.md` on MF-1 is byte-identical to the branch revision, and MF-1's own mirror is
      in sync with #60 at the moment `set-body` last ran (AC-9)
- [ ] B-10's fifteen graded blocks go green on the merged tree, where today they read one green and
      fourteen red (AC-3)
- [ ] The SW report names the `settings_router` / `tables_router` split as the one contract difference
      the branch introduced, and repeats that the 212 non-blank main-only mirror lines are superseded R2
      block bodies
- [ ] The SW report changes no AC text, ticks no AC box, writes no label, and merges or pushes nothing

## Why this happened (Orchestrator attribution)

The R2 groom was mirrored into the tracked file at `9125edf`, then the R2a groom was adopted onto the
feature branch instead of onto `main`, so the tracked mirror and the branch diverged by design and
nothing detected it until merge time. Follow-up worth its own ticket: the branch file is 211,653
bytes, above the 200,000-byte Platform body ceiling, so the Platform body for #36 cannot be brought
into sync with it - the mirror gap must be closed by a size repair, not by `set-body`.
