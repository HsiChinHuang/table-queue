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

# The pinned tables are counted out of the checker's own source rather than taken from its
# arithmetic: a checker whose expected table had been emptied still prints a PASS, and non-empty is
# a property of the file, so the clause reads the file. An entry is a value, so a digest quoted in
# a comment does not count toward the total.
try:
    src = pathlib.Path("_docs/issues/_t20/probes/probe9.py").read_text(encoding="utf-8")
    cut = src.index("EXPECTED_SOURCE_DIGESTS")
    blocks_pinned = len(re.findall(r'"AC-\d+": \(\d, "[0-9a-f]"' + "{16}" + r'"\)', src[:cut]))
    sources_pinned = len(re.findall(r'"[^"]+\.py": "[0-9a-f]"' + "{16}" + r'"\)', src[cut:]))
except Exception:
    blocks_pinned, sources_pinned = 0, 0

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
     "the staged stage steps open exactly one bash fence and close it, so anything that pairs "
     "markers can slice this block out again; saw: opens=%s closes=%s" % (opens, closes)),
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
     blocks_pinned > 0 and sources_pinned > 0,
     "the checker's expected tables must pin entries for both block payloads and probe sources; "
     "an empty table is a green that costs nothing to keep; saw: blocks=%d sources=%d"
     % (blocks_pinned, sources_pinned)),
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
          "pinned tables cover %d block payloads and %d probe sources"
          % (blocks_pinned, sources_pinned))
else:
    print("FAIL AC-13: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
