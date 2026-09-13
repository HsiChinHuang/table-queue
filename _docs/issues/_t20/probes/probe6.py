"""T20 AC-6 probe: the contract this issue changes must be written down where operators read it.

Three facts, all measured from the tree under test without installing anything:

``README_ENV_ROW``    - the README's ``ENV`` table row, read as shipped.
``README_ENV_VALUES`` - every allowed environment value the document names anywhere.
``ARM suite``         - the whole backend suite run in an environment the probe built
                        itself: the gate variables only, with ``ENV`` deliberately absent,
                        so the suite's own ``os.environ.setdefault`` statements are what
                        carry it. ``PYTEST_ADDOPTS=-p no:cacheprovider`` keeps
                        ``.pytest_cache`` out of the tree, so AC-8's cleanliness clause is
                        not contaminated by running this block before AC-8.

Nothing is written into the tree: scratch files live under the scratch directory.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
OUT.mkdir(exist_ok=True)
DB = (OUT / "ac6.db").resolve()

README = Path("README.md").resolve()
text = README.read_text(encoding="utf-8", errors="replace") if README.exists() else ""

rows = [ln for ln in text.splitlines() if re.match(r"^\s*\|\s*ENV\s*\|", ln)]
print("README_ENV_ROW: %s" % (rows[0].strip() if rows else ""), flush=True)
print("README_ENV_VALUES: %s" % ",".join(sorted(set(re.findall(
    r"\b(development|test|production)\b", text)))), flush=True)

env = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": os.path.expanduser("~"),
    "TZ": "UTC",
    "TMPDIR": str(OUT),
    "PYTHONUNBUFFERED": "1",
    "PYTEST_ADDOPTS": "-p no:cacheprovider",
    "PYTHONPATH": str(Path("backend").resolve()),
    "JWT_SECRET": os.environ.get("JWT_SECRET", "t20groom-ac6a" + "a" * 34),
    "STAFF_PIN": "0000",
    "DATABASE_URL": "sqlite:///" + str(DB),
}
res = subprocess.run(["bash", "-c", "backend/.venv/bin/python -m pytest -q 2>&1 | tail -2"],
                     env=env, capture_output=True, text=True, timeout=2400, cwd=str(Path.cwd()))
tail = " | ".join((res.stdout + res.stderr).strip().splitlines()[-2:])
print("ARM suite | TAIL: %s" % tail, flush=True)

if DB.exists():
    DB.unlink()
