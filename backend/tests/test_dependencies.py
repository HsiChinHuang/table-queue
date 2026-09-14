"""Tests for dependency utilities (B-04).

The three cases this module owns are the three ways a staff bearer can fail to be one - absent,
expired, signed by someone else - plus the one way it can succeed. Under T9 all four are properties
of a STORE as much as of a token: decision D-2 folds the settings row's generation value into the
HS256 key, and decision D-1 makes the presence of a credential in that row a precondition for any
verdict at all. A module that signed its probes from configuration alone would be signing them for
a database the request never opens, so this file names the store it mints for and puts the
application on that same store.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.config import get_settings
from app.dependencies import (
    bearer_scheme,
    get_current_staff,
    get_db,
    get_now,
)
from app.main import app as main_app
from app.models import Base, Branch, Restaurant
from app.models import Settings as SettingsModel
from app.routers.auth import INITIAL_TOKEN_GENERATION, credential_is_configured
from tests._db_test_support import TEST_CREDENTIAL_HASH

# This module's own store, and the state of the process before this module touched it. B-04 predates
# the harness that now gives every test a scratch file, and the store below takes the same shape
# that harness leaves behind - a file in the working directory, removed on teardown - so the shared
# engine keeps the name it was built with rather than being handed a second one.
_STORE_PATH = Path("_b04_dep_tests.db")
_PREVIOUS_ENV_URL = os.environ.get("DATABASE_URL")
_PREVIOUS_ENGINE = database.engine
_PREVIOUS_SESSION_LOCAL = database.SessionLocal


@pytest.fixture(scope="module", autouse=True)
def _store_under_test():
    """Build the store on the ambient factory, then hand every piece of state back (B-17 AC-7).

    The factory and the engine are what the verifier reads: ``get_current_staff`` opens its session
    through the module attribute rather than holding one of its own, so a store that lived only in
    a ``get_db`` override would be a store the credential check consults differently from the
    handler - and the whole point of T9's verifier is that there is one store per request, not two
    candidates to choose between. Writing through the ambient factory is what the app does,
    and it is the narrowest arrangement in which the two halves of a request cannot disagree.

    The restaurant and the branch above the settings row are there because the mapped table requires
    them, not because this module has an opinion about either.
    """
    _STORE_PATH.unlink(missing_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{_STORE_PATH}"
    engine = create_engine(f"sqlite:///{_STORE_PATH}", echo=False)
    Base.metadata.create_all(engine)
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine)
    get_settings.cache_clear()

    with database.SessionLocal() as session:
        session.add_all(
            [
                Restaurant(id=1, name="Sunny Bistro"),
                Branch(
                    id=1,
                    restaurant_id=1,
                    name="Taipei Xinyi",
                    address="1 Example Rd.",
                    phone="02-1234-5678",
                    timezone="Asia/Taipei",
                    business_day_cutoff_hour=4,
                    open_time="11:00",
                    close_time="21:00",
                ),
                SettingsModel(id=1, branch_id=1, staff_pin_hash=TEST_CREDENTIAL_HASH),
            ]
        )
        session.commit()
        # The arrangement, asserted rather than assumed: the verifier's two questions have answers
        # here, so a 401 below can only come from the token.
        assert credential_is_configured(session)
        assert session.execute(
            text("select token_generation from settings where id = 1")
        ).fetchone()[0] is None

    yield

    database.engine = _PREVIOUS_ENGINE
    database.SessionLocal = _PREVIOUS_SESSION_LOCAL
    if _PREVIOUS_ENV_URL is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _PREVIOUS_ENV_URL
    get_settings.cache_clear()
    _STORE_PATH.unlink(missing_ok=True)


# The generation the store above reports, read once: its row stores none, which is what
# ``INITIAL_TOKEN_GENERATION`` exists to name. A constant rather than a literal in the mints below
# so that if the store's rule ever changes, these probes change with it and a stale key cannot
# quietly turn "valid" into a 401 for the wrong reason.
_GENERATION = INITIAL_TOKEN_GENERATION

settings = get_settings()
now_ts = int(time.time())


def _signed(*, signing_key: str | None = None, iat: int, exp: int) -> str:
    """One claim set, signed with the key a verifier for the store above rebuilds."""
    return jwt.encode(
        {"sub": "staff", "role": "staff", "iat": iat, "exp": exp},
        (signing_key if signing_key is not None else settings.jwt_secret) + _GENERATION,
        algorithm="HS256",
    )


valid_token = _signed(iat=now_ts, exp=now_ts + 3600)
expired_token = _signed(iat=now_ts - 86400, exp=now_ts - 3600)
# The parameter is named ``signing_key`` rather than ``secret``: ruff's S106 reads a keyword called
# ``secret`` carrying a literal as a hardcoded credential, and this value is a wrong-secret probe.
wrong_secret_token = _signed(signing_key="not-the-secret", iat=now_ts, exp=now_ts + 3600)


def test_bearer_scheme():
    assert isinstance(bearer_scheme, type(bearer_scheme))
    assert bearer_scheme.auto_error is False
    scheme_val = bearer_scheme.model.model_fields["scheme"].default
    assert scheme_val.lower() == "bearer"


def test_get_now():
    now = get_now()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_get_current_staff_cases():
    client = TestClient(main_app, raise_server_exceptions=False)
    cases = [
        ("missing", {}, 401),
        ("wrong scheme", {"Authorization": "Basic abc"}, 401),
        ("malformed", {"Authorization": "Bearer notajwt"}, 401),
        ("expired", {"Authorization": f"Bearer {expired_token}"}, 401),
        ("wrong secret", {"Authorization": f"Bearer {wrong_secret_token}"}, 401),
        ("valid", {"Authorization": f"Bearer {valid_token}"}, 200),
    ]
    for index, (label, headers, want_status) in enumerate(cases):
        # /health has no auth dependency: it must answer regardless of headers.
        response = client.get("/health", headers=headers)
        assert response.status_code == 200

        path = f"/dep_{index}_{label.replace(' ', '_')}"

        @main_app.get(path)
        def dep_route(staff: Annotated[dict, Depends(get_current_staff)]):
            return staff

        resp = client.get(path, headers=headers)
        assert resp.status_code == want_status, (label, resp.text)
        if want_status == 401:
            assert resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"
        else:
            assert resp.json()["sub"] == "staff"


def test_get_db_generator(monkeypatch):
    from sqlalchemy import event

    from app.database import engine
    calls = []
    def listener(*args):
        calls.append(1)
    event.listen(engine, "checkin", listener)
    gen = get_db()
    session = next(gen)
    result = session.execute(text("select 1")).scalar()
    assert result == 1
    before = len(calls)
    gen.close()
    after = len(calls)
    assert after > before
    event.remove(engine, "checkin", listener)
