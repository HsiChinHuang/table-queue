"""Re-run one AC block of an issue file, from the issue, with its provenance checked.

Why a re-runner is committed rather than improvised per review: this issue's blocks are the
contract, but the only copy of a block that bash can execute is a line list inside a Markdown file,
and the two ways a reviewer has of getting at it both have a hole. Cutting the fenced region out of
the file gives text that may have drifted from the probe sources without anything noticing;
regenerating from the sources gives bytes that may not be the text the issue actually ships. This
script closes the gap from the issue's own side: it cuts the block between the two marker lines the
generator emits, checks that the tree's probe sources still reproduce the staged bytes, and only
then runs the staged text.

Refusal is the point. A run whose provenance could not be established prints a refusal rather than a
verdict, so a green from here is a green whose inputs were checked, and a hand-edited block is
reported as an integrity finding instead of being silently re-based.

Usage, from the repo root of the tree under test:

    python3 _docs/issues/_t20/replay_block.py 13 [issue-path]

The block text is written to a scratch file and executed with bash, never under `set -e` or
`set -o pipefail`: the contract is the printed verdict token, and a strict shell turns a truncating
consumer into a false failure. The scratch file is left in place so a block that re-reads `$0` (see
AC-13, which reviews its own stage steps) sees the text it was run from.
"""
import difflib
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

FENCE = chr(96) * 3
# The same stem the generator writes, spelled once more here rather than imported: this file is the
# independent side of the provenance check, and if it located regions with the generator's own helper
# the two sides could agree while both were wrong. The stem is shared vocabulary; the SEARCH stays
# independent of it.
MARK_STEM = "AC-%s stage step" + "s "
BEGIN = MARK_STEM + "begin "
END = MARK_STEM + "end "

def extract(md, ac):
    """The block body between the marker lines, or from the fence pair if the block is older.

    Both shapes are supported because the issue has contained both: a block written before the
    markers existed is still the block a reviewer reads, and a re-runner that only understood the
    newer shape would report it as absent rather than measure it.
    """
    b = md.find(BEGIN % ac)
    e = md.find(END % ac)
    if b != -1 and e > b:
        # De-indent by the marker's own indent: the lines live inside a list item, and the generator
        # emits the stage steps flush, so the difference between those two is the whole indent and it
        # is read from the file rather than assumed.
        bol = md.rfind("\n", 0, b) + 1
        pad = len(md[bol:]) - len(md[bol:].lstrip())
        # The region INCLUDES both marker lines: from the newline that opens the BEGIN line to the one that
        # opens the END line. A block copying itself can locate its markers but cannot reproduce their
        # text, so dropping them on one side only would make two identical blocks differ by exactly
        # those lines. Keeping them on both sides makes the copies comparable with no normalisation
        # step at all, which is the only comparison worth trusting.
        raw = md[md.rfind("\n", 0, b):e].split("\n")
        return "\n".join(ln[pad:].rstrip() if ln.startswith(" " * pad) else ln.rstrip()
                          for ln in raw).strip("\n")
    for m in re.finditer(r"(?m)^[ \t]*" + re.escape(FENCE) + "bash\n(.*?)(?:\n[ \t]*"
                         + re.escape(FENCE) + "$)", md, re.S):
        if ("# AC-%s executes" % ac) in m.group(1):
            return m.group(1).strip("\n")
    return ""


def staged_lines(body):
    """(dest, text) for every staged line the block writes, in order.

    A single parser, used for both sides of the provenance check. Two shell facts shape it. (1) The
    line is tokenised with shlex, exactly as bash will tokenise it, and the argument the printf
    writes is read back UNQUOTED: comparing quoted forms would compare quoting styles rather than
    content, and would miss a line whose quoting was edited into a different quoting. (2) The
    destination is kept, because it decides which of the two probe files the line lands in - AC-12's
    clause table staged into AC-10's path is a difference, not a match. The payload digest ignores
    the destination by design (that is AC-9's contract); this comparison does not, because a replay
    tool is asking a stricter question.
    """
    out = []
    for ln in body.split("\n"):
        s = ln.strip()
        if not s.startswith("printf "):
            continue
        toks = shlex.split(s)
        try:
            arrow = toks.index(">>")
        except ValueError:
            continue
        if len(toks) < 4:
            continue
        # toks[1] is the printf format, so the payload is what remains: the quoted word, in
        # shlex's canonical single-quoted form, exactly as the generator writes it.
        # Only the PAYLOAD is re-quoted; the destination is passed through as the block wrote it.
        # shlex.quote of an already-quoted word re-quotes it (`"$X"` becomes `"$X"` wrapped
        # again), so quoting both sides is not symmetric unless one side was ever unquoted: the
        # generator emits its destination bare and the block emits the block's, so the only
        # symmetric comparison is text-in-canonical-quoting against destination-as-spelled. A
        # destination edit still reads as a difference, because it is compared as written.
        # Canonical form on both sides, and "canonical" has to mean the same function on both
        # sides. shlex.join of a single word is NOT shlex.quote of it - shlex leaves an inner quote
        # bare where quote would close and reopen - so the block side re-quotes the same single word
        # the generator side re-quotes, and the two cannot drift apart by spelling.
        out.append((toks[arrow + 1], shlex.quote(toks[2])))
    return out


def staged_payload(body):
    return ["%s %s" % pair for pair in staged_lines(body)]


def expected_payload(root, probe, clauses):
    """The (dest, text) pairs the generator stages for these two sources.

    The generator supplies the lines - `stage_body()` is the same function that writes them into the
    block - and `shlex.quote`, imported rather than reimplemented, supplies the quoting. What this
    side computes INDEPENDENTLY is the reduction of a block's own text back to payload pairs (see
    `staged_lines`): if that direction also called the generator, the check would compare the
    generator with itself and prove nothing about the file on disk. Two asymmetries make the
    comparison meaningful rather than tautological: the destination is the scratch path the block
    actually writes to (a block stages both files as probe.py/clauses.py, so the destination can
    only agree if the ORDER agrees), and the text is compared in the generator's canonical quoting,
    which a hand-edited block will not reproduce.
    """
    # sys.path is snapshotted and restored: this function imports the generator, and the block it
    # is about to run may itself import a module of that name from somewhere else. A checker that
    # poisoned the interpreter state of the thing it checks would be reporting on itself.
    saved = list(sys.path)
    sys.path.insert(0, str(root / "_docs" / "issues" / "_t20"))
    import generate_t20_probes as gen
    out = []
    for dest, f in (('"$TMPDIR/probe.py"', probe), ('"$TMPDIR/clauses.py"', clauses)):
        for ln in gen.stage_body(Path(gen.BLK) / f):
            # shlex.join on both sides, never quote here and join there (see staged_lines).
            out.append((dest.strip('"'), shlex.join([ln])))
    sys.path[:] = saved
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: replay_block.py <AC-number> [issue-path]")
    ac = sys.argv[1].replace("AC-", "")
    root = Path.cwd()
    issue = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "_docs" / "issues" / "T20.md"
    md = issue.read_text(encoding="utf-8")
    body = extract(md, ac)
    if not body:
        print("REFUSE AC-%s: the issue carries no executable block for that AC, so there is nothing "
              "to replay (this is a finding about the file, not about the fix)" % ac)
        raise SystemExit(0)

    m = re.search(r"# AC-%s executes" % ac, body)
    # The head comment is prose, so its lines are joined before the names are read: the manifest
    # sentence may break across lines for width reasons, and a checker that only understood one
    # line would refuse a block whose provenance it could in fact verify.
    head = body[:m.start()] if m else body
    # The manifest is the two `- Probes:` list items, and only those. Lines are joined first
    # because a bash comment ends at its newline while a markdown list item may not; restricting to
    # the list items matters because AC-13's prose cites probe9.py (the checker it imports), and a
    # scan over the whole head would report three sources for a block that stages two.
    items = [ln for ln in head.split("\n") if ln.strip().startswith("- Probes:")]
    names = sorted(set(re.findall(r"probes/([A-Za-z0-9_]+\.py)", " ".join(items))))
    if len(names) != 2:
        print("REFUSE AC-%s: the block does not name both of its probe sources at its head, so its "
              "provenance cannot be checked; saw %s" % (ac, names or "none"))
        raise SystemExit(0)
    # Order comes from the manifest, not from a sort: the two names are probe9.py and clauses9.py,
    # and sorting them alphabetically hands clauses9.py to the probe position. The bug stayed hidden
    # while every block staged the same pair in the same accidental order, and surfaced the moment
    # AC-9's table became prose-shaped differently from its checker.
    listed = re.findall(r"- Probes: *probes/([A-Za-z0-9_]+\.py)", " ".join(items))
    if len(listed) != 2 or len(set(listed)) != 2:
        print("REFUSE AC-%s: the manifest names %s, and a block whose sources cannot be told apart "
              "cannot be replayed" % (ac, listed or "nothing"))
        raise SystemExit(0)
    probe, clauses = listed
    names = sorted(set(listed))
    missing = [n for n in names if not (root / "_docs" / "issues" / "_t20" / "probes" / n).exists()]
    if missing:
        print("REFUSE AC-%s: %s is not in this tree, so the block's sources are not here to check "
              "against" % (ac, ",".join(missing)))
        raise SystemExit(0)
    if not staged_lines(body):
        print("REFUSE AC-%s: the block stages no probe lines at all, so there is nothing to compare "
              "and nothing that can be certified" % ac)
        raise SystemExit(0)

    want = ["%s %s" % pair for pair in expected_payload(root, probe, clauses)]
    got = ["%s %s" % pair for pair in staged_lines(body)]
    if want == got:
        diff = []
    else:
        # difflib's unified format cannot render a pure insertion at the end of two sequences that
        # otherwise agree: it wants a context hunk and finds none, and raises. The comparison below
        # is therefore made first and the diff is only asked for when there IS a difference - and
        # even then with the error path guarded, because a replay tool that crashes on the shape of
        # a difference would report no finding at all, which is worse than reporting it badly.
        try:
            diff = list(difflib.unified_diff(want, got, "tree sources", "block as the issue ships it",
                                             lineterm="", n=0))
        except Exception as exc:
            diff = ["cannot render a diff (%s); first differing entry below" % type(exc).__name__]
            diff += ["- %s" % x for x in want[:4]] + ["+ %s" % x for x in got[:4]]
    if diff:
        print("REFUSE AC-%s: the block staged in the issue does not reproduce from the probe sources "
              "in this tree (%d staged line(s) vs %d from the sources). That is an integrity "
              "finding: either the block was hand-edited or the sources changed without "
              "regenerating. First differing lines:" % (ac, len(got), len(want)))
        for ln in diff[:12]:
            print("  PROVENANCE " + ln[:200])
        raise SystemExit(0)

    with tempfile.TemporaryDirectory(prefix="t20replay-") as td:
        script = Path(td) / ("ac%s.sh" % ac)
        script.write_text(body + "\n", encoding="utf-8")
        proc = subprocess.run(["bash", str(script)], cwd=str(root), capture_output=True, text=True,
                              env={**dict(os.environ), "T20_REPLAY_OF": issue.name})
        sys.stdout.write(proc.stdout)
        if proc.stderr.strip():
            sys.stdout.write("[stderr]\n" + proc.stderr)
        if proc.returncode:
            print("NOTE AC-%s: bash exited %d. rc is diagnostic only - the verdict is the printed "
                  "PASS/FAIL AC-%s token above." % (ac, proc.returncode, ac))
        print("PROVENANCE OK AC-%s: the block was cut from %s, its %d staged line(s) reproduce from "
              "%s and %s in this tree, and bash ran the staged text itself."
              % (ac, issue.name, len(got), probe, clauses))
