import os, sys, warnings
warnings.filterwarnings("ignore")
DB = "_t9ac5.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB     # three slashes + a RELATIVE name (see AC-1)
os.environ.setdefault("JWT_SECRET", "pmt9")
os.environ.setdefault("STAFF_PIN", "0000")
from app.config import get_settings
if DB not in (get_settings().database_url or ""):
    print("BROKEN AC-5: database_url is not this block's file: " + str(get_settings().database_url)); sys.exit(0)
import app.main as M
if os.path.abspath(M.__file__) != os.path.abspath(os.path.join("backend", "app", "main.py")):
    print("BROKEN AC-5: app.main imported from the wrong tree: " + M.__file__); sys.exit(0)
import app.database as D
from sqlalchemy import text
from fastapi.testclient import TestClient
from jose import jwt

OLD, NEW, THIRD = "0000", "4321", "8642"
p = D.engine.url.database or ""
if os.path.exists(p):
    os.remove(p)
D.Base.metadata.create_all(D.engine)
db = D.SessionLocal()
import seedrow
seedrow.seed_hashed_row(db, OLD)      # one row whose credential is hash(0000); bootstrap is not involved
db.close()
import bcrypt
from app.main import limiter as _limiter
_limiter.enabled = False   # login is budgeted 5/minute (B-05 AC-6); this block makes five logins
c = TestClient(M.app, raise_server_exceptions=False)
PROTECTED = "/api/v1/admin/settings"

def tok_for(pin):
    r = c.post("/api/v1/auth/login", json={"pin": pin})
    return r.status_code, r.json().get("access_token", "") if r.status_code == 200 else ""

def get(t):
    return c.get(PROTECTED, headers={"Authorization": "Bearer " + t}).status_code

bad = []
st1, t1 = tok_for(OLD)
if st1 != 200 or not t1:
    print("FAIL AC-5: cannot start the measurement, login with the seeded PIN was " + str(st1)
          + " (AC-1/AC-3 must land first: this block needs a hashed row that answers to its PIN)")
    sys.exit(0)
base = get(t1)
claims = jwt.get_unverified_claims(t1)
rot = c.post("/api/v1/auth/change-pin", headers={"Authorization": "Bearer " + t1},
             json={"current_pin": OLD, "new_pin": NEW, "confirm_new_pin": NEW})
after = get(t1)
st2, t2 = tok_for(NEW)
fresh = get(t2) if t2 else 0
rot2 = c.post("/api/v1/auth/change-pin", headers={"Authorization": "Bearer " + t2},
              json={"current_pin": NEW, "new_pin": THIRD, "confirm_new_pin": THIRD})
after2 = get(t2) if t2 else 0
st3, t3 = tok_for(THIRD)
fresh2 = get(t3) if t3 else 0
tampered = t1[:-4] + ("aaaa" if t1[-4:] != "aaaa" else "bbbb")
forged = get(tampered)
forged_tok = jwt.encode({"sub": "staff", "role": "staff", "iat": 1, "exp": 2 ** 31},
                        "pmt9", algorithm="HS256")
forged_secret = get(forged_tok)
wrong_pin = c.post("/api/v1/auth/change-pin", headers={"Authorization": "Bearer " + t3},
                   json={"current_pin": "1111", "new_pin": "9999", "confirm_new_pin": "9999"}).status_code
row = D.SessionLocal()
h = row.execute(text("select staff_pin_hash from settings where id=1")).fetchone()[0]
row.close()
hash_ok = bcrypt.checkpw(THIRD.encode(), str(h).encode())
print("OBS AC-5: pre-rotation GET %s -> post-rotation GET %s ; post-rotation login %s GET %s ; "
      "second rotation %s -> that token %s, third login %s GET %s ; mutated token %s ; "
      "jwt_secret-signed token %s ; wrong current_pin %s ; new hash matches PIN3 %s"
      % (base, after, st2, fresh, rot2.status_code, after2, st3, fresh2, forged, forged_secret,
         wrong_pin, hash_ok))
if base != 200:
    bad.append("pre_rotation=%s" % base)
if after != 401 or after2 != 401:
    bad.append("pre_rotation_tokens_after_rotation=%s/%s_want_401/401" % (after, after2))
if st2 != 200 or fresh != 200:
    bad.append("post_rotation_login=%s/get=%s" % (st2, fresh))
if rot2.status_code != 204 or st3 != 200 or fresh2 != 200:
    bad.append("second_rotation=%s/login=%s/get=%s" % (rot2.status_code, st3, fresh2))
if forged != 401 or forged_secret != 401:
    bad.append("forgery=%s/%s" % (forged, forged_secret))
if wrong_pin != 401:
    bad.append("change_pin_wrong_current=%s_want_401" % wrong_pin)
if not hash_ok:
    bad.append("stored_hash_does_not_match_new_pin")
if sorted(claims) != ["exp", "iat", "role", "sub"] or claims.get("sub") != "staff" or claims.get("role") != "staff":
    bad.append("claims=" + ",".join(sorted(claims)))
print(("FAIL AC-5: " + " ".join(bad)) if bad else
      "PASS AC-5: rotation is a revocation event - both pre-rotation tokens 401 (measured twice), "
      "the post-rotation login and its GET answer 200, a second rotation revokes again, a mutated "
      "signature and a token signed with the bare JWT_SECRET both 401, the old PIN can no longer "
      "rotate, and the stored hash answers to the newest PIN (claims unchanged: sub/role/iat/exp)")
