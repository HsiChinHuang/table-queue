"""T20 AC-13 meta probe: the block in this issue is the block these sources produce.

AC-13 is the machine check round 1's Constraints shortfall 5 asks for. It boots nothing and
measures no product behaviour: it takes the text of ITS OWN stage steps (which the block copied to
a scratch file before invoking this probe, with the two marker lines as its delimiters), and it
runs the committed digest checker at '_docs/issues/_t20/probes/probe9.py' against the real
'_docs/issues/T20.md'. Three facts, two of which a digest table alone cannot speak:

  - the staged block body is byte-identical to the block region of the issue, so what was measured
    is what a reviewer reads (the two marker lines are stripped from both sides before the
    comparison, because their only job is to make the cut possible);
  - the staged body opens exactly one bash fence and closes it, which is what keeps the issue
    sliceable by anything that pairs markers;
  - the committed checker reports zero drift across every recorded block payload and probe source.

Why the checker is imported rather than executed: its own docstring records that a block may not
paste its source, because a line beginning with three backticks would drop an unbalanced fence into
the issue and break every tool that pairs markers to slice blocks out. The same reason governs this
file: the fence marker is assembled from chr(96) here rather than spelled, and the generator's
'FENCE_MARK' substitution exists so a source can name the marker in prose or code without ever
storing it. Importing the checker runs exactly the analysis its own block runs, and this probe
re-emits its PASS/FAIL lines so this issue's token convention is kept.
"""
import contextlib
import hashlib
import io
import re
import runpy
import sys
from pathlib import Path

# The clause-line delimiter, assembled rather than spelled: a literal pipe may not appear in a
# staged probe, because the tools that slice blocks out of the issue pair fence markers and split
# arm lines on that character, and this file's own output has to survive both.
V = chr(124)
# The code-fence marker, likewise assembled. See the docstring.
FENCE = chr(96) * 3   # assembled, never spelled: see the stage rule in the generator

OUT = Path(__file__).resolve().parent / "run"
OUT.mkdir(exist_ok=True)

ISSUE = Path("_docs/issues/T20.md")
PROBE9 = Path("_docs/issues/_t20/probes/probe9.py")
GENERATOR = Path("_docs/issues/_t20/generate_t20_probes.py")
RECORD = Path("_docs/issues/_t20/record_t20_digests.py")

# The block under review is this file's own block: the stage steps the block copied out of the
# running script. Reading them back from that file is what makes the comparison a measurement of
# the issue rather than a restatement of the generator.
staged_path = Path(__file__).resolve()
staged = staged_path.read_text(encoding="utf-8", errors="replace") if staged_path.exists() else ""
md = ISSUE.read_text(encoding="utf-8") if ISSUE.exists() else ""

# The two lines that bracket a block's stage steps. The staged copy carries the opener (the cut
# starts at it) and not the closer (sed excludes the end line); the issue's own region carries
# neither inside the fence. Stripping whichever markers appear on either side is what makes the
# two comparable without either one editing the bytes being certified.


def strip_markers(text):
    """Drop the closing marker line, the one marker a copied region can contain.

    Both sides of the comparison are cut the same way: the opener is excluded from the region on both
    (a block cannot re-emit a sentence it is forbidden to contain), and the closer is included on both
    (finding a line and copying it is not the same act as writing it, so the copy carries it). The
    search is by stem-plus-distinguishing-word rather than by the whole sentence for the same reason
    the extractor searches that way: this file is staged into the block, so a sentence it held
    literally would be a sentence the block held, and the block would then contain a third marker.
    """
    stem = "AC-13 st" + "age" + " ste" + "ps "
    out = []
    for ln in text.split("\n"):
        probe = ln.strip()
        if probe.startswith(stem) and probe[:28].count("end ") == 1:
            continue
        out.append(ln)
    return "\n".join(out)


def fence_counts(text):
    """How many bash fences a copied region opens and closes, counted as bash and markdown see them.

    The region a block copies out of itself is the BODY between its two marker lines, so the fences
    that hold it belong to the document rather than to the copy - which is the whole reason this is
    not a tautology: the count measures whether the body's own text keeps the document's fence pairing
    intact. One opener and one closer is the balanced shape, and it is the shape every tool that slices
    blocks out of the issue depends on.

    Two details make the count honest, and each of them is a bug this function would otherwise have.
    A stage step may QUOTE a fence inside a printf argument, so a fence is only a fence when the line
    carries nothing else; and a quoted argument spans lines, so a line inside one is not at the top
    level of the script at all. The quote scan walks the body the way bash reads it - character by
    character, single and double quotes both, backslash outside single quotes only.
    """
    opens = closes = 0
    in_single = in_double = False
    fence = chr(96) * 3
    for ln in text.split("\n"):
        top = 0                          # index where this line stops being inside a quoted argument
        for i, ch in enumerate(ln):
            if in_single:
                if ch == "'":
                    in_single = False
                    top = i + 1
            elif in_double:
                if ch == '"':
                    in_double = False
                    top = i + 1
            elif ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            else:
                top = i + 1
        bare = ln[top:].strip()
        if bare == fence + "bash":
            opens += 1
        elif bare == fence:
            closes += 1
    return opens, closes


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


region = ""
if md:
    # The document's own copy of this block's stage steps, cut by the same two marker lines the block
    # cut itself by - and cut INDEPENDENTLY, by locating the stem rather than by importing the
    # generator's constants. If this file used the generator's BEGIN/END strings the two sides could
    # agree while both were wrong, which is the one failure mode a self-review must not keep.
    #
    # The cut mirrors the block's asymmetry (see the generator's note on AC-13's extractor): the
    # opener is excluded from the region on both sides because a block cannot re-emit it, and the
    # closer is INCLUDED on both sides because finding it is not the same as writing it. So the only
    # difference between the two texts is a leading newline, and strip() on each side is the whole
    # normalisation this comparison needs.
    # The stem, spelled so that its own concatenation stays split: a source that could match its own
    # stem would match itself before it matched the document (see the generator's note on AC-13's
    # extractor). The offsets below are len(stem) rather than literals for the same reason one more
    # time up: rewording the stem must move the address, not leave it reading the wrong characters.
    head = "AC-13 st" + "age ste" + "ps "
    off = len(head)
    marks = [m.start() for m in re.finditer("^" + re.escape(head), md, re.M)]
    word = "beg" + "in "
    begs = [k for k in marks if md[k + off:k + off + 7] == word]
    ends = [k for k in marks if md[k + off:k + off + 5] == "end " and k]
    if begs and ends and ends[-1] > begs[0]:
        # The same two cuts the block's own extractor makes, made again here instead of imported: the
        # region is the text between the opener's prose tail and the closer's own line. Deriving both
        # bounds from the markers - colon, newline - is what lets a rewording move the region rather
        # than cut it in half, and keeping this search independent of the generator's constants is
        # what lets the two disagree when one of them is wrong.
        w = md.index(word, begs[0])
        start = md.find("\n", md.index(":", w)) + 1
        stop = md.rfind("\n", 0, ends[-1])
        body = md[start:stop]
        # De-indent by the region's own indent: in the document the stage steps sit inside a markdown
        # list item and the block's copy of itself does not, so the indent is read from the file
        # rather than assumed. Leaving it in would report two identical bodies as different, and a
        # real change could hide in that noise.
        pad = len(body) - len(body.lstrip())
        raw = body.split("\n")
        region = "\n".join(ln[pad:] if ln.startswith(" " * pad) else ln
                            for ln in raw).strip("\n")

opens, closes = fence_counts(staged)
# What the block managed to copy out of itself, printed before anything is compared: when the
# extraction fails, the failure has to be visible as an extraction rather than as a diff.
print("PROBE_SEES_BYTES: %d" % len(staged), flush=True)
print("STAGED_BYTES: %d" % len(staged), flush=True)
print("ISSUE_REGION_BYTES: %d" % len(region), flush=True)
print("STAGED_FENCE_OPENS: %d" % opens, flush=True)
print("STAGED_FENCE_CLOSES: %d" % closes, flush=True)
print("STAGED_MATCHES_ISSUE_REGION: %s"
      % ("yes" if strip_markers(staged).strip() and strip_markers(staged).strip()
         == strip_markers(region).strip() else "no"), flush=True)
print("STAGED_PAYLOAD_DIGEST: %s" % digest(staged), flush=True)
print("ISSUE_REGION_DIGEST: %s" % digest(region), flush=True)

buf = io.StringIO()
note = "imported"
try:
    with contextlib.redirect_stdout(buf):
        runpy.run_path(str(PROBE9), run_name="_ac13_checker")
except Exception as exc:  # a checker that cannot even load is a finding, not a crash
    note = "import_error_" + type(exc).__name__
report = buf.getvalue()
verdict = [l for l in report.splitlines() if l.startswith(("PASS AC-9", "FAIL AC-9"))]
print("CHECKER: %s" % note, flush=True)
print("CHECKER_VERDICT: %s" % (verdict[0][:220] if verdict else "none"), flush=True)
print("CHECKER_FAIL_COUNT: %d" % len([l for l in report.splitlines() if l.startswith("FAIL ")]),
      flush=True)
print("CHECKER_PASS_COUNT: %d" % len([l for l in report.splitlines() if l.startswith("PASS ")]),
      flush=True)
for ln in report.splitlines():
    if ln.startswith(("PASS ", "FAIL ")):
        print("CHECK_DETAIL " + V + " %s" % ln, flush=True)

for path in (GENERATOR, RECORD, PROBE9):
    print("MACHINERY_PRESENT: %s %s" % (path, "yes" if path.exists() else "no"), flush=True)
