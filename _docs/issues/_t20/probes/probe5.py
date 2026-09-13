"""T20 AC-5 probe: statement echo is never armed by the environment label.

echo=True is how D-2 got guest names and phone numbers onto stdout: database.py:42 and
seed.py:35 both compute it from settings.env == "development". This probe measures the
engine's own echo flag in a fresh process per arm (import-time state), across the
cartesian product of {no ENV, development, test, production} x {no SQL_ECHO, SQL_ECHO
true/false}, plus one end-to-end arm that serves a real guest join through the shipped
app and counts the sqlalchemy echo lines the request wrote to the process log.

Expected truth table: echo True ONLY when the operator explicitly asked for it; the
environment label never contributes.
"""
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
DB = OUT / "ac5.db"

CHILD = """
import os
try:
    import app.database
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)
print("DB_FILE:", app.database.__file__, flush=True)
print("MAIN_ECHO:", app.database.engine.echo, flush=True)
try:
    from app.seed import get_engine
except Exception as exc:
    print("SEED_ECHO: BOOT_" + type(exc).__name__, flush=True)
    raise SystemExit(0)
print("SEED_ECHO:", get_engine().echo, flush=True)
"""
CHILD_FILE = OUT / "child5.py"
CHILD_FILE.write_text(CHILD)

BASE = dict(
    PYTHONPATH=os.environ["T20PROBEPATH"],
    TMPDIR=str(OUT),
    TZ="UTC",
    STAFF_PIN="0000",
    JWT_SECRET="t20groom-ac5aaaaaaaaaaaaaaaaaaaaaaa",
    DATABASE_URL="sqlite:///" + str(DB),
)


def run(name, extra):
    env = dict(BASE)
    env.update(extra)
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=env,
                         capture_output=True, text=True, timeout=120)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("BOOT:", "MAIN_ECHO:", "SEED_ECHO:"))]
    paths = [ln for ln in res.stdout.splitlines() if ln.startswith("DB_FILE:")]
    if paths:
        obs.append(paths[0])
    print("ARM %s " + V + " %s" % (name, " ; ".join(obs) if obs else "NO VERDICT LINE"), flush=True)


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


for envname in (None, "development", "test", "production"):
    for echo in (None, "true", "false"):
        extra = {}
        if envname:
            extra["ENV"] = envname
        if echo is not None:
            extra["SQL_ECHO"] = echo
        run("env=%s;echo=%s" % (envname, echo), extra)

# end-to-end arm: a guest join through the shipped app, with the ENV that used to arm echo.
JOIN = """
import os
from app.seed import seed_data
seed_data(reset=True)
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.post("/api/v1/branches/1/waitlist", json={
    "name": "T20PIICanaryName", "phone": "0977788899", "party_size": 2,
    "note": "canary"})
print("JOIN:", r.status_code, flush=True)
"""
JOIN_FILE = OUT / "join5.py"
JOIN_FILE.write_text(JOIN)
env = dict(BASE, ENV="development")
res = subprocess.run([sys.executable, str(JOIN_FILE)], env=env,
                     capture_output=True, text=True, timeout=180)
joined = [ln for ln in res.stdout.splitlines() if ln.startswith("JOIN:")]
log = res.stderr + "\n" + res.stdout
echo_lines = [ln for ln in log.splitlines() if "sqlalchemy.engine" in ln]
canary = [ln for ln in log.splitlines() if "T20PIICanaryName" in ln or "0977788899" in ln]
print("ARM join-development " + V + " %s ; ECHO_LINES: %d ; PII_LINES: %d" % (
    " ; ".join(joined) or "NO JOIN LINE", len(echo_lines), len(canary)), flush=True)
if DB.exists():
    DB.unlink()
