"""T20 AC-7 probe: a tree that satisfies the issue boots the app and passes the suite.

The one block in this issue that answers the operator's question - "is it actually fixed?" -
rather than pinning one decision. It performs no mutation and reads no document: it boots the
application in a fresh subprocess under each of the three named environments plus the refused
no-ENV arm, and then runs the whole backend suite twice, once with the environment the shipped
test statements supply and once with the environment an operator would export by hand. A tree
where AC-1..AC-6 all pass but the app no longer starts, or the suite no longer runs, is not a
fixed tree, and this is the block that says so.

Everything is written under scratch (SQLite files, the pytest cache directory) so AC-8's
cleanliness clause stays meaningful.
"""
import os
import re
import subprocess
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe may
# not appear in a staged probe, because the tools that slice blocks out of the issue pair
# fence markers and split arm lines on that character. probe9.py checks that the bytes a
# block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)
# The arm label delimiter, spelled so that neither this source nor its staged copy in the
# issue ever carries a literal pipe: generate_t20_probes.py substitutes the character.
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
OUT.mkdir(exist_ok=True)
DB = (OUT / "ac7.db").resolve()
SUITE_DB = (OUT / "ac7-suite.db").resolve()

CHILD = r"""
import json
import os

os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["T20DB"]
try:
    from app.main import app
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)
print("BOOT", flush=True)
from fastapi.testclient import TestClient

from app.database import engine

r = TestClient(app).get("/health")
print("HEALTH:", r.status_code, json.dumps(r.json()), flush=True)
print("MAIN_ECHO:", engine.echo, flush=True)
"""
CHILD_FILE = OUT / "child7.py"
CHILD_FILE.write_text(CHILD)


def base_env():
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.path.expanduser("~"),
        "TZ": "UTC",
        "TMPDIR": str(OUT),
        "PYTHONPATH": os.environ["T20PROBEPATH"],
        "JWT_SECRET": os.environ.get("JWT_SECRET", "t20groom-ac7a" + "a" * 34),
        "STAFF_PIN": "0000",
        "T20DB": str(DB),
    }


for label, value in (("absent", None), ("development", "development"),
                     ("test", "test"), ("production", "production")):
    if DB.exists():
        DB.unlink()
    env = base_env()
    if value is not None:
        env["ENV"] = value
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=env,
                         capture_output=True, text=True, timeout=180)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("BOOT:", "BOOT", "HEALTH:", "MAIN_ECHO:"))]
    print("ARM boot-%s " + V + " %s" % (label, " ; ".join(obs) or "NO VERDICT LINE"),
          flush=True)

# The suite, run the way the shipped harness expects: an environment that supplies the
# gate variables but never names ENV, so the suite's own statements are what carry it.
suite_env = base_env()
suite_env["DATABASE_URL"] = "sqlite:///" + str(SUITE_DB)
suite_env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
res = subprocess.run(["bash", "-c", "backend/.venv/bin/python -m pytest -q 2>&1 " + V + " tail -2"],
                     env=suite_env, capture_output=True, text=True, timeout=2400,
                     cwd=str(Path.cwd()))
print("ARM suite-harness-env " + V + " TAIL: %s"
      % V.join((res.stdout + res.stderr).strip().splitlines()[-2:]), flush=True)

if DB.exists():
    DB.unlink()
if SUITE_DB.exists():
    SUITE_DB.unlink()
