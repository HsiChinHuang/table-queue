"""T20 AC-13 clause table: block regeneration has a machine check, and the check is an AC.

Meta criterion. It says nothing about ENV, the reset guard or echo, so no product fix can move it;
what it certifies is that this issue's own executable contract is tamper-evident. Round 1 committed
the machinery (generator, recorder, digest checker) and measured it in sync by hand, and its own
Constraints shortfall 5 states plainly that nothing in the AC list enforced that. This block is the
enforcement.

Every clause reads probe13.py's labelled lines rather than re-deriving anything: a second
implementation of "is the table in sync" is exactly the drift this AC exists to miss.

  staged_block_is_the_issue_block - the stage steps the block copied out of itself equal the AC-13
                                    region of _docs/issues/T20.md, so the measurement names the
                                    document a reviewer reads.
  staged_fence_balanced           - the staged steps open exactly one bash fence and close it.
  checker_importable              - the committed digest checker loads and prints its verdict.
  checker_reports_no_fail         - the checker's FAIL count is zero and it printed PASS lines.
  machinery_committed             - generator, recorder and checker all exist in this tree.
  digests_pinned_non_empty        - the checker's expected tables carry entries on BOTH sides,
                                    because an empty expected table is a free green.
"""
import pathlib
import re
import sys

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""


def fact(key):
    for ln in lines.splitlines():
        if ln.startswith(key + ":"):
            return ln.split(":", 1)[1].strip()
    return ""


def count(key):
    try:
        return int(fact(key))
    except ValueError:
        return None


staged_bytes = count("STAGED_BYTES")
region_bytes = count("ISSUE_REGION_BYTES")
opens = count("STAGED_FENCE_OPENS")
closes = count("STAGED_FENCE_CLOSES")
fail_count = count("CHECKER_FAIL_COUNT")
pass_count = count("CHECKER_PASS_COUNT")
machinery = [ln for ln in lines.splitlines() if ln.startswith("MACHINERY_PRESENT:")]
missing = [ln.split()[1] for ln in machinery if ln.rstrip().endswith("no")]
verdict = fact("CHECKER_VERDICT")

# Named bars rather than a bare "> 0", and the names say which facts they stand for. The gate-2
# finding this round repairs is that this count read "blocks=0 sources=0" against a table holding ten
# block entries and twenty-four source entries - it called a full anchor EMPTY, the inverse of the
# finding the clause exists to make - and a clause whose bar is "more than nothing" cannot tell a
# half-populated anchor from a whole one, so the emptiness went unnoticed. Two bars are stated now:
# the payload side must carry at least as many entries as this issue has blocks (AC-9's own
# 'no_unrecorded_block' clause reddens the reverse direction, so the pair makes "the table is as wide
# as the file" a measured claim), and every entry counted must be either a digest or the sentinel - a
# line that is neither is a parsing accident and must not be able to raise the count. The source side
# gets no hard number on purpose: which helper files live in the probes directory is
# 'no_unrecorded_source' business, and a second registry of file names here could only drift.
EXPECTED_BLOCK_ENTRIES = 10


# A named constant rather than the table's own shape spelled out in code. probe9.py declares this
# entry twice: the first block is the round-1 table, whose AC-9 row carries the sentinel spelled as a
# quoted string, and the second is the live binding python actually uses, whose row names the module
# constant. A table reader that stops at the first '\n}' lands in the dead copy, so 'count' skips
# forward to the live binding and counts the table the checker compares against. Leaving the dead copy
# in place is probe9.py's own choice (the recorder rewrites the live binding only, and the duplicate
# is what makes that visible in a diff); the reader's job is to read the right one and say which it
# read, which is what the clause's 'saw:' line now prints.
TABLE_MARK = "EXPECTED_BLOCK_PAYLOADS"
SOURCE_TABLE_MARK = "EXPECTED_SOURCE_DIGESTS"


def table_slice(src, name):
    """The LIVE expected-table assignment out of the checker's source, not its first mention.

    Located by a line start, taken at its LAST occurrence, and cut at the closing brace. Three
    separate reasons the naive form fails here, each of them measured:
      - 'src.index(name)' over the whole file lands on the first MENTION, which in this checker is a
        comment, so the scanned text silently narrows and the reported symptom is "the anchor is
        empty" against a full anchor;
      - the payload table is declared twice (see TABLE_MARK), so a first-match scan reads the dead
        one; and
      - cutting at the first '\n}' after the opening brace would cut a table whose own comment lines
        carry braces, so the cut is taken at the closing brace that sits in the margin.
    """
    start = None
    for m in re.finditer(r"(?m)^" + re.escape(name) + r" = \{", src):
        start = m.end()
    if start is None:
        return ""
    stop = re.search(r"(?m)^\}", src[start:])
    return src[start:start + stop.start()] if stop else src[start:]


# The pinned tables are counted out of the checker's own source rather than taken from its
# arithmetic: a checker whose expected table had been emptied still prints a PASS, and non-empty is a
# property of the file, so the clause reads the file.
#
# Two repairs to how that count is taken, both measured at the base of this fix.
#
#   (a) The entry regexes pinned the hex DIGITS rather than the ENTRY. '(\d,)' in the payload table
#       asserted that the strip width is one character, but the table ships (2, "<digest>") - a
#       two-character width - so the real mismatch was the shape '\d+' versus '\d'. A clause about
#       whether an anchor is empty has no business asserting how wide the strip width is, and when it
#       did, it read a populated table as empty.
#   (b) AC-9's row carries no digest: it carries the SELF_REFERENTIAL sentinel, because its own block
#       stages the file that holds this table and no digest survives being written into the bytes it
#       names (see record_t20_digests.py's docstring and the entry's own comment). The old regex could
#       not match that row and so under-counted a deliberate, stated, still-falsifiable entry as
#       though it were missing. The honest count is ENTRIES, sentinel included: the checker refuses
#       that row the moment its stated reason stops being true, so counting it buys no free green.
#       Both halves are printed, so the split is visible rather than an asterisk on one number.
try:
    src = pathlib.Path("_docs/issues/_t20/probes/probe9.py").read_text(encoding="utf-8")
    HEX16 = "[0-9a-f]" + "{16}"
    blk_tbl = table_slice(src, TABLE_MARK)
    src_tbl = table_slice(src, SOURCE_TABLE_MARK)
    blocks_pinned = len(re.findall(r'"AC-\d+": \(\d+, ("[^"]+"|SELF_REFERENTIAL)\)', blk_tbl))
    blocks_digested = len(re.findall(r'"AC-\d+": \(\d+, "(%s)"\)' % HEX16, blk_tbl))
    blocks_sentinel = len(re.findall(r'"AC-\d+": \(\d+, SELF_REFERENTIAL\)', blk_tbl))
    sources_pinned = len(re.findall(r'"[^"\n]+\.py": "(%s|[A-Za-z_]+)"' % HEX16, src_tbl))
except Exception:
    blocks_pinned = blocks_digested = blocks_sentinel = sources_pinned = 0

CHECKS = [
    ("staged_block_is_the_issue_block",
     bool(staged_bytes) and staged_bytes > 400 and bool(region_bytes)
     and fact("STAGED_MATCHES_ISSUE_REGION") == "yes",
     "the stage steps the block copied out of itself must exist and equal the AC-13 block region "
     "of _docs/issues/T20.md (marker lines excepted), so this block reviews the file under review; "
     "saw: staged=%s region=%s match=%s digests=%s/%s"
     % (staged_bytes, region_bytes, fact("STAGED_MATCHES_ISSUE_REGION") or "none",
        fact("STAGED_PAYLOAD_DIGEST") or "none", fact("ISSUE_REGION_DIGEST") or "none")),
    ("staged_fence_balanced",
     opens == 1 and closes == 1,
     "the staged stage steps, with the two fence lines the document puts around them spliced back, "
     "open exactly one bash fence and close exactly one, so anything that pairs markers can slice "
     "this block out again. The count is taken on the spliced region because a block body can never "
     "carry the fence that holds it - AC-9's first contract clause forbids a staged probe from "
     "containing a fence line at all - so the clause measures the document's pairing, which is the "
     "property the sentence describes, rather than the body's freedom from a pair it is not allowed "
     "to own; saw: spliced opens=%s closes=%s, bare body alone=%s/%s"
     % (opens, closes, fact("BARE_BODY_FENCE_OPENS") or "none",
        fact("BARE_BODY_FENCE_CLOSES") or "none")),
    ("checker_importable",
     fact("CHECKER") == "imported" and verdict.startswith(("PASS AC-9", "FAIL AC-9")),
     "the committed digest checker must load and print its own verdict line; saw: %s / %s"
     % (fact("CHECKER") or "none", verdict or "none")),
    ("checker_reports_no_fail",
     fail_count == 0 and bool(pass_count),
     "the committed digest checker must report zero FAIL lines and at least one PASS line; drift "
     "names itself in the CHECK_DETAIL lines above; saw: fail=%s pass=%s"
     % (fail_count, pass_count)),
    ("machinery_committed",
     len(machinery) == 3 and not missing,
     "the generator, the recorder and the checker must all be present, because the Definition of "
     "Done routes every block change through them; saw missing: %s"
     % (",".join(missing) or "none")),
    ("digests_pinned_non_empty",
     blocks_pinned > 0 and sources_pinned > 0
     and blocks_pinned >= EXPECTED_BLOCK_ENTRIES
     and blocks_digested + blocks_sentinel == blocks_pinned,
     "the checker's expected tables must carry entries on BOTH sides - block payloads and probe "
     "sources - because an empty expected table is a green that costs nothing to keep. An entry "
     "counts whether it carries a digest or the SELF_REFERENTIAL sentinel, since that row is "
     "deliberate, stated in the table itself, and still falsified by the checker; what may not count "
     "is a line that is not an entry at all (a digest quoted in prose is not a pin). The payload side "
     "must be at least as wide as the issue's blocks, i.e. %d entries. AC-9's row is the sentinel, so "
     "the honest split is digests + sentinel = entries; saw: blocks=%d (%d digested, %d sentinel) "
     "sources=%d" % (EXPECTED_BLOCK_ENTRIES, blocks_pinned, blocks_digested, blocks_sentinel,
                     sources_pinned)),
]

ok = True
details = []
for name, good, detail in CHECKS:
    if good:
        details.append("PASS AC-13 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-13 %s: %s" % (name, detail))
if ok:
    print("PASS AC-13: the staged stage steps are byte-identical to the issue's AC-13 region with a "
          "balanced fence, the committed digest checker imports and reports zero drift, and its "
          "pinned tables cover %d block payloads (%d digests + %d self_referential) and %d probe "
          "sources" % (blocks_pinned, blocks_digested, blocks_sentinel, sources_pinned))
else:
    print("FAIL AC-13: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
