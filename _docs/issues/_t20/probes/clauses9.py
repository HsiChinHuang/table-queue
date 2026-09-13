"""T20 AC-9 clause table: transposes the digest checker's lines into one verdict token.

The checker at _docs/issues/_t20/probes/probe9.py already prints one PASS/FAIL line per clause and a
whole-AC verdict, so this table re-derives none of its arithmetic. Re-deriving it would measure the
copy of "the payload" sitting in the tree, which is the disagreement AC-9 exists to detect, not a
restatement of it. What the table adds is the block's shell contract: whether the checker produced a
verdict at all, and whether that verdict survives as the block's own token line so a truncating
consumer carries the answer even when it never reaches a detail line.

One addition over a plain transposition, and it is deliberate. The checker prints its whole-AC verdict
FIRST and its per-clause detail after it, so the block's first line repeats the verdict with the
number of unpinned entries inside it. That number matters: an entry pinned as a self-reference is a
gap the checker states rather than a clause it measured, and a reader who sees only the first line
must learn the gap is there instead of scrolling forty lines to discover that part of the green was
pass-by-declaration.
"""
import sys

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""
text = lines.splitlines()
verdict = [l for l in text if l.startswith(("PASS AC-9:", "FAIL AC-9:"))]
fails = [l for l in text if l.startswith("FAIL AC-9:")]
passes = [l for l in text if l.startswith("PASS AC-9:")]
unpinned = [l for l in text
            if l.startswith(("PASS AC-9 ", "FAIL AC-9 ")) and "self_referential" in l]
pin_count = len([l for l in text if l.startswith("PASS AC-9 payload_")]) - len(unpinned)

if not verdict:
    print("FAIL AC-9: the digest checker printed no verdict line, so this block measured nothing "
          "(its rc is diagnostic only; re-run it from the repo root of the tree under test)")
elif verdict[0].startswith("PASS AC-9:"):
    print("PASS AC-9: the committed digest checker reports zero drift over %d clause line(s); %d of "
          "its recorded block payloads are pinned digests and %d is the block that cannot pin itself "
          "(see its own line below)" % (len(passes) - 1, pin_count, len(unpinned)))
else:
    print("FAIL AC-9: the committed digest checker reports %d failed clause(s), named below"
          % (len(fails) - 1))
print("\n".join(l for l in text if l.startswith(("PASS AC-9 ", "FAIL AC-9 "))))
