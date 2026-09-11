"""Admin tables endpoint tests for B-11 (``/api/v1/admin/tables``).

The seven behaviours ``_docs/testing.md`` names for B-11, plus the error-shape case AC-12
names:

``test_create_table_success``, ``test_create_table_duplicate_label``,
``test_update_table_success``, ``test_update_table_duplicate_label``,
``test_delete_table_soft``, ``test_delete_table_occupied_conflict`` and
``test_list_admin_tables_include_inactive`` - the three owner-stub bullets a happy-path-only
file can silently skip being ``include_inactive``'s two truth values, the duplicate-label
409 and the occupied-delete 409.

Ownership, because ``_docs/testing.md`` forbids shared state and a B-06 QA finding proved the
hazard: this module owns its engine and its ``get_db`` override, and it restores the override
and the limiter flag on teardown. It never writes to ``app.database.engine``, never calls
``os.environ.setdefault`` and never imports ``tests.public_fixtures`` (whose import side
effects point the shared engine at a ``/tmp`` file and leave it there for whichever test runs
next). Two consequences:

* **Pollution-proof** - every row these tests write goes to a file under ``tmp_path`` that
  ``pytest`` removes, on an engine no other module holds a reference to.
* **Pollution-survivable** - ``conftest.py``'s env bootstrap resolves the shared engine at
  import time, which makes ``monkeypatch.setenv(DATABASE_URL)`` a no-op for the app, so the
  ``get_db`` override is what isolates these tests. It is installed before the ``TestClient``
  is built and removed afterwards, along with ``limiter.enabled``.

Auth reuses the shipped ``Staff`` dependency: the token below is signed with the
``JWT_SECRET`` the environment carries - the claim shape ``app/routers/auth.py`` issues - so
the 401 and 200 answers come from the product rather than from a stub.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, limiter
from app.models import Branch, Restaurant, Table, TableStatus
from app.models import Settings as SettingsRow

TABLES = "/api/v1/admin/tables"

TABLE_KEYS = {
    "id",
    "label",
    "capacity",
    "section",
    "sort_order",
    "status",
    "is_active",
    "current_waitlist",
}
"""The eight ``TableResponse`` fields AC-3 pins."""

SCRATCH_LIMIT = 200
"""How often the scratch directory name is regenerated.

One name per test, so two tests can never share a database file even when they run inside the
same session, and so a stale file from an interrupted run is never reused: the number only
ever counts up, and the file is created fresh under it.
"""


@pytest.fixture()
def db(engine, request):
    """A session on this test's own schema, with no row from any other test in it.

    The database is a file under ``tmp_path`` rather than a bare ``sqlite:///:memory:`` URL
    because the application opens its own connection per request, and a memory URL gives
    every connection its own empty database - a row seeded here would be invisible to the
    request that has to read it. ``check_same_thread=False`` is the same SQLite concession
    ``app/database.py`` makes, since a ``TestClient`` request runs on a worker thread.
    """
    del request  # fixture ordering only: the engine below is already per test
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def engine(tmp_path, request):
    """A fresh SQLite engine the test owns outright, schema and all."""
    global _SCRATCH_COUNT
    del request
    _SCRATCH_COUNT += 1
    dbfile = tmp_path / f"b11_{_SCRATCH_COUNT}.db"
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


_SCRATCH_COUNT = 0
"""Monotonic counter behind each test's database file name (see :data:`SCRATCH_LIMIT`)."""


@pytest.fixture()
def client(db):
    """A client whose ``get_db`` is this test's session, limiter disabled first.

    The AC-14 discipline learned on B-06: ``limiter.enabled`` goes to ``False`` BEFORE the
    ``TestClient`` is constructed and is restored afterwards, so no test leaves the shared
    process limiter mute for the rest of the suite. The override is popped on the way out, so
    no test leaves the application reading someone else's session.
    """
    previous_enabled = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)
        limiter.enabled = previous_enabled


def staff_headers() -> dict[str, str]:
    """A valid staff bearer: the env's own secret, the auth router's own claim shape."""
    now = int(time.time())
    token = jwt.encode(
        {"sub": "staff", "role": "staff", "iat": now, "exp": now + 3600},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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
            staff_pin_hash=None,
        )
    )
    db.commit()


def seed_table(db, label: str, **kwargs) -> Table:
    """Add one table of the default branch and return the row."""
    row = Table(
        branch_id=kwargs.pop("branch_id", 1),
        label=label,
        capacity=kwargs.pop("capacity", 2),
        section=kwargs.pop("section", None),
        sort_order=kwargs.pop("sort_order", 100),
        status=kwargs.pop("status", TableStatus.AVAILABLE),
        is_active=kwargs.pop("is_active", True),
    )
    db.add(row)
    db.commit()
    return row


def labels(payload: dict) -> set[str]:
    """The labels a list response carries."""
    return {item["label"] for item in payload["items"]}


def test_create_table_success(db, client):
    """A create answers 201 with the eight contract fields and really lands the row."""
    seed_branch(db)
    res = client.post(
        TABLES,
        headers=staff_headers(),
        json={"label": "A5", "capacity": 2, "section": "Patio", "sort_order": 5000},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert set(body) == TABLE_KEYS
    assert body["label"] == "A5"
    assert body["capacity"] == 2
    assert body["section"] == "Patio"
    assert body["sort_order"] == 5000
    # Neither `status` nor `is_active` is a request field: a new table seats nobody.
    assert body["status"] == "AVAILABLE"
    assert body["is_active"] is True
    db.expire_all()
    stored = db.query(Table).filter(Table.label == "A5").one()
    assert (stored.branch_id, stored.capacity, stored.sort_order) == (1, 2, 5000)


def test_create_table_duplicate_label(db, client):
    """A duplicate label is 409 CONFLICT, active holder or soft-deleted holder alike.

    The second half is R-B11-2: ``uq_branch_label`` carries no ``is_active`` predicate, so the
    label of a hidden row is still taken, and the ``IntegrityError`` has to reach the client as
    a 409 rather than as the 500 handler.
    """
    seed_branch(db)
    seed_table(db, "A1")
    seed_table(db, "GONE", is_active=False)
    headers = staff_headers()
    for label in ("A1", "GONE"):
        res = client.post(TABLES, headers=headers, json={"label": label, "capacity": 4})
        assert res.status_code == 409, f"{label}: {res.status_code} {res.text}"
        body = res.json()
        assert "detail" not in body
        assert body["error"]["code"] == "CONFLICT"
        assert body["error"]["message"]
    assert db.query(Table).count() == 2  # a rejected POST writes nothing


def test_update_table_success(db, client):
    """PATCH writes the fields it carries, echoes them, and persists them."""
    seed_branch(db)
    row = seed_table(db, "A1", capacity=2, sort_order=100)
    res = client.patch(
        f"{TABLES}/{row.id}",
        headers=staff_headers(),
        json={"label": "B7", "capacity": 6, "section": "Hall", "sort_order": 7},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == TABLE_KEYS
    assert (body["label"], body["capacity"], body["section"], body["sort_order"]) == (
        "B7",
        6,
        "Hall",
        7,
    )
    db.expire_all()
    stored = db.query(Table).filter(Table.id == row.id).one()
    assert (stored.label, stored.capacity, stored.section, stored.sort_order) == (
        "B7",
        6,
        "Hall",
        7,
    )


def test_update_table_duplicate_label(db, client):
    """A rename onto a label another visible row holds is 409 and writes neither row."""
    seed_branch(db)
    keep = seed_table(db, "KEEP")
    seed_table(db, "TAKE")
    res = client.patch(f"{TABLES}/{keep.id}", headers=staff_headers(), json={"label": "TAKE"})
    assert res.status_code == 409, res.text
    body = res.json()
    assert "detail" not in body
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["message"]
    db.expire_all()
    assert db.query(Table).filter(Table.label == "KEEP").one().id == keep.id
    assert db.query(Table).filter(Table.label == "TAKE").one().capacity == 2


def test_delete_table_soft(db, client):
    """DELETE is a 204 with no body and an is_active flip that keeps the row (R-B11-1, -3)."""
    seed_branch(db)
    row = seed_table(db, "FREE1", section="Hall", sort_order=100)
    res = client.delete(f"{TABLES}/{row.id}", headers=staff_headers())
    assert res.status_code == 204, res.text
    assert res.text == ""  # the contract declares no content: no DeletionResponse body
    db.expire_all()
    stored = db.query(Table).filter(Table.id == row.id).one()
    assert stored.is_active is False
    assert stored.label == "FREE1"
    assert stored.status == TableStatus.AVAILABLE
    # The row leaves the default list and stays observable as inactive.
    headers = staff_headers()
    assert "FREE1" not in labels(client.get(TABLES, headers=headers).json())
    hidden = client.get(f"{TABLES}?include_inactive=true", headers=headers).json()
    assert "FREE1" in labels(hidden)
    assert {i["label"]: i["is_active"] for i in hidden["items"]}["FREE1"] is False


def test_delete_table_occupied_conflict(db, client):
    """An OCCUPIED table cannot be retired: 409 CONFLICT, row untouched, still listed."""
    seed_branch(db)
    row = seed_table(
        db, "BUSY1", capacity=4, section="Hall", sort_order=200, status=TableStatus.OCCUPIED
    )
    res = client.delete(f"{TABLES}/{row.id}", headers=staff_headers())
    assert res.status_code == 409, res.text
    body = res.json()
    assert "detail" not in body
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["message"]
    db.expire_all()
    stored = db.query(Table).filter(Table.id == row.id).one()
    assert stored.is_active is True
    assert stored.status == TableStatus.OCCUPIED
    assert (stored.capacity, stored.section, stored.sort_order) == (4, "Hall", 200)
    assert "BUSY1" in labels(client.get(TABLES, headers=staff_headers()).json())


def test_list_admin_tables_include_inactive(db, client):
    """include_inactive is the only filter, and total is the count of what came back."""
    seed_branch(db)
    seed_table(db, "ACT1", sort_order=100)
    seed_table(db, "HID1", sort_order=200, is_active=False)
    headers = staff_headers()
    default = client.get(TABLES, headers=headers)
    assert default.status_code == 200, default.text
    visible = default.json()
    assert labels(visible) == {"ACT1"}
    assert visible["total"] == len(visible["items"])
    everything = client.get(f"{TABLES}?include_inactive=true", headers=headers).json()
    assert labels(everything) == {"ACT1", "HID1"}
    assert everything["total"] == len(everything["items"])
    assert {i["label"]: i["is_active"] for i in everything["items"]} == {
        "ACT1": True,
        "HID1": False,
    }
    for item in everything["items"]:
        assert set(item) == TABLE_KEYS


def test_admin_errors_never_leak_the_fastapi_detail_shape(client):
    """AC-12's shape rule: every 4xx a client can produce on this surface is the envelope.

    An unauthenticated request, an id with no row, a malformed UUID path parameter and a
    malformed body are all 4xx in the envelope rather than a 500 with a ``detail`` key, and
    none of them writes anything. The branch seed is deliberately absent: the AC-12 probe runs
    these same requests against an empty schema, and that is the arrangement in which a 401
    (which never reaches the database) is guaranteed rather than assumed.
    """
    missing = str(uuid.uuid4())
    headers = staff_headers()

    def post(body: dict):
        return client.post(TABLES, headers=headers, json=body)

    cases = [
        ("GET unauthenticated", client.get(TABLES)),
        ("POST unauthenticated", client.post(TABLES, json={"label": "A1", "capacity": 2})),
        ("PATCH unauthenticated", client.patch(f"{TABLES}/{missing}", json={"capacity": 3})),
        ("DELETE unauthenticated", client.delete(f"{TABLES}/{missing}")),
        (
            "PATCH malformed uuid",
            client.patch(f"{TABLES}/not-a-uuid", headers=headers, json={"capacity": 3}),
        ),
        ("DELETE malformed uuid", client.delete(f"{TABLES}/not-a-uuid", headers=headers)),
        (
            "PATCH unknown id",
            client.patch(f"{TABLES}/{missing}", headers=headers, json={"capacity": 3}),
        ),
        ("DELETE unknown id", client.delete(f"{TABLES}/{missing}", headers=headers)),
        ("POST empty body", post({})),
        ("POST string capacity", post({"label": "S1", "capacity": "two"})),
        ("POST empty label", post({"label": "", "capacity": 2})),
        ("POST capacity 21", post({"label": "S2", "capacity": 21})),
    ]
    for tag, res in cases:
        assert 400 <= res.status_code < 500, f"{tag}: {res.status_code} {res.text}"
        body = res.json()
        assert "detail" not in body, f"{tag}: {body}"
        assert body["error"]["code"], tag
        assert body["error"]["message"], tag
    codes = {res.status_code for _, res in cases}
    assert codes == {401, 404, 422}, sorted(codes)  # the three shapes these can ask for
    assert {tag: res.status_code for tag, res in cases}["POST capacity 21"] == 422
