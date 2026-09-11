"""Staff table endpoint tests (issue B-08).

Test names come from ``_docs/testing.md`` section 2 (Staff Tables). The file is deliberately
pollution-proof and pollution-survivable:

- It owns a file-scoped SQLite database and binds ``app.database.SessionLocal`` to it for the
  whole module, restoring the original factory in teardown. QA's B-06 finding is that
  ``tests/test_auth.py`` leaks ``DATABASE_URL`` / the engine, so relying on the ambient engine
  would make a whole-suite run depend on collection order.
- The shared limiter is disabled *before* the module-level ``TestClient`` is built, so a whole-suite
  run cannot turn these calls into 429s.
- Time is frozen with ``freezegun`` at the ``_docs/testing.md`` instant; no assertion reads
  wall clock.

Each test seeds its own rows and clears the two tables it touches, so order does not matter.
"""

from __future__ import annotations

import os
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./_b08_test.db")
os.environ.setdefault("STAFF_PIN", "0000")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("JWT_EXPIRE_HOURS", "12")
os.environ.setdefault("ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from freezegun import freeze_time  # noqa: E402
from jose import jwt  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.database as app_database  # noqa: E402
from app.main import (
    app,  # noqa: E402
    limiter,  # noqa: E402  # the one shared process limiter
)

warnings.filterwarnings("ignore")  # SQLAlchemy bcrypt-free probes emit deprecation noise

from app.models import (  # noqa: E402
    Base,
    Branch,
    Restaurant,
    Settings,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistStatus,
)

# ---------------------------------------------------------------------------
# Isolated database: bound to SessionLocal for this module, restored afterwards.
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent / "_b08_test.db"

test_engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
# The limiter must be off before TestClient is constructed below (B-06 QA finding).
limiter.enabled = False

client = TestClient(app, raise_server_exceptions=False)

FROZEN = "2026-09-10 13:00:00"
FROZEN_DT = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)


def _staff_token() -> str:
    return jwt.encode(
        {"sub": "staff", "role": "staff", "iat": 1, "exp": 9999999999},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


@pytest.fixture(scope="module", autouse=True)
def isolated_database():
    """Point ``app.database.SessionLocal`` at this file's own database, then restore it."""
    original = app_database.SessionLocal
    app_database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    Base.metadata.create_all(bind=test_engine)
    session = app_database.SessionLocal()
    _seed_branch(session)
    session.close()
    try:
        yield
    finally:
        app_database.SessionLocal = original
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        limiter.enabled = False
        if DB_PATH.exists():
            DB_PATH.unlink()


def _seed_branch(session) -> None:
    """Create the single restaurant / branch / settings row the app expects."""
    if session.query(Branch).first() is None:
        session.add(Restaurant(id=1, name="Sunny Bistro"))
        session.add(
            Branch(
                id=1,
                restaurant_id=1,
                name="Taipei Xinyi",
                address="No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
                phone="02-1234-5678",
                timezone="Asia/Taipei",
                business_day_cutoff_hour=4,
                open_time="11:00",
                close_time="21:00",
            )
        )
        session.add(
            Settings(
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
        session.commit()


def _clear(session) -> None:
    """Drop every waitlist row and every table so each test starts from a known state."""
    session.query(WaitlistEntry).delete()
    session.query(Table).delete()
    session.commit()


def _make_table(
    session, label, status, sort_order, capacity=2, is_active=True, section="Main Hall"
):
    row = Table(
        branch_id=1,
        label=label,
        capacity=capacity,
        section=section,
        sort_order=sort_order,
        status=status,
        is_active=is_active,
    )
    session.add(row)
    session.commit()
    return row


def _make_entry(session, queue_number, status, table=None, seated_at=None, party_size=2, seq=1):
    entry = WaitlistEntry(
        branch_id=1,
        queue_number=queue_number,
        full_queue_number=f"A-20260910-{seq:03d}",
        queue_prefix="A",
        seq=seq,
        business_date="2026-09-10",
        name=f"Party {queue_number}",
        phone=f"09000000{seq:02d}",
        party_size=party_size,
        status=status,
        sort_order=seq,
        source="CUSTOMER",
        table_id=table.id if table is not None else None,
        seated_at=seated_at,
    )
    session.add(entry)
    session.commit()
    return entry


def _headers():
    return {"Authorization": "Bearer " + _staff_token()}


def test_list_tables_active():
    """Only active tables come back, ordered by sort_order then label, total matches items."""
    session = app_database.SessionLocal()
    _clear(session)
    _make_table(session, "B2", TableStatus.AVAILABLE, 2000, section="Patio")
    _make_table(session, "A9", TableStatus.AVAILABLE, 1000)
    _make_table(session, "A1", TableStatus.CLEANING, 1000)
    _make_table(session, "OFF", TableStatus.AVAILABLE, 1500, is_active=False)
    session.close()

    response = client.get("/api/v1/staff/tables", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    labels = [item["label"] for item in body["items"]]
    assert labels == ["A1", "A9", "B2"]
    assert body["total"] == len(labels)
    assert "OFF" not in labels


def test_list_tables_includes_current_waitlist():
    """An OCCUPIED row carries the four openapi fields with backend-computed elapsed_minutes."""
    session = app_database.SessionLocal()
    _clear(session)
    occupied = _make_table(session, "A1", TableStatus.OCCUPIED, 1000)
    _make_entry(
        session,
        "A005",
        WaitlistStatus.SEATED,
        table=occupied,
        seated_at=FROZEN_DT - timedelta(minutes=20),
        party_size=4,
        seq=5,
    )
    _make_table(session, "A2", TableStatus.AVAILABLE, 1100)
    session.close()

    with freeze_time(FROZEN):
        response = client.get("/api/v1/staff/tables", headers=_headers())
    assert response.status_code == 200
    items = {item["label"]: item for item in response.json()["items"]}
    for key in ("id", "label", "capacity", "section", "status", "is_active", "sort_order",
                "current_waitlist"):
        assert key in items["A1"]
    waitlist = items["A1"]["current_waitlist"]
    assert sorted(waitlist) == ["elapsed_minutes", "party_size", "queue_number", "seated_at"]
    assert waitlist["queue_number"] == "A005"
    assert waitlist["party_size"] == 4
    assert waitlist["elapsed_minutes"] == 20
    assert waitlist["seated_at"].endswith("+00:00")
    assert items["A2"]["current_waitlist"] is None


def test_update_table_status_available_to_cleaning():
    """PATCH AVAILABLE -> CLEANING answers 200 and persists the new status."""
    session = app_database.SessionLocal()
    _clear(session)
    table = _make_table(session, "A1", TableStatus.AVAILABLE, 1000)
    table_id, table_pk = str(table.id), table.id
    session.close()

    with freeze_time(FROZEN):
        response = client.patch(
            "/api/v1/staff/tables/" + table_id, json={"status": "CLEANING"}, headers=_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "CLEANING"
    session = app_database.SessionLocal()
    assert session.get(Table, table_pk).status is TableStatus.CLEANING
    session.close()


def test_update_table_status_cleaning_to_available():
    """PATCH CLEANING -> AVAILABLE answers 200 and persists the new status."""
    session = app_database.SessionLocal()
    _clear(session)
    table = _make_table(session, "A2", TableStatus.CLEANING, 1100)
    table_id, table_pk = str(table.id), table.id
    session.close()

    with freeze_time(FROZEN):
        response = client.patch(
            "/api/v1/staff/tables/" + table_id, json={"status": "AVAILABLE"}, headers=_headers()
        )
    assert response.status_code == 200
    assert response.json()["status"] == "AVAILABLE"
    session = app_database.SessionLocal()
    assert session.get(Table, table_pk).status is TableStatus.AVAILABLE
    session.close()


def test_update_table_status_occupied_rejected():
    """Setting OCCUPIED is 422 VALIDATION_ERROR from the body enum and leaves the row untouched."""
    session = app_database.SessionLocal()
    _clear(session)
    table = _make_table(session, "A1", TableStatus.AVAILABLE, 1000)
    table_id, table_pk = str(table.id), table.id
    session.close()

    response = client.patch(
        "/api/v1/staff/tables/" + table_id, json={"status": "OCCUPIED"}, headers=_headers()
    )
    assert response.status_code == 422
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]
    session = app_database.SessionLocal()
    assert session.get(Table, table_pk).status is TableStatus.AVAILABLE
    session.close()


def test_release_table_success():
    """Release answers 200 AVAILABLE and closes the SEATED party with closed_at (specs 4.8)."""
    session = app_database.SessionLocal()
    _clear(session)
    table = _make_table(session, "A1", TableStatus.OCCUPIED, 1000)
    table_id, table_pk = str(table.id), table.id
    entry = _make_entry(
        session,
        "A005",
        WaitlistStatus.SEATED,
        table=table,
        seated_at=FROZEN_DT - timedelta(minutes=20),
        party_size=4,
        seq=5,
    )
    entry_id = entry.id
    session.close()

    with freeze_time(FROZEN):
        response = client.post("/api/v1/staff/tables/" + table_id + "/release", headers=_headers())
        listed = client.get("/api/v1/staff/tables", headers=_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "AVAILABLE"
    assert response.json()["current_waitlist"] is None
    session = app_database.SessionLocal()
    row = session.get(Table, table_pk)
    assert row.status is TableStatus.AVAILABLE
    assert row.updated_at.strftime("%Y-%m-%d %H:%M") == "2026-09-10 13:00"
    party = session.get(WaitlistEntry, entry_id)
    assert party.status is WaitlistStatus.DONE
    assert party.closed_at is not None
    assert party.seated_at is not None
    items = {item["label"]: item for item in listed.json()["items"]}
    assert items["A1"]["current_waitlist"] is None
    session.close()


def test_release_table_not_occupied():
    """A non-OCCUPIED release is 409 TABLE_NOT_AVAILABLE; an entry-less OCCUPIED row releases."""
    session = app_database.SessionLocal()
    _clear(session)
    available = _make_table(session, "A1", TableStatus.AVAILABLE, 1000)
    cleaning = _make_table(session, "A2", TableStatus.CLEANING, 1100)
    orphan = _make_table(session, "A3", TableStatus.OCCUPIED, 1200, section="Patio")
    available_id, cleaning_id, orphan_id = (
        str(available.id),
        str(cleaning.id),
        str(orphan.id),
    )
    available_pk, cleaning_pk, orphan_pk = available.id, cleaning.id, orphan.id
    session.close()

    for table_id in (available_id, cleaning_id):
        response = client.post("/api/v1/staff/tables/" + table_id + "/release", headers=_headers())
        assert response.status_code == 409
        body = response.json()
        assert "detail" not in body
        assert body["error"]["code"] == "TABLE_NOT_AVAILABLE"
        assert body["error"]["message"]

    orphan_response = client.post(
        "/api/v1/staff/tables/" + orphan_id + "/release", headers=_headers()
    )
    assert orphan_response.status_code == 200
    assert orphan_response.json()["status"] == "AVAILABLE"

    session = app_database.SessionLocal()
    assert session.get(Table, available_pk).status is TableStatus.AVAILABLE
    assert session.get(Table, cleaning_pk).status is TableStatus.CLEANING
    assert session.get(Table, orphan_pk).status is TableStatus.AVAILABLE
    assert session.query(WaitlistEntry).count() == 0
    session.close()
