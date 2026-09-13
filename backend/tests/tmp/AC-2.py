import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))          # the seedrow.py copy this block wrote there
import seedrow
DB = "_t9ac2.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB    # three slashes + a relative name
os.environ.setdefault("JWT_SECRET", "pmt9")
os.environ["STAFF_PIN"] = "0000"
from app.config import get_settings
if DB not in (get_settings().database_url or ""):
    print("BROKEN AC-2: database_url is not this block's file: " + str(get_settings().database_url)); sys.exit(0)
import app.main as M
if os.path.abspath(M.__file__) != os.path.abspath(os.path.join("backend", "app", "main.py")):
    print("BROKEN AC-2: app.main imported from the wrong tree: " + M.__file__); sys.exit(0)
import app.database as D
p = D.engine.url.database or ""

def fresh_db():
    if os.path.exists(p):
        os.remove(p)
    D.Base.metadata.create_all(D.engine)

from app.main import limiter as _limiter
from fastapi.testclient import TestClient
_limiter.enabled = False   # login carries a 5/minute budget (B-05 AC-6) and this block makes 9 calls
c = TestClient(M.app, raise_server_exceptions=False)


def login(pin):
    return c.post("/api/v1/auth/login", json={"pin": pin}).status_code

def set_hash(value):
    from sqlalchemy import text
    d = D.SessionLocal()
    d.execute(text("update settings set staff_pin_hash=:h where id=1"), {"h": value})
    d.commit(); d.close()

bad = []
# --- shape 1: the row bootstrap_defaults writes, i.e. the shipped fresh-install state (hash NULL) --
fresh_db()
d = D.SessionLocal(); M.bootstrap_defaults(d); d.close()
s_null_env = login("0000")           # the env value: must be refused, A-2's whole point
s_null_wrong = login("1111")
s_null_hash = login(seedrow.GOOD_PIN)
# --- shape 2: a row whose only credential is a hash; the env value must be refused outright -------
fresh_db()
d = D.SessionLocal(); M.bootstrap_defaults(d)
seed_hash = seedrow.seed_hashed_row_on_existing(d)   # overwrite with hash(4321)
d.close()
s_hash_env = login("0000")
s_hash_good = login(seedrow.GOOD_PIN)
s_hash_other = login("1111")
# --- shape 3: blank hash, the other spelling of "no credential configured" ------------------------
set_hash("   ")
s_blank_env = login("0000")
print("OBS AC-2: hash-NULL row: env PIN %s / unrelated %s / good %s ; hashed row: env PIN %s / good %s / unrelated %s ; blank hash: env PIN %s"
      % (s_null_env, s_null_wrong, s_null_hash, s_hash_env, s_hash_good, s_hash_other, s_blank_env))
if s_null_env != 401:
    bad.append("null_hash_env_pin_login=%s_want_401" % s_null_env)
if s_null_wrong != 401 or s_null_hash != 401:
    bad.append("null_hash_any_pin=%s/%s_want_401/401" % (s_null_wrong, s_null_hash))
if s_hash_env != 401:
    bad.append("hashed_row_env_pin_login=%s_want_401" % s_hash_env)
if s_hash_good != 200:
    bad.append("hashed_row_good_pin=%s_want_200" % s_hash_good)
if s_hash_other != 401:
    bad.append("hashed_row_unrelated_pin=%s_want_401" % s_hash_other)
if s_blank_env != 401:
    bad.append("blank_hash_env_pin_login=%s_want_401" % s_blank_env)
print(("FAIL AC-2: " + " ".join(bad)) if bad else
      "PASS AC-2: the env STAFF_PIN string is never an accepted credential (NULL row %s, hashed row %s, blank hash %s) and a stored hash still authenticates (%s) while unrelated PINs stay refused (%s/%s)"
      % (s_null_env, s_hash_env, s_blank_env, s_hash_good, s_hash_other, s_null_wrong))
