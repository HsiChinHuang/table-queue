import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))          # the seedrow.py copy this block wrote there
import seedrow
DB = "_t9ac3.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB    # three slashes + a relative name
os.environ.setdefault("JWT_SECRET", "pmt9")
os.environ["STAFF_PIN"] = "0000"
from app.config import get_settings
if DB not in (get_settings().database_url or ""):
    print("BROKEN AC-3: database_url is not this block's file: " + str(get_settings().database_url)); sys.exit(0)
import app.main as M
if os.path.abspath(M.__file__) != os.path.abspath(os.path.join("backend", "app", "main.py")):
    print("BROKEN AC-3: app.main imported from the wrong tree: " + M.__file__); sys.exit(0)
import inspect
import app.database as D
import app.routers.auth as A
from app.main import limiter as _limiter
from fastapi.testclient import TestClient

_limiter.enabled = False   # login is budgeted 5/minute (B-05 AC-6); this block makes three calls
if not hasattr(A, "_pin_matches"):
    print("BROKEN AC-3: app.routers.auth._pin_matches is gone, so this block lost the verification "
          "site it reads the credential source from; retarget it at whatever function replaced it "
          "rather than deleting the assertion")
    sys.exit(0)
c = TestClient(M.app, raise_server_exceptions=False)
p = D.engine.url.database or ""
if os.path.exists(p):
    os.remove(p)
D.Base.metadata.create_all(D.engine)
d = D.SessionLocal(); M.bootstrap_defaults(d); d.close()   # exactly the shipped fresh-install row


def classify(src_text):
    """SOURCE=hash when the LAST thing the verified path can return is a bcrypt.checkpw against the
    stored column; SOURCE=plaintext otherwise. The tail line is the return the success branch
    reaches, so a fix that grows the function cannot slip past it, and a fix that deletes the
    function is caught by the BROKEN line above rather than by this one."""
    tail = [l.strip() for l in src_text.splitlines() if l.strip()][-1]
    if "checkpw" in tail and "staff_pin" not in tail.replace("staff_pin_hash", ""):
        return "SOURCE=hash"
    return "SOURCE=plaintext(" + tail[:48] + ")"


def login_and_report(pin):
    """Return (status, the credential source the APPLICATION's own verification site used).

    That source is not a constant of this probe, which would be self-fulfilling: it is read out of
    app.routers.auth._pin_matches, the single comparison the login path runs (measured at this base:
    main.py and dependencies.py contain no PIN comparison at all, and the backend/app/services/auth.py
    named in the issue's Files list does not exist). So the line its successful branch returns
    through IS the credential source of every token login minted.
    """
    r = c.post("/api/v1/auth/login", json={"pin": pin})
    if r.status_code != 200:
        return (r.status_code, "no-token")
    return (200, classify(inspect.getsource(A._pin_matches)))


st_env, src_env = login_and_report("0000")     # the env STAFF_PIN value against the NULL-hash row
d = D.SessionLocal(); seedrow.seed_hashed_row_on_existing(d); d.close()
st_good, src_good = login_and_report(seedrow.GOOD_PIN)
st_wrong, _ = login_and_report("1111")
print("OBS AC-3: env STAFF_PIN login %s source %s ; hashed-PIN login %s source %s ; unrelated PIN %s"
      % (st_env, src_env, st_good, src_good, st_wrong))
bad = []
if st_env != 401:
    bad.append("env_pin_mints_a_token=%s_want_401" % st_env)
if src_env != "no-token":
    bad.append("credential_source=%s_want_no-token" % src_env)
if src_good != "SOURCE=hash":
    bad.append("hash_credential_source=%s" % src_good)
if st_good != 200:
    bad.append("hashed_pin_login=%s_want_200" % st_good)
if st_wrong != 401:
    bad.append("unrelated_pin=%s_want_401" % st_wrong)
print(("FAIL AC-3: " + " ".join(bad)) if bad else
      "PASS AC-3: credential source is the stored hash and nothing else - the verified code path reports %s for a minted token, the env STAFF_PIN value cannot mint one at all (%s/%s), and an unrelated PIN stays refused (%s)"
      % (src_good, st_env, src_env, st_wrong))
