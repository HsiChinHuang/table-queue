"""Staff dashboard endpoint tests (issue B-09).

File name comes from ``_docs/testing.md`` section 2 (Staff Dashboard), which names
``test_dashboard_counts`` and ``test_dashboard_avg_wait_null_when_no_data``; the issue's Test
requirements name the nine functions below, one per AC plus the awkward cases, and both spellings
sit in this module (the two testing.md names alias the rollup / null-average cases). The naming
drift between the two documents is known debt, tracked outside this issue - it is not repaired
here, because ``_docs/testing.md`` is outside this issue's Constraints.

What this module adds over the issue's AC blocks is the same ten counters driven inside the suite
with the clock really frozen. The AC blocks cannot freeze - see R-B09-6 in
``_docs/issues/B-09.md``: their helper must ``import app.main`` before any freeze exists, and
freezegun before an app import makes the application unimportable on this lockfile. Inside pytest
that constraint does not apply, because conftest has already imported ``app.main`` at collection
time and ``freeze_time`` is entered per test afterwards. So every test below is deterministic and
none of them reads the real wall clock.

Module shape follows the merged ``test_staff_tables.py`` (B-08), the closest exemplar:

- an engine of its own bound to ``app.database.SessionLocal`` for the module, restored in teardown,
  because conftest's ``tq_isolated`` swaps ``DATABASE_URL`` per test and creates no schema at all -
  a module that rides the ambient engine answers "no such table";
- the shared ``app.main.limiter`` disabled **before** the module-level ``TestClient`` is built, so a
  whole-suite run cannot turn these calls into 429s (and no second ``Limiter`` is built here);
- ``freezegun`` at the ``_docs/testing.md`` instant ``2026-09-10 13:00:00`` UTC, which is
  ``2026-09-10 21:00`` Taipei and therefore business date ``2026-09-10`` under the merged cutoff-4
  rule;
- its own ``_b09_test.db`` file, removed in teardown.

Each test seeds the rows it states an expectation about and clears the two tables it touches first,
so test order carries no meaning.
"""

from __future__ import annotations

import os
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./_b09_test.db")
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
from app.models import (  # noqa: E402
    Base,
    Branch,
    CancelledReason,
    Restaurant,
    Settings,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistStatus,
)

warnings.filterwarnings("ignore")  # app.schemas emits protected-namespace noise on import

DB_PATH = Path(__file__).resolve().parent / "_b09_test.db"

test_engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
# The limiter must be off before TestClient is constructed below (B-06 QA finding).
limiter.enabled = False

client = TestClient(app, raise_server_exceptions=False)

FROZEN = "2026-09-10 13:00:00"
FROZEN_DT = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
DAY = "2026-09-10"
YESTERDAY = "2026-09-09"
HOLD_MINUTES = 10

DASHBOARD_URL = "/api/v1/staff/dashboard"

LIVE_FIELDS = [
    "waiting_count",
    "called_count",
    "seated_count",
    "available_table_count",
    "occupied_table_count",
    "cleaning_table_count",
    "no_show_today",
    "cancelled_today",
    "seated_today",
]
ALL_FIELDS = [*LIVE_FIELDS, "avg_wait_minutes_today"]

# Six tables: two AVAILABLE, two OCCUPIED, one CLEANING - all active - plus one further OCCUPIED
# row that is is_active=False, which is what makes "only active tables are counted" falsifiable.
TABLE_SEEDS = (
    ("T1", TableStatus.AVAILABLE, True),
    ("T2", TableStatus.AVAILABLE, True),
    ("T3", TableStatus.OCCUPIED, True),
    ("T4", TableStatus.OCCUPIED, True),
    ("T5", TableStatus.CLEANING, True),
    ("T6", TableStatus.OCCUPIED, False),
)


def _staff_token(secret: str | None = None, expiry: int = 9999999999) -> str:
    """Mint the merged B-05 staff JWT shape against the ambient secret."""
    return jwt.encode(
        {"sub": "staff", "role": "staff", "iat": 1, "exp": expiry},
        secret or os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


def _headers(secret: str | None = None, expiry: int = 9999999999) -> dict[str, str]:
    return {"Authorization": "Bearer " + _staff_token(secret, expiry)}


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
                hold_minutes=HOLD_MINUTES,
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


def _naive(value: datetime) -> datetime:
    """Return ``value`` as the naive UTC wall time SQLite's DATETIME column round-trips."""
    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)


def _make_table(session, label, status, sort_order, capacity=4, is_active=True):
    """Write one table row and return its primary key."""
    table_id = uuid4()
    session.add(
        Table(
            id=table_id,
            branch_id=1,
            label=label,
            capacity=capacity,
            section="MAIN",
            sort_order=sort_order,
            status=status,
            is_active=is_active,
            created_at=_naive(FROZEN_DT),
            updated_at=_naive(FROZEN_DT),
        )
    )
    session.commit()
    return table_id


def _make_entry(
    session,
    seq,
    status,
    *,
    day=DAY,
    called_minutes_ago=None,
    hold=HOLD_MINUTES,
    seated_minutes_ago=None,
    closed_minutes_ago=None,
    table_id=None,
    cancelled_reason=None,
):
    """Write one waitlist row whose every timestamp is stated relative to the frozen instant.

    Nothing here reads ``datetime.now``: the caller states each offset from ``FROZEN_DT``, and the
    test that drives the request enters ``freeze_time(FROZEN)`` around it, so the clock the
    dashboard reads and the clock the seed stamped are the same clock by construction.
    """
    def shifted(minutes):
        return None if minutes is None else _naive(FROZEN_DT - timedelta(minutes=minutes))

    entry = WaitlistEntry(
        branch_id=1,
        queue_number=f"A{seq:03d}",
        full_queue_number="A-" + day.replace("-", "") + f"-{seq:03d}",
        queue_prefix="A",
        seq=seq,
        business_date=day,
        name=f"Party A{seq:03d}",
        phone=f"09001{seq:05d}",
        party_size=2,
        status=status,
        sort_order=seq,
        source="STAFF",
        hold_minutes_snapshot=hold if called_minutes_ago is not None else None,
        cancelled_reason=cancelled_reason,
        table_id=table_id,
        created_at=_naive(FROZEN_DT),
        updated_at=_naive(FROZEN_DT),
        called_at=shifted(called_minutes_ago),
        seated_at=shifted(seated_minutes_ago),
        closed_at=shifted(closed_minutes_ago),
    )
    session.add(entry)
    session.commit()
    return entry


def seed_today(
    session,
    *,
    called_minutes_ago=3,
    done_durations=(),
    extra_cancelled=0,
    tables=True,
    yesterday=True,
):
    """Write the AC-4/AC-6/AC-8 shape: today's queue, the six tables, and optional prior-day rows.

    Defaults reproduce the seed the issue's AC blocks name: three ``WAITING``, one ``CALLED`` called
    3 minutes ago against the 10-minute hold (so inside it, and counted), two ``SEATED``, one
    ``NO_SHOW``, one ``CANCELLED``, plus ``extra_cancelled - 1`` further cancellations and one
    ``DONE`` row per entry of ``done_durations`` (seat-to-close minutes). ``yesterday`` adds one
    prior-date ``NO_SHOW``, ``CANCELLED`` and ``DONE``, each carrying the frozen instant in its
    timestamp columns, which is what makes a missing day filter visible rather than harmless.
    """
    ids = {}
    if tables:
        for index, (label, status, active) in enumerate(TABLE_SEEDS, start=1):
            ids[label] = _make_table(session, label, status, index * 100, is_active=active)

    _make_entry(session, 4, WaitlistStatus.SEATED, seated_minutes_ago=30, table_id=ids.get("T3"))
    _make_entry(session, 5, WaitlistStatus.SEATED, seated_minutes_ago=50, table_id=ids.get("T4"))
    for seq in (1, 2, 3):
        _make_entry(session, seq, WaitlistStatus.WAITING)
    if called_minutes_ago is not None:
        _make_entry(session, 300, WaitlistStatus.CALLED, called_minutes_ago=called_minutes_ago)
    _make_entry(session, 6, WaitlistStatus.NO_SHOW, closed_minutes_ago=0)
    _make_entry(
        session,
        200,
        WaitlistStatus.CANCELLED,
        closed_minutes_ago=0,
        cancelled_reason=CancelledReason.STAFF,
    )
    for extra in range(1, extra_cancelled):
        _make_entry(
            session,
            210 + extra,
            WaitlistStatus.CANCELLED,
            closed_minutes_ago=0,
            cancelled_reason=CancelledReason.STAFF,
        )
    for index, minutes in enumerate(done_durations):
        _make_entry(
            session,
            100 + index,
            WaitlistStatus.DONE,
            seated_minutes_ago=minutes,
            closed_minutes_ago=0,
        )
    if yesterday:
        _make_entry(session, 7, WaitlistStatus.NO_SHOW, day=YESTERDAY, closed_minutes_ago=0)
        _make_entry(
            session,
            8,
            WaitlistStatus.CANCELLED,
            day=YESTERDAY,
            closed_minutes_ago=0,
            cancelled_reason=CancelledReason.CUSTOMER,
        )
        _make_entry(
            session,
            9,
            WaitlistStatus.DONE,
            day=YESTERDAY,
            seated_minutes_ago=20,
            closed_minutes_ago=0,
        )
    return ids


def _drop(session, statuses, day=DAY) -> None:
    """Remove today's rows in ``statuses`` so a test can state its own population."""
    session.query(WaitlistEntry).filter(
        WaitlistEntry.status.in_(statuses),
        WaitlistEntry.business_date == day,
    ).delete(synchronize_session=False)
    session.commit()


def _get():
    """GET the dashboard with a valid staff token while the documented instant is now."""
    with freeze_time(FROZEN):
        return client.get(DASHBOARD_URL, headers=_headers())


def test_dashboard_requires_auth():
    """AC-1/AC-2: the route is mounted on the app and an unauthenticated call is 401."""
    paths = app.openapi()["paths"]
    operation = paths.get(DASHBOARD_URL) or {}
    assert "get" in operation, sorted(paths)
    ref = (
        ((operation["get"].get("responses") or {}).get("200") or {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref", "")
    )
    assert "DashboardResponse" in ref

    response = client.get(DASHBOARD_URL)
    assert response.status_code == 401
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "AUTH_TOKEN_EXPIRED"
    assert body["error"]["message"].strip()


def test_dashboard_unauthenticated_envelope_all_shapes():
    """AC-2: no header, a non-bearer scheme, a forged secret and a past ``exp`` are all 401."""
    good = _staff_token()
    wrong = _staff_token(secret="not-the-ambient-secret")  # noqa: S106
    expired = _staff_token(expiry=1000000000)
    cases = [
        ("no Authorization header", {}),
        ("scheme is not bearer", {"Authorization": "Basic " + good}),
        ("secret does not match JWT_SECRET", {"Authorization": "Bearer " + wrong}),
        ("exp already passed", {"Authorization": "Bearer " + expired}),
    ]
    for label, headers in cases:
        response = client.get(DASHBOARD_URL, headers=headers)
        assert response.status_code == 401, label
        body = response.json()
        assert "detail" not in body, label
        assert body["error"]["code"] == "AUTH_TOKEN_EXPIRED", label
        assert body["error"]["message"].strip(), label


def test_dashboard_response_shape_all_integer():
    """AC-3: the 200 body carries exactly the ten keys, every one a non-null ``int``."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(20, 40))
    session.close()

    response = _get()
    assert response.status_code == 200, response.text
    payload = response.json()
    assert sorted(payload) == sorted(ALL_FIELDS)
    for field in LIVE_FIELDS:
        value = payload[field]
        assert value is not None, field
        assert isinstance(value, int) and not isinstance(value, bool), (field, value)


def test_dashboard_queue_counts_today_only():
    """AC-4: 3 WAITING, 1 CALLED inside the hold and 2 SEATED today, prior-date rows excluded."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(), yesterday=True)
    session.close()

    payload = _get().json()
    assert payload["waiting_count"] == 3
    assert payload["called_count"] == 1
    assert payload["seated_count"] == 2
    assert payload["seated_today"] == 2


def test_dashboard_table_counts_active_only():
    """AC-5: 2 AVAILABLE, 2 OCCUPIED, 1 CLEANING - the inactive OCCUPIED row is not counted."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=())
    session.close()

    payload = _get().json()
    assert payload["available_table_count"] == 2
    assert payload["occupied_table_count"] == 2
    assert payload["cleaning_table_count"] == 1


def test_dashboard_counts():
    """``_docs/testing.md`` name: the day rollups are today's rows only, 1 / 2 / 2."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(), extra_cancelled=2, yesterday=True)
    session.close()

    payload = _get().json()
    assert payload["no_show_today"] == 1
    assert payload["cancelled_today"] == 2
    assert payload["seated_today"] == 2


def test_dashboard_day_rollups_today_only():
    """Issue name for that measurement, plus the quiet-day half: 0, never null (R-B09-1)."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(), extra_cancelled=2, yesterday=True)
    session.close()

    payload = _get().json()
    assert (payload["no_show_today"], payload["cancelled_today"], payload["seated_today"]) == (
        1,
        2,
        2,
    )

    _clear(session)
    seed_today(session, called_minutes_ago=None, yesterday=True)
    _drop(session, [WaitlistStatus.SEATED, WaitlistStatus.NO_SHOW, WaitlistStatus.CANCELLED])
    session.close()

    quiet = _get().json()
    assert quiet["no_show_today"] == 0
    assert quiet["cancelled_today"] == 0
    assert quiet["seated_today"] == 0
    assert quiet["waiting_count"] == 3
    assert quiet["called_count"] == 0


def test_dashboard_applies_lazy_no_show_and_persists():
    """AC-7: an expired ``CALLED`` is ``NO_SHOW`` in the database after the call, closed_at set."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=None, done_durations=(), yesterday=False)
    expired = _make_entry(session, 400, WaitlistStatus.CALLED, called_minutes_ago=11)
    expired_id = expired.id
    session.close()

    with freeze_time(FROZEN):
        response = client.get(DASHBOARD_URL, headers=_headers())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["called_count"] == 0, payload
    assert payload["no_show_today"] == 2, payload

    check = app_database.SessionLocal()
    row = check.query(WaitlistEntry).filter(WaitlistEntry.seq == 400).first()
    assert row is not None
    assert row.id == expired_id
    assert row.status is WaitlistStatus.NO_SHOW, row.status
    assert row.closed_at is not None
    check.close()


def test_dashboard_avg_wait_minutes():
    """AC-8: two rows closed today after 20 and 40 minutes answer 30, as an ``int``."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(20, 40), yesterday=True)
    session.close()

    payload = _get().json()
    value = payload["avg_wait_minutes_today"]
    assert value == 30, payload
    assert isinstance(value, int) and not isinstance(value, bool)


def test_dashboard_avg_wait_minutes_null_when_no_closed_row():
    """AC-9: null when nothing closed today, 20 once one 20-minute row is added."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=3, done_durations=(), yesterday=False)
    _drop(session, [WaitlistStatus.NO_SHOW, WaitlistStatus.CANCELLED])
    session.close()

    first = _get().json()
    assert first["avg_wait_minutes_today"] is None, first
    for field in LIVE_FIELDS:
        assert first[field] is not None, field

    session = app_database.SessionLocal()
    _make_entry(session, 500, WaitlistStatus.DONE, seated_minutes_ago=20, closed_minutes_ago=0)
    session.close()

    second = _get().json()
    assert second["avg_wait_minutes_today"] == 20, second


def test_dashboard_avg_wait_null_when_no_data():
    """``_docs/testing.md`` name for the null half, plus the floor-truncation boundary."""
    session = app_database.SessionLocal()
    _clear(session)
    seed_today(session, called_minutes_ago=None, tables=False, yesterday=False)
    _drop(session, [WaitlistStatus.DONE, WaitlistStatus.NO_SHOW, WaitlistStatus.CANCELLED])
    session.close()

    payload = _get().json()
    assert payload["avg_wait_minutes_today"] is None, payload
    assert payload["waiting_count"] == 3

    extra = app_database.SessionLocal()
    _make_entry(extra, 600, WaitlistStatus.DONE, seated_minutes_ago=20, closed_minutes_ago=0)
    extra.close()
    assert _get().json()["avg_wait_minutes_today"] == 20

    _clear(session)
    seed_today(session, called_minutes_ago=None, done_durations=(20, 41), yesterday=False)
    session.close()

    truncated = _get().json()
    assert truncated["avg_wait_minutes_today"] == 30, truncated
