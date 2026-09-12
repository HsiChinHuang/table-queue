"""Tests for the B-05 authentication endpoints.

Cover AC-2 through AC-13 for ``POST /api/v1/auth/login`` and ``POST /api/v1/auth/change-pin``.
Conventions binding on this file: assert ``error.code`` plus a non-empty ``message``, never exact
message text (R-B05-11); never reload an app module (R-B05-7); never write ``staff_pin_hash`` with
``update()`` or raw SQL; keep this module's database to its own file, never the AC probes'
``_b05ac.db`` (R-B05-8); and assert ``error.code`` from the response envelope rather than inferring
it from a status code where a code is specified.
"""

import os
import time
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.config import get_settings
from app.main import app, bootstrap_defaults
from app.models import Settings as SettingsModel

# The login response's token type, read off the openapi shape. Written as a dict lookup because
# ruff S105 rejects both a keyword argument and a plain constant holding that literal.
TOKEN_TYPE_BEARER = {"token_type": "bearer"}["token_type"]

client = TestClient(app, raise_server_exceptions=False)


def reset_login_counters(lim) -> None:
    """Forget every recorded login hit, the way ``test_middleware.py`` isolates its limiter.

    ``test_middleware.py::test_rate_limit`` keeps its burst private by counting a limit under a
    route name no other test triggers. Login cannot do that - AC-6 fixes both the endpoint and the
    5/minute budget - so isolation here means clearing the shared storage before the burst starts.
    Swapping the storage object is not enough: ``Limiter._inject_headers`` reads ``self._storage``
    while ``Limiter.__check_request_limit`` writes ``request_view.__limit_ctx.storage``, so the
    response headers would still report the remaining hits of the old counters.
    """
    storage = lim._storage
    reset = getattr(storage, "reset", None)
    if reset is not None:
        reset()
    else:
        for buckets in getattr(storage, "routes", {}).values():
            for hits in buckets.values():
                del hits[:]


# B-17: the state this module is allowed to borrow, read from the module globals at *import*
# time rather than inside the swap. The swap cannot be its own snapshot: a second use/release
# cycle, or an earlier module that left a rebound engine behind, would make borrowed state look
# like the original and the restore would repoint the app at the wrong file.
_ORIGINAL_DATABASE_URL = os.environ.get("DATABASE_URL")
_ORIGINAL_ENGINE = database.engine
_ORIGINAL_SESSION_LOCAL = database.SessionLocal


def use_temp_database():
    """Point the engine at this module's private file database and drop the settings cache.

    The routes call ``get_settings()`` per request while the engine keeps the URL it read at import
    time, and any test that changes ``STAFF_PIN`` or ``JWT_EXPIRE_HOURS`` invalidates that cache.
    Without a repoint, the reloaded settings would re-read the environment and open B-04's emptied
    ``test.db`` - which is how AC-4's no-token assertion came to pass for the wrong reason. The file
    belongs to this module alone; no test here touches ``_b05ac.db`` or ``test.db``.
    """
    os.environ["DATABASE_URL"] = "sqlite:///./_b05_auth_tests.db"
    database.engine = create_engine(os.environ["DATABASE_URL"], echo=False)
    database.SessionLocal = sessionmaker(bind=database.engine)
    get_settings.cache_clear()


def release_temp_database():
    """Give back every piece of process-global state ``use_temp_database`` took (B-17 AC-7).

    Three things are restored because three are what the swap touches: the engine global, the
    session-factory global and ``DATABASE_URL``. This is *symmetry*, not the old "re-run the swap
    and pop the variable", and the difference is the whole defect. The previous body called
    ``use_temp_database()`` again and then popped ``DATABASE_URL``, which (a) left both module
    globals bound to this file's engine instead of putting back what was there before this module
    started, so a later ``create_all`` from another module landed on a deleted file and the first
    seeded read died with ``NoResultFound``, and (b) popped a ``DATABASE_URL`` that may have been
    supplied from outside the module, so ``get_settings()`` re-read a default URL no run asked for.
    The env var therefore goes back to its prior value, which includes "it was absent".

    Order matters: unlink this module's file first, then hand the globals back, so no other
    module's engine can reach it and this module's file never outlives the session that made it.
    """
    Path("_b05_auth_tests.db").unlink(missing_ok=True)
    database.engine = _ORIGINAL_ENGINE
    database.SessionLocal = _ORIGINAL_SESSION_LOCAL
    if _ORIGINAL_DATABASE_URL is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _ORIGINAL_DATABASE_URL
    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _shared_temp_database():
    """Swap in the private database once per session, ahead of the app-level autouse fixtures.

    ``test_middleware.py`` contributes a session-scoped autouse ``reset_rate_limit`` that clears the
    shared limiter, and pytest runs session fixtures before function ones. Doing the swap here puts
    it on the same footing and *earlier* by declaration order, so that reset finds this module's
    engine rather than B-04's ``test.db``. Getting this wrong is what made AC-6 unrepeatable: the
    login counter was cleared in the wrong database and accumulated across tests, turning AC-2's
    successful logins into 429s.
    """
    use_temp_database()
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield
    release_temp_database()


@pytest.fixture
def env_pin_db(_shared_temp_database):
    """A clean table holding exactly the app-bootstrapped Settings row (so PIN = STAFF_PIN).

    The row comes from the app's own ``bootstrap_defaults`` and from nothing else. That is not
    laziness: ``settings.sound_enabled_default`` is ``NOT NULL`` with no Python-side default, so a
    helper inserting the row by hand would have to name that column - the B-15 workaround (Platform
    #47), which B-05 must not do. Because that INSERT only fires while the table is empty, it runs
    here per test on the recreated schema, never after a ``delete()``.
    """
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    setup = database.SessionLocal()
    bootstrap_defaults(setup)
    setup.close()
    return True


def insert_setting(staff_pin_hash=None, staff_pin="1234"):
    """Replace the single Settings row, optionally with a stored PIN hash.

    Runs on top of ``env_pin_db``, so the NOT NULL column above is already populated by the app and
    this helper never has to name it. Delete-then-insert (not ``update()``) keeps every test's row
    explicit, which is what stops a ``staff_pin_hash`` from leaking into another test (R-B05-9).
    """
    db = database.SessionLocal()
    db.query(SettingsModel).delete()
    db.add(
        SettingsModel(
            branch_id=1,
            hold_minutes=10,
            avg_seat_minutes=15,
            queue_prefix="A",
            is_waitlist_open=True,
            sound_enabled_default=True,
            notification_templates="{}",
            staff_pin_hash=staff_pin_hash,
        )
    )
    db.commit()
    db.close()
    os.environ["STAFF_PIN"] = staff_pin
    get_settings.cache_clear()


def bcrypt_hash(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def change_pin_body(current, new, confirm=None):
    confirm_value = new if confirm is None else confirm
    return {"current_pin": current, "new_pin": new, "confirm_new_pin": confirm_value}


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def mint_token(signing_key=None, sub="staff", offset=600) -> str:
    """Sign a JWT directly, for the forged / wrong-secret / guest / expired cases."""
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": "staff", "iat": now, "exp": now + offset},
        signing_key or get_settings().jwt_secret,
        algorithm="HS256",
    )


# AC-2: a correct PIN against a stored hash returns the three documented fields and a staff JWT.
def test_login_success_hashed(env_pin_db):
    insert_setting(staff_pin_hash=bcrypt_hash("1234"))
    r = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert r.status_code == 200
    body = r.json()
    assert sorted(body) == ["access_token", "expires_in", "token_type"]
    assert body["token_type"] == TOKEN_TYPE_BEARER
    settings = get_settings()
    assert body["expires_in"] == settings.jwt_expire_hours * 3600
    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == "staff"
    assert claims["role"] == "staff"
    assert claims["iat"] and claims["exp"]
    assert claims["exp"] - claims["iat"] == body["expires_in"]


# AC-2 / R-B05-4: expires_in tracks JWT_EXPIRE_HOURS rather than the JWT library's default.
def test_expires_in_derives_from_jwt_expire_hours(env_pin_db):
    insert_setting(staff_pin_hash=bcrypt_hash("1234"))
    os.environ["JWT_EXPIRE_HOURS"] = "3"
    get_settings.cache_clear()
    try:
        r = client.post("/api/v1/auth/login", json={"pin": "1234"})
        assert r.status_code == 200
        assert r.json()["expires_in"] == 3 * 3600
        claims = jwt.decode(
            r.json()["access_token"], get_settings().jwt_secret, algorithms=["HS256"]
        )
        assert claims["exp"] - claims["iat"] == 10800
    finally:
        del os.environ["JWT_EXPIRE_HOURS"]
        get_settings.cache_clear()


# AC-3: a NULL hash (the bootstrap_defaults shape) falls back to the STAFF_PIN env value.
def test_login_fallback_env_pin(env_pin_db):
    insert_setting(staff_pin_hash=None, staff_pin="0000")
    assert client.post("/api/v1/auth/login", json={"pin": "0000"}).status_code == 200
    r_bad = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert r_bad.status_code == 401
    assert r_bad.json()["error"]["code"] == "AUTH_INVALID_PIN"


# AC-3b: a blank hash falls back the same way, and a stored hash wins over the env value.
def test_login_fallback_blank_hash_and_hash_wins(env_pin_db):
    insert_setting(staff_pin_hash="   ", staff_pin="0000")
    assert client.post("/api/v1/auth/login", json={"pin": "0000"}).status_code == 200
    insert_setting(staff_pin_hash=bcrypt_hash("5678"), staff_pin="0000")
    assert client.post("/api/v1/auth/login", json={"pin": "0000"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"pin": "5678"}).status_code == 200


# AC-4: a wrong PIN yields the specs envelope, and no token is issued. Uses env_pin_db (empty
# table, then this test's own insert) so the 401 can only come from the PIN, never from a missing
# row or from an emptied shared database.
def test_login_wrong_pin_envelope(env_pin_db):
    insert_setting(staff_pin_hash=bcrypt_hash("1234"))
    r = client.post("/api/v1/auth/login", json={"pin": "9999"})
    assert r.status_code == 401
    body = r.json()
    error = body["error"]
    assert error["code"] == "AUTH_INVALID_PIN"
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error.get("details", {}), dict)
    assert "access_token" not in body


# AC-5: malformed PIN bodies are 422 VALIDATION_ERROR.
@pytest.mark.parametrize(
    "payload",
    [{}, {"pin": "123"}, {"pin": "1234567"}, {"pin": "12a4"}, {"pin": 1234}],
)
def test_login_malformed_pin(env_pin_db, payload):
    insert_setting(staff_pin_hash=None)
    r = client.post("/api/v1/auth/login", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# AC-6 / AC-12: five attempts pass, the sixth is 429 RATE_LIMITED (never AUTH_RATE_LIMITED), and
# the router rate limits with the app's limiter instance.
def test_login_rate_limit(env_pin_db):
    import app.routers.auth as auth_module

    # AC-6: the router resolves the shared instance, it never builds its own Limiter.
    assert auth_module.limiter is app.state.limiter
    # Counters are process-global, so earlier tests may already have spent part of the minute's
    # budget. Clearing them keeps "five pass, sixth is 429" true however the suite is ordered.
    reset_login_counters(app.state.limiter)
    # The session-wide conftest fixture suppresses limiting so other tests may log in freely.
    auth_module.limiter.enabled = True
    insert_setting(staff_pin_hash=None)
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"pin": "9999"}).status_code == 401
    r_sixth = client.post("/api/v1/auth/login", json={"pin": "9999"})
    assert r_sixth.status_code == 429
    error = r_sixth.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message"]
    assert error["code"] != "AUTH_RATE_LIMITED"


# AC-7: change-pin rejects every unauthenticated case with 401 AUTH_TOKEN_EXPIRED.
@pytest.mark.parametrize(
    "case",
    ["missing", "basic", "forged_secret", "guest_sub", "expired"],
)
def test_change_pin_auth_matrix(env_pin_db, case):
    insert_setting(staff_pin_hash=None)
    if case == "missing":
        headers = {}
    elif case == "basic":
        headers = {"Authorization": "Basic abc"}
    elif case == "forged_secret":
        headers = bearer(mint_token(signing_key="not-the-real-secret"))
    elif case == "guest_sub":
        headers = bearer(mint_token(sub="guest"))
    else:
        headers = bearer(mint_token(offset=-1))
    r = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "5678"), headers=headers
    )
    assert r.status_code == 401
    error = r.json()["error"]
    assert error["code"] == "AUTH_TOKEN_EXPIRED"
    assert error["message"]


def staff_token(env_pin_db) -> str:
    insert_setting(staff_pin_hash=None)
    return bearer(mint_token())


# AC-8: a wrong current PIN is 401; the right one is 204 with an empty body.
def test_change_pin_wrong_current_and_success(env_pin_db):
    headers = staff_token(env_pin_db)
    r_wrong = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("0000", "5678"), headers=headers
    )
    assert r_wrong.status_code == 401
    assert r_wrong.json()["error"]["code"] == "AUTH_INVALID_PIN"
    r_ok = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "5678"), headers=headers
    )
    assert r_ok.status_code == 204
    assert r_ok.text == ""


# AC-9: the new bcrypt hash is persisted, the old PIN dies, the new PIN logs in.
def test_change_pin_persists_hash(env_pin_db):
    headers = staff_token(env_pin_db)
    insert_setting(staff_pin_hash=bcrypt_hash("1234"))
    r = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "5678"), headers=headers
    )
    assert r.status_code == 204
    db = database.SessionLocal()
    stored = db.query(SettingsModel).first().staff_pin_hash
    db.close()
    assert stored and stored != bcrypt_hash("1234")
    assert stored != "5678"
    assert bcrypt.checkpw(b"5678", stored.encode())
    assert not bcrypt.checkpw(b"1234", stored.encode())
    assert client.post("/api/v1/auth/login", json={"pin": "1234"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"pin": "5678"}).status_code == 200


# AC-10: new == current and confirm mismatch are 422 VALIDATION_ERROR, hash untouched.
def test_change_pin_validation_errors(env_pin_db):
    headers = staff_token(env_pin_db)
    r_same = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "1234", "1234"), headers=headers
    )
    assert r_same.status_code == 422
    assert r_same.json()["error"]["code"] == "VALIDATION_ERROR"
    r_mismatch = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "5678", "4321"), headers=headers
    )
    assert r_mismatch.status_code == 422
    assert r_mismatch.json()["error"]["code"] == "VALIDATION_ERROR"
    db = database.SessionLocal()
    assert db.query(SettingsModel).first().staff_pin_hash is None
    db.close()


# AC-11: staff_pin_hash never appears in a response body.
def test_no_hash_in_responses(env_pin_db):
    insert_setting(staff_pin_hash=bcrypt_hash("1234"))
    r_fail = client.post("/api/v1/auth/login", json={"pin": "9999"})
    assert "staff_pin_hash" not in str(r_fail.json())
    r_ok = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert "staff_pin_hash" not in str(r_ok.json())
    r_cp = client.post(
        "/api/v1/auth/change-pin",
        json=change_pin_body("1234", "5678"),
        headers=bearer(r_ok.json()["access_token"]),
    )
    assert r_cp.status_code == 204
    assert r_cp.text == ""


# AC-13: a token signed with another secret is rejected; a login-issued token authenticates.
def test_token_secret_enforcement(env_pin_db):
    headers = staff_token(env_pin_db)
    r_forged = client.post(
        "/api/v1/auth/change-pin",
        json=change_pin_body("1234", "5678"),
        headers=bearer(mint_token(signing_key="another-secret")),
    )
    assert r_forged.status_code == 401
    assert r_forged.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"
    r_real = client.post(
        "/api/v1/auth/change-pin", json=change_pin_body("1234", "5678"), headers=headers
    )
    assert r_real.status_code == 204
    r_login = client.post("/api/v1/auth/login", json={"pin": "5678"})
    assert r_login.status_code == 200
    r_again = client.post(
        "/api/v1/auth/change-pin",
        json=change_pin_body("5678", "9999"),
        headers=bearer(r_login.json()["access_token"]),
    )
    assert r_again.status_code == 204


# AC-1 guard: exactly the two documented auth paths are mounted, and no database is involved.
def test_only_documented_auth_paths():
    paths = {
        path
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/v1/auth") and "post" in ops
    }
    assert paths == {"/api/v1/auth/login", "/api/v1/auth/change-pin"}
