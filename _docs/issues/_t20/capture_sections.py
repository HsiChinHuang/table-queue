"""Split the shipped issue into the prose files the builder consumes. Run from the repo root.

    python3 _docs/issues/_t20/capture_sections.py [output-dir]

Why this exists: `_docs/issues/T20.md` is the only complete copy of the acceptance contract, and the
builder that assembles it composes it from per-AC prose files. Once a block has been regenerated and
a digest recorded, the prose in that file is the version the issue actually carries - re-typing it
would be re-authoring the contract by hand, which is how round 1 lost a section. So the round-2
sections are lifted back out of the issue by heading, with their fenced block removed (the builder
re-emits every block from the probe sources; a section file that carried a copy of a block would be
exactly the un-regenerable text AC-9 and AC-13 exist to refuse).

Round-1 sections (AC-1..AC-5) are deliberately NOT captured: the builder carries those from base
`bad4f98`, so a capture that rewrote them would let this round silently re-author another round's
prose.

The output is written under the output dir with the names the builder reads.
"""
import re
import sys
from pathlib import Path

F = chr(96) * 3
# AC numbers, not labels: the HEAD template supplies the "AC-" prefix, and a caller that passed
# "AC-9" here produced the pattern "- [ ] **AC-AC-9**", found nothing, and reported that a section
# this file had just built did not exist. The numbers are also what the builder's EXPECT list and
# the generator's block heads use, so all three agree on one vocabulary.
SECTIONS = {"9": "9", "10": "10", "11": "11", "12": "12", "13": "13"}
HEAD = "- [ ] **AC-%s**"


def section_span(md, ac):
    """(start, end) of one AC's own section, or None if this round did not author it.

    The end is the next heading of any kind, AC heading or `##` section heading: AC-13 sits last
    among this round's sections, so its prose runs to a `##`, and any other AC heading that appears
    later belongs to a section this file has no business rewriting.

    Returning None is the common case, not an error. The round-1 headings are only *mentioned* in
    this round's prose (AC-10 cross-references AC-1, AC-12 cites AC-2's token, AC-9 quotes
    `block_missing_ac-3`), and an unanchored substring search lands on one of those sentences. A
    mention is not a section: a real heading sits at the margin, so the search is line-anchored, and
    a heading at the margin means the issue's own section for that AC, which round 1 authored and
    round 2 must not capture.
    """
    m = re.search(r"(?m)^" + re.escape(HEAD % ac), md)
    if m is None:
        return None
    start = m.start()
    tail_from = start + len(HEAD % ac)
    bounds = [mm.start() + tail_from for mm in
              re.finditer(r"(?m)^(## |\- \[ \] )", md[tail_from:])]
    bounds = [b for b in bounds if b > start]
    if not bounds:
        raise SystemExit("refusing to capture %s: no heading follows its own, so the section would "
                         "swallow the rest of the file" % ac)
    return start, min(bounds)


def strip_fence(text, ac):
    """The section's prose with its block body removed, ready for the builder to re-emit.

    The cut is made by the two MARKER lines rather than by a fence pair, because a fence is a
    markdown detail that this file's own content keeps imitating: AC-9's staged printf lines carry a
    quoted three-backtick sequence (probe9.py assembles that marker from chr(96)), and AC-13's prose
    names a fence in its rationale. A `find("```")` in prose therefore lands inside the wrong thing -
    which is how a section once got written with a neighbour's block and a digest table got recorded
    against a file nobody built. A marker sentence is never a printf line, never a comment and never
    payload text, so it brackets a region exactly.

    What comes back is prose, the block's own fence line (kept as the section's opener), and the
    `Measured today:` paragraph. The builder rebuilds the body between markers from the probe
    sources, so the round trip is lossy by design: the only copy of a block is its sources.
    """
    b = text.find("AC-%s stage steps begin here" % ac)
    e = text.find("AC-%s stage steps end here" % ac)
    if b == -1 or e == -1 or e < b:
        raise SystemExit("refusing to capture %s: its block carries no marker lines, so its prose "
                         "cannot be split from its body without guessing" % ac)
    bol = text.rfind("\n", 0, b) + 1          # start of the marker line, indentation included
    head = text[:bol].rstrip("\n")            # prose plus the block's opening fence line
    # One opener and exactly one closer: the opener is the block's fence, which the builder re-writes
    # for its own indentation, so the captured file keeps only the opener and drops the closer with
    # the body it closes. Two openers would mean a block inside prose; none would mean the block was
    # never fenced, and either way a silent pass here corrupts the document.
    if head.count(F) != 1:
        raise SystemExit("refusing to capture %s: its prose carries %d fence marker(s) outside the "
                         "block, which cannot round-trip" % (ac, head.count(F)))
    # Cut the opener out and re-rstrip: the opener's line carries the block's indentation, so
    # rstrip("\n") alone leaves a line of trailing spaces behind, and the next capture would see
    # those spaces as new content and the builder would write them again. Round-tripping means the
    # capture is the builder's inverse at the character level, not at the line level.
    head = head[:head.rindex(F)].rstrip()
    tail = text[e + len("AC-%s stage steps end here" % ac):]
    tail = tail[tail.index("\n") + 1:] if "\n" in tail else ""
    # Drop the block's closing fence (whatever indentation carries it): the builder writes its own.
    tail = tail.lstrip("\n")
    if tail.lstrip().startswith(F):
        tail = tail.lstrip()[len(F):]
    tail = tail.strip("\n")
    # A leading space is markdown's continuation indent for a paragraph under a list item, which is
    # where a Measured paragraph belongs; the builder re-applies it, the file stores it flush.
    # The paragraph arrives wrapped and indented to sit inside the AC's bullet; the section file
    # stores it flush and unwrapped so the builder is the only thing that decides its layout.
    tail = "\n".join(ln.strip() for ln in tail.split("\n"))
    tail = tail.strip()
    tail = tail[1:] if tail.startswith(" Measured today") else tail
    if tail and not tail.startswith("Measured today"):
        raise SystemExit("refusing to capture %s: the text after its block is not the Measured "
                         "paragraph (%r); refusing to drop it silently" % (ac, tail[:60]))
    return head + "\n" + ("\n" + tail + "\n" if tail else "")


if __name__ == "__main__":
    # The path is anchored to this file's own repository, not to the interpreter's working
    # directory: a tool that silently reads a DIFFERENT checkout's issue and writes section files
    # derived from it is how a builder ends up shipping a contract nobody reviewed.
    ROOT = Path(__file__).resolve().parents[3]
    issue = ROOT / "_docs" / "issues" / "T20.md"
    if not issue.exists():
        raise SystemExit("refusing to capture: %s does not exist" % issue)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp")
    md = issue.read_text(encoding="utf-8")
    captured = 0
    for name, ac in SECTIONS.items():
        span = section_span(md, ac)
        if span is None:
            print("skipped section%s.md: %s has no section of its own in the issue (a mention in "
                  "another section's prose is not a section)" % (name, ac))
            continue
        captured += 1
        text = strip_fence(md[span[0]:span[1]].rstrip("\n") + "\n", ac)
        # The captured section is prose plus the fence that the builder re-opens; the block body
        # between the markers is gone, which is the point. Asserting the marker is gone is the check
        # that the block really was cut rather than carried along as prose.
        assert F not in text and ("AC-%s stage steps" % ac) not in text, \
            "captured %s kept a fence or kept its block body" % ac
        (out / ("section%s.md" % name)).write_text(text, encoding="utf-8")
        print("captured section%s.md: %d line(s), %d char(s)"
              % (name, len(text.split("\n")), len(text)))
    if captured != len(SECTIONS):
        raise SystemExit("refusing to capture: only %d of %d round-2 sections were found, so the "
                         "issue on disk is not the file this tool describes"
                         % (captured, len(SECTIONS)))
