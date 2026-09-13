"""T20 AC-9: the executable blocks in the issue are the ones these sources produce."""
import hashlib
import re
from pathlib import Path

ISSUE = Path("_docs/issues/T20.md")
PROBES = Path("_docs/issues/_t20/probes")
GENERATOR = Path("_docs/issues/_t20/generate_t20_probes.py")

EXPECTED_BLOCK_PAYLOADS = {
    "AC-1": "6adf08de77699fb7",
    "AC-2": "c4a7d3028fd4d2a6",
    "AC-3": "ac95adde3e8f3340",
    "AC-4": "427fbabc5338bc34",
    "AC-5": "9ceac9bbbcf92322",
}
EXPECTED_SOURCE_DIGESTS = {
    "clauses1.py": "0ad22343998b9bbc",
    "clauses2.py": "4bc72d70acf8e635",
    "clauses3.py": "cb54f54308c6889d",
    "clauses4.py": "1eb84ddd9bbcd32d",
    "clauses5.py": "6fbc6dae4a24a325",
    "probe1.py": "8e3d0019b373cab7",
    "probe2.py": "72e31d263ba08514",
    "probe3.py": "7d1316cc67ca3557",
    "probe4.py": "372c13ba121169af",
    "probe5.py": "14e618beb9673c7d",
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def normalised(block_text):
    lines = [ln[2:].rstrip() for ln in block_text.split("\n")
             if ln.lstrip().startswith("printf ")]
    return "\n".join(re.sub(r" >> .*$", "", ln) for ln in lines)


md = ISSUE.read_text(encoding="utf-8") if ISSUE.exists() else ""
# The fence markers are split at runtime so this probe's own source does not contain a
# literal fence: a block that pasted this file verbatim would otherwise drop an unterminated
# fence into T20.md and break every tool that extracts blocks by pairing markers.
FENCE = FENCE_MARK
blocks = {}
for body in re.findall(FENCE + "bash\n(.*?)" + FENCE, md, re.S):
    m = re.search(r"# AC-(\d+) executes", body)
    if m:
        blocks.setdefault("AC-" + m.group(1), []).append(body)

ok = True
details = []


def clause(name, good, detail):
    global ok
    if good:
        details.append("PASS AC-9 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-9 %s: %s" % (name, detail))


clause("issue_readable", bool(md) and len(blocks) >= len(EXPECTED_BLOCK_PAYLOADS),
       "the issue must exist and carry every recorded AC block; saw %d of %d (%s)"
       % (len(blocks), len(EXPECTED_BLOCK_PAYLOADS), ",".join(sorted(blocks)) or "none"))

for ac in sorted(EXPECTED_BLOCK_PAYLOADS):
    bodies = blocks.get(ac, [])
    if len(bodies) != 1:
        clause("payload_" + ac.lower(), False,
               "expected exactly one block for %s, found %d, so the pairing is ambiguous"
               % (ac, len(bodies)))
        continue
    got = digest(normalised(bodies[0]))
    clause("payload_" + ac.lower(), got == EXPECTED_BLOCK_PAYLOADS[ac],
           "%s stages payload %s but the recorded digest is %s: the block and the recorded "
           "contract disagree. Regenerate the block with generate_t20_probes.py and commit the "
           "table update in the same change" % (ac, got, EXPECTED_BLOCK_PAYLOADS[ac]))

orphans = sorted(a for a in blocks if a not in EXPECTED_BLOCK_PAYLOADS)
clause("no_unrecorded_block", not orphans,
       "these blocks exist in the issue with no recorded payload, so nothing verifies what they "
       "stage: %s" % (",".join(orphans) or "none"))

if PROBES.is_dir():
    for name in sorted(EXPECTED_SOURCE_DIGESTS):
        p = PROBES / name
        got = digest(p.read_text(encoding="utf-8")) if p.exists() else "missing"
        clause("source_" + name, got == EXPECTED_SOURCE_DIGESTS[name],
               "%s hashes to %s, recorded %s" % (name, got, EXPECTED_SOURCE_DIGESTS[name]))
    extra = sorted(p.name for p in PROBES.iterdir()
                   if p.suffix == ".py" and p.name not in EXPECTED_SOURCE_DIGESTS
                   and p.name not in ("probe9.py", "record_t20_digests.py"))
    clause("no_unrecorded_source", not extra,
           "these probe files exist with no recorded digest: %s" % (",".join(extra) or "none"))
    nums = sorted({re.match(r"(?:probe|clauses)(\d+)\.py", n).group(1)
                   for n in EXPECTED_SOURCE_DIGESTS})
    missing = ["probe%s/clauses%s" % (n, n) for n in nums
               if not all((PROBES / ("%s%s.py" % (k, n))).exists()
                          for k in ("probe", "clauses"))]
    clause("probe_clause_pairing", not missing,
           "these AC numbers lack one half of their pair: %s" % (",".join(missing) or "none"))
else:
    clause("sources_present", False,
           "_docs/issues/_t20/probes/ is absent, so nothing backs the blocks in this tree")

clause("generator_present", GENERATOR.exists(),
       "%s must exist: it is the only sanctioned way to rebuild a block from these sources"
       % GENERATOR)

if ok:
    print("PASS AC-9: every recorded block's staged payload matches its digest, every canonical "
          "probe matches its digest, and the block-to-probe pairing is complete on both sides "
          "(%d blocks, %d sources)" % (len(blocks), len(EXPECTED_SOURCE_DIGESTS)))
else:
    print("FAIL AC-9: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
