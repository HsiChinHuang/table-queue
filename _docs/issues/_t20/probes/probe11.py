"""T20 AC-11 probe: the reset and echo arms are functions of the named ENV and nothing else.

D-2 refused a second opt-in gate ('ALLOW_DATA_RESET' or similar) with a reason: a second flag
whose default is also a default is the same class of bug one level down. This probe measures
the escape-hatch refusal rather than asserting it, by booting a fresh process per arm and
exporting, alongside the ENV of the arm, one candidate second-gate variable apiece:

  - a name a fix might invent for a reset opt-in (ALLOW_DATA_RESET, TQ_ALLOW_RESET,
    REQUIRE_RESET_TOKEN, RESET_ALLOWED, DEV_MODE, FEATURE_DEV_MODE, RESET_CONFIRM),
  - and the one documented operator request this issue DOES add, SQL_ECHO.

The contract: 'production' and 'test' answer 403 and arm no echo whatever else is exported,
and 'development' answers 204 with nothing exported beyond the documented body confirmation.
An arm where 'production' plus some invented flag answers 204 is exactly the second default
D-2 rejected, arrived at by a different road: the fix would then be one exported variable away
from the audit's wipe in the environment the audit names.

A 'test'-labelled arm additionally proves the guard is not merely broken: it must 403 with or
without an opt-in flag. Everything is written under the scratch directory.
"""
import os
import subprocess
import sys
from pathlib import Path

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe
# may not appear in a staged probe, because the tools that slice blocks out of the issue
# pair fence markers and split arm lines on that character. probe9.py checks that the bytes
# a block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
OUT.mkdir(exist_ok=True)
DB = (OUT / "ac11.db").resolve()

CHILD = r"""
import json
import os
import time

os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["T20DB"]
try:
    from app.main import app
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)
print("BOOT", flush=True)
from fastapi.testclient import TestClient
from jose import jwt

from app.database import engine

c = TestClient(app)
print("HEALTH:", json.dumps(c.get("/health").json()), flush=True)
print("MAIN_ECHO:", engine.echo, flush=True)
print("SEED_ECHO:", __import__("app.seed", fromlist=["get_engine"]).get_engine().echo, flush=True)
tok = jwt.encode({"sub": "staff", "role": "staff", "iat": int(time.time()),
                  "exp": int(time.time()) + 3600},
                 os.environ["JWT_SECRET"], algorithm="HS256")
r = c.post("/api/v1/admin/reset", json={"confirm": "RESET"},
           headers={"Authorization": "Bearer " + tok})
print("RESET:", r.status_code, flush=True)
"""
CHILD_FILE = OUT / "child11.py"
CHILD_FILE.write_text(CHILD)

EXTRA = ["ALLOW_DATA_RESET=true", "TQ_ALLOW_RESET=1", "REQUIRE_RESET_TOKEN=1",
         "RESET_ALLOWED=1", "DEV_MODE=1", "FEATURE_DEV_MODE=1", "RESET_CONFIRM=yes"]


def base_env():
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.path.expanduser("~"),
        "TZ": "UTC",
        "TMPDIR": str(OUT),
        "PYTHONPATH": os.environ["T20PROBEPATH"],
        "JWT_SECRET": os.environ.get("JWT_SECRET", "t20groom-ac11a" + "a" * 33),
        "STAFF_PIN": "0000",
        "T20DB": str(DB),
    }


def run(label, env_value, extra):
    if DB.exists():
        DB.unlink()
    env = base_env()
    if env_value is not None:
        env["ENV"] = env_value
    for pair in extra:
        key, _, value = pair.partition("=")
        env[key] = value
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=env,
                         capture_output=True, text=True, timeout=180)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("BOOT", "HEALTH:", "MAIN_ECHO:", "SEED_ECHO:", "RESET:"))]
    summary = " ; ".join(obs) if obs else "NO VERDICT LINE"
    print(("ARM %s " + V + " %s") % (label, summary), flush=True)


run("absent-bare", None, [])
run("absent-plus-optin-flags", None, EXTRA)
for e in EXTRA:
    run("production-plus-" + e.split("=")[0], "production", [e])
for e in EXTRA:
    run("test-plus-" + e.split("=")[0], "test", [e])
run("development-bare", "development", [])
for e in EXTRA:
    run("development-plus-" + e.split("=")[0], "development", [e])
run("development-plus-sql_echo", "development", ["SQL_ECHO=true"])

if DB.exists():
    DB.unlink()
