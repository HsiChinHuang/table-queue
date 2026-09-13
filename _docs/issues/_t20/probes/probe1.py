"""T20 AC-1 probe: the environment is never resolved implicitly.

Boots the shipped application in a subprocess once per ENV arm (a subprocess is the
only honest harness here: app.config.get_settings is lru_cached and app.main plus
app.database read settings at import time, so the boot-time decision is a process
fact, not a per-request one), and prints one labelled line per measurement.
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

CHILD = """
import os, sys
try:
    from app.main import app
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)
print("BOOT", flush=True)
from fastapi.testclient import TestClient
print("HEALTH:", TestClient(app).get("/health").text, flush=True)
"""
CHILD_FILE = OUT / "child.py"
CHILD_FILE.write_text(CHILD)

BASE = dict(
    PYTHONPATH=os.environ["T20PROBEPATH"],
    TMPDIR=str(OUT),
    TZ="UTC",
    STAFF_PIN="0000",
    JWT_SECRET="t20groom-ac1aaaaaaaaaaaaaaaaaaaaaaaa",
)


def run(name, env_extra):
    db = OUT / ("ac1_%s.db" % name)
    if db.exists():
        db.unlink()
    env = dict(BASE)
    env["DATABASE_URL"] = "sqlite:///" + str(db)
    env.update(env_extra)
    res = subprocess.run([sys.executable, str(CHILD_FILE)], env=dict(env, T20DB=str(db)),
                         capture_output=True, text=True, timeout=120)
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(("BOOT:", "HEALTH:"))]
    print("ARM %s " + V + " %s" % (name, " ; ".join(lines) if lines else "NO VERDICT LINE"), flush=True)
    if db.exists():
        db.unlink()


run("absent", {})
run("blank", {"ENV": ""})
run("staging", {"ENV": "staging"})
run("dev", {"ENV": "development"})
run("test", {"ENV": "test"})
run("prod", {"ENV": "production"})
