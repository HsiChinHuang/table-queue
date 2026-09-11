"""Board privacy and shape tests for B-06 (AC-6, AC-7 and the section 15 privacy rule).

The board is the public surface a stranger can read with no credential at all, so these are privacy
tests first and shape tests second: each one names the two fields a queue item may expose and, where
a leak is possible, asserts what must NOT be in the payload. Fixtures come from
``tests.public_fixtures`` - the same seed shape the AC probes use.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tq_b06_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time

from app.main import app
from app.models import Settings, WaitlistStatus
from app.services import waitlist as service
from tests.public_fixtures import NOW, fresh_session, seed_branch, seed_entry

BOARD = "/api/v1/public/branches/1/board"

LEFT = [
    ("A010", 10, WaitlistStatus.SEATED),
    ("A011", 11, WaitlistStatus.DONE),
    ("A012", 12, WaitlistStatus.NO_SHOW),
    ("A013", 13, WaitlistStatus.CANCELLED),
    ("A014", 14, WaitlistStatus.CALLED),
]
WAITING = [(f"A{i:03d}", i, WaitlistStatus.WAITING) for i in range(15, 20)]


@pytest.fixture()
def db():
    """A session on a schema rebuilt for this test, so no queue leaks between tests."""
    session = fresh_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """A client over a seeded branch, frozen at the AC probes' instant.

    ``freeze_time`` wraps the whole ``yield`` because the request a ``TestClient`` serves runs on a
    worker thread and reads the clock inside the service; freezing only around the assertion would
    let the app see the real date and board a different business date.
    """
    seed_branch(db)
    with freeze_time(NOW):
        yield TestClient(app, raise_server_exceptions=False)


def seed_queue(db):
    """Write AC-6's queue: four closed, one CALLED and five WAITING, in ``sort_order`` order."""
    for qn, seq, status in LEFT + WAITING:
        seed_entry(db, queue_number=qn, seq=seq, status=status, sort_order=seq - 9)


def test_board_reports_the_four_queue_keys(client):
    """The board is a lobby display, not a queue dump: four keys describe the queue state."""
    with freeze_time(NOW):
        body = client.get(BOARD).json()
    assert {"current_called", "next_up", "recent_calls", "waiting_count"} <= set(body)


def test_board_counts_only_waiting_and_caps_recent_calls(db, client):
    """AC-6's arithmetic: five WAITING, four closed plus one CALLED, three recent at most."""
    seed_queue(db)
    with freeze_time(NOW):
        body = client.get(BOARD).json()
    assert body["waiting_count"] == 5
    assert len(body["recent_calls"]) == 3


def test_board_names_the_called_and_the_next_guest(db, client):
    """``current_called`` is the live CALLED row; ``next_up`` the lowest-sort_order WAITING row."""
    seed_queue(db)
    with freeze_time(NOW):
        body = client.get(BOARD).json()
    assert body["current_called"]["queue_number"] == "A014"
    assert body["next_up"]["queue_number"] == "A015"


def test_recent_calls_are_three_rows_that_left_waiting(db, client):
    """The cap of 3 is this issue's ruling (R-B06-1), so it has to be measurable (AC-6).

    Which three is deliberately not pinned: AC-6's sentence lists ``[A012, A011, A010]`` while its
    own probe asserts ``['A014', 'A013', 'A012']``, and the probe is the part that runs. Ordering is
    tested as the invariant the ruling does state - a member of the left-WAITING pool, never a
    WAITING row, never a fourth row - which holds under either reading.
    """
    seed_queue(db)
    with freeze_time(NOW):
        got = [item["queue_number"] for item in client.get(BOARD).json()["recent_calls"]]
    assert len(got) == 3
    assert len(set(got)) == 3
    assert set(got) <= {"A010", "A011", "A012", "A013", "A014"}


def test_board_exposes_no_name_and_no_phone(db, client):
    """Section 15: the public board shows only queue number and party size.

    Asserted on the raw response text rather than on parsed keys: a nested leak - a ``name`` field
    inside a ``current_called`` object - is invisible to a check that only lists top-level keys, the
    shape a leak actually takes. The seed phone is a real Taipei mobile and the seed name is
    not a string the board publishes anywhere, so a hit cannot be a formatting coincidence; the tail
    is asserted too, because a masked leak (``*******321``) still fails that check.
    """
    for qn, seq, status in LEFT:
        seed_entry(
            db,
            queue_number=qn,
            seq=seq,
            status=status,
            sort_order=seq - 9,
            phone="0987-654-321",
            name="Leaked Name",
        )
    with freeze_time(NOW):
        response = client.get(BOARD)
    assert response.status_code == 200
    assert "Leaked Name" not in response.text
    assert "0987" not in response.text
    assert "321" not in response.text
    body = response.json()
    # ``next_up`` is null in this queue: the CALLED guest is the one being served, so the privacy
    # check walks every item the board actually published rather than a fixed list.
    published = [
        item
        for item in [body["current_called"], body["next_up"], *body["recent_calls"]]
        if item is not None
    ]
    assert published, "the board published no queue item at all, so this test proved nothing"
    for item in published:
        assert set(item) == {"queue_number", "party_size"}


def test_board_reports_the_branch_and_its_hours(client):
    """The header block is the branch endpoint's own data, read from the same rows."""
    with freeze_time(NOW):
        body = client.get(BOARD).json()
    assert body["restaurant_name"] == "Sunny Bistro"
    assert body["branch_name"] == "Taipei Xinyi"
    assert body["hours"] == "11:00-21:00"
    assert body["is_waitlist_open"] is True


def test_empty_queue_is_a_valid_board_not_an_error(client):
    """AC-7: no rows boards 200 with nulls, an empty list and a count of 0.

    A quiet queue is a normal state of a restaurant, so the 404 belongs to the branch and never to
    the queue - which the second half of this test pins by asking for a branch that is not there.
    """
    with freeze_time(NOW):
        response = client.get(BOARD)
        missing = client.get("/api/v1/public/branches/999/board")
    assert response.status_code == 200
    body = response.json()
    assert body["current_called"] is None
    assert body["next_up"] is None
    assert body["recent_calls"] == []
    assert body["waiting_count"] == 0
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "BRANCH_NOT_FOUND"


def test_board_reflects_a_paused_waitlist(db, client):
    """The board mirrors the live flag, so a pause changes the next answer, not a constant."""
    with freeze_time(NOW):
        assert client.get(BOARD).json()["is_waitlist_open"] is True
    row = db.query(Settings).filter(Settings.branch_id == 1).first()
    row.is_waitlist_open = False
    db.commit()
    with freeze_time(NOW):
        fresh = TestClient(app, raise_server_exceptions=False).get(BOARD)
    assert fresh.status_code == 200
    assert fresh.json()["is_waitlist_open"] is False


def test_board_only_shows_todays_business_date(db, client):
    """Yesterday's rows are not today's lobby display (specs.md section 8)."""
    seed_entry(
        db,
        queue_number="A001",
        seq=1,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        business_date="2026-09-09",
    )
    seed_entry(
        db, queue_number="A101", seq=101, status=WaitlistStatus.WAITING, sort_order=2
    )
    with freeze_time(NOW):
        body = client.get(BOARD).json()
    assert body["waiting_count"] == 1
    assert body["next_up"]["queue_number"] == "A101"


def test_business_date_rolls_at_the_cutoff_not_at_midnight(db):
    """The boundary the queue is partitioned on: 04:00 Taipei, not 00:00 (specs.md section 8).

    ``business_date = (now_in_branch_tz - cutoff_hour).date()`` with cutoff 4, so the day turns at
    04:00 Taipei. ``_docs/testing.md`` section 2 names three samples and all three are asserted:
    03:59 and 04:00 on the 10th are the boundary itself, and 01:00 on the 11th is the one sample a
    day that rolled at local midnight would get wrong. The branch is the row this test seeds rather
    than a detached instance - ``Branch.restaurant`` has no default, so an unsaved row fails before
    the arithmetic is reached.
    """
    branch = seed_branch(db)
    boundaries = [
        ("2026-09-10 03:59:00", "2026-09-09"),
        ("2026-09-10 04:00:00", "2026-09-10"),
        ("2026-09-11 01:00:00", "2026-09-10"),
    ]
    for local, expected in boundaries:
        moment = datetime.strptime(local, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("Asia/Taipei")
        )
        assert service.business_date_for(branch, moment) == expected, local


def test_service_board_and_http_board_agree(db, client):
    """One rule, one answer: the router adds no opinion of its own to the service payload."""
    seed_queue(db)
    with freeze_time(NOW):
        http_body = client.get(BOARD).json()
        service_body = service.board(db, 1, NOW)
    for key in ("waiting_count", "current_called", "next_up", "recent_calls"):
        assert http_body[key] == service_body[key]
