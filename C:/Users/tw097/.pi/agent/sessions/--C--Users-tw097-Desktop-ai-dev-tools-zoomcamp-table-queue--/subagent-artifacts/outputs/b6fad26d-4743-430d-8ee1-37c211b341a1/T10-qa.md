## QA VERDICT: PASS

T10 / #65, measured in my own detached checkout of the exact commit under test
(`/home/te/tq/qa-T10-r1` @ `23efdd5`, runacs md5 `85e35368ab0c2a4d0ab4ee64e5db69b1`, no other
runacs/uvicorn alive, ports 8310-8319 verified free before and after the boot arms). No code,
test, AC or Platform body was modified by me (`git status --porcelain` shows only `_qa/` scratch).

- [x] AC-1 published example literal refused at construction - PASS
- [x] AC-2 32-char floor pinned on both sides - PASS
- [x] AC-3 empty / whitespace-only refused - PASS
- [x] AC-4 second published literal refused - PASS (with finding F-2 on what it cannot see)
- [x] AC-5 repo ships no usable secret + generation command - PASS
- [x] AC-6 harness boots on a gate-compliant secret, suite green - PASS
- [x] AC-7 forged-token exploit pin, incl. the [ORCH AC AMENDMENT] third arm - PASS, amendment ACCEPTED (see below)
- [x] AC-8 no-regression canary (login 200 / issued token 200 / bare 401 / 41 passed) - PASS, green at tip AND at base

## Gate at tip (runacs, my own run)

`== green=8 ['AC-1'..'AC-8']` / `== red=0 []`, rc=0, 8/8 blocks extracted. Independently re-run
block-by-block with my own fence-paired extractor (fences 3-backtick, de-dented, no `set -e`,
no pipefail, no `head` truncation of a mutating command) - all eight print their own
`PASS AC-<n>` line. Verdict tokens agree with the runacs line-first scan.

## Per-attack table

| # | Attack | Expected | Actual | Classification |
|---|---|---|---|---|
| A | runacs at `23efdd5` | green=8 red=0 | green=8 red=0, 8 blocks extracted | matches expectation |
| A' | Blocks re-run individually (own extractor) | 8x `PASS AC-n` | 8x `PASS AC-n`; AC-7 `rc=1 named=2 bound=000`; AC-6 `total=8 below-gate=0`, `286 passed, 2 xfailed`; AC-8 `login=200 token_len=167 authed=200 bare=401 pytest_rc=0`, `41 passed` | matches |
| B1 | Naive inversion: add the padded published value to `PUBLISHED_JWT_SECRETS` at tip | AC-4 goes RED | **AC-4 stayed GREEN** (`PASS AC-4 ... input_value='test-secret-key'`) | **FINDING F-1 (Medium, gate/AC design)** |
| B2 | Targeted inversion: neutralise the blocklist rule (`if False and secret in ...`) | AC-4 RED | **AC-4 stayed GREEN** - refused by the floor, message carries the literal word "published" | **FINDING F-2 (Medium, AC-4 defect)** |
| B3 | AC-4's Pass clause re-read against a floor-only gate (no blocklist rule at all, both literals) | AC-4 RED | **AC-4 GREEN for both published literals**; in-suite `test_jwt_secret_blocklist_is_a_rule_of_its_own` FAILED with "AC-4 mechanism split is broken" | **FINDING F-2 confirmed: the in-suite test is the real AC-4 pin, the bash block is not** |
| B4 | Same floor-only gate, AC-7 (amended third arm) | AC-7 RED | **AC-7 GREEN** - floor-only boot refusal also gives `rc=1 named=2 bound=000` | FINDING F-3: AC-7 proves *refusal*, not *which* rule refused |
| B5 | Full gate grafted onto base `49b46f9`, run under **both** AC-7 wordings (SW's method claim) | old arm red, new arm green | old: `PUBLISHED-LITERAL SERVER: FORGED=200` -> FAIL; new: `rc=1 named=2 bound=000` -> **PASS** | **FINDING F-4 (Medium, report inaccuracy): the amendment invalidated AC-7's published red baseline, not just the AC's green arm** |
| B6 | Base + floor-only gate, amended AC-7 | red | `FAIL AC-7 forged=401 genuine=200 boot_rc=124 named=0 bound=200` | AC-7 does discriminate no-gate vs any-gate |
| C1 | Blocklist evasion `change-me-in-productionPADDINGPADDINGPADDING` (44 ch) | - | **ACCEPTED** by the validator AND boots a live uvicorn (`Application startup complete`, port bound) | **FINDING F-5 (Medium, design defect - not "pinned design", see text)** |
| C2 | Case variants `CHANGE-ME-IN-PRODUCTION`, `Change-Me-In-Production`, `TEST-SECRET-KEY` | refused | refused - but by the **floor** (all 23/15 ch), not case-insensitively; the >32-char case variant `change-me-in-productionAAAAAAAAAAAAAAAA` is ACCEPTED | covered by F-5 (the 23-char published literals cannot reach 32 ch, so case-insensitivity is currently unreachable in production) |
| C3 | Unicode homoglyph `changé-me-in-production` + padding | refused | ACCEPTED at 38 ch (23-char pure homoglyph form is refused by the floor) | same class as F-5, lower still |
| C4 | Internal whitespace `change-me-in-production PADDING_123456` (38 ch) | refused | **ACCEPTED, 38 ch** | same class as F-5 |
| C5 | Surrounding whitespace / trailing NL on a published literal (all < 32 ch after strip) | refused | refused, all five variants (`\t`, spaces, `\n`) | correct; `strip()` cannot smuggle a 23-ch literal |
| C6 | `_env_file=None` vs `os.environ` precedence (SW's documented quirk) | env wins over init kwarg | **CONFIRMED**: good kwarg + ambient `JWT_SECRET=change-me-in-production` -> `Settings(_env_file=None, jwt_secret=<good>)` returns the kwarg; ambient wins for plain `Settings()`; `test_config._clean_env` pops the keys first, so the pin does not depend on the quirk | design quirk, documented, correctly handled |
| C7 | Env-wins class, end to end | - | AC-1/AC-2/AC-3/AC-4 all use `env ... JWT_SECRET=<candidate>` with a valid kwarg-free construction, so the ACs exercise the ambient path | no gap |
| D | Harness-guard attack: throwaway copy of `backend/tests` with `conftest.py`'s swept literal rewound to `grfg-frperg-xrl` (15 ch) | in-tree guard goes RED | real-tree guards stay `2 passed`; the copy cannot even be collected: conftest ImportError -> `ValidationError: jwt_secret ... input_value='grfg-frperg-xrl'`; and the guard's own logic is falsifiable (see D2) | **FINDING F-6 (Low): the guard's RED path is reachable only through its own replay, not through a real file edit, because conftest boots the app at import** |
| D2 | Same attack as an AC-5-style grep + gate arithmetic (shape-independent) | red | `hits=1, bad=1, total=9` -> RED | the AC-6 bash block catches it; the in-suite guard catches it under its own replay. Both mechanisms falsifiable |
| E1 | Full backend suite, `TZ=UTC` @ tip | 286 + 2 xfailed | **286 passed, 2 xfailed**, rc=0 | matches the new floor |
| E2 | Same, `TZ=America/Los_Angeles` @ tip | same | **286 passed, 2 xfailed**, rc=0 | clock-independent |
| E3 | Identity of the 2 xfails at tip vs base, both clocks | same 2 | `test_db_atomicity.py::test_half_write_table_available_party_still_seated` and `::test_half_write_table_occupied_entry_seated_before_the_commit` - identical 2 at base and tip, both TZs | same 2 clock-independent xfails; no xfail drift |
| E4 | Base floor re-derivation (independent, not copied) | 272 + 2 | `git checkout` of base config.py -> **272 passed, 2 xfailed** UTC + LA | +14 delta attributable to `test_config.py` (15 collected: 14 net-new + `test_config_validates_required_env` moved) |
| E5 | `ruff check .` in `backend/` | 0 | `All checks passed!` (also clean on every mutation I applied) | 0 |
| E6 | `tsc --noEmit` (frontend, node v20.20.2) | 0 | 0 errors, rc=0 | 0 |
| E7 | Frontend suite (DoD "not applicable" - measured anyway) | green | **27 files / 228 tests passed** | no frontend regression |
| F | AC-8 canary arms | login 200 / token 200 / bare 401 | `login=200 token_len=167 authed=200 bare=401 pytest_rc=0` + `41 passed`; green at base too (`login=200 token_len=167 authed=200 bare=401`) | green both sides, as pinned |
| G1 | Scope: `git diff 49b46f9..23efdd5 --name-only` | within Constraints + amendment + issue file | 16 files; 15 permitted (`backend/app/config.py`, `backend/.env.example`, `README.md`, `_docs/deployment.md`, `_docs/issues/T10.md`, `backend/tests/` x 11); **`_docs/issues/T9.md` is T9's own groom, delivered by the interleaved merge `1fc1521`, not by T10** (`git diff 49b46f9..1fc1521 -- _docs/issues/T10.md` = 0 files) | **FINDING F-8 (Info): range-scope audit is contaminated by an interleaved merge; the T10-only range `1fc1521..23efdd5` is 15/15 in scope** |
| G2 | AC section byte-identity: `3777e35..23efdd5 -- _docs/issues/T10.md` | AC-7 only | 2 hunks, both inside AC-7 (amendment prose + third-arm re-pin); AC-1..AC-6, AC-8 blocks untouched | matches; nothing else re-pinned |
| G3 | AC section 49b46f9 vs tip | differs by the amendment only | diff = 46 lines, all inside AC-7; outside the AC section only SW's `[SW - filled]` sections + the Out-of-scope measured note changed | matches |
| G4 | Platform mirror DoD bullet ("body mirrors AC text byte-for-byte") | mirrored | **#65 body is the 984-char SA template** (`## Acceptance` prose paragraph, no AC blocks at all) | **FINDING F-7 (Low): DoD item unsatisfied at tip; PM/orch mirror, never QA's write** |
| H | Line terminators: CR count in every touched committed blob | 0 | 16/16 files `tip_CR=0 base_CR=0` (`git show <sha>:<file> | tr -d -c '\r' | wc -c`) | 0 everywhere |
| I | AC-7 amendment soundness | satisfiable + stronger | at tip: `rc=1 named=2 bound=000` -> PASS; at base (pre-amendment tip): `bound=200 named=0` -> FAIL; port genuinely never binds; the arm is strictly stronger than the 401 it replaces | **amendment ACCEPTED** - I do not re-pin it |

## Findings

1. **F-1 (Medium) - the inversion method does not hold for AC-4 in either direction.** Two
   independent mutations that both destroy AC-4's stated property left AC-4 GREEN: (a) adding the
   padded published value to the blocklist (a *strengthening*, and the tip's own
   `test_jwt_secret_blocklist_is_a_rule_of_its_own` fails under it -> suite goes red, AC-4 does not);
   (b) neutralising the blocklist rule (`if False and secret in PUBLISHED_JWT_SECRETS:`). AC-4's Pass
   clause is `rc != 0 AND name>=1 AND bl>=1`, and bl is `grep -Eic "known|example|published"` -
   the **shorter**-than-32 branch of the shipped validator already prints "a known example or
   otherwise published value is never accepted", so AC-4 cannot distinguish the two rules for any
   candidate shorter than 32 characters, which is the only range its own inputs live in (23 ch, 15 ch).
2. **F-2 (Medium) - AC-4's AC text and its block disagree, and the green is bought by the wrong arm.**
   AC-4 says "refused by the **known-value** rule and not merely by the length floor". I grafted a
   floor-only gate onto base and ran AC-4's **published** block verbatim: `FAIL AC-4 published literal
   in play name=2 bl=0 rc=1` for the 15-char literal and the same for the 23-char literal, both
   refused only by the floor. The same floor-only gate also made the in-suite
   `test_jwt_secret_blocklist_is_a_rule_of_its_own` fail with "AC-4 mechanism split is broken", so
   the mechanism split is real in the suite and unasserted by the block. `failure_type: test_quality`
   for AC-4's block; not a FAIL verdict because AC-4's property is carried end to end by
   `test_config.py`, AC-4's own AC text promises a bash block, and QA does not edit ACs.
3. **F-3 (Medium, consequence of F-2) - the amended AC-7 is also floor-only blind.** Floor-only gate
   + AC-7's amended third arm -> `PASS AC-7 ... rc=1 named=2 bound=000`: the "boot refused, log names
   `jwt_secret`, port never binds" arm is satisfied by a gate with no blocklist at all. AC-7 proves
   *a* refusal and the forged-401/genuine-200 controls, which is exactly what a length floor gives.
   It does not, on its own, prove a *published literal* is refused by name. The published-literal
   property is pinned by the in-suite mechanism-split test, not by AC-7.
4. **F-4 (Medium) - the report's method claim is one-sided, and AC-7's published RED baseline is now
   stale.** SW's comment says the pre-T10 reds "reproduce at this base exactly", quoting
   `FAIL AC-7 forged=401 genuine=200 forged-on-published=200` - which is the **pre-amendment**
   wording. At the same base, the **amended** AC-7 already reads `PASS AC-7 published literal cannot
   boot any server...`. So (i) AC-7's `Measured today:` line is false for the block as it now stands,
   and (ii) AC-7 has lost its red baseline and can no longer demonstrate RED-at-base -> GREEN-after-fix;
   it is now a green-only canary like AC-8, which contradicts the DoD bullet "AC-1..AC-7 each flip RED
   at base -> GREEN after fix" unless the amendment is read as an explicit exception. **The claim that
   is true and worth keeping: AC-7 still fires on *no gate at all*, in both wordings - that is the
   class of mutation the block actually discriminates.**
5. **F-5 (Medium) - the blocklist is exact-match after `strip()`, so a published literal with >= 32
   chars total is accepted and boots.** Measured against a real uvicorn, not a probe:
   `JWT_SECRET=change-me-in-productionPADDINGPADDINGPADDING` -> `Application startup complete`, port
   bound. Accepted variants: internal whitespace (`...production PADDING_123456`, 38 ch), unicode
   homoglyph (`changé-me-in-production-aaaaaaaaaaaaaa`, 38 ch), case-folded beyond the floor. Design
   or defect: the Context pins the blocklist as exactly the literals "this repo publishes", and
   Out of scope names only *entropy estimation* and *cross-field* checks as excluded - substring /
   case-insensitive matching is named in neither, and SW's own self-caught-incident #1 records that
   this exact case was **decided** as "exact match by design" and downgraded from an AC suggestion to a
   residual risk with no PM ruling. So: **not a scope violation, but an unpinned design decision, and
   a weaker property than AC-4's own sentence claims.** Practically mitigated: both published literals
   are 23 and 15 chars, so any case/homoglyph/whitespace variant that is still recognisably one of them
   and >= 32 chars must have been deliberately padded by an operator who had to add >= 9 characters to a
   credential - the audited failure mode (verbatim copy of `.env.example`) is closed, AC-5 removed the
   copyable value, and T24/#79 owns entropy/fingerprint work. Natural destination for substring /
   case-insensitive / NFKC matching: **#79 (T24)** alongside entropy.
6. **F-6 (Low) - the harness guard's RED path is only reachable through its own replay.** A naive
   regression (rewind a swept file's literal to a 15-char value) is caught by AC-6's bash block and by
   AC-5-style grep arithmetic (`hits=1 bad=1 total=9`), but `test_harness_boots_on_a_gate_compliant_secret`
   never runs on such a tree: the mutated `conftest.py` boots `app.main` at import, so pytest dies with
   a conftest ImportError first. Honest reading: the design is **over**-falsifiable (a weak harness secret
   makes the whole suite uncollectable, which is louder than a test failure), and the in-tree guard
   still demonstrably goes RED on the tmp_path replay. No action owed here.
7. **F-7 (Low) - DoD bullet unmet**: "Platform issue #65 body mirrors `_docs/issues/T10.md` AC text
   byte-for-byte" - the body is the 984-char SA template with no AC blocks. Owed by PM/orchestrator
   (`platform-post.sh set-body`); QA has no body write and did not touch it.
8. **F-8 (Info)** - `_docs/issues/T9.md` appears in the `49b46f9..23efdd5` name-only audit but is not
   T10's work: it arrives through the interleaved `1fc1521` T9-groom merge. Scope for T10's own range is
   15/15 inside Constraints + the orch amendment. `_docs/specs.md:663` still tabulating
   `change-me-in-production` is **confirmed present and confirmed out of Constraints** - correctly
   reported by SW rather than silently fixed (a silent fix there would have been the scope violation).

## Confirmed-as-measured (SW residual risks I re-derived, not assumed)

- 286 + 2 xfailed at tip, both clocks; **272 + 2** at base re-derived in my own base worktree; the 2
  xfailed are the **same 2** `test_db_atomicity` cases at base and tip -> **+14 floor delta confirmed**.
  This is now the standing backend floor for later issues (T31 re-pin input), and AC-8's sub-suite
  sub-arm grew `27 passed` (base) -> `41 passed` (tip), so the AC-8 tail is a 14-test floor too.
- Frontend `tsc --noEmit` = 0 errors; frontend suite 228/228 (SW did not claim the suite, only tsc).
- Harness: `total=8 below-gate=0`; all 9 sweep sites plus `test_seed.py`'s dict entry boot one shared
  41-char value; `total=8` (not 9) is explained and honest - the two extra matches AC-6 counted at base
  are count-only matches in `test_config.py`.
- Env quirk (`_env_file=None` does not mask `os.environ`) reproduced as described.
- Line terminators 0 CR in all 16 touched blobs.
- No orphan uvicorn on 8310/8311/8312 after every arm; no `.db`/`-wal`/`-shm` beside the repo; every
  block self-cleans its scratch dir.
- `eslint` (`npm run lint`) **not run**: eslint 9 finds no config in this repo - pre-existing, outside
  this issue's scope; recorded as not-run rather than as a pass, same as SW did.

## AC-7 amendment ruling

**Accepted; I do not re-pin it.** The amendment's third arm is (a) satisfiable - it is GREEN at tip in
my own tree; (b) genuinely stronger than the arm it replaces - "the port never binds" is verified as
`bound=000` plus a non-zero uvicorn exit plus `jwt_secret` named twice in the log, whereas the old
`401` arm is unsatisfiable by any working no-bypass implementation (I measured `FORGED=000` at
`3777e35` myself); (c) still discriminating - FAIL on base with no gate. Two consequences the
amendment text does not state and that later rounds should carry as comments, not silent
accommodation: it retires AC-7's published `Measured today:` baseline (F-4), and it inherits F-2 / F-3's
floor-only blindness, so `test_config.py` remains the only assertion in this issue that pins
"refused *by name*".

## DoD Verification

- [x] All acceptance criteria pass (8/8 green at tip)
- [x] Backend tests pass (286 + 2 xfailed, both clocks)
- [x] Frontend tests pass - measured anyway: 228 passed, tsc 0 (issue has no frontend surface)
- [x] No lint errors (ruff 0; eslint pre-existing no-config, not this issue's)
- [x] Manual verification completed (AC-7 / AC-8 HTTP arms run from the repo root exactly as written)
- [ ] PM bullet 1 "AC-1..AC-7 each flip RED-at-base -> GREEN-after-fix with their own runacs line":
  AC-1..AC-6 + AC-8 verified in both directions; **AC-7 satisfied only under the pre-amendment
  wording** (F-4) - treat as satisfied-by-amendment or re-pin the baseline, PM/orch call, not QA's
- [ ] PM bullet 3 falsifiability: measured, and **AC-4 specifically fails to falsify AC-4** (F-1, F-2);
  the other three (floor -> AC-2, empty -> AC-3, docs -> AC-5) plus AC-7-vs-no-gate were reproduced by me
- [x] PM bullet 4 no published literal left, with the stated arbiters: shipped docs + harness are clean;
  `_docs/specs.md:663` + unrelated issue files remain, as SW reported
- [x] PM bullet 5 self-cleaning blocks, no orphans
- [ ] PM bullet 6 Platform body mirror - **F-7**

## Test Quality Warnings

- AC-4's block cannot express its own AC sentence (F-2); its `bl` arm is satisfied by the floor's
  message text. Suggested for the block owner (not me): demand a blocklist-only refusal by feeding a
  **published literal padded past the floor**, or compare `PUBLISHED_JWT_SECRETS` membership directly.
- AC-7's `Measured today:` line now describes a block that no longer exists (F-4).
- No `assert True`, no empty tests; every AC has a real assertion; the in-suite mechanism-split test is
  the strongest artifact in the change set (it is what actually pins AC-4's property).

## Lint Report (non-blocking)

- `ruff check .` in `backend/`: **All checks passed!** (0 errors, 0 warnings)
- Mutations I applied were ruff-clean too, so a lint failure never masked an inversion result.

## Summary

Fix is real and the exploit is closed (forged-from-published 401 against a compliant secret; the
published literal can no longer boot a server at all; base reproduced `FORGED=200`). The verdict is
PASS with two Medium AC-quality defects that belong to the AC owner, not the implementer: **AC-4's
block cannot distinguish its own two rules (proved by mutation), and AC-7's amendment silently retired
its red baseline and inherited the same blindness.**

### B7 - blocklist-neutralised run at FIXED tip (added after the first draft, for precision)

The B2 mutation (`if False and secret in PUBLISHED_JWT_SECRETS:`) applied to `23efdd5`'s own
`config.py`, i.e. the blocklist rule removed from the shipped gate with the empty and floor rules
untouched (md5 `513b4cd...` -> `2071c9d...` -> reverted to `513b4cd...`):

| AC | result under blocklist-neutralised FIXED tip |
|---|---|
| AC-1 | `PASS AC-1 refused at construction rc=1` (23-ch literal caught by the floor) |
| AC-2 | `PASS AC-2 floor enforced at 32` |
| AC-4 | **`PASS AC-4 second published literal refused by name`** - the rule it claims to pin is gone |
| AC-7 | **`PASS AC-7 ... rc=1 named=2 bound=000`** - third arm still satisfied |
| `test_config.py` | RED - `test_jwt_secret_blocklist_is_a_rule_of_its_own` fails, and `_build()` raises the floor `ValidationError` on `test-secret-key` |
| **whole backend suite** | **rc=4 - collection ERROR**: pytest cannot import a module that mints a token with `test-secret-key` as fixture data, so the mutation makes the suite uncollectable rather than merely red (louder than a test failure, and the reason no weak literal can hide in the tree) |

This is the sharpest form of F-2/F-3: with the known-value rule deleted from the shipped product, four
of the eight AC blocks stay green and only the in-suite mechanism-split test notices. The fix under
test **does** contain the rule (I read it: `config.py:51`, and AC-4's own run prints
`input_value='test-secret-key'` with the "known example secrets" message) - this is an AC/measurement
defect, not an implementation defect.

---

## QA VERDICT (machine-readable summary)

**VERDICT PASS per AC**

| AC | verdict | evidence (my own run at `23efdd5`) |
|---|---|---|
| AC-1 | PASS | `PASS AC-1 refused at construction rc=1`, message names `jwt_secret` + "known example secrets" + 32 |
| AC-2 | PASS | `len31 rc=1` refused / `len32 SECRET_OK len=32 rc=0` -> `PASS AC-2 floor enforced at 32` |
| AC-3 | PASS | empty + four-space both rc=1, both name `jwt_secret` -> `PASS AC-3` |
| AC-4 | PASS (**findings F-1/F-2**) | `PASS AC-4`; refusal message carries the blocklist text; but the block stays green with the blocklist rule removed (B2/B7) |
| AC-5 | PASS | `example line: #JWT_SECRET=` / `hits=0 unusable=1 gen=1` -> `PASS AC-5` |
| AC-6 | PASS | `total=8 below-gate=0`, `286 passed, 2 xfailed`, `pytest_rc=0` -> `PASS AC-6` |
| AC-7 | PASS, amendment ACCEPTED (**findings F-3/F-4**) | `FORGED=401 GENUINE=200` + `rc=1 named=2 bound=000` -> `PASS AC-7`; base reproduced `FORGED=200` under the pre-amendment arm, amended arm already green at base |
| AC-8 | PASS (green at base and tip) | `login=200 token_len=167 authed=200 bare=401 pytest_rc=0`, `41 passed` |

**Overall verdict: PASS** - label `qa-passed` applied and re-GET confirmed
(`['backlog','groomed','qa-ready','qa-passed','prio-high']`, state open); verdict comment id `5655924545`.

**Floor deltas for the orchestrator to re-pin (T31 and later):**
- Backend suite standing floor: **286 passed + 2 xfailed**, both `TZ=UTC` and `TZ=America/Los_Angeles`,
  rc=0. Base re-derived independently: **272 passed + 2 xfailed** -> delta **+14**.
- The 2 xfails are the SAME 2 at base and tip, both clocks:
  `tests/test_db_atomicity.py::test_half_write_table_available_party_still_seated`,
  `::test_half_write_table_occupied_entry_seated_before_the_commit`. No xfail drift, no xpass.
- AC-8's sub-suite arm moved **27 passed (base) -> 41 passed (tip)**; any later issue that re-pins AC-8
  style arms must use 41, not 27.
- `ruff check .` in `backend/`: 0 errors, 0 warnings. `tsc --noEmit`: 0. Frontend suite: 27 files / 228 tests passed.
- Standing floor for runacs on this file: **green=8 red=0** at `23efdd5`.

reached_state: qa-passed

## Appendix: evidence index
# T10 QA round 1 - evidence index (all files in this _qa/ dir, mirrored to /home/te/tq/qa-T10-base/_qa/)

Gate: /home/te/tq/qa-T10-r1 @ 23efdd5 (detached). Base worktree: /home/te/tq/qa-T10-base @ 49b46f9.

| File | What it is |
|---|---|
| runacs.py | orchestrator runacs copy, md5 85e35368ab0c2a4d0ab4ee64e5db69b1 (matches .tq-orchestrator/runacs.py) |
| runacs-tip.log | gate at tip: green=8 red=0 |
| extract.py, block-AC-<n>.sh | my fence-paired de-indenting extractor and the 8 extracted blocks (byte-counts 714/858/802/689/949/863/1899/1726) |
| own-AC-<n>.log | my per-block re-runs at tip, each printing its own PASS AC-<n> |
| probes.py / quirk.py / realboot.py | validator-design probes: blocklist evasion, case, homoglyph, whitespace; env-vs-kwarg precedence; real uvicorn boot |
| mut.py mut2.py mut3.py mut4.py mut5.py | mutations (B1,B2,B3,B5,B6) with md5 trail |
| mut-ac4.log mut2-ac4.log | AC-4 under B1/B2 -> stayed GREEN (finding F-1/F-2) |
| orig-AC-<n>.log | PRE-amendment blocks run against base+full-gate graft (F-4) |
| base-suite-UTC.log base-suite-LA.log | base floor 272 passed + 2 xfailed, both clocks |
| suite-UTC.log suite-LA.log suite-LA2.log | tip floor 286 passed + 2 xfailed, both clocks |
| blind-AC-<n>.log | blocklist-neutralised FIXED tip: AC-1/2/4/7 all PASS (finding F-2/F-3) |
| fe-test.log | frontend suite 228 passed |
| md5-tip.txt md5-after-revert.txt | config.py md5 513b4cd71cd37e44776f61f77dfc0d76 before and after every mutation |
| verdict.md skeleton.md | the two posted comments (ids 5655786759, 5655924545) |

## Appendix: commands run
# every command below was run from /home/te/tq/qa-T10-r1 (or the base worktree where noted),
# with PATH node v20.20.2, TMPDIR=/home/te/tq/pytest_tmp, TZ as named, no set -e, no pipefail
git -C /mnt/c/.../table-queue worktree add /home/te/tq/qa-T10-r1 --detach 23efdd5
python3 _qa/runacs.py _docs/issues/T10.md --cwd .                     # green=8 red=0
bash _qa/block-AC-{1..8}.sh                                            # 8x PASS AC-n
/home/te/tq/suite/backend/.venv/bin/python _qa/probes.py               # 13 design probes
/home/te/tq/suite/backend/.venv/bin/python _qa/quirk.py                # 5 precedence probes
/home/te/tq/suite/backend/.venv/bin/python _qa/realboot.py             # 3 real uvicorn boots
python3 _qa/mut.py && python3 _qa/runacs.py ... --only AC-4            # B1: AC-4 GREEN (defect)
python3 _qa/mut2.py && python3 _qa/runacs.py ... --only AC-4           # B2: AC-4 GREEN (defect)
git checkout -- backend/app/config.py                                  # md5 restored 513b4cd...
python3 _qa/mut3.py && pytest tests/test_config.py::test_jwt_secret_blocklist_is_a_rule_of_its_own  # GREEN under strengthening
# base worktree /home/te/tq/qa-T10-base @ 49b46f9
python3 _qa/mut4.py && python3 _qa/runacs.py _docs/issues/T10.md --cwd .   # green=4 red=4 (B5)
bash _qa/orig-AC-{1,2,4,5,6,7}.sh                                       # pre-amendment baselines at base
TZ=UTC  pytest -q  (base) -> 272 passed, 2 xfailed
TZ=America/Los_Angeles pytest -q (base) -> 272 passed, 2 xfailed
cp tip config.py + bash _qa/fixed-AC-7.sh at base -> PASS (F-4)
python3 _qa/mut5.py (floor-only) + bash /home/te/tq/qa-T10-r1/_qa/block-AC-4.sh -> FAIL AC-4 bl=0 (F-2 proof)
python3 _qa/mut5.py + bash _qa/block-AC-7.sh -> FAIL AC-7 named=0 bound=200 (B6)
# harness-guard attack
cp -r backend/tests _qa/hgmut/tests; rewind conftest.py literal to 15 chars
pytest _qa/hgmut/tests/test_config.py::... -> conftest ImportError (guard never ran, F-6)
pytest tests/test_config.py::test_harness_boots_on_a_gate_compliant_secret ::test_harness_secret_guard_is_falsifiable -> 2 passed
# blocklist-neutralised at FIXED tip (B7)
cp tip config.py; sed 'if secret in' -> 'if False and secret in'; AC-1/2/4/7 all PASS; full suite rc=4 collection error
# floors at tip
TZ=UTC pytest -q -rxX -> 286 passed, 2 xfailed; TZ=America/Los_Angeles -> 286 passed, 2 xfailed
ruff check . (backend/) -> All checks passed!
npx tsc --noEmit (frontend) -> 0 errors; npm run test -- --run -> 27 files / 228 tests passed
# scope + terminators
git diff 49b46f9..23efdd5 --name-only (16 files); git diff 49b46f9..1fc1521 -- _docs/issues/T10.md (0 files)
git diff 3777e35..23efdd5 -- _docs/issues/T10.md (AC-7 only, 2 hunks)
for f in $(git diff 49b46f9..23efdd5 --name-only); do git show 23efdd5:$f | tr -d -c '\r' | wc -c; done  -> 0 x16
# platform
platform-post.sh comment T10 _qa/skeleton.md ; platform-post.sh comment T10 _qa/verdict.md
POST /issues/65/labels {"labels":["qa-passed"]} -> 200; GET recheck confirmed
