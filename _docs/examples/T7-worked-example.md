# Worked example: a Constraints file list narrower than its own ACs (debt D9)

This is the worked example `CONTRIBUTING.md`'s **Constraints Convention** section points at. It is
a tracked document under `_docs/examples/` on purpose: an example a convention points at has to be
readable by the next engineer and by the gate, not sit in the ignored `_docs/state/` tree.

## The pattern, in one line

A `## Constraints` section lists the files an issue may touch and closes with "Nothing else", while
an AC in the same file can only go green by editing a file that list does not name. The AC set is
then unsatisfiable: the ACs say do the work, the Constraints say you may not, and the scope probe
says you did it wrong either way.

## Four real instances, all measured

| Case | What the Constraints list said | What an AC required | How it was caught |
|---|---|---|---|
| B-08 (#34) | the issue's own file list, closed with "Nothing else" | ACs that needed `services/table_write.py`, `table_conflict.py` | `git diff --name-only main...origin/issue/<branch>` listed files outside the list, ACs green |
| B-10 (#36) | same shape | `services/settings.py`, `errors.py`, `schemas.py`, `database.py` | same diff, same result |
| B-12 (#38) | same shape | `conftest.py` and friends | same diff, same result |
| **T7 (#59) itself** | round 2's AC-8 allowed-path regex admitted neither `_docs/issues/B-11.md` nor `_docs/testing.md` | **AC-2** must edit `_docs/issues/B-11.md` (three paperwork lines); **AC-3** must edit the `test_*.py` list in `_docs/testing.md`'s `### Structure` block | handoff, not CI: the groom-to-SW baseline run showed AC-2/AC-3 green forces AC-8 red and vice versa, so no implementation state satisfied all three |

The fourth case is the instructive one, because the issue written to legislate this exact defect
(item D9, scope items 4 and 5 of Platform #59) committed it on itself: its Constraints section and
its own scope-discipline probe had drifted apart. Round 3 fixed both at once, and the Constraints
section of `_docs/issues/T7.md` now opens with the rule that came out of it - if a round adds a
write target to the Constraints list, it must add the same entry to the scope probe's allowed set,
and the other way round.

## What the repair looked like

- `_docs/testing.md` moved from T7's denied list to a **narrow exception** entry, bounded to the
  `test_*.py` filename entries inside the `### Structure` code block, so a later section addition by
  the file's owning issue and this repair cannot collide.
- `_docs/issues/B-11.md` stayed an exception with three named line-kinds: the Metadata `Owner stub`
  count, the Definition of Done first-line count, and the Test-requirements bullet that names
  fixtures. No AC text, no DoD semantics beyond the count.
- AC-8's allowed-path regex gained exactly those two alternatives. Nothing else in the regex moved.

## What to do instead of repeating it

1. Before the AC set is frozen, list what each AC has to touch to print its PASS line, and compare
   that union against the Constraints list. That comparison is five minutes and costs one child
   round if skipped (see `_docs/debt-register.md` rows D9 and D7).
2. If the union escapes the list, widen the list **in the same edit that lands the AC**, with a
   one-line reason per added path, and bound it as narrowly as the AC allows (a section, a
   filename-entry set, a prefix) rather than a whole directory.
3. Never resolve the collision by deleting the AC's requirement or by editing a merged issue file
   that a frozen gate reads. Post `[CONSTRAINT VIOLATION REQUEST]` and let the groom decide.
