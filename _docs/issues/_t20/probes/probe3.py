"""T20 AC-3 probe: what /health reports is what the operator chose, never a default.

/health keeps its env field (A-11's trim-to-status proposal is out of scope). What this
AC pins is the fail-open half: the value an anonymous caller reads must be the value the
process was explicitly booted with, and a process that was NOT given one must not be
answering at all. One subprocess boot per arm; the response body is printed verbatim.
"""
import json
import os
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
DB = OUT / "ac3.db"

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

r = TestClient(app).get("/health")
print("HEALTH:", r.status_code, json.dumps(r.json()), flush=True)
"""
CHILD_FILE = OUT / "child3.py"
CHILD_FILE.write_text(CHILD)


def arm(name, env_value):
    if DB.exists():
        DB.unlink()
    env = dict(
        PYTHONPATH=os.environ["T20PROBEPATH"],
        TMPDIR=str(OUT),
        TZ="UTC",
        STAFF_PIN="0000",
        JWT_SECRET="t20groom-ac3aaaaaaaaaaaaaaaaaaaaaaaa",
        DATABASE_URL="sqlite:///" + str(DB),
        T20DB=str(DB),
    )
    if env_value is not None:
        env["ENV"] = env_value
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=env,
                         capture_output=True, text=True, timeout=120)
    obs = [ln for ln in res.stdout.splitlines() if ln.startswith(("BOOT:", "HEALTH:"))]
    print("ARM %s " + V + " %s" % (name, " ; ".join(obs) if obs else "NO VERDICT LINE"), flush=True)
    if DB.exists():
        DB.unlink()


for value in (None, "development", "test", "production"):
    arm("env-" + (value if value else "absent"), value)
