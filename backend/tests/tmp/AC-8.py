import os, re, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seedrow
DB = "_t9ac8.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB    # three slashes + a relative name
os.environ.setdefault("JWT_SECRET", "pmt9")
os.environ["STAFF_PIN"] = "0000"
from app.config import get_settings
if DB not in (get_settings().database_url or ""):
    print("BROKEN AC-8: database_url is not this block's file: " + str(get_settings().database_url)); sys.exit(0)
import app.main as M
if os.path.abspath(M.__file__) != os.path.abspath(os.path.join("backend", "app", "main.py")):
    print("BROKEN AC-8: app.main imported from the wrong tree: " + M.__file__); sys.exit(0)
import app.database as D
from app.main import limiter as _limiter
from sqlalchemy import text
from jose import jwt as _jwt
_limiter.enabled = False   # login is budgeted 5/minute; this block logs in once and does not care to 429
from fastapi.testclient import TestClient
p = D.engine.url.database or ""
if os.path.exists(p):
    os.remove(p)
D.Base.metadata.create_all(D.engine)
d = D.SessionLocal(); seedrow.seed_hashed_row(d); d.close()      # hash(4321), no bootstrap involved
c = TestClient(M.app, raise_server_exceptions=False)
st, tok = 0, ""
for _ in range(3):   # AC-3/AC-1 must have landed for this to have a token; retry across limiter states
    r = c.post("/api/v1/auth/login", json={"pin": seedrow.GOOD_PIN})
    st = r.status_code
    if st == 200:
        tok = r.json().get("access_token", "")
        break
H = {"Authorization": "Bearer " + tok}
if st != 200:
    print("FAIL AC-8: cannot start the measurement, login with the hashed PIN was " + str(st)
          + " (AC-1/AC-2/AC-3 must land first)")
    raise SystemExit(0)
bad = []
claims = _jwt.get_unverified_claims(tok)
if sorted(claims) != ["exp", "iat", "role", "sub"]:
    bad.append("claims=" + ",".join(sorted(claims)))
if claims.get("sub") != "staff" or claims.get("role") != "staff":
    bad.append("sub/role=%s/%s" % (claims.get("sub"), claims.get("role")))
if not claims.get("exp") or not claims.get("iat"):
    bad.append("iat/exp missing")
if int(claims["exp"]) - int(claims["iat"]) != int(get_settings().jwt_expire_hours) * 3600:
    bad.append("lifetime=%s_want_%s" % (int(claims["exp"]) - int(claims["iat"]), int(get_settings().jwt_expire_hours) * 3600))
ok = c.get("/api/v1/admin/settings", headers=H)
body = ok.text
stored = d2 = None
dd = D.SessionLocal()
stored = dd.execute(text("select staff_pin_hash from settings where id=1")).fetchone()[0]
dd.close()
if ok.status_code != 200:
    bad.append("settings_get=%s_want_200" % ok.status_code)
if stored and (stored in body or str(stored)[:12] in body):   # full hash, or the 12 chars a leak would carry
    bad.append("HASH LEAKED in the settings body")
if "staff_pin_hash" in body or "staff_pin" in body:
    bad.append("staff_pin field name present in the settings body")
if "has_pin" not in body:
    bad.append("has_pin missing from the settings body")
# PATCH must refuse both keys, and must not accept the second one as a plaintext PIN
r1 = c.patch("/api/v1/admin/settings", headers=H, json={"staff_pin_hash": "$2b$12$attacker"})
r2 = c.patch("/api/v1/admin/settings", headers=H, json={"staff_pin": "987654"})
r3 = c.patch("/api/v1/admin/settings", headers=H, json={"hold_minutes": 7})
dd = D.SessionLocal()
after = dd.execute(text("select staff_pin_hash, hold_minutes from settings where id=1")).fetchone()
dd.close()
# B-11 AC-3 is the binding contract here: the PATCH body must be REJECTED outright (400/422), not
# silently ignored, and the stored hash must be what the request left it as.
if r1.status_code not in (400, 422):
    bad.append("patch_hash_key=%s_want_400/422_rejected_outright" % r1.status_code)
if r2.status_code not in (400, 422):
    bad.append("patch_plaintext_pin=%s_want_400/422_rejected_outright" % r2.status_code)
if after and after[0] != stored:
    bad.append("hash_changed_by_patch")
if r3.status_code == 200 and after and after[1] != 7:
    bad.append("legitimate_patch_did_not_apply")
if r3.status_code != 200:
    bad.append("legitimate_patch=%s_want_200" % r3.status_code)
print("OBS AC-8: claims %s lifetime %ss ; settings GET %s has_pin=%s ; patch(staff_pin_hash) %s ; patch(staff_pin) %s ; patch(hold_minutes) %s ; stored hash unchanged by the rejected patches: %s"
      % (",".join(sorted(claims)), int(claims["exp"]) - int(claims["iat"]), ok.status_code,
         ok.json().get("has_pin") if ok.status_code == 200 else "?", r1.status_code, r2.status_code, r3.status_code,
         "yes" if (after and after[0] == stored) else "NO"))
print(("FAIL AC-8: " + " ".join(bad)) if bad else
      "PASS AC-8: the auth contract did not move - claims stay sub/role/iat/exp with the JWT_EXPIRE_HOURS lifetime, a staff settings read answers 200 and carries has_pin but never the hash or a staff_pin field, PATCH refuses both staff_pin_hash and the plaintext staff_pin without touching the stored hash, and a legitimate field still patches")
