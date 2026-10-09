"""Integer and length bounds at the request boundary (t29 / Platform #84).

Regression tests for the audit overflow class: no overflow-500 on unauthenticated path
params, no out-of-domain value persisted through the table schemas, and the service-layer
``_reject_int`` retained as a range guard rather than an ``isinstance`` check.

The six behaviours the AC set pins:

- AC-1 - the table request schemas carry explicit ``ge``/``le`` (and ``min``/``max_length``).
- AC-2 - a ``sort_order`` beyond SQLite INTEGER max is 422 on create and update, naming the
  field, never a 500.
- AC-3 - a negative ``limit``/``offset`` on the staff waitlist list route is 422, never a 200.
- AC-4 - an out-of-domain ``branch_id`` on the unauthenticated public branch routes is 422,
  never a 500 ``OverflowError``.
- AC-5 - ``sort_order`` at SQLite INTEGER max and ``capacity`` at its domain max still create.
- AC-6 - ``app.services.tables._reject_int`` range-checks and answers 422.

Ownership follows the shipped discipline in ``test_admin_tables.py``: this module owns its engine
and ``get_db`` override, and restores both (and the limiter flag) on teardown. Auth reuses the
shipped ``Staff`` dependency, minted against the store the request will read.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.errors import AppError
from app.main import app, limiter
from app.models import Branch, Restaurant
from app.models import Settings as SettingsRow
from app.schemas import CreateTableRequest, UpdateTableRequest
from app.services.tables import _reject_int
from tests._db_test_support import (
    TEST_CREDENTIAL_HASH,
)
from tests._db_test_support import (
    staff_headers as _staff_headers,
)

TABLES = "/api/v1/admin/tables"
WAITLIST = "/api/v1/staff/waitlist"
PUBLIC_BRANCH = "/api/v1/public/branches/{branch_id}"
PUBLIC_BOARD = "/api/v1/public/branches/{branch_id}/board"
JOIN = "/api/v1/branches/{branch_id}/waitlist"

SQLITE_INT_MAX = 9223372036854775807
SQLITE_INT_OVERFLOW = 9223372036854775808
OUT_OF_DOMAIN_BRANCH = "99999999999999999999"


@pytest.fixture()
def engine(tmp_path):
    """A fresh SQLite engine the test owns outright, schema and all."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 't29.db'}",
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
    """A client whose ``get_db`` is this test's session, limiter disabled first."""
    previous_enabled = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[get_db] = lambda: db
    global _SCRATCH_SESSION  # noqa: PLW0603 - the mint below reads the session this fixture owns
    _SCRATCH_SESSION = db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        _SCRATCH_SESSION = None
        app.dependency_overrides.pop(get_db, None)
        limiter.enabled = previous_enabled


_SCRATCH_SESSION = None
"""The session the running test owns, recorded by the ``client`` fixture and read by the mint."""


def staff_headers() -> dict[str, str]:
    """A valid staff bearer, minted against the store the running request will read."""
    if _SCRATCH_SESSION is not None:
        return _staff_headers(role="staff", session=_SCRATCH_SESSION)
    return _staff_headers(role="staff")


def seed_branch(db) -> None:
    """Seed the restaurant, branch and settings row the admin and staff surfaces read."""
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
            staff_pin_hash=TEST_CREDENTIAL_HASH,
        )
    )
    db.commit()


def _constraints(node) -> dict:
    """Collect every ``minimum``/``maximum``/``minLength``/``maxLength`` under a schema node.

    Optional fields may carry their constraints inside an ``anyOf`` branch, so the walk is
    recursive rather than a single ``get``.
    """
    out: dict = {}

    def rec(x) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("minimum", "maximum", "minLength", "maxLength"):
                    out[k] = v
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)

    rec(node)
    return out


# --- AC-1: the table request schemas carry explicit bounds ---------------------


def test_create_sort_order_bounded_to_sqlite_int():
    """CreateTableRequest.sort_order declares both a lower and an upper bound."""
    cs = _constraints(CreateTableRequest.model_json_schema()["properties"]["sort_order"])
    assert "minimum" in cs, f"CreateTableRequest.sort_order missing minimum: {cs}"
    assert "maximum" in cs, f"CreateTableRequest.sort_order missing maximum: {cs}"
    assert cs["maximum"] == SQLITE_INT_MAX


def test_update_sort_order_bounded_to_sqlite_int():
    """UpdateTableRequest.sort_order declares both a lower and an upper bound."""
    us = _constraints(UpdateTableRequest.model_json_schema()["properties"]["sort_order"])
    assert "minimum" in us, f"UpdateTableRequest.sort_order missing minimum: {us}"
    assert "maximum" in us, f"UpdateTableRequest.sort_order missing maximum: {us}"
    assert us["maximum"] == SQLITE_INT_MAX


def test_update_capacity_matches_create():
    """UpdateTableRequest.capacity declares ge=1 le=20, matching CreateTableRequest."""
    uc = _constraints(UpdateTableRequest.model_json_schema()["properties"]["capacity"])
    assert uc.get("minimum") == 1, f"UpdateTableRequest.capacity minimum: {uc}"
    assert uc.get("maximum") == 20, f"UpdateTableRequest.capacity maximum: {uc}"


def test_update_label_matches_create():
    """UpdateTableRequest.label declares min_length=1 max_length=10, matching create."""
    ul = _constraints(UpdateTableRequest.model_json_schema()["properties"]["label"])
    assert ul.get("minLength") == 1, f"UpdateTableRequest.label minLength: {ul}"
    assert ul.get("maxLength") == 10, f"UpdateTableRequest.label maxLength: {ul}"


# --- AC-2: sort_order overflow is 422, not 500 --------------------------------


def test_create_sort_order_overflow_is_422_naming_field(db, client):
    """A create with a sort_order beyond SQLite INTEGER max is 422 naming sort_order."""
    seed_branch(db)
    res = client.post(
        TABLES,
        headers=staff_headers(),
        json={"label": "T1", "capacity": 2, "sort_order": SQLITE_INT_OVERFLOW},
    )
    assert res.status_code == 422, res.text
    fields = (res.json().get("error", {}).get("details", {}).get("fields", {}) or {})
    assert "sort_order" in fields, res.text


def test_update_sort_order_overflow_is_422_naming_field(db, client):
    """A PATCH with a sort_order beyond SQLite INTEGER max is 422 naming sort_order."""
    seed_branch(db)
    created = client.post(
        TABLES, headers=staff_headers(), json={"label": "T9", "capacity": 2}
    ).json()
    res = client.patch(
        f"{TABLES}/{created['id']}",
        headers=staff_headers(),
        json={"sort_order": SQLITE_INT_OVERFLOW},
    )
    assert res.status_code == 422, res.text
    fields = (res.json().get("error", {}).get("details", {}).get("fields", {}) or {})
    assert "sort_order" in fields, res.text


# --- AC-3: negative limit/offset is 422, not 200 ------------------------------


def test_negative_limit_is_422(db, client):
    """A negative limit on the staff waitlist list route is 422, never a 200."""
    seed_branch(db)
    res = client.get(f"{WAITLIST}?limit=-1", headers=staff_headers())
    assert res.status_code == 422, res.text


def test_negative_offset_is_422(db, client):
    """A negative offset on the staff waitlist list route is 422, never a 200."""
    seed_branch(db)
    res = client.get(f"{WAITLIST}?offset=-5", headers=staff_headers())
    assert res.status_code == 422, res.text


# --- AC-4: unauth branch_id overflow is 422, not 500 --------------------------


def test_public_branch_id_overflow_is_422(db, client):
    """An out-of-domain branch_id on the unauth public branch route is 422, not a 500."""
    seed_branch(db)
    res = client.get(PUBLIC_BRANCH.format(branch_id=OUT_OF_DOMAIN_BRANCH))
    assert res.status_code == 422, res.text


def test_public_board_branch_id_overflow_is_422(db, client):
    """An out-of-domain branch_id on the unauth public board route is 422, not a 500."""
    seed_branch(db)
    res = client.get(PUBLIC_BOARD.format(branch_id=OUT_OF_DOMAIN_BRANCH))
    assert res.status_code == 422, res.text


def test_unauth_join_branch_id_overflow_is_422(db, client):
    """An out-of-domain branch_id on the unauth join route is 422, not a 500."""
    seed_branch(db)
    res = client.post(
        JOIN.format(branch_id=OUT_OF_DOMAIN_BRANCH),
        json={"name": "G", "phone": "0912345678", "party_size": 2},
    )
    assert res.status_code == 422, res.text


# --- AC-5: bounds sized to SQLite INTEGER and domain, not over-tightened ------


def test_sqlite_max_sort_order_and_capacity_max_create(db, client):
    """sort_order at SQLite INTEGER max and capacity at its domain max both create (201)."""
    seed_branch(db)
    r1 = client.post(
        TABLES,
        headers=staff_headers(),
        json={"label": "M1", "capacity": 2, "sort_order": SQLITE_INT_MAX},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(TABLES, headers=staff_headers(), json={"label": "M2", "capacity": 20})
    assert r2.status_code == 201, r2.text


# --- AC-6: _reject_int is a range guard, not just isinstance ------------------


def test_reject_int_overflow_raises_422():
    """_reject_int with a value beyond SQLite INTEGER max raises AppError 422."""
    with pytest.raises(AppError) as exc:
        _reject_int(SQLITE_INT_OVERFLOW)
    assert exc.value.status_code == 422


def test_reject_int_in_range_passes():
    """_reject_int with an in-range value does not raise and reports it was not rejected."""
    assert _reject_int(0) is True
    assert _reject_int(SQLITE_INT_MAX) is True
