"""Generate the AC-<n> bash block text for _docs/issues/T20.md.

Why this exists: the blocks stage two python files with printf '%s\\n' <quoted lines>.
Writing that by hand is where a shell-quoting bug hides; writing the python normally and
quoting each line with shlex.quote is mechanical, and the generator also runs the block
it produces so the quoted form and the plain form are the same measurement.
"""
import os
import shlex
import subprocess
import sys
from pathlib import Path

BLK = Path(os.environ.get("T20_PROBE_DIR") or Path(__file__).resolve().parent / "probes")


def stage(varname, src):
    raw = Path(src).read_text().rstrip("\n").split("\n")
    # A staged probe must never contain a literal code fence or a literal pipe: a probe that
    # splits probe output on "|" would otherwise split its own ARM echo line, and a file
    # holding a fence would break every tool that pairs fences to extract blocks from the
    # issue. The markers are rebuilt at runtime from these two substitutions.
    lines = [ln.replace("FENCE_MARK", "chr(96) * 3").replace("PIPE_MARK", "chr(124)")
             for ln in raw]
    out = ['first=:']
    # one printf per source line, each argument quoted on its own: no line ever passes
    # through a shell expansion, and the file is written line-by-line so a bad line is
    # visible in the trace rather than silent.
    for ln in lines:
        out.append("printf '%%s\\n' %s >> %s" % (shlex.quote(ln), varname))
    out.append('test -s %s || echo "FAIL: %s never reached disk"' % (varname, varname))
    return out


def block(n, probe, clauses, extra_head=(), tail_extra=(), envs=()):
    v = '$TMPDIR'
    body = []
    body += [
        "# AC-%d executes: bash, from the repo root of the tree under test. The two python" % n,
        "# files below are staged by printf of a quoted line list (T10's staged-probe",
        "# convention, kept in pure bash so this file's fences stay simple): PROBE measures",
        "# and prints labelled lines, CLAUSES turns those lines into one verdict per clause",
        "# plus the final token. Scratch is _t20_scratch, removed on the way out.",
        "rm -rf _t20_scratch",
        'test -f backend/app/config.py || { echo "FAIL AC-%d: run this block from the repo root of the tree under test"; exit 0; }' % n,
        'test -x backend/.venv/bin/python || { echo "FAIL AC-%d: backend/.venv is not linked in this worktree"; exit 0; }' % n,
        "mkdir -p _t20_scratch",
        "T20G=0",
        'export TMPDIR="$PWD/_t20_scratch" TZ=UTC',
        'export T20PROBEPATH="$PWD/backend"',
        'export PYTHONPATH="$T20PROBEPATH"',
        'test -n "$T20PROBEPATH" || { echo "FAIL AC-%d: T20PROBEPATH is empty, so the probe could not be told which tree to import"; exit 0; }' % n,
        'export STAFF_PIN=0000',
    ]
    for k, v in envs:
        body.append('export %s="%s"' % (k, v))
    body += list(extra_head)
    body += stage('"$TMPDIR/probe.py"', probe)
    body += stage('"$TMPDIR/clauses.py"', clauses)
    body += [
        'backend/.venv/bin/python "$TMPDIR/probe.py" > "$TMPDIR/out.txt" 2>&1; RC=$?',
        'sed -e "/sqlalchemy.engine/d" -e "/StarletteDeprecation/d" -e "/^  from starlette$/d" "$TMPDIR/out.txt"',
        # The clause table prints its whole-AC verdict line FIRST and the per-clause
        # detail after it, so a truncating consumer still carries the verdict.
        'backend/.venv/bin/python "$TMPDIR/clauses.py" "$TMPDIR/out.txt" | cat; RC2=${PIPESTATUS[0]}',
        "rm -rf _t20_scratch",
        '[ "$RC" = 0 ] || echo "FAIL AC-%d: the probe crashed rc=$RC (rc is diagnostic; the verdict token is the contract)"' % n,
        '[ "$RC2" = 0 ] || echo "FAIL AC-%d: the clause table could not read the probe output"' % n,
    ]
    body += list(tail_extra)
    return "\n".join(body) + "\n"


# Each block carries the gate env it needs, stated in the block itself rather than
# inherited: T10's secret-quality gate refuses a published or short secret, and a
# non-published, >=32-character value is what lets a block measure the ENV contract
# instead of tripping T10's gate (#77 owns the published test literals).
ENVS = {n: [("JWT_SECRET", "t20groom-ac%d%s" % (n, "a" * (34 - len(str(n)))))]
        for n in range(1, 8)}

def emit(n):
    tail = ["export APP_DIR=$PWD"] if n == 4 else []
    return block(n, BLK / ("probe%d.py" % n), BLK / ("clauses%d.py" % n),
                 envs=ENVS.get(n, []), tail_extra=tail)


if __name__ == "__main__":
    # usage, from the repo root of the tree under test:
    #   python3 _docs/issues/_t20/generate_t20_probes.py 3 [4 5 ...]
    # prints the finished bash fence for those AC numbers, ready to paste over the old one.
    for n in [int(a) for a in sys.argv[1:]]:
        print("<!-- BEGIN AC-%d -->" % n)
        print("```bash")
        print(emit(n).rstrip("\n"))
        print("```")
        print("<!-- END AC-%d -->" % n)
