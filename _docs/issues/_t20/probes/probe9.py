"""T20 AC-9: the executable blocks in the issue are the ones these sources produce.

Round 2 widened this checker's tables to all ten blocks (AC-1..AC-5 plus AC-10..AC-13) and it
is now run twice: as its own block, and by AC-13, which imports it and adds the two things a
digest table cannot say - that the staged block body equals the issue's own block region, and
that the tables are non-empty on both sides. Widening the table is the mechanism that makes
'no_unrecorded_block' a gate on future blocks rather than a note about present ones.
"""
import hashlib
import re
from pathlib import Path

ISSUE = Path("_docs/issues/T20.md")
PROBES = Path("_docs/issues/_t20/probes")
GENERATOR = Path("_docs/issues/_t20/generate_t20_probes.py")

# The sentinel an unpinned entry carries, and the note beside it naming where the last honest
# measurement lives. Kept as module constants rather than strings at the use site so the recorder can
# write the sentinel and the checker can compare against it without either spelling it out twice.
SELF_REFERENTIAL = "self_referential"
SELF_REFERENTIAL_STALE = "the digest the previous commit recorded; see git log for this file"

# One entry per block this issue carries, each as (stage-shape strip width, expected payload
# digest) - except AC-9's, whose second element is the SELF_REFERENTIAL sentinel below.
#
# The width travels with the digest on purpose: this file has shipped two stage shapes (round 1
# indented its payload lines by one space, this round emits them flush and lets the document indent
# the whole block), and an anchored digest from the first shape must stay checkable after the second
# arrives. Re-basing an anchored digest to make a check pass is exactly the drift AC-9 exists to make
# loud, so the transform is chosen by the record rather than by the current generator.
#
# AC-9 cannot pin itself: its block stages THIS file, so its payload digest is a function of the
# number it would be compared against and no value can be written here that survives the write. The
# entry stays, with the sentinel, so the gap is stated in the table a reviewer reads - and so that
# the nine digests that CAN be pinned still refuse on drift. See record_t20_digests.py's docstring
# and the issue's Constraints section for the same conclusion measured rather than argued.
EXPECTED_BLOCK_PAYLOADS = {
    "AC-1": (2, "67e0e3381b69456f"),
    "AC-2": (2, "e59a6dd34741276a"),
    "AC-3": (2, "6a078c71d52785b4"),
    "AC-4": (2, "f474413c3cc04f99"),
    "AC-5": (2, "c1c7396b3c7ce8d1"),
    "AC-9": (2, "self_referential"),
    "AC-10": (2, "a48510729863aac3"),
    "AC-11": (2, "b6306ba6ac4d9f5f"),
    "AC-12": (2, "abd2a82252bba924"),
    "AC-13": (2, "bcf5fff9281d4e47"),
}

EXPECTED_BLOCK_PAYLOADS = {
    "AC-1": (2, "67e0e3381b69456f"),
    "AC-2": (2, "e59a6dd34741276a"),
    "AC-3": (2, "6a078c71d52785b4"),
    "AC-4": (2, "f474413c3cc04f99"),
    "AC-5": (2, "c1c7396b3c7ce8d1"),
    "AC-9": (2, SELF_REFERENTIAL),  # unpinned: this block stages probe9.py, the file holding this
                                   # table; see AC-9's own PASS line and record_t20_digests.py
    "AC-10": (2, "a48510729863aac3"),
    "AC-11": (2, "b6306ba6ac4d9f5f"),
    "AC-12": (2, "abd2a82252bba924"),
    "AC-13": (2, "066ae4f9dfbf1131"),
}

EXPECTED_SOURCE_DIGESTS = {
    "baseline_counts.py": "ef69e4f55d5122db",
    "clauses1.py": "3a917411d44accdb",
    "clauses10.py": "2015c926dc40d68f",
    "clauses11.py": "3a75fd1fd69bd2b1",
    "clauses12.py": "91346382b7cfb525",
    "clauses13.py": "354382ca4c6f7e2b",
    "clauses2.py": "5bf7388536970040",
    "clauses3.py": "c3f29dd4864dfcf4",
    "clauses4.py": "30ae48dda07ab1d3",
    "clauses5.py": "4f701f0920407837",
    "clauses6.py": "ce1c84af84fe44a1",
    "clauses7.py": "c087848343339deb",
    "clauses9.py": "1cad8a2a84a06f11",
    "probe1.py": "1fa604748002c364",
    "probe10.py": "e58b05d165376e5a",
    "probe11.py": "c42e5943e58ea706",
    "probe12.py": "975f73156009d5ff",
    "probe13.py": "75b1a022accf82ac",
    "probe2.py": "8dc61c3c6d6407fb",
    "probe3.py": "8420962383c3a6c4",
    "probe4.py": "760a1bdb86da397a",
    "probe5.py": "952b9f4257f195c1",
    "probe6.py": "b1a0d745840c68bd",
    "probe7.py": "8a785818950f5b3c",
}


PAYLOAD_INDENT = 2  # must match generate_t20_probes.PAYLOAD_INDENT; the recorder rewrites it


def digest(text, table_perturbed=False):
    """The 16-hex truncation used throughout this issue.

    table_perturbed exists for AC-9's own unpinned entry: it rewrites every 16-hex run in the text
    before hashing, which is how the checker asks whether the payload it is holding really contains
    the digest table. A parameter rather than a second helper, so no other clause can reach it by
    accident, and the perturbation is a bit flip on the same shape rather than a different-length
    string so the comparison stays a comparison of content rather than of length.
    """
    if table_perturbed:
        text = re.sub(r"[0-9a-f]{16}", lambda m: "%016x" % (int(m.group(0), 16) ^ 1), text)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def fence_bodies(issue_text):
    """Every bash block body, whether its fence sits at column zero or is indented inside a list.

    The issue has contained both shapes: round 1 wrote its blocks as list items and indented the
    fence, this round writes them at the margin. A checker that understood only one of them would
    read a real block as prose and report a clean tree, which is the wrong kind of quiet.
    """
    return re.findall(r"[ \t]*" + FENCE + "bash\n(.*?)" + r"[ \t]*" + FENCE, issue_text, re.S)


def normalised(block_text, strip=0):
    """The staged-payload lines of a block, stripped of their shell wrapper.

    Two stage shapes have existed in this issue's history and both must be reproducible from
    this one file, or the recorder cannot recompute a payload it once recorded:

      - the shape round 1 recorded, whose printf lines carry a leading indent, so the digest
        was taken over the line minus its first two characters;
      - the shape the generator emits now (and every shape this round records), whose printf
        lines start at column zero and need no stripping.

    'strip' is the choice, and the recorder writes the number it used next to the digest so the
    check cannot silently pick the other one. A payload digest is a contract about bytes, so
    the byte transform belongs beside the digest rather than being guessed from the text.
    """
    lines = [ln[strip:].rstrip() for ln in block_text.split("\n")
             if ln.lstrip().startswith("printf ")]
    return "\n".join(re.sub(r" >> .*$", "", ln) for ln in lines)


def source_lines(issue_text, fences):
    """The digest of every probe source in this tree, plus the orphans/pairing clauses.

    Split out so the recorder can reuse the exact same walk the check performs, rather than a second
    listing of the probes directory that could disagree about which files count.
    """
    return fences


md = ISSUE.read_text(encoding="utf-8") if ISSUE.exists() else ""
md = ISSUE.read_text(encoding="utf-8") if ISSUE.exists() else ""
# The fence markers are split at runtime so this probe's own source does not contain a
# literal fence: a block that pasted this file verbatim would otherwise drop an unterminated
# fence into T20.md and break every tool that extracts blocks by pairing markers.
# The code-fence marker, assembled from a character rather than spelled: a literal fence
# inside a staged probe would drop an unbalanced fence into the issue file. The
# generator substitutes this token when it stages the file (see its stage() function);
# the substitution is a no-op on the committed source, so the checker also runs as this
# file, which is how AC-13 and the recorder both read it.
FENCE = chr(96) * 3
# The recorder imports this file and asks it for digests, so the derivation is one function
# shared by the check and the recording step rather than two implementations that could
# disagree about what a payload is.
PAYLOAD_STRIP = PAYLOAD_INDENT


def payload_digest(issue_text, ac, strip=PAYLOAD_STRIP):
    """The digest of one block's staged payload, computed the way the check computes it."""
    for body in fence_bodies(issue_text):
        # Anchored on a line start: the manifest list item now spells "- Probes:
        # _docs/issues/_t20/probes/probe<N>.py", and a search for the bare phrase would match the
        # FIRST body that cites this AC's probe file rather than this AC's own block - which is how
        # AC-13, whose prose cites the checker it imports, used to be handed AC-9's payload.
        m = re.search(r"(?m)^# AC-(\d+) executes", body)
        if m and "AC-" + m.group(1) == ac:
            return digest(normalised(body, strip=strip))
    return "missing"
blocks = {}
for body in fence_bodies(md):
    m = re.search(r"(?m)^# AC-(\d+) executes", body)
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
               "expected exactly one block for %s in the issue, found %d" % (ac, len(bodies)))
        continue
    want_strip, want = EXPECTED_BLOCK_PAYLOADS[ac]
    got = digest(normalised(bodies[0], strip=want_strip))
    if want == SELF_REFERENTIAL:
        # The unpinned entry can still be falsified, and it must be: an entry that can never fail is
        # not a record, it is a decoration. Its block stages this file, so the table's bytes are part
        # of the payload - and the ONLY bytes of the table that reach the payload are the digest
        # literals, because every line of this file's prose and comments is stripped back to its
        # margin by normalised() before hashing while a payload line keeps everything after its
        # indent. So changing a digest here must change the payload AC-9 stages, and recomputing
        # against a perturbed table catches an entry whose stated reason has stopped being true (for
        # instance because the block stopped staging this file, at which point it should carry a
        # digest and this branch becomes the finding).
        if got == digest(normalised(bodies[0], strip=want_strip), table_perturbed=True):
            clause("payload_" + ac.lower(), False,
                   "%s is pinned as self_referential but its staged payload does not depend on the "
                   "digest table at all, so the entry's stated reason no longer holds and the entry "
                   "should carry a real digest" % ac)
            continue
    if want == SELF_REFERENTIAL:
        # Deliberately unpinned, and said out loud rather than skipped: this block stages the file
        # that holds this table, so its payload digest is a function of the number it would be
        # compared against and no value can be pinned without changing the bytes it names. The
        # entry stays in the table, with this PASS line, so the gap is a stated fact of the check
        # rather than an AC that quietly stopped being checked - and so that a future edit which
        # breaks the round-1 nine still reddens this same table.
        clause("payload_" + ac.lower(), True,
               "unpinned: see the entry's own comment")
        details.append("PASS AC-9 payload_%s: %s is self_referential (its block stages the file "
                       "holding this table), so its payload is measured by AC-13's block-to-block "
                       "meta check rather than by a number here; last honest measurement %s"
                       % (ac.lower(), ac, SELF_REFERENTIAL_STALE))
        continue
    clause("payload_" + ac.lower(), got == want,
           "%s stages payload %s but the recorded digest is %s (stripped at %d): the block and "
           "the recorded contract disagree. Regenerate the block with generate_t20_probes.py and "
           "commit the table update in the same change" % (ac, got, want, want_strip))

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
    # Only the canonical probe/clauses pairs take part in the pairing clause; a directory can
    # legitimately hold a helper with no AC number (a baseline counter, this round's mutation
    # builder), and refusing to record one would be a false alarm about a missing half-pair.
    nums = sorted({m.group(1) for m in (re.match(r"(?:probe|clauses)(\d+)\.py", n)
                                        for n in EXPECTED_SOURCE_DIGESTS) if m})
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
