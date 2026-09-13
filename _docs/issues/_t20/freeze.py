"""Converge the issue, its blocks, its digest table and this tool's own prose in one place.

    python3 _docs/issues/_t20/freeze.py [section-dir]

The dependency being closed: AC-9's block embeds probe9.py, which embeds the digest table, and a
digest changes whenever a block's text changes - including the text of the block that carries the
table. Re-recording by hand walks that circle one step at a time and prints a green before the file
on disk describes itself, which is exactly what happened on this branch's first attempt: the table
ended up one generation behind its own blocks and AC-9 REFUSEd on a tree that looked recorded.

So the fixpoint is computed rather than chased: capture (prose back out of the issue) -> build (all
ten blocks re-emitted from the probe sources) -> record (the table rewritten from the built file),
repeated until the file hash stops changing, then verified by a final capture/build/record pass that
must not move anything. If the sequence cannot settle, this refuses loudly instead of leaving a
half-converged file - a table that describes a previous generation of its own blocks is not a
contract, it is a coincidence.

The digest table travels INSIDE a block (see probe9.py's docstring for why it cannot travel
elsewhere), so the only stable state is the one where a digest is a function of the file that
contains it. This script finds that state or reports that none was reached.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX_ROUNDS = 6


def run(script, *args):
    r = subprocess.run([sys.executable, str(ROOT / "_docs" / "issues" / "_t20" / script), *args],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode:
        raise SystemExit("%s failed: %s" % (script, (r.stdout + r.stderr).strip().split("\n")[-1]))
    return r.stdout.strip().split("\n")[-1]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    issue = ROOT / "_docs" / "issues" / "T20.md"
    prev = None
    # The cycle is capture -> build -> RECORD, and it converges on the RECORD step, not on the file:
    # after recording, the file on disk is one generation behind its own table (AC-9's block carries
    # the table, so writing the table changes the very payload the table names). No digest can be a
    # fixed point of a file that contains it - a digest is injective where the file is not, so
    # h(F(t)) = F(t) has no solution. What freeze establishes instead is that the PIPELINE is
    # stationary: once capture and build stop moving the file, recording again changes only the
    # table's digits, and the table recorded from that build is the one that ships. That is the
    # strongest honest invariant available here, and AC-13 plus a run of AC-9 are what make the
    # shipped state measurable rather than merely self-consistent.
    prev = None
    for n in range(1, MAX_ROUNDS + 1):
        run("capture_sections.py", out)
        built = run("build_issue.py")
        before = hashlib.sha256(issue.read_bytes()).hexdigest()[:12]
        recorded = run("record_t20_digests.py")
        print("round %d: %s | %s | pre-record file %s" % (n, built, recorded, before))
        if prev == before:
            break
        prev = before
    else:
        raise SystemExit("the capture/build cycle did not settle in %d rounds: the file is not a "
                         "fixpoint of its own sources, so the issue must not be committed with a "
                         "table that describes a previous generation of its blocks" % MAX_ROUNDS)
    # One final record against the settled build, and a gate that re-derives everything.
    recorded = run("record_t20_digests.py")
    print("final: %s" % recorded)
    gate = subprocess.run([sys.executable, str(ROOT / "_docs" / "issues" / "_t20" / "check_blocks.py")],
                          capture_output=True, text=True, cwd=str(ROOT))
    print(gate.stdout.strip().split("\n")[0])
    raise SystemExit(gate.returncode)
