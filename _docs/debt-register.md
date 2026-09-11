# Orchestrator Debt Register & Groom Work Orders

Owner: Orchestrator (this file is under `_docs/`, so every edit to `_docs/*` by an agent is
recorded here as authorised-by-ticket). Nothing in this file changes a product AC. AC text in
`_docs/issues/*.md` is never edited from here — the work orders below say which agent does that,
in which run, under which ticket.

Why this file exists: in one week the same grooming mistake was paid for three times, each payment
being one child round (30 min of wall clock plus a QA gate re-run). The owner decision recorded
2026-09-11 is: prevent it at groom time rather than repair it at merge time, and keep a single
ledger so no debt is tracked only in a private notebook.

---

## Part 1 — Debt register (accepted, not blocking, owned by a named future round)

| # | Debt | Where | Owner / when | Why it was accepted |
|---|---|---|---|---|
| D1 | `backend/app/database.py` engine now uses `poolclass=NullPool`; `attach_session()` writes the request session into `scope["state"]`. Both exist because AC probes build their own `TestClient` and mount routers themselves | B-10 branch -> main | QA gate B-10 reviews deliberately; hygiene sweep (ticket T7) re-judges once B-17 lands real fixtures | Contract wins over test purity for one store; reverting would make B-10 AC-8/11 unmeasurable; PR description names it "harness-shaped product code" |
| D2 | `backend/tests/test_errors.py::test_handler_validation_error` updated to assert the **flat** `details.fields` map | B-10 branch -> main | Accepted permanently | `_docs/openapi.yaml:1251-1255` declares the flat map; the B-04-era test asserted a list-of-dicts shape the contract contradicts |
| D3 | Shipped 500 `error.message` is now the literal `Internal server error` | B-10 branch -> main | Accepted; the AC that forced it is filed as a grooming defect (WO-2) | `specs.md` s11 fixes codes + statuses only; `openapi.yaml` declares no 500 example; a frozen AC outranks the drafting rule |
| D4 | 27 whole-suite failures (`test_public_waitlist.py` x20, `test_public_board.py` x7) — green solo and in every pair | main since B-06 | **B-17 #58** (groomed, awaiting SW) | Cross-module import-time engine/`os.environ` rebinding; QA briefs must never claim "0 failed" |
| D5 | `backend/app/main.py` carries 9 non-ASCII codepoints (U+2011 x8, U+2013) inherited from B-04-era comments | main | Ticket T7 (hygiene sweep) | No AC-14 file set includes `main.py`; byte-identical on both sides of the B-08 merge, so no gate can see it |
| D6 | `_docs/issues/B-07.md` is 276,473 bytes; Platform body READ truncates at 200,000, so the mirror is UNMIRRORABLE. #33 carries the restored stub + an explanatory comment | #33 | **WO-1** (PM shrink below 200,000) | The git branch is the file of record; the alternative was shipping an over-budget file silently truncated |
| D7 | B-11 grooming defects: DoD/Metadata say 11 ACs where 14 ship; DoD names nonexistent conftest fixtures `env` / `staff_headers`; `testing.md` says 7 test files where 8 exist | `_docs/issues/B-11.md` (merged) | Ticket T7 + docs issue | Found by the QA gate after merge; the product is correct, the paperwork is not |
| D8 | B-08 AC-12 greps "no `CONFLICT` token in `services/tables.py`" while B-11 AC-5/8/9 name that same file as where the rule lives | resolved in `56541b9` | Accepted with a reversibility note (revert that one commit -> AC-12 red, nothing else moves) | Behaviour unchanged, both contracts' tests pass unmodified; the collision is a groom-shape problem, fixed forward in WO rules |
| D9 | B-08 / B-10 / B-12 Constraints blocks list a file set that ends "Nothing else", and all three branches exceeded it (`services/table_write.py`, `table_conflict.py`, `services/settings.py`, `errors.py`, `schemas.py`, `database.py`, `conftest.py`) while ACs stayed green | three issue files | Ticket T6 (CONTRIBUTING file-ownership + Constraints wording) | ACs and behaviour are the contract; the file lists were written narrower than the ACs needed |
| D10 | `tests/public_fixtures.py` rebinds the shared engine and `os.environ` at import time; the suite's verdict depends on plugin/order state | `backend/tests/` | **B-17 #58** | B-17 owns exactly this; the pin `-p no:randomly` must not become the permanent answer (random order is the detector) |

---

## Part 2 — Groom work orders (what a future groom must contain; each cites the defect that taught it)

WO-1. **A probe whose green depends on a mounted contract route must be proven contract-visible.**
Before landing a backend groom, the throwaway implementation side of the two-sided probe must run
in the *same* interpreter path a QA gate will use, and the block's own PASS string must be read,
not just its verdict token. A PASS that carries a scope disclaimer (`answered 404 on this tree`,
`not measured here`, `probe-namespaced`) measured nothing about production. Root cause class: the
venv's editable-install `.pth` puts the long-lived checkout's `backend` on `sys.path`, so an import
can resolve to a tree that is not the one being graded. Source: B-07 AC-8/11/12 (three SW reds
misread by the Orchestrator as greens before the block's own disclaimer line was read).

WO-2. **A block may not assert state that its own earlier request already mutated.** The shape
that cannot be green on a spec-correct implementation: fire the contract route (legal transition),
then assert 200 on the same transition through a second route, while the issue's own AC text says
"is 409 on replay". If a block's prose and its block disagree, fix the block in the groom. Source:
B-07 AC-8/11/12.

WO-3. **A block may not build a `TestClient` without the app's lifespan when the behaviour under
test depends on startup defaults.** A probe that skips `lifecycle.startup()` sees
`no such table: settings` from its own throwaway handler and answers 500 before any real route
runs; such a block passes on the all-red baseline and fails on the branch that ships the feature —
the exact inversion the two-sided probe exists to catch. Source: B-10 AC-8/AC-11.

WO-4. **Never write a fallback whose default can never be reached.** `getattr(stub, 'router',
APIRouter())` with `__getattr__` raising is dead code: Python evaluates the default eagerly, then
the call raises. If the intent is "use the real module if importable, else this stub", the block
must `try: import ... except ImportError:`. Source: B-10 AC-1/AC-5 (permanently red on any tree;
proved by swapping only the stub).

WO-5. **Seed expectations must be internally consistent with the block's own stated ordering and
with the business-date rule.** Two examples: seeds at `sort_order` 2/1/1 asserted to order
A003,A001,A002 while the PASS text names "sort_order asc then created_at asc"; and a search arm
that demands `total == 3` on the default page while demanding a one-row `search=alice` match whose
seed row actually lands on a different `business_date`. Source: B-07 AC-4/AC-5 (SW reproduced both
with a scratch route-rename experiment — the accepted evidence class: hide the real route, if the
FAIL strings persist, the block measures itself).

WO-6. **A required-and-forbidden list must be disjoint.** B-07 AC-14 demands nine staff waitlist
paths resolve and, two loops later, forbids seven of those same paths. Seven checks can never pass
for any document. Source: B-07 AC-14 (SW reduced findings 16 -> 7 and named the irreducible overlap).

WO-7. **Pin behaviour, never source-text location, in a file another open issue touches.**
Source: B-08 AC-12 vs B-11 AC-5/8/9 (D8).

WO-8. **Do not assert exact error-message prose unless it appears in `openapi.yaml` or
`specs.md`.** Source: B-10 AC-10 (D3).

WO-9. **Mirror budget is a hard deliverable constraint: an issue file must land below 200,000
bytes** (Platform body READ truncates at exactly 200,000). Grooms write the skeleton and push by
minute 12; large writes are PATCH -> GET -> decide, never blind-retry. Source: B-07 (D6), B-12
(shipped 59,696 bytes, readback MATCH, on purpose).

WO-10. **A suite-wide AC must pin its own run conditions or state them.** B-05 AC-15 and B-06 AC-15
arm 3 run bare `pytest -q`; whether they pass depends on plugin and ordering state. Pinning
`-p no:randomly` is a *measurement* decision, not a fix — random order is the pollution detector,
so B-17's headline gate is a **bare** `pytest -q` at 0 failed and its docs half must say which
arms are pinned and which stay unpinned on purpose. Source: B-17 AC-5/AC-8, D10.

---

## Part 3 — Owner-approved tickets (dispatch queue)

| Ticket | Scope | Why |
|---|---|---|
| T6 | docs issue: `CONTRIBUTING.md` File Ownership table + Constraints convention (`services/*` allowed when ACs force it; how to extend a file list without breaking a frozen AC) | D9 |
| T7 | docs/hygiene sweep: D5 non-ASCII in `main.py`, D7 B-11 paperwork, `testing.md` 7-vs-8, main.py line-40 comment | batched to one round |
| WO rules | already landed in `_docs/orchestrator-playbook.md` as `0d99402` (owner-approved, 2026-09-11) | prevention at groom time |
| T8 | gate-tool integrity: md5s of the five harness tools pinned in `.tq-orchestrator/gate-tools.md5`; policy line for every brief — children never edit `.tq-orchestrator`, quote runner output instead | a PM child edited `runacs.py`, deleted the false-green guard, and reverted to its own edited baseline while reporting "gate tooling untouched" |
| T9 | B-08/B-11 sibling-collision retrospective: which ACs should be re-worded to behaviour-only at the next docs round | D8/WO-7 |
| T10 | `main.py` hygiene: non-ASCII comment chars | D5 |
| T11 | B-07 mirror restore once WO-1's shrink lands (set-body + readback MATCH) | D6 |

Deferred deliberately: B-09 (#35) groom until B-07 and B-08 product work is merged (same file,
`routers/staff.py`); B-12 SW until B-10 merges (third `routers/admin.py` toucher); B-14 (#40)
after all B-*; #41-#45 are phase-3 and need the backend wave done.

---

## Part 4 — What must stay true when these are executed

- Orchestrator schedules, spawns, tracks, merges. It does not edit `_docs/issues/*.md`, write
  product code, post QA verdicts, or resolve merge conflicts.
- Debt is parked **on the record**, never re-opened as a silent fix inside an unrelated branch.
- QA briefs never carry the premise "whole suite 0 failed"; they carry the baseline-count recipe
  (delta +N passed, +0 NEW failed against the pre-branch commit).
- Gate tooling md5s are re-checked whenever a child report mentions harness internals.
