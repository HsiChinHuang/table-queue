"""Waitlist business rules for the guest-facing (public) surface - B-06.

Transport lives in ``app/routers/public.py``; this module owns the rules and never builds an HTTP
response: business date and ``seq`` allocation (specs.md section 8), the duplicate-phone rule
(section 7), ``waiting_ahead`` and ``estimated_wait_minutes`` (ruling R-B06-3), the hold countdown
and the lazy ``NO_SHOW`` transition (section 4.10), guest cancel (section 4.7) and the derived
``status_token`` (R-B06-4).

Contract rules that bind every function here:

- Time is never read from the wall clock inside a rule. ``utc_now()`` is the module-level clock
  seam; routers inject ``app.dependencies.get_now`` and tests inject ``fixed_now`` or freezegun
  (testing.md section 5). Freezegun patches ``datetime.datetime`` itself, so calling
  ``datetime.now`` from this function is what makes a freeze observable.
- Every failure is an ``AppError`` whose code is listed in ``_docs/specs.md`` section 11
  (``BRANCH_NOT_FOUND``, ``WAITLIST_CLOSED``, ``WAITLIST_DUPLICATE_PHONE``, ``WAITLIST_NOT_FOUND``,
  ``WAITLIST_INVALID_STATUS``). B-04's handler renders the envelope; nothing here assembles one.
- A caller that knows the branch primary key is answered ``BRANCH_NOT_FOUND`` for an unknown branch.
  A caller that only knows a queue number is answered ``WAITLIST_NOT_FOUND`` - a bad credential must
  not disclose whether the branch, the day or the entry is what is missing.
- A read may persist (the lazy no-show), but only once every row that read still needs has been
  fetched. SQLite's default deferred transaction hands the write lock to the first write statement
  of a transaction, so a mid-request commit would make a later SELECT fail; the lazy transition is
  therefore always the last database step of a request.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.errors import AppError
from app.models import Branch, WaitlistEntry, WaitlistStatus
from app.models import Settings as SettingsModel

ACTIVE_STATUSES: tuple[WaitlistStatus, ...] = (
    WaitlistStatus.WAITING,
    WaitlistStatus.CALLED,
    WaitlistStatus.SEATED,
)
"""Statuses that hold a phone, so a new join is refused while one of them is live (section 7)."""

LEFT_WAITING_STATUSES: tuple[WaitlistStatus, ...] = (
    WaitlistStatus.CALLED,
    WaitlistStatus.SEATED,
    WaitlistStatus.DONE,
    WaitlistStatus.NO_SHOW,
    WaitlistStatus.CANCELLED,
)
"""Statuses an entry can hold once it has left ``WAITING``: the ``recent_calls`` pool."""

CANCELABLE_STATUSES: tuple[WaitlistStatus, ...] = (
    WaitlistStatus.WAITING,
    WaitlistStatus.CALLED,
)
"""States a guest may still leave from; anything else is ``WAITLIST_INVALID_STATUS``."""

_DIGITS = re.compile(r"\D+")

# ---------------------------------------------------------------------------
# Clock seam
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time.

    The only place this module reads a clock. Freezegun patches ``datetime.datetime`` itself, so
    ``datetime.now`` is looked up on that module at call time and a frozen test sees the frozen
    value while production sees the real time - through this one function.
    """
    return datetime.now(UTC)


def _ensure_aware(value: datetime) -> datetime:
    """Treat a naive timestamp as UTC, since section 13 stores every timestamp in UTC.

    SQLite's DATETIME column round-trips without an offset, so a value read back from the database
    (or written by a seed row or an earlier issue's fixture) arrives naive while ``utc_now()`` is
    aware. Without this the subtraction behind the countdown would raise ``TypeError``.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc(value: datetime) -> datetime:
    """Return the same instant as ``_ensure_aware``, expressed in UTC."""
    return _ensure_aware(value).astimezone(UTC)


def _stamp(value: Any) -> datetime:
    """Return a comparable UTC timestamp for a nullable column, oldest possible when absent."""
    return _as_utc(value) if isinstance(value, datetime) else datetime.min.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Phone helpers
# ---------------------------------------------------------------------------


def normalize_phone(phone: str) -> str:
    """Return the digits of a phone number and nothing else (section 6, "normalized digits").

    ``0900-000-001`` and ``0900000001`` therefore collide, which is what the duplicate check needs;
    separators are only ever preserved in what the caller typed back.
    """
    return _DIGITS.sub("", phone or "")


def mask_phone(phone: str) -> str:
    """Mask the middle three digits of a phone number, keeping the caller's separators.

    ``0900-000-001`` becomes ``0900-***-001`` and ``0900000001`` becomes ``0900***001``, which is
    the
    contract example. Short or malformed input is masked in full rather than leaked.
    """
    digits = normalize_phone(phone)
    if len(digits) < 7:
        return "*" * len(digits)
    head = digits[: len(digits) - 6]
    tail = digits[-3:]
    return f"{head}{'*' * (len(digits) - len(head) - len(tail))}{tail}"


def phone_last3(phone: str) -> str:
    """Return the credential form of a phone: its last three normalized digits."""
    return normalize_phone(phone)[-3:]


# ---------------------------------------------------------------------------
# Derived status token (R-B06-4)
# ---------------------------------------------------------------------------


def _entry_created_at(entry: WaitlistEntry) -> str:
    """Return the ISO text of ``created_at`` exactly as the stored row spells it.

    The token input must be the stored value: re-formatting through UTC would add an offset a naive
    SQLite round-trip does not carry, and the token would no longer be reproducible from the columns
    AC-8 reads back.
    """
    created = entry.created_at
    return created.isoformat() if isinstance(created, datetime) else str(created)


def derive_status_token(entry: WaitlistEntry) -> str:
    """Return an entry's status token: the first 16 hex characters of a SHA-256 over stored data.

    ``WaitlistEntry`` (B-02, merged) has no ``status_token`` column, so the token is recomputed from
    ``entry.id | entry.phone | entry.created_at.isoformat()`` rather than stored (R-B06-4). That
    triple is stable for a stored row, which is what lets a later request re-derive and check the
    credential, and it keeps the token a different secret from the ``phone_last3`` credential AC-10
    checks.
    """
    raw = f"{entry.id}|{entry.phone}|{_entry_created_at(entry)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def status_token_matches(entry: WaitlistEntry, token: str | None) -> bool:
    """Compare a submitted token with the derived one, tolerating case and stray whitespace."""
    if not token:
        return False
    return token.strip().lower() == derive_status_token(entry)


def status_url(entry: WaitlistEntry) -> str:
    """Return the guest status page path for an entry, carrying its token (openapi example)."""
    return f"/status/{entry.queue_number}?token={derive_status_token(entry)}"


# ---------------------------------------------------------------------------
# Branch and settings
# ---------------------------------------------------------------------------


def get_branch_or_404(db: Any, branch_id: int) -> Branch:
    """Return the branch row or raise ``BRANCH_NOT_FOUND`` (section 11)."""
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise AppError("BRANCH_NOT_FOUND")
    return branch


def get_settings_or_500(db: Any, branch_id: int) -> SettingsModel:
    """Return the branch's settings row, or raise ``INTERNAL_ERROR`` when there is none.

    ``openapi.yaml`` declares no 404 for this operation and section 11 explicitly keeps
    ``SETTINGS_NOT_FOUND`` outside the contract, so a missing settings row is a broken deployment
    rather than something a guest did wrong.
    """
    row = db.query(SettingsModel).filter(SettingsModel.branch_id == branch_id).first()
    if row is None:
        raise AppError("INTERNAL_ERROR")
    return row


def as_utc(value: Any) -> datetime | None:
    """Return a stored timestamp as an aware UTC datetime, or ``None`` when the column is empty.

    The response models declare these columns as plain ``datetime``, and SQLite hands them back
    naive. A router building a response therefore normalises through here instead of passing a raw
    column, which keeps "a stored timestamp is UTC" in one place rather than in every field of every
    model.
    """
    return _as_utc(value) if isinstance(value, datetime) else None


# ---------------------------------------------------------------------------
# Entry lookups and credentials
# ---------------------------------------------------------------------------


def find_entry_by_token(db: Any, queue_number: str, token: str) -> WaitlistEntry:
    """Return the entry with this queue number whose derived token matches, or 404.

    A derived token belongs to a row rather than to a day, so every row carrying the number is a
    candidate - which is also what makes a token work after midnight. Newest first, so a guest who
    re-joined under the same number is looking at the entry just created.
    """
    rows = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.queue_number == queue_number)
        .order_by(WaitlistEntry.created_at.desc())
        .all()
    )
    for row in rows:
        if status_token_matches(row, token):
            return row
    raise AppError("WAITLIST_NOT_FOUND", message="Waitlist entry not found")


def find_entry_by_tail(db: Any, queue_number: str, last3: str, now: datetime) -> WaitlistEntry:
    """Return today's entry with this number whose phone ends in ``last3``, or 404.

    Section 8: "Guest lookup without token only searches current business_date". The number alone
    does not say which branch owns it, so each branch that carries the number is asked for its own
    current business date - a stale row from the previous day, or a row belonging to a branch whose
    settings row is gone, is simply not the answer.
    """
    rows = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.queue_number == queue_number)
        .order_by(WaitlistEntry.created_at.desc())
        .all()
    )
    for row in rows:
        if phone_last3(row.phone) != last3:
            continue
        branch = db.get(Branch, row.branch_id)
        if branch is None:
            continue
        if row.business_date != business_date_for(branch, now):
            continue
        return row
    raise AppError("WAITLIST_NOT_FOUND", message="Waitlist entry not found")


def find_entry_for_cancel(
    db: Any, queue_number: str, last3: str, now: datetime
) -> WaitlistEntry:
    """Return the entry a phone tail unlocks for cancellation.

    Cancelling needs a live entry, and a live entry belongs to one business date, so the branch
    whose number carries a live row decides the day - falling back to the current-date search when
    the number matches only closed rows, which then answers 404 the way any stale credential does.
    """
    live = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.queue_number == queue_number,
            WaitlistEntry.status.in_(CANCELABLE_STATUSES),
        )
        .order_by(WaitlistEntry.created_at.desc())
        .all()
    )
    for row in live:
        branch = db.get(Branch, row.branch_id)
        if branch is None:
            continue
        if row.business_date != business_date_for(branch, now):
            continue
        if phone_last3(row.phone) == last3:
            return row
    return find_entry_by_tail(db, queue_number, last3, now)


# ---------------------------------------------------------------------------
# Business date and queue-number allocation (section 8)
# ---------------------------------------------------------------------------


def _branch_zone(branch: Branch) -> ZoneInfo:
    """Return the branch's timezone, falling back to the product default for an unusable name."""
    try:
        return ZoneInfo(branch.timezone)
    except Exception:  # noqa: BLE001 - a bad zone name must not take the public board down
        return ZoneInfo("Asia/Taipei")


def business_date_for(branch: Branch, now: datetime) -> str:
    """Return ``YYYY-MM-DD`` for the branch timezone shifted back by its cutoff hour (section 8).

    ``business_date = (now_in_branch_tz - cutoff_hour).date()``: 2026-09-10 21:00 Taipei with cutoff
    4 is ``2026-09-10``, 03:59 Taipei is ``2026-09-09`` and 2026-09-11 01:00 Taipei is
    ``2026-09-10`` - the three boundaries testing.md section 2 names.
    """
    local = _as_utc(now).astimezone(_branch_zone(branch))
    return (local - timedelta(hours=branch.business_day_cutoff_hour)).date().isoformat()


def next_seq(db: Any, branch_id: int, business_date: str, queue_prefix: str) -> int:
    """Return ``max(seq) + 1`` for the branch / business date / prefix triple, starting at 1."""
    top = (
        db.query(WaitlistEntry.seq)
        .filter(
            WaitlistEntry.branch_id == branch_id,
            WaitlistEntry.business_date == business_date,
            WaitlistEntry.queue_prefix == queue_prefix,
        )
        .order_by(WaitlistEntry.seq.desc())
        .first()
    )
    return int(top[0]) + 1 if top is not None else 1


def queue_number_for(prefix: str, seq: int) -> str:
    """Return the display number: prefix plus a three-digit sequence, e.g. ``A001``."""
    return f"{prefix}{seq:03d}"


def full_queue_number_for(prefix: str, business_date: str, seq: int) -> str:
    """Return the globally unique number, e.g. ``A-20260910-001``."""
    return f"{prefix}-{business_date.replace('-', '')}-{seq:03d}"


def next_sort_order(db: Any, branch_id: int) -> int:
    """Return the position after the current tail of this branch's queue.

    A guest joins at the back, so a new entry takes one past the highest ``sort_order`` the branch
    holds on any row, whatever its status. AC-9 depends on this: its rows are seeded in
    ``sort_order`` order, so a join can never land ahead of the guests it is waiting behind.
    """
    top = (
        db.query(WaitlistEntry.sort_order)
        .filter(WaitlistEntry.branch_id == branch_id)
        .order_by(WaitlistEntry.sort_order.desc())
        .first()
    )
    return int(top[0]) + 1 if top is not None else 1


# ---------------------------------------------------------------------------
# Join (section 4.1)
# ---------------------------------------------------------------------------


def active_entry_for_phone(
    db: Any, branch_id: int, business_date: str, normalized_phone: str
) -> WaitlistEntry | None:
    """Return today's live entry holding this phone, or ``None``.

    Uniqueness spans WAITING, CALLED and SEATED only (section 7), and is scoped to one branch
    and
    one business date (ruling R-B06-2). A CANCELLED, NO_SHOW or DONE row releases the phone, which
    is
    lets the same guest join again after cancelling.
    """
    rows = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.branch_id == branch_id,
            WaitlistEntry.business_date == business_date,
            WaitlistEntry.status.in_(ACTIVE_STATUSES),
        )
        .order_by(WaitlistEntry.created_at.asc())
        .all()
    )
    for row in rows:
        if normalize_phone(row.phone) == normalized_phone:
            return row
    return None


def join_waitlist(
    db: Any,
    *,
    branch_id: int,
    name: str,
    phone: str,
    party_size: int,
    note: str | None = None,
    now: datetime | None = None,
) -> WaitlistEntry:
    """Add a guest to the waitlist and return the persisted entry.

    The order is the contract's: the branch must exist, the queue must be open (section 4.1 step 3 -
    a paused queue writes nothing at all, AC-13), the phone must not already hold a place for this
    branch and day (section 7, ruling R-B06-2), and only then are ``seq`` and ``sort_order``
    allocated
    and the row written in this single transaction (section 14, "Duplicate phone checked in
    transaction").

    The row's own ``created_at`` is the injected ``now`` rather than the model's default: the
    business
    date, the ``full_queue_number`` and the derived token all rest on one instant, and letting the
    database clock supply a second one would let a token and a day disagree about when the guest
    joined.
    """
    clock = _ensure_aware(now) if now is not None else utc_now()
    branch = get_branch_or_404(db, branch_id)
    settings = get_settings_or_500(db, branch_id)
    if not settings.is_waitlist_open:
        raise AppError("WAITLIST_CLOSED", message="Waitlist is currently closed")

    digits = normalize_phone(phone)
    day = business_date_for(branch, clock)
    live = active_entry_for_phone(db, branch_id, day, digits)
    if live is not None:
        raise AppError(
            "WAITLIST_DUPLICATE_PHONE",
            message="Phone already on waitlist",
            details={"queue_number": live.queue_number},
        )

    prefix = settings.queue_prefix
    seq = next_seq(db, branch_id, day, prefix)
    entry = WaitlistEntry(
        branch_id=branch_id,
        queue_number=queue_number_for(prefix, seq),
        full_queue_number=full_queue_number_for(prefix, day, seq),
        queue_prefix=prefix,
        seq=seq,
        business_date=day,
        name=(name or "").strip(),
        phone=digits,
        party_size=party_size,
        note=(note or "").strip() or None,
        status=WaitlistStatus.WAITING,
        sort_order=next_sort_order(db, branch_id),
        created_at=clock,
        updated_at=clock,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Status read (section 4.10, ruling R-B06-3)
# ---------------------------------------------------------------------------


def waiting_ahead(db: Any, entry: WaitlistEntry) -> int:
    """Count the ``WAITING`` entries ahead of ``entry`` in its branch and business date.

    "Ahead" is strictly lower ``sort_order``, and only WAITING rows count: a guest already CALLED or
    SEATED in front is being served, not queued. Party size is deliberately not a weight - AC-9 puts
    2, 6 and 1 pax ahead precisely so an implementation that weighted by size could not pass.
    """
    return (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.branch_id == entry.branch_id,
            WaitlistEntry.business_date == entry.business_date,
            WaitlistEntry.status == WaitlistStatus.WAITING,
            WaitlistEntry.sort_order < entry.sort_order,
        )
        .count()
    )


def estimated_wait_minutes(db: Any, entry: WaitlistEntry, ahead: int | None = None) -> int:
    """Return ``waiting_ahead * avg_seat_minutes`` (R-B06-3), with the rate read from settings."""
    count = waiting_ahead(db, entry) if ahead is None else ahead
    settings = get_settings_or_500(db, entry.branch_id)
    return count * settings.avg_seat_minutes


def remaining_seconds(entry: WaitlistEntry, now: datetime) -> int | None:
    """Return the hold countdown for a ``CALLED`` entry, or ``None`` for any other status.

    ``hold_minutes_snapshot * 60`` minus the seconds since ``called_at`` (section 7: "hold_minutes
    change applies to future calls; existing calls use snapshot"). An expired call is already
    answered
    by :func:`apply_lazy_no_show`, which runs first, so a normal read never reports a stale positive
    countdown; the value is not clamped, so the seconds between expiry and the next read still count
    down rather than sticking at 03:00.
    """
    if entry.status is not WaitlistStatus.CALLED:
        return None
    minutes = entry.hold_minutes_snapshot
    if minutes is None or entry.called_at is None:
        return None
    elapsed = (_as_utc(now) - _as_utc(entry.called_at)).total_seconds()
    return int(minutes * 60 - elapsed)


def apply_lazy_no_show(db: Any, entry: WaitlistEntry, now: datetime) -> WaitlistEntry:
    """Flip an expired ``CALLED`` entry to ``NO_SHOW`` and persist it (section 4.10).

    ``called_at + hold_minutes_snapshot < now`` closes the entry with ``closed_at`` and commits,
    because the rule says the backend *sets* the status rather than reporting it on the fly, so the
    next reader - staff list, dashboard, another guest - sees the same truth. Callers must have read
    everything else they need first (module docstring), because the commit ends the transaction that
    SQLite opened for the read.
    """
    if entry.status is not WaitlistStatus.CALLED:
        return entry
    minutes = entry.hold_minutes_snapshot
    if minutes is None or entry.called_at is None:
        return entry
    if _as_utc(now) < _as_utc(entry.called_at) + timedelta(minutes=minutes):
        return entry
    entry.status = WaitlistStatus.NO_SHOW
    entry.closed_at = _as_utc(now)
    entry.updated_at = _as_utc(now)
    db.commit()
    db.refresh(entry)
    return entry


def build_status_payload(db: Any, entry: WaitlistEntry, now: datetime) -> dict[str, Any]:
    """Return the ``WaitlistStatusResponse`` field mapping for one entry.

    Queue number, status, party size, timing and the estimate - no name and no phone (section 15).
    ``hold_minutes`` reports the snapshot the countdown runs on, which is the number the guest was
    told to arrive within, not whatever the setting says today. The lazy no-show is applied last so
    a
    read cannot half-complete.
    """
    row = apply_lazy_no_show(db, entry, now)
    ahead = waiting_ahead(db, row)
    return {
        "queue_number": row.queue_number,
        "status": row.status,
        "party_size": row.party_size,
        "created_at": as_utc(row.created_at),
        "waiting_ahead": ahead,
        "estimated_wait_minutes": estimated_wait_minutes(db, row, ahead),
        # Echo the timestamp whole: the response model re-reads it through the same normalisation
        # the other three timestamps take, so a naive stored value cannot fail validation.
        "called_at": _as_utc(row.called_at) if row.called_at else None,
        "remaining_seconds": remaining_seconds(row, now),
        "hold_minutes": row.hold_minutes_snapshot,
    }


# ---------------------------------------------------------------------------
# Cancel (section 4.7)
# ---------------------------------------------------------------------------


def cancel_entry(db: Any, entry: WaitlistEntry, now: datetime) -> WaitlistEntry:
    """Cancel a live entry as the guest and return the persisted row.

    WAITING and CALLED are cancellable - a CALLED guest confirms in the UI, which is a frontend step
    (section 4.7 step 3), so the endpoint asks for no confirmation flag of its own. Anything already
    closed answers ``WAITLIST_INVALID_STATUS``, the code ``openapi.yaml`` declares for this
    operation,
    so a second cancel is a conflict instead of a second success. ``cancelled_reason`` is CUSTOMER
    because this is the guest-facing path; the staff cancel of B-07 writes STAFF. A table is not
    released here: nothing on this path seats anyone, and table release is B-08's flow.
    """
    clock = _ensure_aware(now) if now is not None else utc_now()
    if entry.status not in CANCELABLE_STATUSES:
        raise AppError("WAITLIST_INVALID_STATUS")
    from app.models import CancelledReason

    entry.status = WaitlistStatus.CANCELLED
    entry.cancelled_reason = CancelledReason.CUSTOMER
    entry.closed_at = clock
    entry.updated_at = clock
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Branch info and board (sections 4.1, 15, ruling R-B06-1)
# ---------------------------------------------------------------------------


def hours_for(branch: Branch) -> str:
    """Return the opening window as ``HH:MM-HH:MM`` (openapi example ``11:00-21:00``).

    An ASCII hyphen rather than the example's en dash: ``_docs/ui.md`` bans the em/en dash form in
    copy this repo generates, and the dash carries no meaning a guest can lose.
    """
    return f"{branch.open_time}-{branch.close_time}"


def branch_info(db: Any, branch_id: int) -> dict[str, Any]:
    """Return the ``PublicBranchResponse`` mapping for a branch (section 4.1 step 2).

    Every value is read from the seeded rows rather than a constant: the restaurant name arrives
    through the branch's relationship and ``is_waitlist_open`` through the settings row, so editing
    either column changes the next response (AC-2 flips the flag and re-reads). The branch ``phone``
    is allowed here because it is the restaurant's own published line, not a guest's mobile.
    """
    branch = get_branch_or_404(db, branch_id)
    settings = get_settings_or_500(db, branch_id)
    return {
        "restaurant_name": branch.restaurant.name,
        "branch_name": branch.name,
        "address": branch.address,
        "phone": branch.phone,
        "open_time": branch.open_time,
        "close_time": branch.close_time,
        "hours": hours_for(branch),
        "is_waitlist_open": settings.is_waitlist_open,
        "timezone": branch.timezone,
    }


def board(db: Any, branch_id: int, now: datetime) -> dict[str, Any]:
    """Return the ``BoardResponse`` mapping: who is called, who is next, who was last called.

    Privacy is structural rather than a filter: every row goes through :func:`_board_item`, which
    projects two fields, so only ``queue_number`` and ``party_size`` leave for a guest row (section
    15, "Public board shows only queue number and party size") and no ``name`` or ``phone`` key can
    reach the response by accident.

    An empty queue is a valid board, not an error: zero rows answer with two nulls, an empty
    ``recent_calls`` and ``waiting_count`` 0 (AC-7). The 404 belongs to the branch, never to the
    queue.

    ``recent_calls`` holds at most the 3 most recent entries that have left ``WAITING``, newest
    first
    (ruling R-B06-1). The ``CALLED`` entry is one of them - that is what "has left WAITING" says,
    AC-6
    asserts four left-WAITING rows against a cap of three while separately naming the ``CALLED``
    entry
    as ``current_called``, and the openapi example shows a called number on the board beside
    ``next_up``.
    """
    branch = get_branch_or_404(db, branch_id)
    settings = get_settings_or_500(db, branch_id)
    day = business_date_for(branch, now)

    rows = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.branch_id == branch_id,
            WaitlistEntry.business_date == day,
        )
        .order_by(WaitlistEntry.sort_order.asc())
        .all()
    )
    waiting = [row for row in rows if row.status is WaitlistStatus.WAITING]
    called = [row for row in rows if row.status is WaitlistStatus.CALLED]
    left_waiting = [row for row in rows if row.status in LEFT_WAITING_STATUSES]

    return {
        "restaurant_name": branch.restaurant.name,
        "branch_name": branch.name,
        "hours": hours_for(branch),
        "is_waitlist_open": settings.is_waitlist_open,
        "waiting_count": len(waiting),
        "current_called": _board_item(called[0]) if called else None,
        "next_up": _board_item(waiting[0]) if waiting else None,
        "recent_calls": [_board_item(row) for row in recent_calls(left_waiting)],
    }


def recent_calls(rows: list[WaitlistEntry], limit: int = 3) -> list[WaitlistEntry]:
    """Return the newest few entries that left ``WAITING``, most recent first (R-B06-1).

    "The most recent 3" is the highest ``seq`` - the position the guest held in the queue - because
    AC-6's rows carry no timestamps at all: ``created_at``, ``called_at`` and ``closed_at`` are all
    null there, so ``seq`` is the only order those rows state, and ``sort_order`` is the same order
    with the ``WAITING`` rows interleaved. Two readings of "recent" are therefore compatible with
    the probe: the highest queue positions today, or the most recent status transition (which a later
    issue with real timestamps can re-measure). What is NOT compatible is the AC-6 prose's own
    ``[A012, A011, A010]`` - see the delivery note; the code follows the probe's list, not the
    sentence describing it.
    """
    return sorted(rows, key=lambda row: int(row.seq), reverse=True)[:limit]


def _board_item(row: WaitlistEntry) -> dict[str, Any]:
    """Project a row onto the two fields the public board may show (section 15)."""
    return {"queue_number": row.queue_number, "party_size": row.party_size}
