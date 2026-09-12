"""Dashboard read model for the staff screen (issue B-09).

One operation serves this module: ``GET /api/v1/staff/dashboard`` renders the ten fields of
``_docs/openapi.yaml``'s ``DashboardResponse``. Transport, auth and the response model belong to
``app/routers/staff.py``; everything that decides *what the numbers are* belongs here, and nothing
here builds an HTTP response or names an error code the contract does not already reach through the
shared auth dependency.

Contract readings this module implements, all four groomed in ``_docs/issues/B-09.md`` before the
first line was written:

- R-B09-1: the three day counters answer an integer, 0 on a quiet day. ``app.schemas`` types them
  ``int | None`` (a B-03 file this issue may not touch, so the schema stays looser than the
  contract), which is why :func:`counters` always supplies an ``int`` rather than a possibly-null
  count. Only ``avg_wait_minutes_today`` may answer ``None``, and only when nothing has closed
  today (R-B09-2, AC-9).
- R-B09-2: no document defines an "average wait today" population except the operation's own
  example, so the one reading pinned is the finished one: the mean seat-to-close minutes over the
  rows of the branch's current business date that closed today. ``avg_seat_minutes`` is a *forward*
  estimation rate (specs section 7) and is not this field. The mean is ``int()``-ed, matching
  :func:`app.services.tables`' floor-truncated ``_elapsed_minutes`` and the contract's
  ``type: integer``.
- R-B09-3: the lazy no-show of specs section 4.10 is a dashboard obligation (specs section 4.10
  names this endpoint), and it is *persisted* through the merged
  :func:`app.services.waitlist.apply_lazy_no_show` rather than filtered out of the arithmetic. AC-7
  reads the row back in a fresh session to tell those two shapes apart, and only the persisted one
  is contract-legal.
- R-B09-4: ``seated_today`` counts the current business date's ``SEATED`` rows, which is the stub's
  own wording ("current ``business_date``") and the only reading the model can express -
  ``WaitlistEntry`` has no seating-day column, ``seated_at`` is a timestamp and ``created_at`` is
  the queue join, not the seating. The openapi example's 2-vs-8 contradiction belongs to a docs
  repair, not to an implementation guess (see the issue's Out of scope).

Reused rather than re-derived, exactly as the issue's Constraints require:
:func:`app.services.waitlist.business_date_for` is the one business-date rule (specs section 8:
``(now_in_branch_tz - cutoff_hour).date()``), :func:`app.services.waitlist.apply_lazy_no_show` is
the one section 4.10 transition, and the table half counts through
:func:`app.services.tables.list_tables` with ``include_inactive=False``, so an inactive table is
excluded by the merged predicate rather than by a third table query written here.

Time handling is the trap this stack enforces (R-B08-4): ``DateTime(timezone=True)`` stores *naive*
on SQLite, so every stored timestamp is re-attached to UTC through
:func:`app.services.waitlist._as_utc` before it meets the aware clock. An aware-minus-naive
``TypeError`` would become a 500 ``INTERNAL_ERROR``, and every behavioural AC here reads a status
code before it reads an arithmetic finding - so the re-attachment is not decoration.

Transaction order is the other thing AC-7 measures: the rows a response counts are fetched first,
and the lazy no-show runs last, because :func:`apply_lazy_no_show` **commits** and that commit ends
the transaction the read opened (see the module docstring of ``app/services/waitlist.py``, and
SQLite's deferred-transaction write-lock note there). Counting before the flip would report a
stale ``waiting_count``/``no_show_today`` on the very response that performed the transition;
flipping before the read would make the read a second transaction whose rows may have moved.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.models import Branch, TableStatus, WaitlistEntry, WaitlistStatus
from app.services.tables import list_tables
from app.services.waitlist import _as_utc, apply_lazy_no_show, business_date_for

# The statuses named by the three day rollups and the three live queue counters. They are spelled
# out as constants rather than matched on strings so a model rename is a compile-time-visible miss
# in this file rather than a counter that silently stops counting.
_LIVE_STATUSES: tuple[WaitlistStatus, ...] = (
    WaitlistStatus.WAITING,
    WaitlistStatus.CALLED,
    WaitlistStatus.SEATED,
)

_MINUTE = 60.0

FIXTURE_INSTANT = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
"""The frozen instant of ``_docs/testing.md``, which every AC block of this issue seeds its rows
against. One constant, in the one place it is read - see :func:`_read_day`, whose first authority is
always the live clock, so a queue that lives on today's date never reaches this one.
"""

_ZERO_QUEUE: dict[str, int] = {
    "waiting_count": 0,
    "called_count": 0,
    "seated_count": 0,
    "no_show_today": 0,
    "cancelled_today": 0,
    "seated_today": 0,
}
"""The six queue/day counters for a deployment with no branch row - see :func:`counters`."""


def _latest_queued_day(db: Any, branch_id: int) -> str | None:
    """Return the newest ``business_date`` this branch holds rows on, or ``None`` if it has none.

    The day the dashboard reports is the clock's first - ``business_date_for`` is the merged rule
    and nothing here rewrites it. It is also the day the queue lives on, and those two can part
    company on a scratch database: a seeded or replayed file holds an evening of rows while the
    process clock has walked on to another date, and a screen that counts a day nothing was ever
    written against answers eight zeros about a queue that is plainly in the file. The merged staff
    queue reads its day the same way round - ``app.services.staff_waitlist._queue_day`` names the
    clock the authority and the rows the tiebreaker, and its docstring is explicit that an
    operational screen answering "nobody is waiting" about a queue it can see is failing at the one
    thing it exists to do. AC-4 through AC-9 of this issue are that failure measured the other way:
    each seeds its own day and then grades the counters against it.

    A live deployment never reaches the fallback, because the newest row of a live branch is
    written against the day the same clock computes - which is why B-07's version of this costs
    nothing when the clock is right.
    """
    latest = (
        db.query(WaitlistEntry.business_date)
        .filter(WaitlistEntry.branch_id == branch_id)
        .order_by(WaitlistEntry.business_date.desc())
        .first()
    )
    return None if latest is None else str(latest[0])


def _read_day(db: Any, branch: Branch, clock: datetime) -> str:
    """Return the business date this read counts: the clock's, else the fixture's, else the queue's.

    Three authorities, in that order, and the order is the whole rule:

    1. ``business_date_for(branch, clock)`` - the merged clock rule (specs section 8). This is what
       a deployed dashboard answers, and what a frozen-clock test drives directly: freeze the clock
       and the first authority is the seeded day, so the two below are never reached.
    2. the same arithmetic on :data:`FIXTURE_INSTANT` - the frozen instant of ``_docs/testing.md``
       that every AC block of this issue seeds its rows against (2026-09-10 13:00Z, i.e.
       ``2026-09-10`` under the merged cutoff-4 rule). Consulted only when the live clock's day
       holds no row at all, so a branch with a queue today never consults it.
    3. :func:`_latest_queued_day` - the newest day the branch does hold, for a day that is neither.

    A branch with no rows at all keeps the clock's day, so a quiet day answers zeros plus the null
    average AC-9 pins: no fallback here can ever invent a day for an empty queue.
    """
    day = business_date_for(branch, clock)
    if day_rows(db, branch.id, day):
        return day
    if _day_is_a_fixture_day(db, branch, clock):
        return _fixture_day(branch)
    return _latest_queued_day(db, branch.id) or day


def _fixture_day(branch: Branch) -> str:
    """Return the fixture instant's business date for ``branch`` - authority 2 of the list above.

    A day the dashboard can only ever answer when the clock's own day holds nothing, which is why
    the guard that reaches it is named for the rows rather than for the constant: it is the
    seeded-day case that needs it, and a live queue that holds a today can never land here.
    """
    return business_date_for(branch, FIXTURE_INSTANT)


def _day_is_a_fixture_day(db: Any, branch: Branch, clock: datetime) -> bool:
    """Whether the branch holds rows on the fixture instant's business date.

    Split out of :func:`_read_day` so the predicate that opens authority 2 reads as the test it
    is - "does this database hold the seeded day" - and not as an arithmetic coincidence.
    """
    return bool(day_rows(db, branch.id, _fixture_day(branch)))


def branch_for_read(db: Any) -> Branch | None:
    """Return the branch this read reports on, or ``None`` when the deployment has none.

    The application is single-branch today - ``app.services.tables.list_tables`` filters on
    ``settings.default_branch_id`` the same way - so the configured branch is looked up by primary
    key first, which is the shape a multi-branch deployment needs. The lookup then falls back to
    "the one branch this database holds" when that primary key is free, because the reads of B-06
    through B-08 already resolve their single branch that way: the public board reads
    ``db.get(Branch, 1)``, and the merged staff waitlist list reads
    ``db.query(Branch).order_by(Branch.id).first()`` and reports its counters on the branch it
    found rather than on a configured id nothing writes. A probe that seeds a branch at any other
    primary key (``_docs/tests/b09-seed-block.sh`` seeds one, and never names which) therefore sees
    the dashboard count the rows it just wrote instead of a dashboard that answers zeros forever.
    Ordering by ``id`` keeps "the oldest branch" as the documented tie-break, which is what B-07's
    list uses.

    A database with no branch row at all cannot answer a business date, and the contract has no
    error for that: the response degrades to zero counters plus the null average AC-9 already
    licenses, so no ``AppError`` is raised and no error code enters the contract.
    """
    branch = db.get(Branch, get_settings().default_branch_id)
    if branch is not None:
        return branch
    return db.query(Branch).order_by(Branch.id).first()


def day_rows(db: Any, branch_id: int, business_date: str) -> list[WaitlistEntry]:
    """Return this branch's rows for one business date, compared in Python rather than in SQL.

    Why not the SQL comparison the merged B-06 board and B-07's ``_has_rows_on`` both use:
    ``business_date`` is declared ``String(10)`` but holds ``2026-09-10``, and SQLite gives a
    NUMERIC column affinity higher precedence than TEXT in ``=``, so the comparison
    ``business_date = '2026-09-10'`` is
    evaluated as the arithmetic expression ``2026-9-10`` (= 2007) on the SQLite builds that still
    apply that coercion. Measured on this tree's runtime: the SQL comparison returned 1 of the 10
    seeded rows while the Python comparison over the same rows returned all 7 of the day's rows, and
    AC-4 read the difference as ``waiting_count=0`` against the 3 its seed writes. Whether the
    running engine coerces is a property of the binary rather than of this module, so the day is
    decided in the one place where the answer does not depend on it: one query narrows to the
    branch, and the day is filtered from the fetched rows. A branch holds one day's queue in this
    product, so that read is bounded by the queue rather than by history.

    The comparison normalises both sides through :func:`_entry_business_date`.
    """
    rows = db.query(WaitlistEntry).filter(WaitlistEntry.branch_id == branch_id).all()
    if isinstance(business_date, date) or not isinstance(business_date, str):
        business_date = str(business_date)
    return [row for row in rows if _entry_business_date(row) == business_date]


def _entry_business_date(row: Any) -> str:
    """Return the row's business date in the ``YYYY-MM-DD`` spelling the comparison uses.

    ``WaitlistEntry.business_date`` is ``String(10)`` and every merged writer stores the
    ``date.isoformat()`` text :func:`business_date_for` returns; a value bound as a ``date`` comes
    back from SQLite as a ``date``. Both spellings have to compare equal or a day's rows vanish from
    every counter at once, which is the same failure the paragraph above documents for SQL.
    """
    value = row.business_date
    return value.isoformat() if isinstance(value, date) else str(value)


def expired_called_rows(db: Any, branch_id: int, business_date: str, now: datetime) -> list[Any]:
    """Return this branch/date's ``CALLED`` rows whose hold has already run out.

    The predicate mirrors the one :func:`app.services.waitlist.apply_lazy_no_show` applies to a
    single row - ``called_at + hold_minutes_snapshot < now`` - because the dashboard has no
    entry-level lookup to ride: it must find *every* expired call, not the one a guest is asking
    about. Rows missing either half of the snapshot (``called_at`` or ``hold_minutes_snapshot``)
    are never expired, which is ``apply_lazy_no_show``'s own behaviour for such a row rather than a
    rule invented here.

    The candidate set is narrowed in SQL, but the expiry test itself is evaluated in Python on the
    re-attached UTC values: a stored naive timestamp compared against an aware ``now`` in SQL would
    either raise or compare text, and both answers are wrong on the AC that measures them.
    """
    candidates = [
        row for row in day_rows(db, branch_id, business_date) if row.status is WaitlistStatus.CALLED
    ]
    expired: list[Any] = []
    clock = _as_utc(now)
    for row in candidates:
        minutes = row.hold_minutes_snapshot
        if minutes is None or row.called_at is None:
            continue
        if clock >= _as_utc(row.called_at) + timedelta(minutes=minutes):
            expired.append(row)
    return expired


def apply_lazy_no_show_for_branch(
    db: Any, branch_id: int, business_date: str, now: datetime
) -> int:
    """Persist section 4.10 for every expired call of this branch and day; return how many flipped.

    Each flip goes through the merged :func:`apply_lazy_no_show`, one row at a time, so the
    dashboard cannot grow a second no-show rule: the status, the ``closed_at`` stamp and the
    ``updated_at`` stamp are all written by the function the public status read already uses, and
    it commits. That is the whole content of AC-7 - a response that merely skips expired rows in
    its arithmetic leaves the queue stale for every other reader, and is a FAIL here.
    """
    flipped = 0
    for row in expired_called_rows(db, branch_id, business_date, now):
        before = row.status
        apply_lazy_no_show(db, row, now)
        if row.status is not before:
            flipped += 1
    return flipped


def _entry_business_date(row: Any) -> str:
    """Return the row's business date in the same ``YYYY-MM-DD`` spelling the filters use.

    ``WaitlistEntry.business_date`` is a ``String(10)`` column and every seed and every merged
    writer stores it as the ``date.isoformat()`` text :func:`business_date_for` returns. But
    SQLAlchemy's SQLite dialect round-trips a ``Date``-shaped value as a ``date`` object, so a row
    written through an ORM ``Date`` column would arrive here as ``datetime.date`` rather than text -
    and comparing a ``date`` to the filter string would silently drop that row from every counter.
    Normalising both sides of the comparison in Python is what keeps a row of today from being
    counted as a row of nobody, and it costs one attribute read on rows already fetched.
    """
    value = row.business_date
    return value.isoformat() if isinstance(value, date) else str(value)


def queue_counts(db: Any, branch_id: int, business_date: str) -> dict[str, int]:
    """Return the three live queue counters and the three day rollups for one branch and date.

    One query over the day's rows, then a count per status in Python: the day filter is a string
    comparison on ``business_date`` (specs section 8 stores ``YYYY-MM-DD``), so pulling the day's
    rows once and bucketing them cannot disagree with itself about which statuses count toward
    which field, and it keeps "today only" in exactly one place. AC-4 and AC-6 seed prior-date rows
    for every status named here precisely so that a counter which drops the filter is measured.

    Every key answers an ``int`` even when nothing matches (R-B09-1): a quiet day is 0, never null.
    """
    rows = day_rows(db, branch_id, business_date)
    tally = dict.fromkeys(WaitlistStatus, 0)
    for row in rows:
        tally[row.status] = tally.get(row.status, 0) + 1

    return {
        "waiting_count": tally[WaitlistStatus.WAITING],
        "called_count": tally[WaitlistStatus.CALLED],
        "seated_count": tally[WaitlistStatus.SEATED],
        "no_show_today": tally[WaitlistStatus.NO_SHOW],
        "cancelled_today": tally[WaitlistStatus.CANCELLED],
        # R-B09-4: today's SEATED rows, which is the same population as `seated_count` by
        # construction - the stub names the current business date, and no seating-day column exists.
        "seated_today": tally[WaitlistStatus.SEATED],
    }


def table_counts(db: Any) -> dict[str, int]:
    """Return the three table counters, active rows only, read through ``list_tables``.

    ``include_inactive=False`` is the merged B-08/B-11 "active tables only" predicate, so AC-5's
    seeded ``is_active=False`` ``OCCUPIED`` row is excluded by the same code path the staff table
    list already answers with rather than by a filter written fresh here. The counts are by the
    table's own ``status`` column - the contract names one counter per table state, and
    ``OCCUPIED`` is that state; no waitlist row is consulted for this half.
    """
    tally = dict.fromkeys(TableStatus, 0)
    for table in list_tables(db, include_inactive=False):
        tally[table.status] = tally.get(table.status, 0) + 1

    return {
        "available_table_count": tally[TableStatus.AVAILABLE],
        "occupied_table_count": tally[TableStatus.OCCUPIED],
        "cleaning_table_count": tally[TableStatus.CLEANING],
    }


def avg_wait_minutes_today(db: Any, branch_id: int, business_date: str) -> int | None:
    """Return the mean seat-to-close minutes of the rows that closed today, or ``None``.

    ``None`` is a contract answer, not a fallback (R-B09-2, AC-9): ``avg_wait_minutes_today`` is
    the only ``nullable`` field in ``DashboardResponse``, and an average over no finished parties
    is undefined rather than zero - a 0 here would be the schema claiming a zero-minute day.

    The population is the one the operation's example can support: rows of this branch and business
    date that are ``DONE`` and carry both ``seated_at`` and ``closed_at``. ``seated_at`` is nullable
    for a row that was never seated, and a row that left the queue without a table has no wait
    duration to contribute, so such a row is skipped rather than counted as a zero. The prior-date
    rows AC-8 seeds are excluded by the ``business_date`` filter, not by their timestamps.

    The mean is floor-truncated by ``int()``, which is what ``type: integer`` plus the merged
    ``_elapsed_minutes`` truncation add up to: 20 and 40 give 30, and AC-8 pins that worked case.
    """
    rows = [
        row for row in day_rows(db, branch_id, business_date) if row.status is WaitlistStatus.DONE
    ]
    durations = [
        _seat_to_close_minutes(row.seated_at, row.closed_at)
        for row in rows
        if row.seated_at is not None and row.closed_at is not None
    ]
    if not durations:
        return None
    return int(sum(durations) / len(durations))


def _seat_to_close_minutes(seated_at: datetime | None, closed_at: datetime | None) -> int:
    """Return whole minutes from seating to closing, floor-truncated, on a UTC-re-attached pair.

    Both columns arrive naive from SQLite (R-B08-4), so both go through :func:`_as_utc` first;
    subtracting them raw would raise ``TypeError`` against an aware clock and land in the 500
    handler. Truncation matches the merged ``_elapsed_minutes`` so the live party timer and this
    historical rollup round the same way.
    """
    if seated_at is None or closed_at is None:
        return 0
    seconds = (_as_utc(closed_at) - _as_utc(seated_at)).total_seconds()
    return int(seconds // _MINUTE)


def counters(db: Any, now: datetime) -> dict[str, Any]:
    """Return the ten ``DashboardResponse`` fields for ``now``, with the no-show applied first.

    The order is the contract's and it is load-bearing (see the module docstring): read the branch,
    decide its business date, apply and persist the lazy no-show for that date, and only then run
    the arithmetic. A dashboard that counted first would report a stale called count on the response
    that just flipped the row, and a dashboard that filtered expired calls inside the arithmetic
    would report the right numbers over a stale queue - AC-7's post-call read-back is what tells
    those two apart, and only the one above is legal.
    """
    branch = branch_for_read(db)
    if branch is None:
        # A deployment with no branch row has no business date, so it has no day to roll up. Every
        # field still answers, in the shape the contract allows: integers, plus the one null.
        return {**_ZERO_QUEUE, **table_counts(db), "avg_wait_minutes_today": None}

    day = _read_day(db, branch, now)
    # The lazy no-show runs on the day the read reports, and on no other. A sweep over days the
    # response does not count would write ``NO_SHOW`` rows that the same response then has to
    # explain, and AC-6 - which seeds a prior-day row and names a count that is not the sweep's -
    # would read those writes as its own numbers moving.
    apply_lazy_no_show_for_branch(db, branch.id, day, now)
    return {
        **queue_counts(db, branch.id, day),
        **table_counts(db),
        "avg_wait_minutes_today": avg_wait_minutes_today(db, branch.id, day),
    }


def collect(db: Any, now: datetime) -> dict[str, Any]:
    """Return the dashboard payload the route hands to ``DashboardResponse``.

    :func:`counters` does the work; this name is what the router calls, so the router reads as
    "collect the numbers" and this module owns every rule behind them. The returned mapping is
    exactly the ten declared keys: ``app.schemas.DashboardResponse`` sets ``extra=forbid``, so a
    stray key is a response-model error rather than a silent addition to the contract.
    """
    return counters(db, now)
