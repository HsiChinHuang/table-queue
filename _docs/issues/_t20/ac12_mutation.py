"""Build the AC-12 mutation tree: the fix, plus a guard that refuses every named environment.

AC-12's fourth clause needs a *different wrong answer* to measure against, not a description
of one. Round 1 reasoned about that arm in D-4 and never built it, and Constraints names that
as a shortfall. This script builds it mechanically so the arm is reproducible instead of
remembered:

    python3 _docs/issues/_t20/ac12_mutation.py <destination>

copies the tree under test (cwd must be its repo root) into <destination>, leaves
backend/app/config.py and backend/app/database.py exactly as they are there - the D-1 gate and
the D-3 echo decoupling stay landed - and rewrites only the reset guard's condition in
backend/app/routers/admin.py to the shape a developer reaches for when they want the guard to
"agree" with what /health reports. The result answers 403 in every environment AND wipes the
store, which is precisely the wrong answer AC-12's fingerprint clause is written to refuse.

The destination must be outside the repo (the block puts it under its scratch directory), and
nothing is copied into the tree under review: the mutation lives in a throwaway tree whose path
AC-12's ARM line names.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

GUARD_FIXED = 'if get_settings().env != "development":'
# The mutant is the wrong answer D-4 reasons about: a guard that answers 403 in the
# environments the fix refuses in, for the wrong reason, and therefore wipes in the one place
# the fix must not. Concretely: the env term is dropped from the condition, so the documented
# confirm is honoured in a named-production process. If this delta ever stops producing that
# asymmetry the mutation step says so out loud instead of leaving the clause to guess.
GUARD_MUTANT = "if False:  # AC-12 MUTATION: the guard no longer reads the named environment"
ASYMMETRY_TEST = """
import os

os.environ.setdefault("ENV", "production")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/ac12-import-check.db")
os.environ.setdefault("JWT_SECRET", "ac12-mutation-import-check-" + "x" * 20)
os.environ.setdefault("STAFF_PIN", "0000")
import inspect

from app.routers import admin

src = inspect.getsource(admin)
assert "if False:  # AC-12 MUTATION" in src, "mutation not present"
print("ASYMMETRY_SOURCE_OK")
"""

# app/errors.py reads _docs/specs.md by walking up from __file__ at import time, so the
# document tree travels with the code tree or the copy cannot boot.
COPY = ["backend", "_docs"]


def build(destination):
    root = Path.cwd()
    dest = Path(destination)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in COPY:
        src = root / name
        if src.is_dir():
            shutil.copytree(src, dest / name, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db",
                                                        "outputs"))
    target = dest / "backend/app/routers/admin.py"
    text = target.read_text(encoding="utf-8")
    if GUARD_FIXED not in text:
        print("MUTATION_NOT_BUILDABLE: %r is not in %s, so this tree is not the fixed shape "
              "the mutation is defined against" % (GUARD_FIXED, target))
        return 1
    target.write_text(text.replace(GUARD_FIXED, GUARD_MUTANT, 1), encoding="utf-8")
    # Prove the mutation is the only delta, so the arm cannot be accused of measuring three
    # changes at once. git diff in a non-repo copy prints nothing, hence the file-level check.
    diff = subprocess.run(["diff", "-u", str(root / "backend/app/routers/admin.py"), str(target)],
                          capture_output=True, text=True)
    changed = [ln for ln in diff.stdout.splitlines()
               if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    check = subprocess.run([sys.executable, "-c", ASYMMETRY_TEST],
                           env={**os.environ, "PYTHONPATH": str(dest / "backend")},
                           capture_output=True, text=True, timeout=120)
    print("MUTATION_IMPORT: %s" % ((check.stdout + check.stderr).strip().splitlines()
                                   or [""])[-1][:160])
    print("MUTATION_TREE: %s" % dest)
    print("MUTATION_LINES: %d (%s)" % (len(changed), " ; ".join(c.strip() for c in changed)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(build(sys.argv[1]))
