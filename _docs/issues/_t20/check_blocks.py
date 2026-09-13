"""Gate every AC block of this issue before it is committed. Run from the repo root.

    python3 _docs/issues/_t20/check_blocks.py

Four checks per block, all of which this file's history has already paid for:

  emit        the generator can produce the block text at all (a block no source regenerates is a
              block nobody can re-derive, and this round lost a section to a hand-assembled file);
  fence-safe  no staged line carries a backtick, single or triple, because a block body sits inside
              a bash fence and one backtick makes the whole block unparseable;
  bash -n     the emitted body parses as shell, so a quoting bug fails here rather than at run time
              (bash -n catches what a successful `bash file` run hides: an error inside a single-
              quoted printf argument never reaches the parser, so the staged python can be corrupt
              while the block reports a clean run);
  manifest    the head's `- Probes:` items name exactly the two sources the block stages, because
              that is the only place a block states its own provenance and replay_block.py refuses
              on it.

The end-to-end counterpart is replay_block.py, which additionally re-derives the staged bytes from
the sources and runs the block. This gate is the cheap pre-run: it never executes a block, so it is
safe on a dirty tree.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BLOCKS = (1, 2, 3, 4, 5, 9, 10, 11, 12, 13)


def emit(n):
    return subprocess.run([sys.executable, str(ROOT / "_docs/issues/_t20/generate_t20_probes.py"),
                           str(n)], capture_output=True, text=True, cwd=str(ROOT))


def main():
    scratch = ROOT / "_t20_gate.sh"
    fails = []
    for n in BLOCKS:
        r = emit(n)
        if r.returncode:
            fails.append("AC-%d emit: %s" % (n, r.stderr.strip().split("\n")[-1][:150]))
            continue
        lines = r.stdout.rstrip("\n").split("\n")
        if lines[1] != "```bash" or lines[-2] != "```":
            fails.append("AC-%d shape: the emitted text is not one fenced block (%r / %r)"
                         % (n, lines[1], lines[-2]))
            continue
        body = lines[2:-2]
        bad = [ln for ln in body if chr(96) in ln]
        if bad:
            fails.append("AC-%d fence-safe: %d line(s) carry a backtick, first: %s"
                         % (n, len(bad), bad[0][:100]))
        scratch.write_text("\n".join(body) + "\n", encoding="utf-8")
        b = subprocess.run(["bash", "-n", str(scratch)], capture_output=True, text=True)
        if b.returncode:
            fails.append("AC-%d bash -n: %s" % (n, (b.stderr.strip().split("\n") or [""])[0][:130]))
        items = [ln for ln in body if ln.strip().startswith("- Probes:")]
        names = sorted(set(re.findall(r"probes/([A-Za-z0-9_]+\.py)", " ".join(items))))
        want = sorted(["probe%d.py" % n, "clauses%d.py" % n])
        if names != want:
            fails.append("AC-%d manifest: head names %s, expected %s" % (n, names or "none", want))
    scratch.unlink(missing_ok=True)
    if fails:
        print("FAIL AC-blocks: %d problem(s) across the ten blocks" % len(fails))
        for ln in fails:
            print("  GATE " + ln)
    else:
        print("PASS AC-blocks: all %d blocks emit, stay fence-safe, parse under bash -n, and name "
              "exactly their two probe sources" % len(BLOCKS))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
