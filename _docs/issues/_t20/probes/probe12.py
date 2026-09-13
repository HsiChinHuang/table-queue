"""T20 AC-12 probe: the guard's refusal does not depend on /health telling the truth.

D-4 keeps the 'env' field of /health and pins that it reports the value the operator named.
This probe measures the half of D-4 that a green AC-3 cannot give: the guard and the report
are separate reads of the same setting, and a tree whose /health hands out a defaulted label
while the guard is genuinely fixed is not a fixed tree - the externally readable state is the
only thing an operator has to reason about, and it would be lying in exactly the direction the
audit calls the defect.

Four arms, all booted with ENV=production, differing only in what else travels with them:
  prod-bare                     - the plain named-production process.
  prod-echo-requested           - plus the one documented operator flag (SQL_ECHO), so a fix
                                  that re-coupled echo to the label cannot hide inside this AC.
  prod-guard-defaulted          - the fourth mutation arm, made executable instead of reasoned
                                  about: a mutation tree identical to the fix except that the
                                  reset guard's condition is restored to "refuse everything
                                  except a defaulted development", which is the shape a
                                  developer reaches for when they want /health to "match" the
                                  guard. The store fingerprint then shows whether the guard is
                                  honest or merely loud.
  prod-health-defaults-development - the injected arm: an audit hook (a sitecustomize module
                                  on PYTHONPATH, active only under T20_AC12_PUBLISH) rebinds
                                  the module-level 'settings' object that the /health handler
                                  reads to one whose 'env' is "development", WITHOUT touching
                                  app.config or the router. Guard fixed, /health lying.

The store fingerprint behind each COUNT_* line is "<waitlist rows>/<first 7 chars of the
stored staff_pin_hash>/<max updated_at>", so a refusal that touched nothing is observable
rather than inferred from a status code. Everything is written under the scratch directory.
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
DB = (OUT / "ac12.db").resolve()

CHILD = r"""
import json
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["T20DB"]
try:
    from app.main import app
except Exception as exc:
    print("BOOT:", type(exc).__name__, flush=True)
    raise SystemExit(0)


def published_label(value):
    import app.config

    class _Label:
        def __init__(self, v):
            self.env = v

        def __getattr__(self, name):
            return getattr(app.config.get_settings(), name)

    return _Label(value)


if os.environ.get("T20_AC12_PUBLISH"):
    # The /health handler reads the module global at call time, so rebinding it after the
    # import completes is the honest injection point: app.config is never patched, the
    # reset guard keeps reading the real validated setting, and the hook prints a banner
    # naming the label it published so this arm cannot be mistaken for a real dev boot.
    sys.modules["app.main"].settings = published_label(os.environ["T20_AC12_PUBLISH"])
    sys.modules["app.main"]._t20_ac12_published = True
    print("PUBLISHED_ENV:", os.environ["T20_AC12_PUBLISH"], flush=True)

print("BOOT", flush=True)
from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.database import SessionLocal, engine
from jose import jwt

c = TestClient(app)
r = c.get("/health")
print("HEALTHCODE:", r.status_code, flush=True)
print("HEALTHBODY:", json.dumps(r.json()), flush=True)

tok = jwt.encode({"sub": "staff", "role": "staff", "iat": int(time.time()),
                  "exp": int(time.time()) + 3600},
                 os.environ["JWT_SECRET"], algorithm="HS256")


def cell(conn, sql):
    try:
        return str(conn.execute(sa.text(sql)).scalar())
    except Exception:
        return "ERR"


def fingerprint(conn):
    return "%s/%s/%s" % (
        cell(conn, "select count(*) from waitlist_entries"),
        (cell(conn, "select staff_pin_hash from settings") or "none")[:7],
        cell(conn, "select max(updated_at) from waitlist_entries"))


with engine.begin() as conn:
    print("COUNT_BEFORE:", fingerprint(conn), flush=True)
CONFIRM = os.environ.get("T20_CONFIRM", "RESET")
print("CONFIRM:", CONFIRM, flush=True)
r = c.post("/api/v1/admin/reset", json={"confirm": CONFIRM},
           headers={"Authorization": "Bearer " + tok})
print("RESET:", r.status_code, flush=True)
with engine.begin() as conn:
    print("COUNT_AFTER:", fingerprint(conn), flush=True)
SessionLocal.remove()
"""
CHILD_FILE = OUT / "child12.py"
CHILD_FILE.write_text(CHILD)


def base_env():
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.path.expanduser("~"),
        "TZ": "UTC",
        "TMPDIR": str(OUT),
        "PYTHONPATH": os.environ["T20PROBEPATH"],
        "JWT_SECRET": os.environ.get("JWT_SECRET", "t20groom-ac12a" + "a" * 33),
        "STAFF_PIN": "0000",
        "DATABASE_URL": "sqlite:///" + str(DB),
        "T20DB": str(DB),
        "ENV": "production",
    }


def tree_env(label):
    """One arm is a MUTATION arm: it runs against a copy of the tree under test carried in
    T20_AC12_MUTATION_TREE, where the reset guard's condition has been rewritten (see the
    arm list). The tree copy exists so the mutation is visible in the diff of a scratch tree
    rather than in the tree under review.
    """
    return base_env()


def run(label, extra_env, mutation=False, confirm="RESET"):
    if DB.exists():
        DB.unlink()
    env = tree_env(label)
    env.update(extra_env)
    if mutation:
        target = os.environ.get("T20_AC12_MUTATION_TREE")
        if not target:
            print("ARM %s " + V + " ARM NOT RUN: T20_AC12_MUTATION_TREE is unset, so the "
                  "mutation arm has no tree to measure (it is built by the block's own "
                  "mutation step, never by hand)" % label, flush=True)
            return
        env["PYTHONPATH"] = str(Path(target) / "backend")
        env["T20DB"] = str(DB)
        env["DATABASE_URL"] = "sqlite:///" + str(DB)
    # The store is seeded once per arm under an explicit development boot (the documented
    # reset contract), so the fingerprint has real rows and a real stored PIN hash to move.
    seed = subprocess.run(
        [sys.executable, "-c", "from app.seed import seed_data; seed_data(reset=True)"],
        env=dict(env, ENV="development"), capture_output=True, text=True, timeout=180)
    env["T20_CONFIRM"] = confirm
    if mutation:
        # The mutation tree is a copy of the tree under test, so its child must run with the
        # copy's own module path AND its own document tree: the child file itself is re-staged
        # into the copy so __file__-relative lookups cannot reach the reviewed tree.
        mut_child = Path(env["PYTHONPATH"]).parent / "_t20_ac12_child.py"
        mut_child.write_text(CHILD, encoding="utf-8")
        child = mut_child
    else:
        child = CHILD_FILE
    res = subprocess.run([sys.executable, str(child)], env=env,
                         capture_output=True, text=True, timeout=180)
    obs = [ln for ln in res.stdout.splitlines()
           if ln.startswith(("BOOT", "HEALTHCODE:", "HEALTHBODY:", "RESET:", "CONFIRM:",
                             "COUNT_", "PUBLISHED_ENV:"))]
    if not obs:
        # An arm that printed nothing at all is a harness failure, not a behaviour, so the
        # last line the child managed to write is carried into the ARM line. The delimiter is
        # substituted so the ARM line stays one parseable record.
        tail = [ln for ln in (res.stderr + res.stdout).splitlines() if ln.strip()]
        obs = ["NO VERDICT LINE tail=" + (tail[-1][:160] if tail else "nothing")
               + " seedrc=" + str(seed.returncode)]
    summary = " ; ".join(obs)
    print(("ARM %s " + V + " %s") % (label, summary), flush=True)


run("prod-bare", {})
run("prod-echo-requested", {"SQL_ECHO": "true"})
run("prod-health-defaults-development", {"T20_AC12_PUBLISH": "development"})
# The second half of the fourth mutant: a tree whose guard answers 403 for EVERY named
# environment, i.e. the fail-open is closed only by disabling the endpoint. The store
# fingerprint is what refuses it: the request that the fixed tree refuses here, this tree
# wipes, so the two arms cannot be confused by a status-code-only reader.
run("mutant_guard-ignores-the-named-environment-documented-confirm", {}, True, confirm="RESET")
# Same mutation tree, differently-cased confirm: recorded so the reader can see that the
# mutant honours the documented confirm in a named-production process at all, which is the
# whole refusal of this clause. The fix cannot reach this arm's answer under any confirm.
run("mutant_guard-ignores-the-named-environment-alternate-confirm", {}, True, confirm="Development")

if DB.exists():
    DB.unlink()
