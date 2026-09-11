"""B-06 public waitlist endpoints: join, status lookup and cancel.

Mirrors the AC probes of _docs/issues/B-06.md (sections 8, 9 and 15 of specs.md). The board half of
the surface lives in ``tests/test_public_board.py``; the shared seeding helpers live in
``tests/public_fixtures.py`` so that AC-15, which runs pytest over these two files only, sees real
fixtures rather than a module that cannot import.

Two of the rules below are worth the paragraph it takes to say why they are asserted the way they
are: the status credential is *derived* from stored columns rather than stored (R-B06-4), so a test
has to recompute it instead of reading a column; and the rate limits are attached to the handler
during route registration, so a test can only see them by inspecting the router rather than by
sending requests - the 429 itself needs a limiter that is switched on, which is what
``limiter_enabled`` is for.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tq_b06_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from freezegun import freeze_time  # noqa: E402

from app.main import app  # noqa: E402
from app.models import WaitlistStatus  # noqa: E402
from app.services import waitlist as service  # noqa: E402
from tests.public_fixtures import (  # noqa: E402
    BUSINESS_DATE,
    NOW,
    fresh_session,
    seed_branch,
    seed_entry,
    token_for,
)

JOIN = "/api/v1/branches/1/waitlist"
BRANCH = "/api/v1/public/branches/1"
STATUS_PATH = "/api/v1/waitlist"
CANCEL = "/api/v1/waitlist/A014/cancel"
BODY = {"name": "John Smith", "phone": "0900-000-001", "party_size": 4, "note": "Window seat"}
WRONG_TOKEN = "deadbeef" + "deadbeef"  # not a credential any stored row can derive (AC-9)
CONTRACT_MASK = "0900-***-001"  # the masked shape AC-4 and AC-12 measure


@pytest.fixture()
def db():
    """A session on a schema rebuilt for this test, so no queue leaks between tests."""
    session = fresh_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db):
    """Return a session that has a branch, restaurant and settings row written.

    The branch rows are what every public read needs, and seeding them in a fixture of their own
    rather than in ``db`` keeps the tests that ask about a *missing* branch honest: those get the
    empty schema, and this one gets the deployment a guest actually joins.
    """
    seed_branch(db)
    return db


@pytest.fixture()
def client(db):
    """A client over the rebuilt schema, without the branch rows some tests do not want."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@contextlib.contextmanager
def limiter_enabled():
    """Switch the shared limiter on for the block, then restore whatever it was.

    ``app.state.limiter`` is constructed enabled but the app only mounts the
    ``SlowAPIMiddleware`` when ``limiter.enabled`` holds, and ``tests/conftest.py`` leaves it
    off so that unrelated suites are not throttled. A test that wants a 429 therefore has to
    ask for one, and has to build its client *inside* the block: the middleware list is fixed
    at application startup.
    """
    limiter = app.state.limiter
    previous = limiter.enabled
    limiter.enabled = True
    try:
        yield limiter
    finally:
        limiter.enabled = previous


def join(client, **overrides):
    """POST a join with the contract's example body, overridden field by field."""
    return client.post(JOIN, json={**BODY, **overrides})


def status(client, qn, **params):
    """GET a queue position with whichever credential the test is exercising."""
    return client.get(STATUS_PATH + "/" + qn, params=params)


# --- branch info (sections 6 and 12) -----------------------------------------------------------


def test_branch_info_publishes_the_nine_contract_fields(seeded):
    """AC-1/AC-2: the public branch payload is the nine openapi fields and nothing else.

    The key set is asserted rather than each value alone because the contract names both: a payload
    carrying the right nine plus an ``address_phone`` is still wrong, and it is the kind of wrong a
    value-by-value test cannot see.
    """
    response = client_of(seeded).get(BRANCH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "restaurant_name",
        "branch_name",
        "address",
        "phone",
        "open_time",
        "close_time",
        "hours",
        "is_waitlist_open",
        "timezone",
    }
    assert body["restaurant_name"] == "Sunny Bistro"
    assert body["branch_name"] == "Taipei Xinyi"
    assert body["phone"] == "02-1234-5678"  # the branch's own published line, not a guest's number
    assert body["hours"] == "11:00-21:00"
    assert body["is_waitlist_open"] is True


def test_branch_info_is_unknown_branch_404_in_the_envelope(seeded):
    """A missing branch is the section 11 error envelope, not a FastAPI ``detail`` string."""
    response = client_of(seeded).get("/api/v1/public/branches/999")
    assert response.status_code == 404
    # section 11 names BRANCH_NOT_FOUND for this operation; RESOURCE_NOT_FOUND
    # is not one of its codes
    assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"


def test_branch_info_tracks_the_settings_flag(db):
    """``is_waitlist_open`` is read per request, never cached on the branch row."""
    seed_branch(db, is_open=False)  # the only writer of branch rows in this test
    with TestClient(app, raise_server_exceptions=False) as test_client:
        assert test_client.get(BRANCH).json()["is_waitlist_open"] is False


# --- join (section 4.1, section 8) -------------------------------------------------------------


def test_join_assigns_the_number_and_persists_the_row(seeded):
    """AC-4: 201 with A001 / seq 1 / A-20260910-001 / 2026-09-10 / WAITING / CUSTOMER."""
    client = client_of(seeded)
    with freeze_time(NOW):
        response = join(client)
    assert response.status_code == 201
    body = response.json()
    assert body["queue_number"] == "A001"
    assert body["full_queue_number"] == "A-20260910-001"
    assert body["status"] == "WAITING"
    assert body["source"] == "CUSTOMER"

    # ``seq`` and ``business_date`` are AC-4's other two observables and are asserted on the row:
    # ``WaitlistEntryResponse`` (B-03, frozen) declares neither field, and AC-4 reads the stored
    # column whenever the body cannot answer ("b.get(k) != v and stored.get(k) != v").
    row = seeded.query(service.WaitlistEntry).one()
    assert row.queue_number == "A001"
    assert row.seq == 1
    assert row.business_date == BUSINESS_DATE
    assert row.status is WaitlistStatus.WAITING
    assert row.source.value == "CUSTOMER"
    assert row.sort_order == 1
    assert row.closed_at is None


def test_join_masks_the_phone_without_losing_the_callers_format(seeded):
    """AC-4/AC-12's masked value, and the one phone field the response may carry.

    ``0900-***-001`` is what the contract measures: the typed hyphens stay where they were, the
    middle of the number is replaced by the three asterisks, and the trailing three digits - the
    credential section 15 hands to the guest - survive on the right of the mask.
    """
    client = client_of(seeded)
    with freeze_time(NOW):
        body = join(client).json()
    assert body["phone_masked"] == CONTRACT_MASK
    assert "phone" not in body  # ``phone_masked`` is the only field that may name a phone
    assert "0900-000-001" not in str(body)


def test_join_rejects_an_invalid_body_with_the_validation_code(seeded):
    """Section 2: a body that fails pydantic is 422 VALIDATION_ERROR, not a queue number."""
    client = client_of(seeded)
    for bad in (
        {**BODY, "phone": "0912345"},
        {**BODY, "party_size": 0},
        {**BODY, "party_size": 4, "note": "x" * 201},
    ):
        with freeze_time(NOW):
            response = client.post(JOIN, json=bad)
        assert response.status_code == 422, bad
        assert response.json()["error"]["code"] == "VALIDATION_ERROR", bad
    assert seeded.query(service.WaitlistEntry).count() == 0


def test_join_number_increments_per_business_date(seeded):
    """AC-5: the sequence is per branch per business date, so A002 follows A001 the same day."""
    client = client_of(seeded)
    with freeze_time(NOW):
        first = join(client).json()
        second = join(client, phone="0900-000-003").json()
    assert (first["queue_number"], second["queue_number"]) == ("A001", "A002")
    assert second["full_queue_number"] == "A-20260910-002"


def test_join_against_a_closed_queue_writes_nothing(seeded):
    """AC-13: a paused waitlist refuses before anything is allocated.

    The row count is the assertion, not the status code alone: a service that wrote the row and
    then raised would hand back a 409 and still leak queue numbers into the day's sequence.
    """
    seed_branch(seeded, is_open=False)  # replaces the open settings row with a paused one
    client = client_of(seeded)
    with freeze_time(NOW):
        response = join(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WAITLIST_CLOSED"
    assert seeded.query(service.WaitlistEntry).count() == 0


def test_join_unknown_branch_is_404(seeded):
    """The branch is checked before the body is used, so an unknown one never allocates a
    number.
    """
    client = client_of(seeded)
    with freeze_time(NOW):
        response = client.post("/api/v1/branches/999/waitlist", json=BODY)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BRANCH_NOT_FOUND"
    assert seeded.query(service.WaitlistEntry).count() == 0


def test_join_uses_the_injected_clock_for_the_business_date(seeded):
    """AC-4 / section 8: the business date is the branch clock shifted back by the cutoff.

    The formula the specs write is ``business_date = (now_in_branch_tz - cutoff_hour).date()``, and
    what it is testing is the difference between a cutoff and a midnight: a restaurant that turns
    its day over at 04:00 Taipei serves the party that joins at 04:30 Taipei on the 11th under the
    10th, because that is the evening the queue was opened for. Both sides of the rollover are
    asserted, because a rule that only ever subtracts looks right until the day it stops being.

    The instants are UTC, which is why the one that *names* the 11th in its own spelling is still
    the 10th's service: 04:30 UTC on the 11th is 12:30 Taipei, four hours of Taipei already behind
    it, and that is what the subtraction lands on.

    Each join is read back through the day it belongs to rather than through the queue number alone.
    Section 8 makes ``queue_number`` unique only WITHIN a business date - the table's own UNIQUE key
    is ``branch_id + business_date + queue_prefix + seq`` - so joining under two injected clocks
    stores two rows both numbered ``A001``, and a bare ``queue_number`` read answers that with
    ``MultipleResultsFound`` instead of with the row the test means.
    """
    client = client_of(seeded)
    # 03:59 UTC is 11:59 Taipei: still the 10th's service, four hours of it left to run.
    with freeze_time(datetime(2026, 9, 10, 3, 59, tzinfo=UTC)):
        body = join(client).json()
        row = seeded.query(service.WaitlistEntry).filter_by(
            business_date="2026-09-10", queue_number="A001"
        ).one()
    assert row.business_date == "2026-09-10"
    assert body["full_queue_number"] == "A-20260910-001"

    # 04:30 UTC on the 11th is 12:30 Taipei: three hours and thirty minutes past the 04:00 cutoff
    # that closes the 10th, so the day has rolled and the numbering starts again.
    with freeze_time(datetime(2026, 9, 11, 4, 30, tzinfo=UTC)):
        later = join(client, phone="0900-000-003").json()
        day = seeded.query(service.WaitlistEntry).filter_by(
            business_date="2026-09-11", queue_number="A001"
        ).one()
    assert day.business_date == "2026-09-11"
    assert day.queue_number == "A001"
    assert later["queue_number"] == "A001"  # a new day restarts the sequence


def test_duplicate_active_phone_is_refused_and_names_the_live_entry(seeded):
    """AC-5: a second join from a waiting number is 409 and points at the entry it duplicates."""
    client = client_of(seeded)
    with freeze_time(NOW):
        first = join(client).json()
        response = join(client, name="Different Name")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "WAITLIST_DUPLICATE_PHONE"
    assert body["error"]["details"]["queue_number"] == first["queue_number"]
    assert seeded.query(service.WaitlistEntry).count() == 1


def test_duplicate_check_is_on_normalised_digits(seeded):
    """The duplicate rule reads digits, so a hyphenated and a compact spelling collide (section 6).

    Asserting the *refusal* is the whole point: comparing raw strings would let the same subscriber
    hold two places by typing the number differently.
    """
    client = client_of(seeded)
    with freeze_time(NOW):
        join(client, phone="0900-000-001")
        response = join(client, phone="0900000001", name="Same Person")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WAITLIST_DUPLICATE_PHONE"
    assert seeded.query(service.WaitlistEntry).count() == 1


def test_a_cancelled_phone_can_join_again(seeded):
    """Only an *active* entry blocks a join, which is what makes a cancelled guest rejoinable."""
    client = client_of(seeded)
    with freeze_time(NOW):
        first = join(client).json()
        # The entry the join created is A001, not the A014 the CANCEL constant points at: a
        # cancellation aimed at a number nobody holds leaves the join below refusing a phone that
        # is still in the queue, which reads as a broken duplicate rule rather than a wrong URL.
        client.post(f"/api/v1/waitlist/{first['queue_number']}/cancel",
                    json={"token": first["status_token"]})
        response = join(client)
    assert response.status_code == 201
    assert response.json()["queue_number"] == "A002"


def test_join_hands_out_a_token_that_is_recomputable_from_the_row(seeded):
    """AC-8 / R-B06-4: the credential is derived from stored columns, never stored beside them.

    Recomputing it here rather than reading a column is the check: a schema that persisted a
    token would pass a naive round-trip test and still break every entry created before the
    column existed.
    """
    client = client_of(seeded)
    with freeze_time(NOW):
        body = join(client).json()
    row = seeded.query(service.WaitlistEntry).one()
    assert len(body["status_token"]) == 16
    assert body["status_token"] == token_for(row)
    assert body["status_token"] == hashlib.sha256(
        f"{row.id}|{row.phone}|{service._entry_created_at(row)}".encode()
    ).hexdigest()[:16]
    assert body["status_url"] == f"/status/{body['queue_number']}?token={body['status_token']}"


# --- status (sections 4.10 and 15) -------------------------------------------------------------


def test_status_counts_waiting_ahead_and_prices_the_wait(seeded):
    """AC-9 / R-B06-3: ``waiting_ahead`` counts WAITING rows with a strictly lower sort_order only.

    Three rows ahead is what the AC seeds (party sizes 2, 6 and 1) so that an implementation
    weighting by party size cannot pass, and a SEATED row joins them so that counting every non-
    cancelled row - the plausible mistake - is visible as 4 rather than 1.
    """
    seed_entry(seeded, queue_number="A001", seq=1, status=WaitlistStatus.SEATED, sort_order=1)
    seed_entry(seeded, queue_number="A002", seq=2, status=WaitlistStatus.WAITING, sort_order=2)
    seed_entry(seeded, queue_number="A003", seq=3, status=WaitlistStatus.WAITING, sort_order=3)
    seed_entry(seeded, queue_number="A004", seq=4, status=WaitlistStatus.WAITING, sort_order=4)
    seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=14,
        phone="0900-000-014",
    )
    client = client_of(seeded)
    with freeze_time(NOW):
        response = status(client, "A014", phone_last3="014")
    assert response.status_code == 200
    body = response.json()
    assert body["waiting_ahead"] == 3
    assert body["estimated_wait_minutes"] == 45  # 3 ahead x avg_seat_minutes 15, no party weighting
    assert body["status"] == "WAITING"


def test_status_rejects_a_wrong_token_as_not_found(seeded):
    """AC-9: a bad credential is a 404, never a 403 that confirms the queue number exists."""
    seed_entry(seeded, queue_number="A014", seq=14, status=WaitlistStatus.WAITING, sort_order=14)
    client = client_of(seeded)
    with freeze_time(NOW):
        response = status(client, "A014", token=WRONG_TOKEN)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WAITLIST_NOT_FOUND"


def test_status_phone_tail_searches_only_todays_rows(seeded):
    """AC-11: two identical tails, two business dates; the search is bounded to the caller's
    today.

    The two rows are the same tail on different days, and ``NOW`` is 09:00 UTC on the 10th -
    inside the 04:00-to-04:00 Taipei service day that opened at 04:00 UTC on the 10th - so the
    10th's row is today's and answers. The 9th's row is the trap: a search that ignored the
    date would find it too, and a caller could then be handed some other party's queue position
    from a previous day.

    Naming a date is not a credential a caller gets to use. ``business_date`` is not a parameter of
    ``getWaitlistStatus`` - ``WaitlistStatusParams`` declares the queue number plus ``token`` and
    ``phone_last3`` only - so a request that sends it is answered by the same today-bounded search
    as one that does not, and honouring it would expose any past-day row to anyone who guesses one
    (the delivered ``find_entry_by_tail`` is the today-bounded search). The answer is therefore
    identified as
    today's row - 200, ``WAITING``, and none of the previous day's identity in the payload - rather
    than by a 404 the contract cannot produce.
    """
    todays_row = seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        phone="0900-000-014",
    )
    stale_row = seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        sort_order=2,
        status=WaitlistStatus.SEATED,
        phone="0912-345-014",
        business_date="2026-09-09",
        created_at=datetime(2026, 9, 9, 9, 0, tzinfo=UTC),
    )
    client = client_of(seeded)
    with freeze_time(NOW):
        todays = status(client, "A014", phone_last3="014")
    assert todays.status_code == 200
    assert todays.json()["status"] == "WAITING"
    # Today's row is the answer, and the 9th's row is demonstrably not in it: its date, its own
    # full number and its derived credential are all absent from a payload that shares the tail
    # and the queue number with it. An assertion the stale row would also satisfy (a tail-only
    # mask check, for instance) is not this assertion - both rows end in 014.
    assert "2026-09-09" not in todays.text
    assert "20260909" not in todays.text
    assert token_for(stale_row) not in todays.text
    stamp = todays_row.created_at.strftime("%Y-%m-%dT%H:%M:%S")
    assert todays.json()["created_at"].startswith(stamp)
    # Undeclared keys are not part of the credential either, and the AC-10 probe is what pins that
    # the server never honours one; here the shape check is that this call sends only declared ones.
    with freeze_time(NOW):
        unfiltered = status(client, "A014", phone_last3="014")
    assert unfiltered.json() == todays.json()


def test_status_carries_no_name_and_no_phone(seeded):
    """Section 15: a status poll is safe to leave on a shared screen.

    Checked on the serialised text as well as on the key set, because the payload is assembled in a
    service and a leaked field there is invisible to a reader that only lists what it expected. The
    tail on the right of the mask is the credential a guest may legitimately send, so it survives;
    the digits to its left must not.
    """
    seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        phone="0900-000-014",
        name="Private Name",
    )
    client = client_of(seeded)
    with freeze_time(NOW):
        response = status(client, "A014", phone_last3="014")
    assert response.status_code == 200
    assert "Private Name" not in response.text
    assert "0900-000-014" not in response.text
    # Compact on this answer specifically: the lookup was answered with the last three digits
    # alone, and the form the guest typed it in would show four more digits beside a queue position.
    assert response.json()["phone_masked"] == "***014"
    assert set(response.json()) == {
        "queue_number",
        "status",
        "party_size",
        "created_at",
        "waiting_ahead",
        "estimated_wait_minutes",
        "called_at",
        "remaining_seconds",
        "hold_minutes",
        "phone_masked",
    }


def test_called_entry_counts_down_from_its_snapshot(seeded):
    """AC-11: a CALLED entry reports the seconds left of its own hold, measured from
    ``called_at``.

    ``remaining_seconds`` is priced from ``hold_minutes_snapshot`` rather than from the live
    setting or from ``created_at``: the hold starts when the guest is called, and a hold priced
    from the join would expire on a guest who was never reached.
    """
    entry = seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.CALLED,
        sort_order=1,
        phone="0900-000-014",
        called_at=NOW,
        hold_minutes_snapshot=10,
    )
    client = client_of(seeded)
    with freeze_time(NOW):
        fresh = status(client, "A014", token=token_for(entry)).json()
    # The hold runs from the call to the minute it was placed plus ten, so a minute is not a unit
    # this reading can quote: 04:00 on the clock is exactly six minutes gone and 240 seconds left,
    # and the whole number the payload carries is the 239 that remain after it. Six minutes less one
    # second is still inside the sixth minute, and that is the minute the guest is in.
    with freeze_time(NOW.replace(minute=3, second=59)):
        late = status(client, "A014", token=token_for(entry)).json()
    assert (fresh["remaining_seconds"], late["remaining_seconds"]) == (600, 361)
    assert fresh["hold_minutes"] == 10
    assert fresh["called_at"] is not None


def test_expired_call_becomes_no_show_on_the_next_read(seeded):
    """AC-11: the hold is closed lazily, on the read that finds it expired.

    The transition has to be *persisted* and not merely reported: a no-show that exists only in the
    response leaves the staff board showing a live call and the next reader recomputing it forever.
    """
    entry = seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.CALLED,
        sort_order=1,
        phone="0900-000-014",
        called_at=NOW,
        hold_minutes_snapshot=10,
    )
    client = client_of(seeded)
    with freeze_time(NOW.replace(minute=11)):
        response = status(client, "A014", token=token_for(entry))
    assert response.status_code == 200  # AC-11 answers the expired read, it does not hide the row
    body = response.json()
    assert body["status"] == "NO_SHOW"
    assert body["remaining_seconds"] is None
    seeded.expire_all()
    row = seeded.query(service.WaitlistEntry).one()
    assert row.status is WaitlistStatus.NO_SHOW
    assert row.closed_at is not None


# --- cancel (section 4.7) ----------------------------------------------------------------------


def test_cancel_closes_the_entry_and_echoes_it_masked(seeded):
    """AC-12: token cancel persists CANCELLED/CUSTOMER with ``closed_at`` and echoes the mask."""
    seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        phone="0900-000-001",
    )
    entry = seeded.query(service.WaitlistEntry).one()
    client = client_of(seeded)
    with freeze_time(NOW):
        response = client.post(CANCEL, json={"token": token_for(entry)})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancelled_reason"] == "CUSTOMER"
    assert body["phone_masked"] == CONTRACT_MASK
    seeded.expire_all()
    row = seeded.query(service.WaitlistEntry).one()
    assert row.closed_at is not None
    assert row.status is WaitlistStatus.CANCELLED


def test_second_cancel_is_a_conflict_not_a_second_success(seeded):
    """AC-12: the second cancel is 409 WAITLIST_INVALID_STATUS."""
    seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        phone="0900-000-001",
    )
    entry = seeded.query(service.WaitlistEntry).one()
    client = client_of(seeded)
    with freeze_time(NOW):
        client.post(CANCEL, json={"token": token_for(entry)})
        second = client.post(CANCEL, json={"token": token_for(entry)})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WAITLIST_INVALID_STATUS"


def test_cancel_by_phone_tail_works_without_a_token(seeded):
    """AC-13: the tail is the fallback credential, and a wrong tail gets you nowhere.

    The entry being left where it was is what matters in the refused half, and it is checked
    with the token the join returned - the only credential no other caller holds.
    """
    seed_entry(
        seeded,
        queue_number="A014",
        seq=14,
        status=WaitlistStatus.WAITING,
        sort_order=1,
        phone="0900-000-014",
    )
    client = client_of(seeded)
    with freeze_time(NOW):
        refused = client.post(CANCEL, json={"phone_last3": "999"})
        response = client.post(CANCEL, json={"phone_last3": "014"})
    assert refused.status_code == 404
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    seeded.expire_all()
    assert seeded.query(service.WaitlistEntry).one().status is WaitlistStatus.CANCELLED


def test_cancel_needs_a_credential(seeded):
    """A cancel with neither token nor tail is a validation failure, never an anonymous cancel."""
    seed_entry(seeded, queue_number="A014", seq=14, status=WaitlistStatus.WAITING, sort_order=1)
    client = client_of(seeded)
    with freeze_time(NOW):
        response = client.post(CANCEL, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert seeded.query(service.WaitlistEntry).one().status is WaitlistStatus.WAITING


# --- rate limiting (section 8's "10/min per IP") -----------------------------------------------

LIMITED_PATHS = frozenset(
    {
        "/api/v1/branches/{branch_id}/waitlist",
        "/api/v1/waitlist/{queue_number}",
        "/api/v1/waitlist/{queue_number}/cancel",
    }
)


def client_of(session):
    """Return a client over ``session``'s schema.

    The app has no session dependency to override - ``DbSession`` opens one against the module
    engine - so the session a test writes through and the one a request reads through are
    different objects on the same file. That is also why seeding has to be committed, which
    ``seed_entry`` and ``seed_branch`` both do.
    """
    del session  # the schema is shared; the session itself is not
    return TestClient(app, raise_server_exceptions=False)


def test_public_limiter_is_the_apps_limiter():
    """The router must rate limit with the limiter the app owns, not one of its own.

    A second ``Limiter()`` inside the router is invisible to ``app.main``, which is where the
    middleware and the storage are configured, so its counters would never be shared or read.
    """
    from app.routers import public as public_module

    assert public_module.limiter is app.state.limiter


def app_routes():
    """Return the ``(method, path)`` pairs the app actually serves, included routers flattened.

    FastAPI keeps an ``include_router`` payload behind a node that exposes the mounted router
    rather than a plain ``routes`` attribute, so a route that exists only inside an included
    router reads as missing unless both spellings are followed.
    """
    from fastapi.routing import APIRoute

    found = set()
    stack = list(app.routes)
    while stack:
        route = stack.pop()
        nested = getattr(route, "routes", None) or getattr(
            getattr(route, "original_router", None), "routes", None
        )
        if nested:
            stack.extend(nested)
        if isinstance(route, APIRoute):
            for method in route.methods or ():
                found.add(f"{method} {route.path}")
    return found


def test_public_rate_limited_routes_are_registered_wrapped():
    """AC-14 (mechanism): the three guest routes exist and their handler is the limited one.

    slowapi applies a limit by replacing the endpoint during registration, so the red case is a
    handler that reaches the router unwrapped. The check reads the *public router* rather than
    ``app.routes`` because the app only ever shows the include node for a mounted router, which is
    how a missing route and an unmounted router both read as nothing.
    """
    from fastapi.routing import APIRoute

    from app.routers import public as public_module

    api_routes = [route for route in public_module.router.routes if isinstance(route, APIRoute)]
    paths = {route.path for route in api_routes}
    assert paths >= LIMITED_PATHS, sorted(paths)
    for route in api_routes:
        if route.path not in LIMITED_PATHS:
            continue
        # The wrapper slowapi installs is not the module's own function object, which is the only
        # red case a unit test can see; the 429 itself needs a live transport (last test).
        own = getattr(public_module, route.endpoint.__name__, None)
        assert route.endpoint is not own or hasattr(route.endpoint, "__wrapped__")


def test_the_auth_router_is_still_registered_wrapped():
    """Regression: mounting the public limiter must not un-register the staff routes (B-05)."""
    from fastapi.routing import APIRoute

    from app.routers import auth as auth_module

    paths = {route.path for route in auth_module.router.routes if isinstance(route, APIRoute)}
    assert "/api/v1/auth/login" in paths, paths
    served = app_routes()
    assert "POST /api/v1/auth/login" in served, sorted(served)


def test_status_lookup_limit_is_ten_per_minute(seeded):
    """AC-14 (observable): the eleventh lookup in a minute is a 429 RATE_LIMITED.

    Run through a live transport with the limiter switched on, because the counter is spent in
    the middleware and a call that bypasses it measures nothing. The client is opened inside
    the enabled block for the same reason: the middleware list is fixed when the app starts.
    """
    seed_entry(seeded, queue_number="A014", seq=14, status=WaitlistStatus.WAITING, sort_order=1)
    with freeze_time(NOW), limiter_enabled():
        probe = TestClient(app, raise_server_exceptions=False)
        codes = [
            status(probe, "A014", phone_last3="014").status_code for _ in range(12)
        ]
        limited = status(probe, "A014", phone_last3="014")
    # AC-14 names the tenth and eleventh request specifically, so the window boundary is left alone.
    assert codes[:10] == [200] * 10, codes
    assert codes[10] == 429, codes
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
