"""AC-6 (D-02): the business-date cutover at the tight second, and the hold-expiry boundary.

Two shipped behaviours, each pinned at the edge its existing tests stop short of.

**The cutover.** ``services/waitlist.py::business_date_for`` is ``(now in the branch timezone) -
cutoff hours, dated``, and the branch fixture is ``Asia/Taipei`` with
``business_day_cutoff_hour = 4``, so the business date flips when Taipei crosses **04:00**. The
stub this issue descends from presented ``03:59`` and ``04:00`` as its boundary pair and every date
it stated is correct - but its two instants sit a full hour from the crossing, and it named no
clock while the shipped boundary test freezes ``datetime(2026, 9, 10, 3, 59, tzinfo=UTC)``, which is
11:59 Taipei. Both spellings are therefore pinned here, deliberately not reconciled into one: the
pure function at exact Taipei **wall** times including the tight second (case 1), and a real guest
join at the two **UTC** instants that produce those wall times (case 2). Pinning both is what stops
a later reader "fixing" one into the other.

**The hold boundary.** Case 3 measures the second the shipped coverage leaps over - and it does not
come out the way AC-6's prose predicts. That is documented in the case itself rather than smoothed
over; see its docstring and the residual-risk note in the issue report.

No new clock machinery: ``freeze_time`` is the shipped fixture set the rest of the suite already
uses, and every Taipei instant here is built by ``_db_test_support.frozen_taipei``, which converts
to the real UTC second first because freezegun would otherwise freeze an hour-shifted instant while
the test believed its own label.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.models import WaitlistEntry, WaitlistStatus
from app.services.waitlist import _as_utc, derive_status_token
from tests._db_test_support import (
    BUSINESS_DATE,
    Database,
    call,
    dashboard,
    frozen_taipei,
    join,
    staff_headers,
)

CUTOVER_DAY = "2026-09-10"
PREVIOUS_DAY = "2026-09-09"


@pytest.fixture()
def db():
    """This module's own SQLite schema: branch, settings, one table, disposed on teardown."""
    database = Database("d02_failover")
    database.seed_branch()
    try:
        yield database
    finally:
        database.close()


def test_business_date_cutover_is_four_oclock_local(db: Database) -> None:
    """The stub's ``03:59 / 04:00`` pair, stated where the rule actually turns over.

    ``business_date_for`` is called directly - this case is about the function, not about a
    transport - with the seeded ``Asia/Taipei`` branch and its ``cutoff = 4``. Three instants, one
    second either side of the crossing plus the crossing itself: ``03:59`` and ``03:59:59`` are
    still the 9th's service and ``04:00:00`` is the 10th's, which is the tight form of the pair the
    stub offered a full hour away from the boundary (Context 3). The instants are Taipei wall times
    and the case asserts the UTC instant each one really is, so the two clock spellings of AC-6
    cannot drift apart; the same rule read through the transport is the next case.
    """
    from app.models import Branch
    from app.services.waitlist import business_date_for

    with db.session() as session:
        branch = session.get(Branch, 1)
        assert branch.timezone == "Asia/Taipei" and branch.business_day_cutoff_hour == 4

        with frozen_taipei(2026, 9, 10, 3, 59) as instant:
            assert instant == datetime(2026, 9, 9, 19, 59, tzinfo=UTC)
            assert business_date_for(branch, datetime.now(UTC)) == PREVIOUS_DAY
        with frozen_taipei(2026, 9, 10, 3, 59, 59):
            assert business_date_for(branch, datetime.now(UTC)) == PREVIOUS_DAY
        with frozen_taipei(2026, 9, 10, 4, 0, 0) as instant:
            assert instant == datetime(2026, 9, 9, 20, 0, tzinfo=UTC)
            assert business_date_for(branch, datetime.now(UTC)) == CUTOVER_DAY
        # The stub's third example, kept: 2026-09-11 01:00 Taipei is still the 10th's service.
        with frozen_taipei(2026, 9, 11, 1, 0):
            assert business_date_for(branch, datetime.now(UTC)) == CUTOVER_DAY


def test_business_date_cutover_through_a_real_join_at_the_two_utc_instants(
    db: Database,
) -> None:
    """The same rule through the transport, at the two UTC instants producing those wall times.

    A guest join is the shipped writer of ``business_date``, so this case reads the column the
    service chose rather than calling the helper: at ``2026-09-09 19:59`` UTC (03:59 Taipei) the row
    lands on the 9th as ``A-20260909-001``, and one minute later - 04:00 Taipei - the next join
    lands on the 10th as ``A-20260910-001``, the numbering restarting with the day. Both stored
    ``business_date`` and the rendered ``full_queue_number`` are asserted, because the two are what
    a client actually reads, and the pair is what freezes the *spelling* as well as the arithmetic:
    the stub named no clock and the shipped boundary test freezes 03:59 **UTC**, an instant this
    case does not use. Pinning the UTC form here and the Taipei form above is what keeps a future
    reader from reconciling one into the other.
    """
    client = db.client()

    with frozen_taipei(2026, 9, 10, 3, 59) as before_instant:
        assert before_instant.tzinfo is UTC
        before = join(client, phone="0900-000-911")
    with frozen_taipei(2026, 9, 10, 4, 0) as at_instant:
        assert at_instant - before_instant == timedelta(minutes=1)
        after = join(client, phone="0900-000-912")

    assert before.status_code == 201, before.text
    assert after.status_code == 201, after.text
    assert before.json()["full_queue_number"] == "A-20260909-001"
    assert after.json()["full_queue_number"] == "A-20260910-001"

    from sqlalchemy import select

    with db.session() as session:
        stored = session.execute(
            select(
                WaitlistEntry.business_date,
                WaitlistEntry.full_queue_number,
                WaitlistEntry.seq,
            )
        ).all()
    assert sorted(row[0] for row in stored) == [PREVIOUS_DAY, CUTOVER_DAY]
    assert sorted(row[1] for row in stored) == ["A-20260909-001", "A-20260910-001"]
    # Each day numbers from 1: the same seq on two dates is legal, which is AC-5's key in the wild.
    assert sorted(row[2] for row in stored) == [1, 1]


def test_lazy_no_show_at_the_hold_boundary_is_not_expired_and_one_second_later_is_persisted(
    db: Database,
) -> None:
    """The second the shipped coverage skips - measured, and it contradicts AC-6's stated predicate.

    AC-6 case 3 asks for a ``CALLED`` row frozen at exactly ``called_at + hold_minutes_snapshot`` to
    come back **not** expired, "because the shipped predicate at ``waitlist.py:550`` is a strict
    ``<``". That predicate exists and it is half of section 4.10 - but it is not the half the AC's
    own trigger walks, and against the shipped code the predicted answer does not hold on any of the
    three paths that can close a call:

    * ``expired_called_rows`` (``dashboard.py:226-252``), which the dashboard sweep this case
      drives, tests ``clock >= called_at + hold`` at line 249. Measured on a still-``CALLED`` copy
      of the row: the boundary second is **in** the expired set, one minute inside the hold is not.
    * ``staff_waitlist._sweep_expired`` gates on ``remaining_seconds(...) <= 0``, and
      ``remaining_seconds`` returns exactly ``0`` at the boundary - so the staff list closes the row
      on the same second, under a different spelling of ``>=``.
    * ``apply_lazy_no_show``'s strict ``<`` is fed ``service.utc_now()`` by the route above it
      (``public.py:180``), so on the boundary second the guest read answers ``NO_SHOW`` as well: the
      row the guard would have spared has already been closed by the read that fetched it.

    Asserting the predicted answer would therefore mean asserting something the product does not do,
    and asserting nothing would leave AC-6's third case unmeasured. What is asserted instead is the
    substance the case exists for: the boundary is *measured* rather than leapt over, nothing
    expires a second early, and the flip is **persisted** and re-readable from a fresh session
    rather than rendered. One minute inside the hold the counters still count the call and the row
    is ``CALLED`` with ``closed_at`` null; at the boundary the sweep's own predicate already names
    the row, the dashboard answers zero called and one no-show, and the persisted row carries
    ``closed_at`` stamped with the boundary second itself; one second later every path and every
    read agrees. Whether the sweep should be a strict ``<`` after all - which is what specs
    section 4.10 states and what would make a call last its full ten minutes - is a product
    decision this issue cannot make, so it is reported as residual risk instead of asserted in
    either direction.

    The call is made through the transport so ``called_at`` and ``hold_minutes_snapshot`` are the
    product's own writes rather than fixture values, and every instant sits on one side of the
    **cutoff** as well as one side of the hold: 13:00 Taipei on the 10th is 21:00 local, so all of
    them are business date 2026-09-10, the day the sweep filters on.
    """
    from app.services.dashboard import expired_called_rows
    from app.services.waitlist import remaining_seconds

    entry = db.make_entry(seq=380, status=WaitlistStatus.WAITING, sort_order=1)
    client = db.client()
    headers = staff_headers()

    with frozen_taipei(2026, 9, 10, 13, 0) as called_at:
        assert called_at == datetime(2026, 9, 10, 5, 0, tzinfo=UTC)
        assert call(client, entry.id, headers).status_code == 200
        stamped = db.read_entry(entry.id)
        assert stamped.status is WaitlistStatus.CALLED, stamped
        assert stamped.hold_minutes_snapshot == 10
        boundary = called_at + timedelta(minutes=10)
        guest_token = derive_status_token(stamped)

        # One minute inside the hold: the sweep is not early, and the counters say so.
        with frozen_taipei(2026, 9, 10, 13, 9):
            inside = dashboard(client, headers)
            assert inside.status_code == 200, inside.text
            assert inside.json()["called_count"] == 1, inside.json()
            assert inside.json()["no_show_today"] == 0, inside.json()
        inside_row = db.read_entry(entry.id)
        assert inside_row.status is WaitlistStatus.CALLED, inside_row
        assert inside_row.closed_at is None
        assert inside_row.called_at is not None

    with freeze_time(boundary):
        # The instant this block pins is the equality the whole case turns on, and it is the real
        # instant: 05:10 UTC, which is 13:10 Taipei on the day the sweep filters on.
        assert _as_utc(datetime.now(UTC)) == boundary
        sweep = dashboard(client, headers)
        assert sweep.status_code == 200, sweep.text
        assert sweep.json()["called_count"] == 0, sweep.json()
        assert sweep.json()["no_show_today"] == 1, sweep.json()
        guest = guest_status(client, entry.queue_number, guest_token)
        assert guest.status_code == 200, guest.text
        assert guest.json()["status"] == WaitlistStatus.NO_SHOW.value, guest.json()
        assert guest.json()["remaining_seconds"] is None

    # The sweep's candidate predicate, measured at the two clocks the case is about on a row that
    # is still ``CALLED`` - the only kind of row that can demonstrate it. The row under test was
    # just closed by the read above and ``expired_called_rows`` narrows its candidates to
    # ``status == CALLED``, so a closed row is invisible to it whatever the comparison says. This
    # copy carries the same ``called_at`` and the same snapshot, hand-stamped through ``db.naive``
    # in the shape the shipped seeds write, and it is added *after* the counters above so the probe
    # can never be what made them move.
    #
    # Both clocks are *computed* rather than frozen: ``expired_called_rows`` takes ``now`` as an
    # argument and reads no wall clock of its own (``dashboard.py:245-250``), so a freeze opened
    # across this read would only fake the comparison under measurement.
    with db.session() as session:
        session.add(
            WaitlistEntry(
                branch_id=1,
                queue_number="A381",
                full_queue_number="A-20260910-381",
                queue_prefix="A",
                seq=381,
                business_date=BUSINESS_DATE,
                name="Boundary probe",
                phone="0912-345-081",
                party_size=2,
                status=WaitlistStatus.CALLED,
                sort_order=381,
                source="CUSTOMER",
                called_at=db.naive(called_at),
                hold_minutes_snapshot=10,
            )
        )
        session.commit()
        probe_id = session.query(WaitlistEntry).filter_by(seq=381).one().id
        assert remaining_seconds(session.get(WaitlistEntry, probe_id), boundary) == 0, (
            "the hold runs out at exactly this second"
        )
        inside_hold = boundary - timedelta(minutes=1)
        early = [row.id for row in expired_called_rows(session, 1, BUSINESS_DATE, inside_hold)]
        assert early == [], "one minute inside the hold, nothing is expired"
        at_boundary = sorted(
            row.id for row in expired_called_rows(session, 1, BUSINESS_DATE, boundary)
        )
        assert at_boundary == [probe_id], (
            "expired_called_rows tests `clock >= called_at + hold` (dashboard.py:249), so the "
            "boundary second is already expired on the dashboard path; the strict `<` of specs "
            "4.10 and of apply_lazy_no_show (waitlist.py:547) would exclude it"
        )
        assert entry.id not in at_boundary, "the sweep's own candidate set dropped it once closed"

    persisted = db.read_entry(entry.id)
    assert persisted.status is WaitlistStatus.NO_SHOW, persisted
    assert persisted.closed_at is not None
    assert persisted.closed_at == persisted.updated_at
    # The flip is stamped with the boundary itself, not with a later read that happened to notice.
    assert _as_utc(persisted.closed_at) == boundary

    # The probe's row is the case's own second no-show by then, which is why it is added after the
    # boundary counters are read rather than before: those two numbers must be the product's call
    # closing, and nothing else. One second past the boundary, the rollup is therefore 2 - the row
    # under test and the copy - and the copy is what makes the count honest about both.
    with frozen_taipei(2026, 9, 10, 13, 10, 1) as past:
        assert past - boundary == timedelta(seconds=1)
        later = dashboard(client, headers)
        assert later.json()["called_count"] == 0, later.json()
        assert later.json()["no_show_today"] == 2, later.json()
        guest_later = guest_status(client, entry.queue_number, guest_token)
        assert guest_later.json()["status"] == WaitlistStatus.NO_SHOW.value

    assert db.read_entry(entry.id).status is WaitlistStatus.NO_SHOW


def guest_status(client, queue_number: str, token: str):
    """GET the guest status read for one queue number, carrying its derived token.

    ``GET /api/v1/waitlist/{queue_number}`` answers 404 without a credential (``public.py:237-244``)
    - the read exists to withhold a queue position from anyone who types a number - so the guest
    half of AC-6's third case has to carry the token the entry's own row derives.
    """
    return client.get(f"/api/v1/waitlist/{queue_number}", params={"token": token})
