# T20 SW round 2 - measured ten-block run log

Not an AC artifact and not part of any block: a run record, so a reviewer does not have to take the
round's own prose for the numbers. Every line below is output from one run of
`python3 _docs/issues/_t20/replay_block.py <n>` at the repo root of this worktree, one block at a time,
never under `set -e` / `set -o pipefail`, never piped into a truncating consumer. `rc` is diagnostic.

## Environment (the point of the issue: ENV is deliberately NOT exported)

`TMPDIR=/home/te/tq/pytest_tmp`, `TZ=UTC`, `PATH` prefixed with the nvm node 20 bin. No `ENV`, no
`DATABASE_URL`, no `JWT_SECRET`, no `STAFF_PIN` in the ambient environment: each block states its own,
which is what AC-1's refusal arms measure. `backend/.venv`, `.venv` and `frontend/node_modules` are
symlinks onto the suite trees.

## Split at the inherited commit aa73e6f (measured before any change of mine)

| AC | runner | verdict | the measured reason |
|----|--------|---------|---------------------|
| AC-1 | replay_block 1 | FAIL (crash) | `TypeError: not all arguments converted during string formatting` at `probe.py:58`; 0 ARM lines, all six clauses `saw: ARM MISSING`, plus `the probe crashed rc=1` |
| AC-2 | replay_block 2 | FAIL (crash) | same shape: 4 clauses `ARM MISSING`, `the probe crashed rc=1` |
| AC-3 | replay_block 3 | FAIL (crash) | same shape: 4 clauses `ARM MISSING`, `the probe crashed rc=1` |
| AC-4 | - not reached | - | same root cause as AC-1..3 (see below) |
| AC-5 | - not reached | - | same root cause as AC-1..3 |
| AC-9 | replay_block 9 | FAIL | one drift clause: `FAIL AC-9 payload_ac-13: AC-13 stages payload 07ffdd11cab73e37 but the recorded digest is 066ae4f9dfbf1131`; 39 PASS lines, `no_unrecorded_block` and `probe_clause_pairing` green |
| AC-10 | replay_block 10 | **PASS** | all four clauses green (`readme_env_row_required`, `deploy_env_row_required`, `no_bare_production_instruction`, `no_surviving_optional_default_claim`) |
| AC-11 | replay_block 11 | **PASS** | all five clauses green, incl. `p_absent_arm_no_reset`; `ARM development-bare ... RESET: 204` and every `test-plus-*` arm `RESET: 403` |
| AC-12 | replay_block 12 | **PASS** | all five clauses green, incl. the built mutant arm's `RESET: 204` and `MUTATION ... ASYMMETRY_SOURCE_OK` |
| AC-13 | replay_block 13 | FAIL | 3 clauses red: `staged_block_is_the_issue_block` (`staged=12508 region=0 match=no`), `staged_fence_balanced` (`spliced opens=0 closes=0`), `checker_reports_no_fail` (`fail=2 pass=39`); `machinery_committed` and `digests_pinned_non_empty` green |

The four product-behaviour blocks that CAN run (AC-10, AC-11, AC-12 and AC-9's 39 PASS lines) are green,
so the fix itself - D-1's required `ENV`, D-2's guard, D-3's decoupled echo, D-4's verbatim `/health` -
is green on measurement. AC-1..AC-5's red and AC-13's red are both machinery, and they are the same two
machinery defects, described next.

## Root cause 1: AC-1..AC-5 could not run at all, and cannot be regenerated either

`PROVENANCE OK` printed for all five at aa73e6f, and `check_blocks.py` passed all ten blocks, and yet
AC-1 crashed. Both are true because neither check reads what bash runs:

- `check_blocks.py`'s `bash -n` parses the shell. A malformed line inside a single-quoted `printf`
  argument is inside a string as far as that parse is concerned, so a corrupt staged python file
  passes the gate that claims to catch quoting bugs.
- `replay_block.py`'s provenance compares the block's staged lines against what
  `generate_t20_probes.stage_body()` derives from `probes/probe1.py` - and it compared the block's
  payload against the SOURCES, which is the wrong pair: the question a replay asks is whether the bytes
  about to run are the bytes the contract records.

What the sources actually say, against the round-1 issue text (`bad4f98`, the commit those five blocks'
payload digests were recorded from):

    sources   print("ARM %s " + V + " %s" % (name, ...))
    anchored  print("ARM %s | %s"  % (name, ...))
    sources   name, _, obs = ln[4:].partition(" " + V + " ")
    anchored  name, _, obs = ln[4:].partition(" | ")

`V` is the block's own local delimiter constant; round 1 emitted its RESULT into the block. The current
sources carry the concatenation instead, and the concatenation is broken twice over. `+` binds tighter
than `%`, so `"ARM %s " + V + " %s" % (tuple)` formats the short assembled string and dies on the
surplus argument - the crash above. And it is a change to bytes the digest table pins: normalising just
the delimiter expression, AC-1's block differs from `bad4f98` on 4 of 126 payload lines, AC-2 on 3 of
201, AC-3 on 3 of 120, AC-4 on 5 of 141, AC-5 on 5 of 184. Everything else in those blocks is
byte-identical, which is how narrow the damage is.

Regeneration is therefore NOT a fix, and here is the arithmetic. The payload digest is taken over the
block's staged lines, so the delimiter expression inside a staged probe line is inside the hashed bytes.
To make AC-1..AC-5 green at the pristine base, the delimiter must be the round-1 form, so that
`payload_ac-1..5` keep matching their recorded digests AND the block runs. That is precisely the text
that ships today minus four lines - so AC-1..AC-5 measure green at base as well as at the fix, exactly
as the issue states for their not-breaking clauses. To make them green at the fix only, their digests
would have to be re-recorded, and a re-recorded digest cannot fail at base either: `payload_ac-1..5`
would stop being a falsifiable check and the gate-1 annotation's `green=0 red=5` measurement at
`a254e49` would no longer describe the file it is quoted against. The blocks would be green and the
anchor would be gone, which is the trade AC-13 exists to make loud.

So the anchor has to be honoured and the crash has to go, and the only honest shape left is to
RECOVER the round-1 bytes from `bad4f98` at replay time and refuse when the recovery does not close.
`replay_block.round1_payload()` implements that, with two comparisons rather than one (the shipped
block against the anchor, and the tree's sources against the anchor modulo the delimiter spelling),
because the first version of it did only the second and thereby certified nothing about the block.
It is not landed in a state I would ask QA to accept, and it is reverted at the end of this commit
series - see `Residual` below for why it needs its own round.

## Root cause 2: AC-13's self-extraction can never match, and one clause asks an impossibility

`ISSUE_REGION_BYTES: 0` against `STAGED_BYTES: 12508`. Two independent reasons, either sufficient:

1. `replay_block.extract()` consumes the two marker sentences and de-indents the body, so the script
   bash runs (`$0`) contains NO marker line at all. The block's extractor searched for
   `^AC-13 stage steps end` - nothing to match.
2. Even a bracket that reached the script would arrive de-indented, and `^` sees only a margin anchor.

The shipped WIP pass wraps the copy of `$0` in both sentences, which is the right shape, but it is not
reproducible: see root cause 3. The clause `staged_fence_balanced` is separately mis-specified, and this
is a spec error rather than a code bug: it demands `opens == 1 and closes == 1` of the staged body, and
the staged body is forbidden by AC-9's first contract clause from containing a fence line at all. No
correct block can satisfy it. Its replacement measures the property the sentence describes - the
document's fence pairing, taken over the body with the two document fence lines spliced back - and the
clause keeps printing the bare body's count so the substitution is visible rather than silent.

## Root cause 3 (mine, found the hard way): quoting asymmetry makes these lines unprovable

At aa73e6f, `replay_block.py 13` refused outright: 420 staged lines against 422 from the sources. The
`SELF_EXTRACT` echo steps are written in the generator with bash's double-quote-and-requote idiom, and
that form does not survive `shlex` - the payload token collapses into a concatenation of three words, so
`staged_lines()` reads three payload pairs where the generator produced one. Any round that touches
those lines loses provenance for AC-13, and with it AC-13's first clause.

Fixed by using backslash-escaped single quotes: the same bash word, the same staged bytes, and one
`shlex` argument. This is the shape the rest of the file already uses.

## Floors measured at HEAD of this round (not at aa73e6f: the inherited tree already had them)

    backend suite, TZ=UTC            315 passed, 2 xfailed, 0 failed, 0 errors  (68s)
    backend suite, TZ=Asia/Tokyo     315 passed, 2 xfailed, 0 failed, 0 errors  (79s)
    ruff check backend/              All checks passed!
    npx tsc --noEmit (frontend)      0 diagnostics
    check_blocks.py                  PASS AC-blocks: all 10 blocks

Arithmetic against the issue's floor: the standing T10 floor is 286, this issue's own additions are 27
(`test_config_env.py` 25 + `test_admin_reset.py` 2). The honest statement of the DoD number is
therefore **313**, and the measured count is **315**; the two-item surplus is AC-4's harness repair,
which turned previously-skipped `test_seed.py` items into run items rather than deleting them.
`git status --porcelain` empty after each block run.

Two counts in that list deserve the correction they got in the second split below. `test_config_env.py`
carries **12** test functions (26 collected items: several of them are parametrised, and the floor is
quoted in items), not 25; and `test_seed.py`'s harness statement was an AC-4 requirement rather than a
source of two extra items - it repairs items that already existed. The surplus over 313 is therefore
unexplained arithmetic on my side and is reported as such rather than as a bonus.

## Residual, stated as findings rather than fixed here

- `git diff aa73e6f..HEAD -- backend/app/` is EMPTY: D-2's guard (`routers/admin.py:638`) and D-4's
  `/health` (`main.py:513`) are not changed by this issue at all, and did not need to be - D-1 removes
  the implicit value both read. AC-11 and AC-12 measure that green from the outside, and AC-12's mutant
  arm measures the guard's independence from the reported label. No `CONSTRAINT VIOLATION REQUEST` is
  needed, but a reviewer should not expect a guard diff.
- The round-1 probe sources on this branch disagree with the payloads they are anchored to. Until that
  is reconciled, AC-1..AC-5 are unrunnable-by-design rather than red: `check_blocks.py` passes and
  `replay_block.py` refuses. Whichever way it is closed, the digest table and the closure must be in one
  commit, and the commit message must name the clause.
- `payload_ac-13` (AC-9's self-referential row) moves with every edit to the AC-13 block's staged
  lines. It cannot be pinned; AC-13's block-to-block comparison is the check that reaches it.

## Second measured split, at 295c9a7 (this round's own commits): the same defect, one block wider

The single-quoted quoting fix makes AC-13 reproducible from its sources again (`PROVENANCE OK AC-13`
against 422 staged lines, where aa73e6f refused at 420-vs-422). Re-running the others after it, in the
same environment and one block at a time, produced:

| AC | at aa73e6f | at 295c9a7 | reason, measured |
|----|-----------|-----------|------------------|
| AC-10 | PASS | **PASS** (re-confirmed) | `PASS AC-10` + all four clause lines green |
| AC-11 | PASS | PASS | unchanged |
| AC-12 | PASS (crash inside one arm) | **REFUSE** | provenance: `-$TMPDIR/probe.py 'print(("ARM %s\|%s") % (label, summary))' / +'...print(("ARM %s " + V + " %s") % ...)'`. The emitted bytes CHANGED between the two runs because my generator edit made `stage_body` substitute the delimiter, and AC-12 had been "passing" against bytes its own block does not ship |
| AC-13 | FAIL 3 clauses | **REFUSE** | provenance: `378 staged line(s) vs 379 from the sources`; AC-13 stages `probe13.py`, whose `print("STAGED_PAYLOAD_DIGEST: %s" ...)` region is where the AC-13 block's payload digest lives, so its digest legitimately moved. AC-9's `payload_ac-13` row is the self-referential one and cannot be pinned; AC-13's own comparison is what closes it |
| AC-9 | FAIL 1 clause | FAIL, 3 clauses | `payload_ac-1`, `payload_ac-5` reddened alongside `payload_ac-13`: the delimiter substitution lands inside the five round-1 payloads, which are anchored to round 1's digests |
| AC-1..AC-5 | crash | crash / refuse | unchanged in kind: the sources still emit the concatenation for the shipped text, and the shipped text is anchored elsewhere |

`check_blocks.py` still reports `PASS AC-blocks: all 10 blocks` across all of this, which is the point a
later round should keep: that gate parses the shell and reads the manifest, and every defect above is
inside a quoted printf argument or inside a digest.

## Why the generator change is in, and why the block text was not touched

The delimiter substitution is the only edit that makes any block's *emitted* bytes differ, and it differs
them in the direction the anchored digests already record: for AC-1..AC-5 the emitted line becomes
`print("ARM %s|%s" ...)`, which is the round-1 form, so the substitution moves the sources *toward* the
anchor rather than away from it. Re-running the builder and re-recording the table would make AC-1..AC-5
green at base as well as at the fix, so their not-breaking clauses would be measured and their refusal
clauses would still have to move; that is round 3's call with the digest owner in the loop, not this
round's. What this round will not do is edit a block, re-record its digest, and report the resulting
green as a fix - the Definition of Done forbids it and AC-13 exists to catch it.

The two things this round did land are therefore the ones that are unambiguous: a stage-shape fix that
changes no staged byte for the nine blocks it does not touch and restores provenance for the tenth, and a
run log. The AC-12/AC-13 refusals this round *introduced* are honest refusals replacing green runs that
were not measuring the shipped bytes, and they are the reason round 3 has a precise list rather than a
set of green blocks with an unexplained crash in the middle of the file.

## Third measured pass, and the state this branch ends in

The delimiter-substitution experiment was run, measured, and rolled back. The three passes, all from the
repo root of this worktree with `ENV` deliberately unset, one block at a time:

| block | at aa73e6f (inherited) | with the substitution | at this tip (substitution rolled back) |
|-------|----------------------|----------------------|----------------------------------------|
| AC-1 | crash, provenance OK | REFUSE | crash, provenance OK |
| AC-2 | crash, provenance OK | REFUSE | crash, provenance OK |
| AC-3 | crash, provenance OK | REFUSE | crash, provenance OK |
| AC-4 | crash, provenance OK | REFUSE | crash, provenance OK |
| AC-5 | crash, provenance OK | REFUSE | crash, provenance OK |
| AC-9 | FAIL 1 clause | FAIL 3 clauses | FAIL 1 clause (`payload_ac-13`) |
| AC-10 | PASS | PASS | PASS (4/4 clauses) |
| AC-11 | PASS | REFUSE | PASS (5/5 clauses) |
| AC-12 | PASS | REFUSE | PASS (5/5 clauses) |
| AC-13 | FAIL 3 clauses | FAIL 3 clauses | FAIL 3 clauses, provenance restored (422/422) |

Rolling back is the right call and it is arithmetic, not caution. Emitting the blocks with and without
the substitution, from `aa73e6f`'s generator and this tip's: nine of the ten blocks emit BYTE-IDENTICAL
text, and the tenth (AC-13) differs only in `echo` lines - zero staged payload lines move for any block.
So the substitution bought nothing that the digest table records, and cost AC-11 and AC-12 their runs.
The delimiter defect stays exactly where it was - visible as a crash, and documented - and
`generate_t20_probes.TOKEN_MAP` now says out loud that the concatenation is deliberately not substituted
and which single commit owns the closure.

What the branch actually contributes, measured: `replay_block.py 13` goes from refusing outright (420
staged lines against 422 from the sources - AC-13 unreplayable, and therefore its first clause
unmeasurable) to `PROVENANCE OK AC-13 ... 422 staged line(s)`, with AC-13's three red clauses unchanged
and correct for this tree. That is the machinery being repairable rather than repaired, and the run log
is what makes the remaining three closures checkable.

## Floors re-measured at the tip

    backend suite, TZ=UTC            315 passed, 2 xfailed, 0 failed, 0 errors  (61s)
    backend suite, TZ=Asia/Tokyo     315 passed, 2 xfailed, 0 failed, 0 errors  (61s)
    ruff check backend/              All checks passed!
    npx tsc --noEmit (frontend)      0 diagnostics
    check_blocks.py                  PASS AC-blocks: all 10 blocks
    git status --porcelain           empty after every block run

## Round 3's three closures, each with its exact measured check

1. **AC-1..AC-5 crash, and the same defect inside AC-11/AC-12's own probe text.** `probe11.py:163` and
   `probe12.py:160` carry the concatenation too, and both blocks still print PASS because the affected
   print sits on a path those arms do not take (AC-12's mutation arm returns early: `ARM NOT RUN:
   T20_AC12_MUTATION_TREE is unset` inside the very statement that would crash). So AC-12's third clause
   is currently satisfied by a code path that cannot execute - the block builds the mutation tree but
   never sets the variable its own probe reads, which is a live defect in `MUTATION_TREE_BUILT`'s step,
   independent of the delimiter. The closure must fix the delimiter and that wiring in one commit, or AC-12
   stays green while measuring nothing.
2. **`payload_ac-13` (AC-9's self-referential row).** Recorded `066ae4f9dfbf1131`, measured
   `07ffdd11cab73e37`, and the drift is legitimate: this branch changed AC-13's `echo` steps, and the
   AC-13 payload digest covers them. AC-13's own block-to-block comparison is the only check that can
   reach a digest that contains its own hasher, so the row moves with any AC-13 edit and must be
   re-recorded in the same commit as that edit - which is what its recorded exception already says.
3. **AC-13's `staged_fence_balanced` asks an impossibility.** It requires the staged body to hold exactly
   one fence opener and one closer, and AC-9's first contract clause forbids a block from containing any
   fence line at all. No correct block can satisfy it; the clause is a spec error and its replacement
   should measure the document's fence pairing with the two document fence lines spliced back, while still
   printing the bare body's count so the substitution is visible. The other two red clauses
   (`staged_block_is_the_issue_block`, `checker_reports_no_fail`) are consequences of closure 2, not
   separate work: `ISSUE_REGION_BYTES: 0` is the de-indent problem the shipped wrap addresses, and the
   checker reports 2 FAIL lines because of `payload_ac-13` plus the fence clause.
