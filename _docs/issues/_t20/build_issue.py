"""Assemble _docs/issues/T20.md: base prose at bad4f98, plus this round's sections, plus every
block re-emitted from its probe sources.  python3 _docs/issues/_t20/build_issue.py

Why a builder rather than edits to the file: 3300 lines of Markdown cannot be re-authored by hand
without one section going missing, and this branch already lost one that way. The builder takes base
prose verbatim, takes this round's prose from the section files that capture_sections.py lifts out of
the issue, and takes EVERY block body - round 1's five and this round's five - from
generate_t20_probes.py. A block whose text had drifted from its sources is therefore re-printed
rather than trusted, which is the same property AC-9 and AC-13 assert, applied at build time.

The assertions at the bottom are the builder's own contract, not decoration: a file with ten blocks
but nine closers, or a section file carrying a hand-copied fence, has to fail HERE rather than be
discovered by a reviewer whose extraction tool silently returns nothing.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "_docs" / "issues" / "_t20"))
import generate_t20_probes as gen  # noqa: E402

BASE = "bad4f98"
F = chr(96) * 3
IND = "  "
INDENT_OF = 2  # a block body sits two spaces in, as a list item of the AC's bullet


def _wrap(words, pad, width=98):
    """Greedy line wrap with a hanging indent, so the Measured paragraph reflows to the pad."""
    out, line = [], ""
    for w in words.split():
        if len(line) + len(w) + 1 > width - len(pad) and line:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return "\n".join(out)
SECTIONS = ("9", "13", "10", "11", "12")   # document order, see capture_sections.py
EXPECT = ["1", "2", "3", "5", "4", "9", "13", "10", "11", "12"]


def section(name, ac, probe_file=None, clauses_file=None):
    """Prose, then the generated fence, then the `Measured today:` paragraph.

    A section file that still contains a fence is a hard error rather than something to strip: it
    means a block body was copied into prose, which is the drift this file exists to catch.
    """
    txt = Path("/tmp/section%s.md" % name).read_text(encoding="utf-8").strip("\n")
    assert F not in txt, "section%s carries a hand-copied fence; let emit() write it" % name
    k = txt.index("\nMeasured today") if "\nMeasured today" in txt else len(txt)
    # The Measured paragraph is re-indented with one space because it belongs to the AC's list item
    # in markdown; the section file stores it flush so capture and build are inverses.
    # One blank line, then the paragraph re-indented by one space so it stays inside the AC's list
    # item in markdown. The blank line is emitted here and never read back (capture strips leading
    # blanks), which is what makes the two tools inverses instead of each adding a line the other
    # cannot remove.
    # One blank line, then the Measured paragraph, indented by the block's indent + 2 so markdown
    # keeps it inside the AC's list item and - crucially - so no line of it can begin at column 0.
    # A markdown fence only closes on a line whose opener sits in an indented-code region's margin,
    # so indenting this paragraph is also what lets prose quote a fence marker (AC-9 and AC-13 both
    # have to) without any tool mistaking the quote for a real block boundary. The reflow is the
    # builder's job precisely because it is the one place the indent is known; capture_sections.py
    # reads the paragraph back flush, which makes the pair inverses.
    meas = ""
    if k != len(txt):
        pad = " " * (INDENT_OF + 2)
        words = " ".join(txt[k:].split())
        meas = "\n\n" + _wrap(words, pad)
        meas = meas.replace(" Measured", pad + "Measured", 1)
        meas = "\n".join(pad + ln.strip() if ln.strip() else "" for ln in meas.split("\n"))
    body = gen.emit(ac, probe_file=probe_file, clauses_file=clauses_file).rstrip("\n")
    return txt[:k].rstrip("\n") + "\n  " + F + "bash\n" + body + "\n  " + F + meas


base = subprocess.run(["git", "show", "%s:_docs/issues/T20.md" % BASE],
                      capture_output=True, text=True, cwd=str(ROOT)).stdout
if not base:
    raise SystemExit("refusing to build: base %s is not readable in this tree" % BASE)
head = base[:base.index("- [ ] **AC-1**")]
mid = base[base.index("- [ ] **AC-1**"):base.index("## Test requirements")]
tail = base[base.index("## Test requirements"):base.index("## Constraints")]

pat = re.compile("(?m)^" + IND + re.escape(F) + "bash\n(.*?)(?:\n" + IND + re.escape(F) + "$)", re.S)
spans = [(m, re.search(r"# AC-(\d+) executes", m.group(1)).group(1)) for m in pat.finditer(mid)]
assert [a for _, a in spans] == ["1", "2", "3", "5", "4"], [a for _, a in spans]
out_mid, cursor = "", 0
for m, ac in spans:
    out_mid += mid[cursor:m.start()] + F + "bash\n" + gen.emit(int(ac)).rstrip("\n") + "\n" + F
    cursor = m.end()
out_mid += mid[cursor:]

parts = [head.rstrip("\n") + "\n", out_mid.strip("\n") + "\n",
         section("9", 9, probe_file="probe9.py", clauses_file="clauses9.py") + "\n"]
for name in SECTIONS:
    if name == "9":
        continue
    parts.append(section(name, int(name)) + "\n")
parts += [tail.rstrip("\n") + "\n",
          Path("/tmp/part_constraints.md").read_text(encoding="utf-8").strip("\n") + "\n",
          Path("/tmp/part_dod.md").read_text(encoding="utf-8").strip("\n") + "\n"]
text = "\n".join(parts)

heads = re.findall(r"^- \[ \] \*\*AC-(\d+)\*\*", text, re.M)
marks = re.findall(r"^AC-(\d+) stage steps begin here", text, re.M)
opens = len(re.findall(r"^[ \t]*" + F + r"bash\s*$", text, re.M))
closes = len(re.findall(r"^[ \t]*" + F + r"\s*$", text, re.M))
assert heads == EXPECT, heads
assert marks == EXPECT, marks
# Both fence shapes are legal in one file: round 1's blocks were written as indented list items and
# this round's sit at the margin, which is precisely why probe9.py's fence_bodies() accepts either.
# The builder's invariant is that opens and closes PAIR, and that every block has one of each.
assert opens == closes == len(EXPECT), (opens, closes, len(EXPECT))
assert "TBD" not in text, "the built issue carries a TBD placeholder"
(ROOT / "_docs" / "issues" / "T20.md").write_text(text, encoding="utf-8")
print("built %s: %d line(s), %d block(s), %d/%d fences"
      % ("_docs/issues/T20.md", len(text.split("\n")), len(heads), opens, closes))
