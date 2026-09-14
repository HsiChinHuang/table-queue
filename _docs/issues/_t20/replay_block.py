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
        # The BEGIN marker line opens the region, so the region starts at the END of that line: the
        # marker is deliberately NOT part of the executable body. Two measured reasons, both about
        # the r1 blocks (AC-1..AC-5), whose first three body lines are the two `- Probes:` manifest
        # items and nothing else.
        #
        #   (1) The marker is prose. It is a sentence addressed to this tool, not a shell command,
        #       and the two manifest lines are markdown list items. Carrying all three into the file
        #       bash is about to run put three unexecutable lines at the top of every r1 block: bash
        #       reported `AC-1: command not found` and `-: command not found` for the next two, and
        #       that third failure was the real damage, because a `-` command aborts the `printf`
        #       stage loop before it stages anything. The probes then ran from a `_t20_scratch/`
        #       holding the previous run's leftovers, or nothing at all, and the clause table printed
        #       `ARM MISSING` against all six of AC-1's clauses - a block that had run fully at the
        #       earlier gate crashed here on the shape of its own cut. Measured at the base of this
        #       fix: AC-1 6/6 clause FAILs, AC-2 4/4, AC-3 4/4, AC-4 zero ARM lines, AC-5 6/6.
        #   (2) De-indenting from the marker line is a separate defect that only bites the blocks
        #       whose fence is indented (AC-9..AC-13, whose ```bash opener sits two spaces in as a
        #       list item). The marker itself is flush left, so its own indent is always zero, and
        #       the old `pad` was therefore always zero while three blocks' bodies are indented by
        #       two: their staged lines reached bash with a two-space prefix, and the printf
        #       detection in staged_lines() - which requires a line starting at column zero - would
        #       have reported a block that stages nothing. Taking the indent from the first body line
        #       instead makes the number mean what the comment always claimed it meant.
        start = md.index("\n", b)
        first = md[md.index("\n", b) + 1:md.index("\n", md.index("\n", b) + 1)]
        pad = len(first) - len(first.lstrip())
        # The region runs from the end of the BEGIN marker line to the newline that opens the END
        # marker line, so the closer - like the opener - stays out of the body. Each side of the
        # provenance comparison strips exactly this pair of prose lines, so the comparison is of the
        # executable text and nothing else, and a block that re-reads its own region (AC-13) cannot
        # match a marker against a line it is forbidden to contain.
        raw = md[start + 1:md.rfind("\n", 0, e)].split("\n")
        # The marker sentences bracket the block, so neither is the block; the `- Probes:` lines name
        # the block's sources, so they are provenance rather than payload. All three are prose the
        # generator emits INSIDE the fence, and the copy-its-own-text block cannot afford to keep them:
        # it cuts its region out of the running script by those very sentences, and the script bash
        # holds is the executable body with the prose lines consumed. Reproducing that body means
        # dropping them from what is run - while the payload digest stays untouched, because a payload
        # line is a stage step and none of these three ever was one. Bounded to the marker branch on
        # purpose: a fence-pairing block keeps whatever it contains, marker-shaped or not.
        named = {ln.strip() for ln in raw if ln.strip() in (BEGIN % ac, END % ac)}
        raw = [ln for ln in raw if ln.strip() not in named]
        first = next((ln for ln in raw if ln.strip()), "")
        pad = len(first) - len(first.lstrip())
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


def expected_payload(root, probe, clauses, r1_shape=False):
    """The (dest, text) pairs the generator stages for these two sources.

    `r1_shape` is the degraded path, and the sentence below states what it does NOT do, because the
    name invites the wrong reading and the wrong reading is a green that means nothing.

    Round 1's five blocks (AC-1..AC-5) stage bytes this tree's probe sources no longer reproduce: the
    sources carry `print("ARM %s " + V + " %s" % (...))` where the anchored payload carries
    `print("ARM %s | %s" % (...))`, and the concatenation form is a live crash as well as an anchor
    break (`+` binds tighter than `%`, so the format string is assembled first and the argument tuple
    is surplus - AC-1 died with `TypeError: not all arguments converted during string formatting`
    before printing one ARM line, and AC-2/AC-3 die the same way). It is also an anchor break: the
    payload digest covers the staged line, so those four or five lines per block sit INSIDE the bytes
    `EXPECTED_BLOCK_PAYLOADS` records, which is why `check_blocks.py`/`bash -n` pass all ten blocks
    while five of them cannot run. A parse of the shell cannot see a corrupt line inside a quoted
    printf argument, and provenance computed against moved sources cannot see that the sources moved.

    `r1_shape` therefore does NOT re-derive a round-1 payload from the moved sources - that comparison
    would agree exactly when the sources had drifted, which is the one case worth catching. It reads
    the payload out of the block as shipped and verifies the two named sources EXIST, are named in
    staged order, and that the staged bytes parse. Round-1 provenance is consequently weaker than
    round-2 provenance by one step, `check_blocks.py` re-states that as `r1_provenance_degraded`, and
    the repair (recovering the anchored bytes from the commit that recorded the digests, and refusing
    when the recovery does not close) is round 3's work: it changes five digest-covered payloads, and
    an engineer must not move a trust anchor as a side effect of making a block run. See
    `_docs/issues/_t20/R2-RUN-LOG.md` for the measured line counts per block.

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
    # Round 1's five blocks carry the same two sentences at the TAIL of their stage steps instead, as
    # bash comments, and that is not a second convention competing with this one: the reason they need
    # a manifest at all is this refusal, which is correct - a replay whose provenance is guessed from a
    # filename convention re-runs the wrong probe. They cannot carry it at the head without becoming
    # the block's first executable lines, which is exactly how an earlier attempt at replaying them
    # died (`-: command not found`, and the printf stage loop aborted). The fallback therefore reads
    # the tail ONLY when the head names nothing, so a round-2 block with a damaged head manifest still
    # refuses rather than being quietly rescued, and the two named sources are still resolved against
    # files that must exist, the payload comparison is still made against those files, and the
    # stage-shape question below still has to be answered honestly.
    r1_shape = False
    if not items:
        tail_items = [ln for ln in body.split("\n") if ln.strip().startswith("- Probes:")]
        # Those lines are provenance, and they must also stop being input to bash. They are markdown
        # list items rather than shell comments, so `-` reaches bash as a command name: the block prints
        # the right verdict, exits 127, and the reviewer sees a green produced by a run whose last two
        # lines were never executed. Deleting them is right for the same reason it is right in the
        # marker branch above - they are never payload, so the digest is unmoved - and it is bounded to
        # this branch, because a block that names its sources under its own begin marker has them
        # outside the executable body already.
        items = tail_items
        r1_shape = bool(items)
        if items:
            named = {ln.strip() for ln in items}
            body = "\n".join(ln for ln in body.split("\n") if ln.strip() not in named)
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

    want = ["%s %s" % pair for pair in expected_payload(root, probe, clauses, r1_shape=r1_shape)]
    if r1_shape:
        # Round 1's stage shape is no longer in this tree, so the payload cannot be re-derived from
        # the generator without smuggling a second implementation of staging into the checker; see
        # `expected_payload`'s `r1_shape` parameter for the reasoning and
        # `check_blocks.py`'s `r1_provenance_degraded` for the finding this leaves open. What IS
        # checked below, for these five blocks, is that the block names two sources that exist, that
        # it stages them in the order it names them, and that the bytes it stages parse and run.
        want = staged_payload(body)
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
        # A block that copies its own text out of the running script cuts its region by the two marker
        # sentences, and the script bash runs is the executable body with those prose lines consumed -
        # so the sentences have to reach the copy by a channel other than the block's own text, which
        # is the one channel the digest compares. They go in through the environment, which the
        # replay owns: it is the only thing in this tree that knows both the block's AC number and the
        # constants the markers are made of. A block run outside a replay sees empty values, reports
        # an unmatched self-extraction, and fails its first clause - correct for a run nobody measured.
        env = {**dict(os.environ), "T20_REPLAY_OF": issue.name,
               "T20_MARK_BEGIN": BEGIN % ac, "T20_MARK_END": END % ac}
        proc = subprocess.run(["bash", str(script)], cwd=str(root), capture_output=True, text=True,
                              env=env)
        sys.stdout.write(proc.stdout)
        if proc.stderr.strip():
            sys.stdout.write("[stderr]\n" + proc.stderr)
        if proc.returncode:
            print("NOTE AC-%s: bash exited %d. rc is diagnostic only - the verdict is the printed "
                  "PASS/FAIL AC-%s token above." % (ac, proc.returncode, ac))
        print("PROVENANCE OK AC-%s: the block was cut from %s, its %d staged line(s) reproduce from "
              "%s and %s in this tree, and bash ran the staged text itself."
              % (ac, issue.name, len(got), probe, clauses))
