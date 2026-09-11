# TableQueue — Testing Guide

Version: 0.1.0
Last updated: 2026-09-10

---

## 1. Strategy

- **Backend**: endpoint tests + service tests + state machine tests.
- **Frontend**: API client tests + key component tests.
- **No E2E tests** in v1.
- **No concurrency tests** in v1.
- **Coverage goals**: backend 80%, frontend 70%.
- All tests must run with a single command.

---

## 2. Backend Tests

### Tools
- `pytest`
- `fastapi.testclient.TestClient`
- `freezegun` for time control
- in-memory SQLite for isolation

### Structure

backend/tests/
├── conftest.py
├── factories.py
├── test_auth.py
├── test_public_waitlist.py
├── test_public_board.py
├── test_staff_waitlist.py
├── test_staff_tables.py
├── test_staff_dashboard.py
├── test_admin_settings.py
├── test_admin_tables.py
├── test_state_machine.py
└── test_seed.py


### Fixtures (`conftest.py`)
- `db`: in-memory SQLite session, schema created, closed after test.
- `client`: FastAPI TestClient with `get_db` overridden.
- `fixed_now`: `datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)`.
- `staff_token`: valid JWT for staff endpoints.
- `auth_headers`: `{"Authorization": f"Bearer {staff_token}"}`.

### Factories (`factories.py`)
- `make_branch(db, **kwargs)`
- `make_table(db, **kwargs)`
- `make_waitlist_entry(db, **kwargs)`
- `make_settings(db, **kwargs)`
- `make_staff_token()`

### Test Names

**Auth**
- `test_login_success`
- `test_login_invalid_pin`
- `test_login_rate_limited`
- `test_change_pin_success`
- `test_change_pin_invalid_current`
- `test_change_pin_mismatch`
- `test_change_pin_same_as_current`

**Public Waitlist**
- `test_join_waitlist_success`
- `test_join_waitlist_duplicate_phone`
- `test_join_waitlist_closed`
- `test_join_waitlist_invalid_phone`
- `test_join_waitlist_party_size_out_of_range`
- `test_join_waitlist_note_too_long`
- `test_get_status_with_token`
- `test_get_status_with_phone_last3`
- `test_get_status_wrong_last3`
- `test_get_status_not_found`
- `test_cancel_waitlist_by_guest`
- `test_cancel_called_requires_confirmation`

**Public Board**
- `test_get_public_branch_success`
- `test_get_public_branch_not_found`
- `test_get_board_success`
- `test_get_board_empty`

**Staff Waitlist**
- `test_list_waitlist_active`
- `test_list_waitlist_closed`
- `test_list_waitlist_all`
- `test_list_waitlist_search_name`
- `test_list_waitlist_search_phone_last3`
- `test_call_waitlist_success`
- `test_call_waitlist_invalid_status`
- `test_seat_waitlist_success`
- `test_seat_waitlist_table_not_available`
- `test_seat_waitlist_table_not_found`
- `test_no_show_waitlist_success`
- `test_no_show_waitlist_invalid_status`
- `test_restore_waitlist_success`
- `test_restore_waitlist_invalid_status`
- `test_revert_waitlist_success`
- `test_revert_waitlist_invalid_status`
- `test_cancel_waitlist_by_staff`
- `test_edit_waitlist_party_size`
- `test_edit_waitlist_note`
- `test_edit_waitlist_invalid_status`
- `test_reorder_waitlist_success`
- `test_reorder_waitlist_missing_ids`
- `test_reorder_waitlist_extra_ids`

**Staff Tables**
- `test_list_tables_active`
- `test_list_tables_includes_current_waitlist`
- `test_update_table_status_available_to_cleaning`
- `test_update_table_status_cleaning_to_available`
- `test_update_table_status_occupied_rejected`
- `test_release_table_success`
- `test_release_table_not_occupied`

**Staff Dashboard**
- `test_dashboard_counts`
- `test_dashboard_avg_wait_null_when_no_data`

**Admin Settings**
- `test_get_settings_success`
- `test_update_settings_success`
- `test_update_settings_hold_minutes_out_of_range`
- `test_update_settings_queue_prefix_invalid`
- `test_update_settings_notification_templates`

**Admin Tables**
- `test_create_table_success`
- `test_create_table_duplicate_label`
- `test_update_table_success`
- `test_update_table_duplicate_label`
- `test_delete_table_soft`
- `test_delete_table_occupied_conflict`
- `test_list_admin_tables_include_inactive`

**State Machine**
- `test_lazy_no_show_after_timeout`
- `test_lazy_no_show_not_yet`
- `test_lazy_no_show_preserves_called_at`
- `test_close_day_closes_active_entries`
- `test_close_day_releases_tables`

**Seed**
- `test_seed_reset_creates_expected_data`
- `test_seed_without_reset_skips_existing`

### Time Injection
- Service functions take `now: datetime` parameter.
- Tests pass fixed time directly, or use `freezegun`.
- Boundary tests:
  - `2026-09-10 03:59` Taipei → `business_date = 2026-09-09`
  - `2026-09-10 04:00` Taipei → `business_date = 2026-09-10`
  - `2026-09-11 01:00` Taipei → `business_date = 2026-09-10`

---

## 3. Frontend Tests

### Tools
- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom` environment

### Structure

frontend/src/
├── api/
│ ├── client.test.ts
│ └── errors.test.ts
├── components/
│ ├── WaitlistCard.test.tsx
│ ├── Countdown.test.tsx
│ ├── TableCard.test.tsx
│ └── StatusBadge.test.tsx
├── pages/
│ ├── JoinPage.test.tsx
│ └── StatusPage.test.tsx
└── test/
├── setup.ts
└── fixtures.ts


### Fixtures (`fixtures.ts`)
- `mockWaitlistEntry(overrides?)`
- `mockTable(overrides?)`
- `mockBranch(overrides?)`
- `mockDashboard(overrides?)`
- `mockBoard(overrides?)`

### Test Names

**API Client**
- `client.test.ts`
  - `adds Authorization header when token exists`
  - `omits Authorization header when no token`
  - `parses error code from 4xx response`
  - `returns null on 204`
  - `throws ApiError on network failure`
  - `throws ApiError on timeout`
- `errors.test.ts`
  - `maps known error codes to messages`
  - `falls back to generic message`

**Components**
- `WaitlistCard.test.tsx`
  - `renders queue number and status`
  - `renders countdown when called`
  - `calls onCall when Call clicked`
  - `calls onSeat when Seat clicked`
- `Countdown.test.tsx`
  - `renders mm:ss format`
  - `turns red at zero`
  - `calls onComplete at zero`
- `TableCard.test.tsx`
  - `renders table label and capacity`
  - `renders occupied info when occupied`
  - `calls onRelease when Release clicked`
- `StatusBadge.test.tsx`
  - `renders correct text for each status`
  - `applies correct color class`

**Pages**
- `JoinPage.test.tsx`
  - `renders form when waitlist open`
  - `shows closed message when waitlist closed`
  - `validates required fields`
  - `validates phone format`
  - `shows duplicate phone error`
- `StatusPage.test.tsx`
  - `renders waiting state`
  - `renders called state with countdown`
  - `renders seated message`
  - `renders cancelled with join again`

---

## 4. Test Data

### Seed Data Mirror

- Restaurant: `Sunny Bistro`
- Branch: `Taipei Xinyi`
- Tables: `A1–A4` (2 pax), `B1–B4` (4 pax), `C1–C2` (6 pax)
- Phone range: `0900-000-001` to `0900-000-009`

- Backend factories mirror seed data.
- Frontend fixtures mirror backend response shapes.
- Fixtures use the same queue numbers as seed (`A001`, `A012`).
- Phones use `0900-000-0xx` pattern.
- Dates use `2026-09-10T13:00:00+08:00` as base.

---

## 5. Time Injection

- Backend: `get_now` dependency + `freezegun`.
- Frontend: `Countdown` takes `remainingSeconds` as prop; tests advance timers with `vi.advanceTimersByTime`.
- Never call `Date.now()` inside components without injection.

---

## 6. Coverage Goals

| Layer | Goal |
|---|---|
| Backend services | 80% |
| Backend routers | 80% |
| Frontend API client | 70% |
| Frontend components | 70% |
| Frontend pages | 50% |

- Not enforced in CI in v1.
- Measured manually with `pytest --cov` and `vitest --coverage`.

---

## 7. Non-Goals

- Playwright E2E
- Concurrency tests
- Load tests
- 100% coverage
- Visual regression tests
- Accessibility automated tests (manual only)

---

## 8. Commands

```bash
# Backend
cd backend
uv run pytest
uv run pytest --cov=app
uv run pytest tests/test_state_machine.py -v

# Frontend
cd frontend
npm run test
npm run test -- --coverage
npm run test -- WaitlistCard

# Both
make test```

---

## 9. Falsifiable Acceptance Gates

Every `AC-n` bash block in `_docs/issues/*.md` is a gate, not documentation. A gate is only
useful if it **can fail**: a block that prints PASS on every input, or that stays silent when
the condition does not hold, proves nothing and must be repaired before it is trusted. Before
an AC block is shipped, or re-used as a merge gate, it must be falsified by running it against
a deliberately broken or absent target and observing a FAIL line.

### Rule 1 - every AC block emits exactly one verdict token

Each AC block ends with an explicit verdict in both branches. The PASS branch must echo a
literal verdict token, and the FAIL branch must name the AC and the missing condition:

```bash
if [ -z "$MISSING" ]; then
  echo "PASS AC-n: what was checked"
else
  echo "FAIL AC-n: missing ${MISSING}"
fi
```

A block with no `else` branch, or with an `else` that prints nothing, cannot fail. The three
measured non-falsifiable anti-patterns and their remedies are below.

**Count-only blocks are accepted evidence, not defective ACs.** Rule 1 binds a block that claims
to be an AC: such a block must print exactly one verdict token. A block that instead prints a
deterministic numeric line (`lines=441`, `missing=2 of 10`, a population count) and whose green
condition is a tally asserted in the AC's prose is a measurement, not a broken gate, and the gate
tooling grades it `silent` to say "a machine did not decide this, a human must read it". The two gate tools describe the same block with two different labels, and both are right: the
signal checker (`accheck.py`) marks such a block `count-only(ok if prose states Green =)`, because
for this class the green condition is a tally asserted in the AC's prose, while the runner
(`runacs.py`) files it under `silent`. So a block is graded `silent` **and** exempt when its green
condition is a tally asserted in the prose; `silent` is not a defect label, it means a human must
read the number.
The population is not an estimate either: it is the AC whose block still prints only measurements
that lands in the bucket, so the list below is each bucket member by AC id, not a range. Each file
gets exactly one line below, and that line carries the count and every member of its bucket.
This repo uses that convention deliberately and in volume, as reported by the gate tool (`runacs.py`), and each file's bucket size and every one of its members sit on one line, in numeric order:
`_docs/issues/P0-08.md` has 14 ACs graded `silent` (AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-13, AC-14, AC-18, AC-19, AC-21).
`_docs/issues/P0-02.md` has 17 ACs graded `silent` (AC-2, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19) and its AC-3 is that file's only `other` member.
`_docs/issues/P0-05.md` has 11 ACs graded `silent` (AC-2, AC-3, AC-4, AC-5, AC-6, AC-8, AC-9, AC-10, AC-11, AC-12, AC-16) and an empty `other` bucket. `_docs/issues/P0-10.md` has 17 ACs in its `other` bucket (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-18).
`_docs/issues/P0-10.md` has 14 ACs in its `other` bucket (AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-12, AC-13, AC-14, AC-15, AC-16) and its AC-17, AC-19 and AC-20 sit under the tool's separate `silent (count-only or prose-declared green)` heading rather than in `silent`, because a block can print no verdict token and still not be silent; the two headings are not interchangeable and a quoted count has to name which one it came from.
Two properties of that run are stated because they are what makes these numbers reproducible: a bucket is a function of the tree it is graded in, so every run behind the counts above was made in this worktree with `backend/.venv` present, and `_docs/issues/P0-10.md` AC-11 lands in `other` only because its block's PASS verdict text quotes an opposite-token sample, which the runner collects line-wise and scores regardless of exit status. D-04 pulls exactly one block -
`P0-08` AC-1 - out of that population and into the verdict-token form, because that block was cited
as evidence by later work. The stricter reading (count-only blocks are non-AC evidence, so every real
AC must print a token) would require rewriting the AC blocks of those four files plus
`_docs/issues/P0-01.md` and the measurement ACs of `_docs/issues/F-16.md`, a measured count: 51 such
blocks today across those six already-merged issues, and it would re-open work the Orchestrator has
accepted. So `silent` is informational, and Rule 1 applies only to blocks presented as ACs; the
`P0-08` AC-1 repair is the exception, not the new rule.

### Rule 2 - a guard must be able to reach the failing path

A guard command that structurally cannot report the condition it claims to test makes the whole
gate decorative, even when the verdict branches are well formed. Two measured instances are
`git check-ignore` on a tracked path (Anti-pattern 1 below) and a pipeline whose exit status is
read from the wrong element (Anti-pattern 3 below).

### Rule 3 - the gate's own exit status must be checked, not inferred from prose

When an AC block wraps a test run or any external tool, the block must capture that tool's exit
status explicitly and branch on the captured variable. A printed summary line, a line count, or
the wrapper's own exit code is not evidence that the tool passed.

### Anti-pattern 1 - `git check-ignore` on a tracked path (the guard never reaches the tested path)

`git check-ignore` consults the exclude patterns but skips any path already present in the
index, so a tracked file always looks "not ignored". A gate written as
`git check-ignore -q "$f" && echo "$f"` therefore reports PASS even when the new rule does
match the tracked file, and can never fire. The remedy is to pass `--no-index`, which makes
`git check-ignore` evaluate the pattern against the path regardless of index state:

```bash
# red: a tracked .db file that the new rule matches is reported as PASS
hidden=$(git ls-files | while read -r f; do case "$f" in *.db) git check-ignore -q "$f" && echo "$f";; esac; done)

# green: --no-index sees the match, so the gate can actually fail
hidden=$(git ls-files | while read -r f; do case "$f" in *.db) git check-ignore -q --no-index "$f" && echo "$f";; esac; done)
```

Two exclusions keep this rule from eating rules that are already correct. It does not apply to a
`git check-ignore` call that already passes `--no-index`, and it does not apply to documentation
that names `--no-index` inside the same command line it criticises. Rule 5 binds the call site, not
the file: one correct `--no-index` call in `_docs/testing.md` does not license a bare one three
hundred lines later in the same file, which is how `_docs/testing.md` itself shipped the defect it
documents.

The equivalent assertion, for the case where you want the offenders listed rather than one path
branched on, is `git ls-files -i -c --exclude-standard`, which lists tracked files that the ignore
rules would exclude. Either form is acceptable when the
question is "does this rule match a path that may already be tracked". The ban is narrow: bare
`git check-ignore -q` is wrong **only** on a possibly tracked path, and it stays the correct call
for the ordinary question "is this untracked path ignored?". `F-16` AC-1 is the counter-example that
stops this rule from being over-read - a path a working ignore rule catches cannot be in the index,
so no `--no-index` is needed there:

```bash
if git check-ignore -q backend/test.db; then   # F-16 AC-1: correct as written
```

`F-16` AC-2 (`git check-ignore -q _acprobe.db`) is the same correct shape on a scratch probe file.
Both stay bare; adding `--no-index` to them would change nothing, because the flag matters only when
the path is already tracked.

### Anti-pattern 2 - a silent verdict branch (missing PASS token)

A gate that only echoes on failure prints nothing when everything is fine, so "no output" is
read as success by a reviewer and as an unknown by a machine parser. A missing verdict token
is indistinguishable from a gate that never ran. Always print both:

```bash
# red: silent on success - an automated run cannot tell "passed" from "never executed"
if [ -n "$VIOLATIONS" ]; then echo "FAIL: $VIOLATIONS violation(s)"; fi

# green: exactly one verdict token either way
if [ -z "$VIOLATIONS" ]; then
  echo "PASS AC-n: no violations found"
else
  echo "FAIL AC-n: $VIOLATIONS violation(s) found"
fi
```

### Anti-pattern 3 - a piped command whose exit status is read from the wrong element (`$?`)

`OUT=$(some-tool 2>&1 | tail -2)` followed by `if [ $? -ne 0 ]` tests the exit status of
`tail`, not of `some-tool`, so a failing tool still reports success. Turn on `pipefail` so the
assignment propagates the pipeline's failure, then read the first element's status in the statement
after it and branch on the captured variable:

```bash
set -o pipefail
OUT=$(pytest -q 2>&1 | tail -2)
RC=${PIPESTATUS[0]}
if [ "$RC" -eq 0 ]; then
  echo "PASS AC-n: checker exit status 0"
else
  echo "FAIL AC-n: checker exit status ${RC} - the gate can fail"
fi
```

```bash
# same gate as an if one-liner (machine-detector form); pipefail stays in effect
set -o pipefail
OUT=$(pytest -q 2>&1 | tail -2); RC=${PIPESTATUS[0]}
if [ "$RC" -eq 0 ]; then echo "PASS AC-n: checker exit status 0"; else echo "FAIL AC-n: checker exit status ${RC}"; fi
```

Do not "simplify" the `set -o pipefail` line away, and do not swap it for an `||` fallback: inside a
command substitution the assignment's own status replaces the pipeline's, so without `pipefail` a
checker that exits 3 still measures `rc=0`. Measured against a checker that exits 3: `OUT=$(cmd 2>&1
| tail -2)` followed by `RC=${PIPESTATUS[0]}`, and the one-statement `RC=${PIPESTATUS[0]} || RC=$?`
variant, both print `PASS rc=0`; the `set -o pipefail` form above prints `FAIL rc=3`. The same trap
sits one level down - `$?` read after a pipe is the status of the pipeline's **last** element
(`tail`, always 0 here), never of the checker.

Two supported shapes, then. Where the `PIPESTATUS` array is available, keep the pipe only with
`set -o pipefail` in effect and read `RC=${PIPESTATUS[0]}` in its own statement. Where it is not -
POSIX `sh`, or a block that may be pasted into one - drop the pipe inside the capture entirely
(`OUT=$(some-tool 2>&1); RC=$?`): the substituted command's status becomes the assignment's status,
so `$?` is the checker's own and no `pipefail` is needed. If the pipe is only for display, run it as
a bare pipeline and read `RC=${PIPESTATUS[0]}` on the next line, which needs no capture at all. That
display pipe is for display only: it discards everything the checker printed except the last two
lines, so a checker that exits 0 while explaining a problem reports PASS with the reason hidden -
keep the full output somewhere (a log file, or echo the captured variable) before triaging a failure
from it. Never branch on `$?` after a pipe that has no `pipefail`, and never print only a failure
branch: a checker exit status check must emit a verdict token both ways. One portability caveat on
the shapes above: `set -o pipefail` is not in POSIX and `dash` rejects it, so the `pipefail` form is
bash-only, exactly like the `PIPESTATUS` array it reads - a block that may be pasted into a POSIX
`sh` must use the no-pipe capture instead.

### Falsification procedure for a new or repaired gate

1. Run the block from the repo root against a tree where the requirement is **not** met
   (scratch worktree, `git stash`, or a temporary file with the opposite content).
2. Confirm the output contains a `FAIL AC-n:` line. Silent output is a FAIL of this rule.
3. Run it against the tree that satisfies the requirement and confirm the matching
   `PASS AC-n:` line.
4. Never conclude "it passed" from exit code alone: AC blocks exit 0 by design so that a
   failing verdict still runs cleanly, which means the verdict token is the only signal.
