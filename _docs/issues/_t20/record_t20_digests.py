"""Rewrite AC-9's recorded digest tables from the sources and blocks as they now stand.

Run this deliberately, never as part of a check: it is the only sanctioned way to widen
AC-9's trust anchor, and the diff it produces is the review surface. After changing
anything under ``_docs/issues/_t20/probes/`` or regenerating a block, run

    python3 _docs/issues/_t20/record_t20_digests.py

from the repo root, then regenerate the affected blocks with ``generate_t20_probes.py``,
run this script again, run AC-9, and commit the table change together with the source
change it describes.

It reuses AC-9's own extraction functions rather than reimplementing them, so the
recorded numbers are computed the same way the check computes them - a disagreement here
would mean the recorder and the checker define the payload differently, which is exactly
the kind of drift this clause is meant to catch.
"""
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE / "probes"
PROBE9 = PROBES / "probe9.py"
ISSUE = Path("_docs/issues/T20.md")
EXCLUDED = {"probe9.py", "record_t20_digests.py"}


def load_producer():
    spec = importlib.util.spec_from_file_location("_t20_producer", PROBE9)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    producer = load_producer()
    md = ISSUE.read_text(encoding="utf-8")

    blocks = {}
    for body in re.findall(producer.FENCE_MARK + "bash\n(.*?)" + producer.FENCE_MARK,
                           md, producer.re.S):
        m = producer.re.search(r"# AC-(\d+) executes", body)
        if m:
            blocks.setdefault(int(m.group(1)), body)
    block_lines = "".join('    "AC-%d": "%s",\n' % (n, producer.payload_digest(md, "AC-%d" % n))
                          for n in sorted(blocks))

    sources = sorted(p.name for p in PROBES.iterdir()
                     if p.suffix == ".py" and p.name not in EXCLUDED)
    src_lines = "".join('    "%s": "%s",\n'
                        % (n, producer.digest((PROBES / n).read_text(encoding="utf-8")))
                        for n in sources)

    s = PROBE9.read_text(encoding="utf-8")
    for marker, payload in (("EXPECTED_BLOCK_PAYLOADS = {", block_lines),
                            ("EXPECTED_SOURCE_DIGESTS = {", src_lines)):
        i = s.index(marker)
        j = s.index("\n}\n", i) + 3
        s = s[:i] + marker + "\n" + payload + "}\n" + s[j:]
    PROBE9.write_text(s, encoding="utf-8")
    print("recorded %d block payloads and %d source digests" % (len(blocks), len(sources)))
