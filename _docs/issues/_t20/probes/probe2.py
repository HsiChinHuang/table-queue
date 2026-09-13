"""T20 AC-2 probe: the dev-only wipe is armed only by an explicit ENV=development.

One subprocess boot per ENV arm - the environment is resolved at import time and
app.config.get_settings is lru_cached, so an in-process monkeypatch of the settings seam
would measure the test seam rather than the shipped default. Each arm: boot, mint one
staff token with the process's own JWT_SECRET through the shipped jose path (that is what
a successful login hands out, and AC-2 is about the reset guard, not about T10's secret
gate), then POST /api/v1/admin/reset exactly once and count the store's waitlist rows
before and after. A wipe is then observable rather than asserted, and the row counts also
prove the request reached a real seeded store. Prints one labelled line per arm.
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
DB = OUT / "ac2.db"

CHILD = r"""
import json
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["T20DB"]
try:
    from app.main import app
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)
print("BOOT", flush=True)
from fastapi.testclient import TestClient

client = TestClient(app)
print("HEALTH:", client.get("/api/v1/health").json(), flush=True)
import sqlalchemy as sa

from app.database import SessionLocal, engine

with engine.begin() as conn:
    def cell(sql):
        try:
            return str(conn.execute(sa.text(sql)).scalar())
        except Exception:
            return "ERR"
    print("COUNT_BEFORE:", "%s/%s/%s" % (
        cell("select count(*) from waitlist_entries"),
        (cell("select staff_pin_hash from settings") or "none")[:7],
        cell("select max(updated_at) from waitlist_entries")), flush=True)
if os.environ.get("NEED_TOKEN") == "1":
    import time

    from jose import jwt
    # The shipped signing path with this process's own secret and the payload shape the
    # contract declares (sub/role/iat/exp), so this probe never depends on T10's token
    # helpers (#76's territory), never sends an unauthenticated request (the router
    # answers 401 for that), and never trips the body-validation arm: the env guard is
    # evaluated after body validation, so a missing confirm would answer 422 everywhere
    # and every arm would look like a 403 pass.
    token = jwt.encode({"sub": "staff", "role": "staff", "iat": int(time.time()),
                       "exp": int(time.time()) + 3600},
                       os.environ["JWT_SECRET"], algorithm="HS256")
else:
    token = ""
r = client.post("/api/v1/admin/reset", json={"confirm": "RESET"},
                headers={"Authorization": "Bearer " + token} if token else {})
print("RESET:", r.status_code, flush=True)
with engine.begin() as conn:
    def cell2(sql):
        try:
            return str(conn.execute(sa.text(sql)).scalar())
        except Exception:
            return "ERR"
    print("COUNT_AFTER:", "%s/%s/%s" % (
        cell2("select count(*) from waitlist_entries"),
        (cell2("select staff_pin_hash from settings") or "none")[:7],
        cell2("select max(updated_at) from waitlist_entries")), flush=True)
SessionLocal.remove()
"""
CHILD_FILE = OUT / "child2.py"
CHILD_FILE.write_text(CHILD)


def arm(name, env_extra):
    if DB.exists():
        DB.unlink()
    base = dict(
        PYTHONPATH=os.environ["T20PROBEPATH"],
        TMPDIR=str(OUT),
        TZ="UTC",
        STAFF_PIN="0000",
        JWT_SECRET="t20groom-ac2aaaaaaaaaaaaaaaaaaaaaaa",
        DATABASE_URL="sqlite:///" + str(DB),
        T20DB=str(DB),
    )
    base.update(env_extra)
    seed = subprocess.run(
        [sys.executable, "-c",
         "from app.seed import seed_data; seed_data(reset=True)"],
        env=dict(base, ENV="development"), capture_output=True, text=True, timeout=180)
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=dict(base, NEED_TOKEN="1"),
                         capture_output=True, text=True, timeout=180)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("BOOT:", "RESET:", "COUNT_"))]
    print("ARM %s " + V + " %s" % (name, " ; ".join(obs) if obs
                           else "NO VERDICT LINE (seed rc=%s)" % seed.returncode),
          flush=True)


arm("absent", {})
arm("development", {"ENV": "development"})
arm("test", {"ENV": "test"})
arm("production", {"ENV": "production"})
if DB.exists():
    DB.unlink()
