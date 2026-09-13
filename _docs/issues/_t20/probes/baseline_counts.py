"""T20 baseline: red-baseline counts for the suites the fix touches (groom baseline item 4).

Groom baseline item 4 in ``_docs/issues/T20.md`` needs a per-file pass/fail count for exactly the
test files the fix must touch, so the implementation round can tell its own damage from inherited
noise. This script is the honest way to get them: it runs each file once in the same gate env the
rest of the baseline uses - a TZ=UTC process whose environment supplies every gate variable *except*
ENV - and reports the collected/passed/failed counts the way pytest -q does.

Two things make the number meaningful rather than decorative:

- the environment is built by hand, so nothing is inherited from an interactive shell. ENV is popped
  explicitly, because the point of the measurement is the state the shipped harness is in with
  respect to this issue;
- the whole-suite run is reported apart from the per-file runs. Under D-1 the suite cannot be run
  file-by-file afterwards: backend/tests/conftest.py is what states ENV=test, so a single-file
  invocation is a different experiment than the suite. Item 4 counts the files, the AC-4 block
  counts the modules, and the whole-suite number is the regression floor.

Run from the repo root of the tree under test:

    backend/.venv/bin/python _docs/issues/_t20/probes/baseline_counts.py

It mutates nothing and writes nothing outside the scratch directory it removes on the way out.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The files whose counts item 4 asks for: the harness plus every module that constructs settings or
# boots the app, i.e. exactly the files a required-ENV change can break.
FILES = [
    "backend/tests/test_config.py",
    "backend/tests/test_health.py",
    "backend/tests/test_admin_reset.py",
    "backend/tests/test_seed.py",
    "backend/tests/test_startup.py",
    "backend/tests/test_startup_bootstrap_settings.py",
]


def gate_env(tmp, secret):
    """The baseline's gate env: gate variables supplied, ENV deliberately absent."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.path.expanduser("~"),
        "TZ": "UTC",
        "TMPDIR": str(tmp),
        "PYTHONPATH": str(Path("backend").resolve()),
        "STAFF_PIN": "0000",
        "JWT_SECRET": secret,
        "DATABASE_URL": "sqlite:///" + str(tmp / "baseline.db"),
        "PYTEST_ADDOPTS": "-p no:cacheprovider",
    }


def counts(out):
    """(passed, failed, errors, collected, xfailed) read off a pytest -q tail."""
    def grab(word):
        m = re.search(r"(\d+) " + word, out)
        return int(m.group(1)) if m else 0

    m = re.search(r"collected (\d+) item", out)
    # xfailed counts are reported under both spellings because pytest writes "2 xfailed" in the
    # summary line and "xfailed" nowhere else; grabbed separately so the printed number is honest.
    return (grab("passed"), grab("failed"), grab("error"),
            int(m.group(1)) if m else 0, grab("xfailed"))


def main(argv):
    if not Path("backend/app").is_dir():
        print("FAIL: run from the repo root; backend/app not found")
        return 1
    targets = argv or FILES + ["backend/tests"]
    venv = os.environ.get("T20_PYTEST_PY", "backend/.venv/bin/python")
    tmp = Path(tempfile.mkdtemp(prefix="t20-baseline-"))
    secret = os.environ.get("JWT_SECRET", "t20groom-baseline-" + "a" * 38)
    env = gate_env(tmp, secret)
    env.pop("ENV", None)
    try:
        for target in targets:
            label = "WHOLE-SUITE" if target.rstrip("/").endswith("tests") else Path(target).name
            res = subprocess.run([venv, "-m", "pytest", target, "-q", "--no-header"],
                                 env=env, capture_output=True, text=True, timeout=3600)
            out = res.stdout + res.stderr
            passed, failed, errors, collected, xfailed = counts(out)
            # "collected" is reported only when pytest prints the line, which -q with a warm cache
            # does not; the summary counts are the numbers that matter, so the field is dropped
            # rather than printed as a misleading zero.
            print("%-38s exit=%d passed=%d failed=%d errors=%d xfailed=%d"
                  % (label, res.returncode, passed, failed, errors, xfailed), flush=True)
            for ln in out.splitlines():
                if " FAILED " in ln or ln.startswith("ERROR "):
                    print("    " + ln.strip()[:140])
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
