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

*(PM light: fill in. Orchestrator background: land B-14 on `main` without losing either side of
the single conflicting region — the `## Structure` `backend/tests/` listing that BOTH T7 (now
merged at 50012be) and B-14 rewrote. The merge commit then carries B-14's green gate with it.)*

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

*(PM light: fill. 5.3: AC = union of the conflicting issues' relevant ACs — the gates that MUST
be green on the merged tree: B-14 AC-4 (doc↔collected both directions), B-14 AC-1 (full suite),
B-14 AC-3 (ruff 0/0), T7 AC-3 (testing.md = exactly the 19 files) — and T7 AC-8 is NOT applicable
to a lane that changes testing.md beyond the inventory region; PM must state each AC with a
runnable block per rules 4.11. SW must additionally re-run runacs of BOTH issue files as
cross-check, and re-run T7 AC-3 from the merged T7.md copy.)*

## Constraints

*(PM light: fill. Non-negotiables: resolve the one hunk by content, never by wholesale checkout of
one side; no force-push; suite runs with TMPDIR off /mnt/c (drvfs breaks pytest capture — WAL 303)
and from a worktree without the orchestrator .env (pydantic extra=forbid — WAL 303); TZ note:
run gate runs while host calendar date == UTC date unless B-14's fix is already in the tree.)*

## Test requirements

## Implementation notes

## Dependencies

## Out of scope

## Definition of Done
