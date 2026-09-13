"""Rewrite AC-9's recorded digest tables from the probe sources and the built issue.

Run this deliberately, never as part of a check: it is the only sanctioned way to widen AC-9's trust
anchor, and the diff it produces IS the review surface.

    python3 _docs/issues/_t20/record_t20_digests.py

from the repo root, after anything under ``_docs/issues/_t20/`` changed. It rewrites probe9.py's two
tables and then rebuilds ``_docs/issues/T20.md`` with the committed builder, so the shipped file is
the build the shipped table describes.

What it records, and what it cannot
----------------------------------
Source digests are a plain map: file content -> digest, and the file is not where the digest is
stored. Those reach a fixed point in one pass.

Block payload digests are NOT a plain map. AC-9's block embeds probe9.py, and probe9.py is where the
table lives, so the bytes a block-payload digest describes are the bytes the digest is written into.
The self-referential entry therefore has NO fixed point, and this recorder will not pretend
otherwise. Writing a digest d into the block that the digest is computed over means the file now
contains d where it previously contained something else, so recomputing gives a different digest - a
map whose own output is its input cannot be stable here, and the earlier version of this file that
looped looking for that stability was correct to refuse forever.

So the self-referential entry is RECORDED AS UNPINNED, with its last-measured digest kept for
provenance and marked stale. AC-9's clause for an unpinned entry is `PASS AC-9 payload_ac-9: ...
pinned as self_referential`, which says plainly that the check does not reach it, and an AC-9 run
prints it on every tree. Nine of the ten blocks stay hard-pinned and refuse on drift. AC-13's
block-to-block meta check, which reads the built file rather than a number, is what actually closes
the gap for the tenth - see the Constraints section of the issue for the same conclusion in the
round's own words, and _docs/issues/_t20/check_blocks.py for the cheap gate that runs on every
change.

Refusals that stay: an empty block set, an empty source set, an undigestable block, or a builder that
rejects the candidate table. A recorder that prints green while erasing its own anchor is the failure
mode this file was rewritten to prevent.
"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE / "probes"
PROBE9 = PROBES / "probe9.py"
ISSUE = Path("_docs/issues/T20.md")
BUILDER = HERE / "build_issue.py"
EXCLUDED = {"probe9.py", "record_t20_digests.py"}
# The AC whose block embeds the file holding this table. See the module docstring: this is the one
# entry that cannot be pinned, and the reason the entry format carries a sentinel rather than only a
# digest.
SELF_REFERENTIAL = 9


def load_producer():
    spec = importlib.util.spec_from_file_location("_t20_producer", PROBE9)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_names():
    names = sorted(p.name for p in PROBES.iterdir()
                   if p.suffix == ".py" and p.name not in EXCLUDED)
    if not names:
        raise SystemExit("refusing to record: %s holds no probe sources" % PROBES)
    return names


def block_bodies(md, producer):
    """Every AC block body in the issue, keyed by AC number.

    Uses the checker's own `fence_bodies()` so recorder and check cannot disagree about what a block
    is, and a line-anchored `# AC-<n> executes` search so a block is identified by its own head and
    not by a neighbouring block that cites this AC's probe file. Round 1's recorder used a
    column-zero-only regex, silently recorded zero payloads against an indented file, and exited
    green while emptying the trust anchor; both failures are refused here rather than printed.
    """
    blocks = {}
    for body in producer.fence_bodies(md):
        m = producer.re.search(r"(?m)^# AC-(\d+) executes", body)
        if m:
            blocks.setdefault(int(m.group(1)), body)
    if not blocks:
        raise SystemExit("refusing to record: no AC block found in %s (%d bytes). A recorder that "
                         "rewrote the table now would erase the trust anchor and print a green while "
                         "doing it." % (ISSUE, len(md)))
    return blocks


def width_for(pinned, producer, n):
    """The strip width already pinned for one block, or the generator's current one for a new AC.

    An entry keeps the width it was recorded at, so round 1's anchored digests stay verifiable after
    the generator's stage shape changed underneath them. Re-basing an anchored digest to silence a
    check is the drift this table exists to make loud, so the width is read from the table and never
    recomputed from the tree.
    """
    m = producer.re.search(r'"AC-%d": \((\d+, )?"?([0-9a-f]{16}|self_referential)"?\)' % n, pinned)
    if m and m.group(1):
        return int(m.group(1).strip(", "))
    return producer.PAYLOAD_STRIP


def render(pinned, values, srcs, producer):
    """The checker's source with both tables replaced - returned as text, never written halfway.

    `values` maps AC number -> (width, digest | "self_referential"); the sentinel renders unquoted so
    the checker can tell "deliberately unpinned" apart from "digest not yet computed", which are two
    different findings and must not share a rendering.
    """
    s = producer.re.sub(r"PAYLOAD_INDENT = \d+",
                        "PAYLOAD_INDENT = %d" % producer.PAYLOAD_INDENT, pinned)
    def entry(n, w, v):
        # The sentinel renders as the module constant, not a bare word: probe9.py is executed by
        # python the moment anything reads it, so an unpinned entry has to name a defined name. The
        # comment on the line says why this entry is the odd one, in the file a reviewer is reading.
        if v == SELF_REFERENTIAL:
            return ('    "AC-%d": (%d, SELF_REFERENTIAL),  # unpinned: this block stages probe9.py,'
                    " the file holding this table; see AC-9's own PASS line\n" % (n, w))
        return '    "AC-%d": (%d, "%s"),\n' % (n, w, v)
    for marker, payload in (
            ("EXPECTED_BLOCK_PAYLOADS = {",
             "".join(entry(n, w, v) for n, (w, v) in sorted(values.items()))),
            ("EXPECTED_SOURCE_DIGESTS = {",
             "".join('    "%s": "%s",\n' % (n, d) for n, d in sorted(srcs.items())))):
        a = s.index(marker)
        b = s.index("\n}\n", a) + 3
        s = s[:a] + marker + "\n" + payload + "}\n" + s[b:]
    return s


if __name__ == "__main__":
    producer = load_producer()
    md = ISSUE.read_text(encoding="utf-8") if ISSUE.exists() else ""
    if not md:
        raise SystemExit("refusing to record: %s is missing" % ISSUE)
    blocks = block_bodies(md, producer)
    pinned = PROBE9.read_text(encoding="utf-8")

    values = {}
    for n in sorted(blocks):
        w = width_for(pinned, producer, n)
        if n == SELF_REFERENTIAL:
            # Unpinned on purpose; see the module docstring. The stale digest beside it is provenance
            # for the last honest measurement, not a value the check may compare against.
            m = re.search(r'"AC-%d": \(\d, "([0-9a-f]{16})"\)' % n, pinned)
            values[n] = (w, "self_referential")
            last = m.group(1) if m else "never"
        else:
            v = producer.payload_digest(md, "AC-%d" % n, w)
            if v == "missing":
                raise SystemExit("refusing to record: no payload digest derivable for AC-%d" % n)
            values[n] = (w, v)

    srcs = {n: producer.digest((PROBES / n).read_text(encoding="utf-8")) for n in source_names()}
    candidate = render(pinned, values, srcs, producer)
    PROBE9.write_text(candidate, encoding="utf-8")
    rebuilt = subprocess.run([sys.executable, str(BUILDER)], capture_output=True, text=True,
                             cwd=str(Path.cwd()))
    if rebuilt.returncode:
        raise SystemExit("refusing to record: the builder rejected the recorded table - %s"
                         % (rebuilt.stdout + rebuilt.stderr).strip().split("\n")[-1])
    print("recorded %d block payloads (%d pinned, %d self_referential) and %d source digests"
          % (len(values), len(values) - 1, 1, len(srcs)))
