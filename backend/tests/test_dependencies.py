"""Tests for dependency utilities (B-04)."""

import time
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt

from app.config import get_settings
from app.dependencies import (
    bearer_scheme,
    get_current_staff,
    get_db,
    get_now,
)
from app.main import app as main_app

settings = get_settings()
now_ts = int(time.time())
valid_token = jwt.encode(
    {"sub": "staff", "role": "staff", "iat": now_ts, "exp": now_ts + 3600},
    settings.jwt_secret,
    algorithm="HS256",
)
expired_token = jwt.encode(
    {"sub": "staff", "role": "staff", "iat": now_ts - 86400, "exp": now_ts - 3600},
    settings.jwt_secret,
    algorithm="HS256",
)
wrong_secret_token = jwt.encode(
    {"sub": "staff", "role": "staff", "iat": now_ts, "exp": now_ts + 3600},
    "not-the-secret",
    algorithm="HS256",
)


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
        assert resp.status_code == want_status
        if want_status == 401:
            assert resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"
        else:
            assert resp.json()["sub"] == "staff"



def test_get_db_generator(monkeypatch):
    from sqlalchemy import event, text

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
