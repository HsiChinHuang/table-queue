"""T18: router-level refusals and the service capacity reject answer the contract envelope.

The two TestClient cases the issue names:

* AC-1 - a path the router does not serve (made-up ``/api/v1/...`` prefixes, including a
  traversal-style path that arrives as an unmatched prefix) answers 404 in the envelope,
  and a method the router does not allow on a mounted path (``DELETE /health``) answers
  405 in the envelope - both produced by the application's own error layer, with no
  framework ``detail`` key anywhere.
* AC-3 - the service-level capacity reject (``PATCH /api/v1/admin/tables/{id}`` with
  ``capacity`` 21 and 0, the values the PATCH schema admits) answers 422 VALIDATION_ERROR
  carrying ``details.fields`` naming ``capacity``, and the schema-level create reject
  (``POST /api/v1/admin/tables`` with ``capacity`` 21) carries the same shape.

Ownership follows ``test_admin_tables.py``: this module owns its engine and its
``get_db`` override, and it restores the override and the limiter flag on teardown. It
never imports ``tests.public_fixtures`` (whose import side effects point the shared
engine at a ``/tmp`` file) and never writes to ``app.database.engine``.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_error_envelope_t18.db")
os.environ.setdefault("JWT_SECRET", "tq-test-jwt-secret-t18-0123456789abcdef")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

if os.sep == "/":  # WSL: the Windows drive is not writable by the venv's platform check
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app, limiter  # noqa: E402
from app.models import Branch, Restaurant  # noqa: E402
from app.models import Settings as SettingsRow  # noqa: E402
from tests._db_test_support import TEST_CREDENTIAL_HASH  # noqa: E402
from tests._db_test_support import (  # noqa: E402
    staff_headers as _staff_headers,
)

TABLES = "/api/v1/admin/tables"

_scratch_count = 0
"""Monotonic counter behind each test's database file name: one file per test, so two
tests can never share a database even inside the same session."""

_scratch_session = None
"""The session the running test owns, recorded by the ``client`` fixture, read by the mint below."""


@pytest.fixture()
def engine(tmp_path):
    """A fresh SQLite engine the test owns outright, schema and all."""
    global _scratch_count
    _scratch_count += 1
    dbfile = tmp_path / f"t18_{_scratch_count}.db"
    test_engine = create_engine(
        f"sqlite:///{dbfile}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture()
def db(engine):
    """A session on this test's own schema, with no row from any other test in it."""
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """A client whose ``get_db`` is this test's session, limiter disabled first.

    The B-06 discipline: ``limiter.enabled`` goes to ``False`` before the ``TestClient``
    is constructed and is restored afterwards, and the override is popped on the way out,
    so no test leaves the application reading someone else's session.
    """
    global _scratch_session  # noqa: PLW0603 - the mint below reads the session this fixture owns
    previous_enabled = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[get_db] = lambda: db
    _scratch_session = db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        _scratch_session = None
        app.dependency_overrides.pop(get_db, None)
        limiter.enabled = previous_enabled


def staff_headers() -> dict[str, str]:
    """A valid staff bearer, minted against the store the running request will read."""
    assert _scratch_session is not None, "staff_headers minted outside a client fixture"
    return _staff_headers(role="staff", session=_scratch_session)


def seed_branch(db) -> None:
    """Seed the restaurant, branch and settings row the admin surface reads."""
    db.add(Restaurant(id=1, name="R"))
    db.add(
        Branch(
            id=1,
            restaurant_id=1,
            name="B",
            address="a",
            phone="p",
            timezone="Asia/Taipei",
            business_day_cutoff_hour=4,
            open_time="11:00",
            close_time="21:00",
        )
    )
    db.add(
        SettingsRow(
            branch_id=1,
            hold_minutes=10,
            avg_seat_minutes=15,
            queue_prefix="A",
            is_waitlist_open=True,
            sound_enabled_default=True,
            notification_templates="{}",
            # T9 (D-1 fail-closed, AC-1): the verifier refuses a store with no credential at all,
            # so the seed row carries one. Minting a bearer reads that same row.
            staff_pin_hash=TEST_CREDENTIAL_HASH,
        )
    )
    db.commit()


def _envelope_problems(resp, want_status: int) -> list[str]:
    """Return the reasons ``resp`` is not the contract envelope for ``want_status``.

    An empty list is the pass. The checks are the AC's own: the status is the one asked
    for, the body is JSON whose top level is exactly the ``error`` key, ``code`` and
    ``message`` are non-empty strings, ``details`` is an object when present, and no
    framework ``detail`` key appears at the top level or inside ``error``.
    """
    if resp.status_code != want_status:
        return [f"status is {resp.status_code}, want {want_status}"]
    try:
        body = resp.json()
    except ValueError:
        return ["the body is not JSON"]
    if not isinstance(body, dict) or set(body) != {"error"}:
        keys = sorted(body) if isinstance(body, dict) else type(body).__name__
        return [f"the top level carries {keys!r}, want exactly ['error']"]
    error = body["error"]
    if not isinstance(error, dict):
        return ["error is not an object"]
    if "detail" in body or "detail" in error:
        return ["a 'detail' key (framework default shape) leaked through"]
    if not isinstance(error.get("code"), str) or not error["code"]:
        return ["error.code is missing or not a non-empty string"]
    if not isinstance(error.get("message"), str) or not error["message"]:
        return ["error.message is missing or not a non-empty string"]
    if "details" in error and not isinstance(error["details"], dict):
        return ["error.details is present but is not an object"]
    return []


def test_router_level_404_answers_the_contract_envelope(client) -> None:
    """AC-1: any path the router does not serve answers 404 in the contract envelope.

    Three shapes of "no route here": a made-up ``/api/v1`` prefix, a traversal-style
    path that arrives at the router as an unmatched prefix, and a path outside the API
    prefix entirely. None of them may answer the framework-default ``detail`` body.
    """
    for path in ("/api/v1/definitely-not-a-route", "/api/v1/../../etc/passwd", "/nope"):
        resp = client.get(path)
        problems = _envelope_problems(resp, 404)
        assert problems == [], f"GET {path}: the envelope is not the contract's: {problems}"


def test_router_level_405_answers_the_contract_envelope(client) -> None:
    """AC-1: a method the router does not allow on a mounted path answers 405 in the envelope.

    ``/health`` serves GET only; DELETE is the refusal. The ``Allow`` header the router
    sets is not the contract's concern, but the body is: it must be the envelope, not the
    framework-default ``{"detail": "Method Not Allowed"}``.
    """
    resp = client.delete("/health")
    problems = _envelope_problems(resp, 405)
    assert problems == [], f"DELETE /health: the envelope is not the contract's: {problems}"


def test_service_capacity_reject_names_the_field_in_details_fields(client, db) -> None:
    """AC-3: the service capacity-reject 422 carries details.fields naming ``capacity``.

    ``UpdateTableRequest.capacity`` declares no bounds (t29 owns moving them into the
    schema), so ``capacity`` 21 and 0 pass the schema and land in the service's
    ``_reject_capacity``. Both answers are 422 VALIDATION_ERROR whose ``details.fields``
    is a non-empty ``field -> message`` map whose key set is exactly ``{"capacity"}`` -
    the same shape the schema-level reject carries, which the parity arm below re-checks.
    """
    seed_branch(db)
    headers = staff_headers()
    created = client.post(TABLES, headers=headers, json={"label": "T18", "capacity": 4})
    assert created.status_code == 201, created.text
    table_id = created.json()["id"]

    for bad in (21, 0):
        resp = client.patch(f"{TABLES}/{table_id}", headers=headers, json={"capacity": bad})
        assert resp.status_code == 422, f"capacity={bad}: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "detail" not in body, f"capacity={bad}: {body}"
        error = body["error"]
        assert error["code"] == "VALIDATION_ERROR", f"capacity={bad}: {error}"
        fields = error.get("details", {}).get("fields")
        assert isinstance(fields, dict), f"capacity={bad}: no details.fields map: {error}"
        assert set(fields) == {"capacity"}, f"capacity={bad}: keys are {sorted(fields)}"
        assert all(
            isinstance(message, str) and message for message in fields.values()
        ), f"capacity={bad}: non-empty string messages required: {fields}"


def test_schema_level_create_reject_keeps_the_same_shape(client, db) -> None:
    """AC-3 parity arm: the schema-level create reject still carries details.fields."""
    seed_branch(db)
    headers = staff_headers()
    resp = client.post(TABLES, headers=headers, json={"label": "T18B", "capacity": 21})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" not in body, body
    error = body["error"]
    assert error["code"] == "VALIDATION_ERROR", error
    fields = error.get("details", {}).get("fields")
    assert isinstance(fields, dict) and "capacity" in fields, f"parity broken: {error}"
