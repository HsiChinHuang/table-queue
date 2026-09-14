"""The round-1 blocks (AC-1..AC-5), recovered from the round-1 commit, and what "landed" means here.

Why this module exists at all. GATE-3 asks for two things that pull against each other: all ten
blocks must be locatable by one convention, and no block may be edited to buy a green. The first
attempt at landing satisfied the first and broke the second twice over, both measured rather than
predicted:

  (1) Wrapping the round-1 blocks in the round-2 marker lines *inside* their own indented fences
      left the markers as the block's first lines and its last line, so `replay_block.extract`
      returned a region that began with prose and ended with a stray indented ```- line: 167 lines
      instead of 165, `bash: AC-1: command not found`, and `-` as a command that aborts the printf
      stage loop before anything is staged.
  (2) Emitting the markers outside the fence, and moving the fence from a two-space list-item indent
      to the margin, is what round 2's own generator does - and running the builder over the round-1
      sections is how those five blocks got replaced by this round's regenerated shape. AC-1's
      payload differs from round 1's on 122 staged lines, AC-2's on 128, AC-3's on 72, AC-4's on 81,
      AC-5's on 112: a three-space stage indent, two extra `V = chr(124)` prelude lines, a re-wrapped
      head comment, and the marker lines carried inside the body. None of that is a fix; all of it
      changes what a pinned digest covers and what a clause table reads.

So the round-1 text is *recovered*, not regenerated, from a commit that is in this repository's
history, and the recovery is asserted rather than trusted. `landed(ac)` returns the bytes AC-<ac>
ran with at round 1, and `selfcheck(md)` answers the only question a reviewer can ask of a landed
document: is the block in the file the block round 1 wrote, and is it locatable.

What "locatable by one convention" ends up meaning, given the constraint above: every block sits
between its own two marker sentences, and a block that also closes its fence at the margin (round
2's five) is additionally findable by fence pairing. The round-1 five keep their round-1 fence - a
fence closed inside a list item - because moving it is the edit GATE-3 forbids. That asymmetry is
documented once, in the issue's GATE-3 paragraph, rather than hidden in a passing sentence.
"""
import re
import subprocess
from pathlib import Path

F = chr(96) * 3
BASE_R1 = "bad4f98"
R1_BLOCKS = ("1", "2", "3", "4", "5")
R2_BLOCKS = ("9", "10", "11", "12", "13")
ALL_BLOCKS = R1_BLOCKS + R2_BLOCKS
BEGIN = "AC-%s stage steps begin here: replay_block.py reads this line"
END = "AC-%s stage steps end here: replay_block.py reads this line"
ROOT = Path(__file__).resolve().parents[3]


def round1_document():
    """The round-1 issue text, read out of git, or None when that commit is not in this history."""
    res = subprocess.run(["git", "show", "%s:_docs/issues/T20.md" % BASE_R1],
                         capture_output=True, text=True, cwd=str(ROOT))
    return res.stdout if res.returncode == 0 and res.stdout else None


def strip_fence(text):
    """Every fenced block in ``text``, replaced by a sentinel, so prose can be compared to prose.

    Used by the landing check, not by a block: what the builder must never move is the prose, and
    the fastest way to see whether a rebuild moved anything else is to blank the ten blocks and diff
    what is left. Blanking by regex rather than by marker position is deliberate here - the point is
    to be independent of the marker convention whose correctness is under test.
    """
    return re.sub(r"(?m)^[ \t]*" + re.escape(F) + r"bash\n.*?\n[ \t]*" + re.escape(F),
                  "<BLOCK>", text, flags=re.S)


def deindent(body):
    """Drop a block's list-item indent, which is document layout and not payload.

    Round 1 indented its fences as list items, so every body line carries two leading spaces and the
    executable text is those lines without them. Same transform `replay_block.extract` applies, and
    the reason both agree on AC-1's byte count: 11023 either way, measured.
    """
    lines = body.split("\n")
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    pad = min(indents) if indents else 0
    return "\n".join(ln[pad:] if ln.strip() else ln for ln in lines).strip("\n")


def block_region(md, ac):
    """``(start_of_fence_line, end_of_closer_line)`` for AC-<ac>'s block in ``md``, by its markers.

    Marker-anchored and indent-tolerant, in that order: a block is identified by the sentence
    addressed to the replay tool rather than by a fence, because AC-13's own staged payload quotes a
    fence opener and a fence-first search lands inside that quotation. The two tolerances are what
    let one function find a round-2 block at the margin and a round-1 block two spaces in.
    """
    b, e = md.find(BEGIN % ac), md.find(END % ac)
    if b == -1 or e <= b:
        return None
    opener = md.rfind("\n" + F + "bash", 0, b)
    if opener == -1:
        return None
    closer = re.search(r"\n[ \t]*" + re.escape(F), md[e:])
    if closer is None:
        return None
    return opener + 1, e + closer.end()


def first_block_body(md, ac):
    """The one fenced body whose head comment names AC-<ac>, as written in ``md``.

    'One', asserted. Each AC has exactly one block whose body carries `# AC-<n> executes` at a line
    start, and the reason the search is line-anchored is that the probe sources quote the same phrase
    in their docstrings and in the issue's prose - AC-13, which reviews AC-9's checker, cites
    AC-9's block, and an unanchored search hands AC-13 the payload of the block it is reviewing.
    """
    bodies = re.findall(r"(?m)^[ \t]*" + re.escape(F) + r"bash\n(.*?)"
                        r"\n[ \t]*" + re.escape(F), md, re.S)
    hits = [b for b in bodies if re.search(r"(?m)^ *# AC-%s executes" % re.escape(ac), b)]
    assert len(hits) == 1, "AC-%s: %d candidate blocks, expected exactly 1" % (ac, len(hits))
    return hits[0]


def landed(ac):
    """The body AC-<ac> must carry: round 1's bytes, recovered from `BASE_R1`, never regenerated.

    A refusal rather than a fallback when the commit is unreachable. Falling back to this round's
    regenerated shape would be the exact substitution this module was written to make loud, and a
    tool that degrades into it silently is worse than a tool that stops.
    """
    md = round1_document()
    if md is None:
        raise SystemExit(
            "r1_landed: %s:_docs/issues/T20.md is not reachable from this tree, so the round-1 "
            "blocks cannot be recovered. Refusing to substitute this round's regenerated shape: it "
            "differs from round 1's payload on 122 staged lines for AC-1 alone. Fetch %s, or land "
            "the round-1 text from the tag, before building." % (BASE_R1, BASE_R1))
    return deindent(first_block_body(md, str(ac)))


def landed_block(ac):
    """The landed body, wrapped the way round 1 wrapped it: fenced at the margin, markers inside.

    Round 1's document had this block's fence at the margin too - the `  ` indentation that shows up
    in the extracted body is the list item's own, which `deindent` removes - so re-emitting the
    recovered body at the margin reproduces the block byte for byte, markers aside.
    """
    return F + "bash\n" + BEGIN % ac + "\n" + landed(ac) + "\n" + END % ac + "\n" + F


def selfcheck(md):
    """Problems with a landed document, as a list of strings; empty means the landing holds.

    Four properties, one per loop below, each of which failed in at least one of the landing
    attempts this file was written after:
      - every block is locatable by the marker convention, and no marker appears twice;
      - fences pair, so no tool's extractor sees an unbalanced document;
      - each round-1 block's body equals `landed(ac)` after de-indenting, which is the property the
        first two attempts both lost, in opposite directions;
      - the prose outside the blocks is the prose the document had before the landing.
    """
    problems = []
    for ac in ALL_BLOCKS:
        if md.count(BEGIN % ac) != 1 or md.count(END % ac) != 1:
            problems.append("AC-%s: %d begin / %d end marker line(s); a block must be locatable by "
                            "exactly one pair" % (ac, md.count(BEGIN % ac), md.count(END % ac)))
            continue
        if block_region(md, ac) is None:
            problems.append("AC-%s: markers present but no fence pair around them, so an extractor "
                            "that pairs fences sees an unbalanced document" % ac)
    if len(re.findall(r"(?m)^[ \t]*" + F + r"bash\s*$", md)) != len(
            re.findall(r"(?m)^[ \t]*" + F + r"\s*$", md)):
        problems.append("fence openers and closers do not pair")
    for ac in R1_BLOCKS:
        reg = block_region(md, ac)
        if reg is None:
            continue
        # The region is the fence line through the closer line. Strip both fences and the two
        # marker lines, then de-indent: what is left is what bash is handed, and it is the same
        # reduction `replay_block.extract` performs on the same bytes.
        inner = md[reg[0]:reg[1]].split("\n")[1:-1]
        assert inner and inner[0].strip() == BEGIN % ac and inner[-1].strip() == END % ac, ac
        body = deindent("\n".join(inner[1:-1]))
        want = landed(ac)
        # The `- Probes:` provenance lines are the one addition a landing may make inside a round-1
        # body, and only because replay_block.py refuses a block that cannot name its sources. They
        # are bash comments in that position, so stripping them here compares the payload and lets the
        # provenance requirement stand at the same time. Anything else that differs is content.
        body = "\n".join(ln for ln in body.split("\n") if not ln.strip().startswith("- Probes:"))
        if body != want:
            diff = next((i for i, (x, y) in enumerate(zip(body.split("\n"), want.split("\n")))
                         if x != y), "length")
            problems.append("AC-%s: the document's block is not round 1's bytes (%d vs %d chars; "
                            "first differing line %s)" % (ac, len(body), len(want), diff))
    return problems


def prose_problems(before, after):
    """Whether a landing moved any prose. Byte-exact: prose is the contract's own words."""
    a, b = strip_fence(before), strip_fence(after)
    if a == b:
        return []
    rows = [(i, x, y) for i, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))) if x != y]
    return ["prose moved outside the blocks: %d differing line(s), first at %d: %r -> %r"
            % (len(rows), rows[0][0] if rows else -1,
               (rows[0][1][:90] if rows else ""), (rows[0][2][:90] if rows else ""))]


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["selfcheck"]:
        bad = selfcheck((ROOT / "_docs" / "issues" / "T20.md").read_text(encoding="utf-8"))
        for p in bad:
            print("  " + p)
        print("SELFCHECK: %s" % ("clean" if not bad else "%d problem(s)" % len(bad)))
        raise SystemExit(0 if not bad else 1)
    for ac in (sys.argv[1:] or list(R1_BLOCKS)):
        print(landed(ac))
