"""T20 AC-4 probe: the suite's own environment statement is enough to boot the app.

conftest.py, public_fixtures.py and the staff modules each carry an
""os.environ.setdefault("ENV", ...)"" line above their imports, and D-1 turns ""ENV"" into
a required setting. This probe boots the application the way pytest does - in a child whose
environment is exactly that module's statement, with no inherited ""ENV"" - and reports the
settings the application resolved, so the AC can check the value AND that the statement is
load-bearing rather than decorative. Prints one labelled line per harness file.
"""
import os
import shutil
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

TARGETS = [
    "backend/tests/conftest.py",
    "backend/tests/public_fixtures.py",
    "backend/tests/test_public_board.py",
    "backend/tests/test_public_waitlist.py",
    "backend/tests/test_staff_dashboard.py",
    "backend/tests/test_staff_tables.py",
    "backend/tests/test_seed.py",
    "backend/tests/_atomicity_probe.py",
]

CHILD_SRC = 'import json\nimport os\nimport re\nimport sys\n\nname = sys.argv[1]\nsrc = open(name).read()\npairs = re.findall(r\'setdefault\\(.([A-Z_]+)., .([^\\"]*).\', src)\nfor key in ("ENV", "JWT_SECRET", "STAFF_PIN", "DATABASE_URL"):\n    os.environ.pop(key, None)\nos.environ["DATABASE_URL"] = "sqlite:///" + os.environ["T20DB"]\n\nfor key, value in pairs:\n    if key in ("ENV", "JWT_SECRET", "STAFF_PIN"):\n        os.environ.setdefault(key, value)\nsecret = os.environ.get("JWT_SECRET", "")\nprint("ENVIRONMENT:", name, json.dumps({\n    "ENV": os.environ.get("ENV", "<absent>"),\n    "STAFF_PIN": os.environ.get("STAFF_PIN", "<absent>"),\n    "JWT_SECRET_LEN": len(secret),\n    "JWT_SECRET_PUBLISHED": secret in ("test-secret-key", "change-me-in-production"),\n}), flush=True)\ntry:\n    from app.main import app\nexcept Exception as exc:\n    print("BOOT:", type(exc).__name__, flush=True)\n    raise SystemExit(0)\nprint("BOOT", flush=True)\nfrom app.config import get_settings\nfrom app.database import engine\n\ns = get_settings()\nprint("RESOLVED_ENV:", s.env, flush=True)\nprint("SQL_ECHO_FIELD:", s.model_dump().get("sql_echo", "no-sql_echo-field"), flush=True)\nprint("MAIN_ECHO:", engine.echo, flush=True)'
CHILD_FILE = OUT / "child4.py"
CHILD_FILE.write_text(CHILD_SRC.replace("TWOCHAR", chr(34) * 2))



SHIPPED = OUT / "shipped"
SHIPPED.mkdir(exist_ok=True)
# The shipped harness modules locate _docs/specs.md by walking up from __file__,
# so the staged copy is pointed at the tree under test explicitly rather than at
# the scratch directory it now sits in. APP_DIR is the tree the probe measures.
ROOT = Path(os.environ["T20PROBEPATH"]).resolve().parent
for name in TARGETS:
    shutil.copy2(Path(name).resolve(), SHIPPED / Path(name).name)


def run(target):
    target = str(SHIPPED / Path(target).name)
    db = OUT / ("ac4_%d.db" % abs(hash(target)))
    env = dict(
        PYTHONPATH=os.environ["T20PROBEPATH"],
        TMPDIR=str(OUT),
        TZ="UTC",
        PATH=os.environ.get("PATH", "/usr/bin:/bin"),
        HOME=os.path.expanduser("~"),
        T20DB=str((OUT / ("ac4_%d.db" % abs(hash(target)))).resolve()),
        APP_DIR=str(ROOT),
    )
    res = subprocess.run([sys.executable, str(CHILD_FILE), target], env=env,
                         capture_output=True, text=True, timeout=180)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("ENVIRONMENT:", "BOOT", "RESOLVED_ENV:", "ECHO:", "MAIN_ECHO:"))]
    if not obs:
        obs = ["NO VERDICT LINE: " + (res.stderr.strip().splitlines() or [""])[-1][:120]]
    print("ARM %s " + V + " %s" % (target, " ; ".join(obs)), flush=True)
    if db.exists():
        db.unlink()


for target in TARGETS:
    run(target)
