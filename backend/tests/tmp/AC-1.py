import os, sys, warnings
warnings.filterwarnings("ignore")
DB = "_t9ac.db"
# URL form matters twice over. "sqlite:///" + os.path.abspath(x) concatenates into FOUR slashes,
# which SQLite resolves relative to the cwd (measured: the engine then writes the file somewhere
# else and every query on it answers "no rows"). A plain relative path is what the B-05 blocks use.
os.environ["DATABASE_URL"] = "sqlite:///" + DB
os.environ.setdefault("JWT_SECRET", "pmt9")
os.environ.setdefault("STAFF_PIN", "0000")
from app.config import get_settings
s0 = get_settings()
if DB not in (s0.database_url or ""):
    print("BROKEN AC-1: database_url is not this block's file: " + str(s0.database_url)); sys.exit(0)
import app.main as M
want = os.path.abspath(os.path.join("backend", "app", "main.py"))
if os.path.abspath(M.__file__) != want:
    print("BROKEN AC-1: app.main imported from the wrong tree: " + M.__file__); sys.exit(0)
import app.database as D
from sqlalchemy import text
p = D.engine.url.database or ""
if os.path.exists(p):
    os.remove(p)
D.Base.metadata.create_all(D.engine)
db = D.SessionLocal()
M.bootstrap_defaults(db)
vals = [r[0] for r in db.execute(text("select staff_pin_hash from settings")).fetchall()]
seed = s0.staff_pin or "0000"
bad = []
if len(vals) != 1:
    bad.append("settings_rows=" + str(len(vals)))
else:
    h = vals[0]
    if h is None or not str(h).strip():
        bad.append("staff_pin_hash=" + repr(h))
    elif not str(h).startswith("$2b$12$"):
        bad.append("prefix=" + str(h)[:7])
    elif len(str(h)) != 60:
        bad.append("len=" + str(len(str(h))))
    else:
        import bcrypt
        if not bcrypt.checkpw(seed.encode(), str(h).encode()):
            bad.append("hash_does_not_match_STAFF_PIN")
        if bcrypt.checkpw("4321".encode(), str(h).encode()):
            bad.append("hash_matches_unrelated_PIN_4321")
        if not bad:
            print("HASH AC-1: prefix=" + str(h)[:7] + " len=" + str(len(str(h))) + " derives_from_STAFF_PIN=True")
            print("SEED AC-1: the bootstrapped hash answers to the env STAFF_PIN value, which is the one-time seed source named in AC-2; the env string itself is no longer a credential (AC-3)")
from fastapi.testclient import TestClient
import sqlite3
c = TestClient(M.app, raise_server_exceptions=False)
tok = c.post("/api/v1/auth/login", json={"pin": "0000"}).json().get("access_token", "")
pre = c.get("/api/v1/admin/settings", headers={"Authorization": "Bearer " + tok}).status_code
conn = sqlite3.connect(p); cur = conn.cursor()
cur.execute("update settings set staff_pin_hash=null where id=1"); conn.commit(); conn.close()
post = c.get("/api/v1/admin/settings", headers={"Authorization": "Bearer " + tok}).status_code
tok2 = c.post("/api/v1/auth/login", json={"pin": "0000"}).json().get("access_token", "")
post_b = c.get("/api/v1/admin/settings", headers={"Authorization": "Bearer " + tok2}).status_code
anon = c.get("/api/v1/admin/settings").status_code
conn = sqlite3.connect(p); cur = conn.cursor()
cur.execute("update settings set staff_pin_hash=? where id=1", (vals[0],)); conn.commit(); conn.close()
post3 = c.get("/api/v1/admin/settings", headers={"Authorization": "Bearer " + tok2}).status_code
if pre != 200:
    bad.append("staff_settings_on_hashed_row=" + str(pre))
if post != 401 or post_b != 401:
    bad.append("hashless_row_status=%s/%s_want_401/401" % (post, post_b))
if post3 != 401:
    bad.append("post_restore_status=%s_want_401" % post3)
if anon != 401:
    bad.append("anonymous_settings=" + str(anon))
db.close()
print(("FAIL AC-1: " + " ".join(bad)) if bad else
      "PASS AC-1: bootstrap writes exactly one settings row carrying a 60-char $2b$12$ hash derived from the one-time STAFF_PIN seed, and a hash-less row fails closed: old token %s, fresh login %s, post-restore %s, anonymous %s (want 401 x4, hashed control %s)" % (post, post_b, post3, anon, pre))
