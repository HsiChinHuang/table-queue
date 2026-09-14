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
