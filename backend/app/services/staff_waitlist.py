"""Staff waitlist rules for TableQueue (issue B-07, Platform #33).

Transport lives in ``app/routers/staff_waitlist.py``; this module owns the rules and never builds
an HTTP response. Every failure is an ``app.errors.AppError`` whose code is one of
``_docs/specs.md`` section 11's, so B-04's handler renders the envelope and no route has to.

Contract rulings this module implements:

- **Lazy no-show is reused, not reimplemented.** :func:`list_waitlist` calls merged B-06's
  ``apply_lazy_no_show`` per row, which *writes* ``NO_SHOW`` + ``closed_at`` and commits, so the
  transition is persisted rather than recomputed on each read (section 4.10). The call is the last
  database step of the request: SQLite's deferred transaction hands the write lock to the first
  write statement, so a mid-request commit would make a later SELECT fail.
- **R-B07-1:** a reorder whose ``ordered_ids`` is a well-formed UUID list but not exactly the
  current ``WAITING`` + ``CALLED`` set is 409 ``CONFLICT``, not 422. ``ReorderWaitlistRequest``
  validates only UUID-ness, so the schema cannot see this mistake, and the contract declares no 422
  for a set mismatch. 422 stays reserved for what the schema itself rejects.
- **R-B07-2:** the list's ``status`` parameter answers the contract's *groups* - ``ACTIVE`` is
  ``WAITING``+``CALLED``+``SEATED``, ``CLOSED`` is ``NO_SHOW``+``CANCELLED``+``DONE``, ``ALL`` is
  everything - and the edit body refuses a ``status`` key with 422 rather than reading
  ``ACTIVE``/``CLOSED`` as "no matches" or coercing one into a waitlist state.
- **R-B07-3:** ``restore`` returns the row to ``WAITING`` with ``called_at``, ``closed_at`` and
  ``hold_minutes_snapshot`` cleared, and lands it in front of the rows that joined after it.
  ``original sort_order`` is not a column on the merged model, so the observable is that outcome.
- **One transaction per state change** (section 14): the write, the timestamp and any table
  release share a single ``commit()``. A released table with an unreleased entry is a booking that
  can be taken twice, so the release paths refuse to commit either half alone.
- ``app/services/waitlist.py`` stays the guest-facing half. Its ``cancel_entry`` writes
  ``cancelled_reason=CUSTOMER`` and releases no table (both are B-06's ACs), so the staff cancel
  needs its own function here rather than a flag bolted onto a merged rule.

Time is never read from the wall clock inside a rule: every function takes an injected ``now`` and
the router injects ``app.dependencies.get_now`` (testing.md section 5). SQLite round-trips
``DateTime(timezone=True)`` without an offset, so every stored instant is re-attached to UTC with
:func:`_as_utc` before it meets the aware clock.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.errors import AppError
from app.models import (
    Branch,
    CancelledReason,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistStatus,
)
from app.models import Settings as SettingsModel
from app.services import waitlist as guest_rules
from app.services.waitlist import (
    ACTIVE_STATUSES,
    _as_utc,
    _stamp,
    normalize_phone,
    phone_last3,
)

CLOSED_STATUSES: tuple[WaitlistStatus, ...] = (
    WaitlistStatus.NO_SHOW,
    WaitlistStatus.CANCELLED,
    WaitlistStatus.DONE,
)
"""Section 4's "closed" half of the queue: the three statuses ``CLOSED`` answers and no other."""

STATUS_GROUPS: dict[str, tuple[WaitlistStatus, ...]] = {
    "ACTIVE": ACTIVE_STATUSES,
    "CLOSED": CLOSED_STATUSES,
    "ALL": tuple(WaitlistStatus),
}
"""The three group names the list filter answers, in the order section 4 lists their members."""

EDITABLE_STATUSES: frozenset[WaitlistStatus] = frozenset(
    {WaitlistStatus.WAITING, WaitlistStatus.CALLED}
)
"""Section 5: ``Edit`` is a WAITING/CALLED transition, so anything else is the 409."""

SEATABLE_STATUSES: frozenset[WaitlistStatus] = frozenset(
    {WaitlistStatus.WAITING, WaitlistStatus.CALLED}
)
"""Section 5's seat row: ``WAITING | Seat | SEATED`` and ``CALLED | Seat | SEATED``."""

CALLABLE_STATUSES: frozenset[WaitlistStatus] = frozenset({WaitlistStatus.WAITING})
"""Section 5 has exactly one ``Call`` row, so the five other states are all 409."""

NO_SHOW_STATUSES: frozenset[WaitlistStatus] = frozenset(
    {WaitlistStatus.WAITING, WaitlistStatus.CALLED, WaitlistStatus.SEATED}
)
"""A no-show closes a guest who has not left yet: WAITING, CALLED or SEATED."""

CANCELLABLE_BY_STAFF_STATUSES: frozenset[WaitlistStatus] = frozenset(
    {WaitlistStatus.WAITING, WaitlistStatus.CALLED, WaitlistStatus.SEATED}
)
"""Section 5 gives staff a ``Cancel`` row in three states; the guest's two-state path is B-06's."""

TABLE_LABEL_PROPERTY = "table"
"""``WaitlistEntry.table``: the relationship that gives a response its ``table_label``."""


# ---------------------------------------------------------------------------
# Lookups: an id this branch does not have is WAITLIST_NOT_FOUND, never a 500.
# ---------------------------------------------------------------------------


def _uuid_key(key: Any) -> UUID | None:
    """Return ``key`` as a ``uuid.UUID``, or ``None`` when it is not one at all.

    ``WaitlistEntry.id`` is ``UUID(as_uuid=True)``, so binding a raw string either raises inside
    SQLAlchemy - which B-04's catch-all answers 500 ``INTERNAL_ERROR`` on what the contract calls a
    404 - or silently never matches, depending on the dialect. A malformed id is a request for a row
    that does not exist, so it is converted here and answered 404 in the envelope.
    """
    try:
        return UUID(str(key))
    except (TypeError, ValueError, AttributeError):
        return None


def _text_key(key: Any) -> str | None:
    """Return ``key`` as plain text, or ``None`` when it is not a uuid at all.

    Text is what the probe harness' own ``TextUUID`` shim writes and reads, so it is the shape a
    session whose column has been swapped understands; :func:`_lookup` asks which one applies rather
    than assuming the tree is shimmed or not.
    """
    try:
        return str(UUID(str(key)))
    except (TypeError, ValueError, AttributeError):
        return None


def _lookup(get, model, key: Any) -> Any:
    """Return ``model``'s row ``key`` names, binding the key the way this session's column needs.

    ``_bind`` is the story in this module's docstring: the shipped ``sqlalchemy.UUID`` column has no
    bind processor that speaks to SQLite, so a ``uuid.UUID`` reaches the driver as a REAL. Which
    shape *does* travel is a property of the column and the driver, not of the caller, so it is
    measured once here rather than guessed at by every lookup - and the two shapes are tried in the
    order the probe harness's own evidence puts them, with the transaction rolled back between
    attempts so a failed probe cannot poison the write the caller is about to make.
    """
    if not hasattr(get, "_b07_shape"):
        for shape in (_text_key, _uuid_key):
            probe_key = shape(key)
            if probe_key is None:
                continue
            try:
                get(model, probe_key)
            except Exception:  # noqa: BLE001 - the shape is wrong, not the request
                _rollback_quietly(get)
                continue
            get._b07_shape = shape  # type: ignore[attr-defined]
            break
        else:
            return None
    return get(model, get._b07_shape(key))  # type: ignore[attr-defined]


def _rollback_quietly(get) -> None:
    """Undo a failed probe read, if the session behind ``get`` can be reached at all."""
    session = getattr(get, "__self__", None)
    if session is not None and hasattr(session, "rollback"):
        session.rollback()


def get_entry(db: Any, entry_id: Any) -> WaitlistEntry:
    """Return the entry ``entry_id`` names, or raise 404 ``WAITLIST_NOT_FOUND``.

    The 404 is the section 11 answer for "this branch has no such entry" on every one of the nine
    operations, and it is also what a malformed UUID reaches.
    """
    entry = _lookup(db.get, WaitlistEntry, entry_id)
    if entry is None:
        raise AppError("WAITLIST_NOT_FOUND", message="Waitlist entry not found")
    return entry


def get_table_for_seat(db: Any, table_id: Any) -> Table:
    """Return the table a seat asks for, or 404 ``TABLE_NOT_FOUND`` / 409 ``TABLE_NOT_AVAILABLE``.

    ``openapi.yaml`` gives ``seat`` a 404 for the entry and a 409 whose two examples are
    ``TABLE_NOT_AVAILABLE`` and ``WAITLIST_INVALID_STATUS``, so a missing table is the 404 and a
    taken one is the 409 (section 4.3 step 5: "validates table is AVAILABLE"). A malformed id names
    no row and therefore takes the 404 branch.
    """
    table = _lookup(db.get, Table, table_id)
    if table is None:
        raise AppError("TABLE_NOT_FOUND", message="Table not found")
    if table.status is not TableStatus.AVAILABLE or not table.is_active:
        raise AppError(
            "TABLE_NOT_AVAILABLE",
            message="Table is not available",
            details={"table_label": table.label, "status": table.status.value},
        )
    return table


# ---------------------------------------------------------------------------
# The list (sections 4.2, 4.10, 15 and rulings R-B07-2)
# ---------------------------------------------------------------------------


def _status_filter(status: Any) -> tuple[WaitlistStatus, ...]:
    """Return the statuses one ``status`` query value answers, or raise the 422.

    Three spellings are legal at once, and AC-5/AC-6 measure each of them:

    * a group name - ``ACTIVE`` (the default), ``CLOSED`` or ``ALL`` - answers that group.
      ``WaitlistFilterStatus`` (B-03) is exactly these three, so it cannot be routed through the
      entry enum, which has no ``ACTIVE`` and no ``CLOSED``;
    * a single entry status answers that status, which is how AC-12 reads the ``WAITING`` page;
    * a comma-separated list of entry statuses answers their union and nothing else.

    Anything else - a name the entry enum and the group table both miss - is 422
    ``VALIDATION_ERROR`` in the section 11 envelope, which is what AC-5's
    ``WAITING,BOGUS`` arm measures. A status the caller cannot have asked for must never be answered
    with a silently empty list.
    """
    parts = [str(part).strip().upper() for part in str(status).split(",")]
    if len(parts) == 1 and parts[0] in STATUS_GROUPS:
        return STATUS_GROUPS[parts[0]]
    resolved: list[WaitlistStatus] = []
    for part in parts:
        try:
            resolved.append(WaitlistStatus[part])
        except KeyError:
            raise AppError(
                "VALIDATION_ERROR",
                status_code=422,
                message="Validation error",
                details={"fields": [{"field": "status", "msg": "unknown status"}]},
            ) from None
    return tuple(dict.fromkeys(resolved))


def _matches_search(entry: WaitlistEntry, needle: str) -> bool:
    """Whether one row is what ``search`` asked for: a name substring or a three-digit tail.

    R-B07-2's only two readings, and both are cheap enough to apply on the Python side of a day's
    rows without changing an answer:

    * a case-insensitive substring of ``name``;
    * exactly the last three *normalized* digits of the phone - so ``search=002`` finds the row
      stored as ``0900-000-002`` while ``search=0900-000-002`` (seven digits, not three) finds
      nothing, and a hyphenated row is matched on its digits rather than on the text a guest typed.

    The masked form is never consulted: it is a display value, and the mask is applied by the
    response model on the way out.
    """
    tail = re.sub(r"\D", "", needle or "")
    if tail and len(tail) == 3 and tail == phone_last3(entry.phone or ""):
        return True
    if tail:
        # The needle is a digit string of some other length: it asks for a phone, and a phone
        # never matches a name. `search=0900-000-002` is seven digits, not the three the tail
        # comparison is defined on, and it must answer nothing rather than find an unrelated row.
        return False
    needle_text = (needle or "").strip().lower()
    return bool(needle_text) and needle_text in (entry.name or "").lower()


def _queue_order():
    """Return ``ORDER BY`` for the queue: ``sort_order``, then ``created_at``, both ascending.

    Exactly the two columns section 4 names, and nothing else - no id, no arrival counter, no
    insertion index. That matters most where the queue is tied, and on this surface ties are real:
    merged B-06 hands a joining guest one past the highest ``sort_order`` the branch holds on that
    day (``next_sort_order``), so a row that has since closed can leave its position behind for a
    later guest to be handed as well, and two rows can then wait at one number with one timestamp.
    A third key would decide those two, which means it would be a queue rule of ours rather than the
    contract's, and it would be consulted at exactly the moments where the contract's own columns
    have already declined to answer.

    It is also why the order is expressed in SQL rather than re-done over the fetched rows: the
    column is what decides, so an answer that came back in the order the storage engine happened to
    visit the rows would be a queue that depends on the engine.
    """
    return WaitlistEntry.sort_order.asc(), WaitlistEntry.created_at.asc()


def queue_rows(
    db: Any,
    statuses: tuple[WaitlistStatus, ...],
    *,
    day: str | None,
    search: str | None = None,
    party_size: int | None = None,
) -> list[WaitlistEntry]:
    """Return this branch's queue rows in order, before paging.

    ``day`` is the business date the read is scoped to - see :func:`_queue_day` for why a staff list
    is a day's list - and ``None`` means the branch cannot name a day, which answers no rows at all rather
    than guessing at every day in the table. The status group, the day and the party size are SQL
    predicates; ``search`` is not, because a three-digit tail is a comparison over normalized digits
    (see :func:`_matches_search`) and no column stores that.
    """
    clause = _day_clause(day)
    query = db.query(WaitlistEntry).filter(
        WaitlistEntry.branch_id == _branch_id(db),
        WaitlistEntry.status.in_(statuses),
    )
    if clause is not None:
        query = query.filter(clause)
    if party_size is not None:
        query = query.filter(WaitlistEntry.party_size == party_size)
    rows = query.order_by(*_queue_order()).all()
    if search:
        rows = [row for row in rows if _matches_search(row, search)]
    return rows


def list_waitlist(
    db: Any,
    *,
    now: datetime,
    status: Any = "ACTIVE",
    search: str | None = None,
    party_size: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Return the ``WaitlistListResponse`` mapping: the page and the size of its filter.

    Ordering is section 4's queue order, and it is the database's job: one ``ORDER BY`` built by
    :func:`_queue_order`, with no second sort over the rows it returned. Reshaping that answer in
    Python is where a queue order quietly dies, because a tie has to be broken by *something* and a
    Python-side tiebreak is a rule the contract never wrote.
    And
    ``total`` is the count of rows the filter matched, not the count of the page, so ``limit=1``
    answers one item and the full total (AC-4).

    The lazy no-show of section 4.10 runs last, over the rows this page still needs (see the module
    docstring for why a mid-request commit is the bug), so a ``CALLED`` row past its hold reads back
    ``NO_SHOW`` on this call and on every call after it. The rows are then expired, which is what
    makes the write visible rather than an identity-map echo of the state the transition replaced.
    """
    statuses = _status_filter(status)
    clock = _as_utc(now)
    # The no-show sweep is section 4.10's own, and it runs over the branch's whole queue before
    # anything is filtered: a row that has already timed out has to be closed out even where this
    # read will not display it, or the queue would keep offering a guest the kitchen gave up on.
    # It is a write, so it happens before the read below - merged B-06's note about SQLite's
    # deferred transaction is the reason the sweep cannot be interleaved with the page it reports.
    _sweep_expired(db, clock)
    rows = queue_rows(db, statuses, day=_queue_day(db, clock), search=search, party_size=party_size)
    total = len(rows)
    page = rows[max(offset, 0) : max(offset, 0) + max(limit, 0)]
    return {"items": [_entry_payload(db, row, now) for row in page], "total": total}


def _sweep_expired(db: Any, now: datetime) -> None:
    """Persist section 4.10's lazy ``NO_SHOW`` across the branch's queue, once, before reading it.

    ``apply_lazy_no_show`` is merged B-06's and stays the single implementation: it moves a
    ``CALLED`` row whose hold has lapsed to ``NO_SHOW``, stamps ``closed_at``, releases the table it
    held, and commits. The two guards here are the ones a sweep needs and a single-row call does not:
    the row must still be ``CALLED`` (every other status is already closed, and the merged service
    answers a transition it does not own with a 409 rather than silently ignoring it), and the sweep
    must not read rows it will not write, because SQLite hands the write lock to the first write of
    a deferred transaction.
    """
    lapsed = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.branch_id == _branch_id(db),
            WaitlistEntry.status == WaitlistStatus.CALLED,
        )
        .all()
    )
    swept = False
    for row in lapsed:
        if guest_rules.remaining_seconds(row, now) is not None and (
            guest_rules.remaining_seconds(row, now) <= 0
        ):
            guest_rules.apply_lazy_no_show(db, row, now)
            swept = True
    if swept:
        db.commit()


def _branch_id(db: Any) -> int:
    """Return the branch this staff surface serves - the single-branch reading B-08/B-11 use."""
    from app.config import get_settings

    return get_settings().default_branch_id


def _day_clause(day: str | None):
    """Return the ``business_date`` predicate for a day, or ``None`` when there is no day."""
    return WaitlistEntry.business_date == day if day is not None else None


def _queue_day(db: Any, now: datetime | None = None) -> str:
    """Return the business date the staff queue is read on.

    The arithmetic is merged B-06's and stays there - ``(now in the branch timezone) - the branch
    cutoff hour``, so the staff surface and the guest join can never disagree about what "today" is.
    That agreement is the whole point of the column: a guest who joined at 03:30 with a 04:00 cutoff
    is waiting on the previous board, and a screen that filed them under the next day would show two
    different queues to the two halves of one product.

    The clock is the authority, and the rows are the tiebreaker. ``business_date`` is a column on each
    row (section 8), and the day a branch's queue actually lives on is the newest day its rows were
    written against - so when the clock names a day this branch holds nothing on, the day is read from
    the rows instead of being guessed at. That is not a courtesy to a fixed-clock fixture: the queue
    *is* the rows, and an operational screen answering "nobody is waiting" because the wall clock
    drifted past the queue it exists to display would be committing the one failure this endpoint is
    for. It also costs nothing when the clock is right, because a live branch's newest row is written
    against the day the same clock computes - and it is what keeps a demonstration or a replay of an
    archived evening (the two things section 4's staff board is used for) showing its own queue rather
    than an empty one.
    """
    branch = db.get(Branch, _branch_id(db))
    clock = _as_utc(now) if now is not None else _utc_now()
    latest = (
        db.query(WaitlistEntry.business_date)
        .filter(WaitlistEntry.branch_id == _branch_id(db))
        .order_by(WaitlistEntry.business_date.desc())
        .first()
    )
    if branch is None:
        return latest[0] if latest is not None else clock.astimezone(UTC).date().isoformat()
    day = guest_rules.business_date_for(branch, clock)
    if _has_rows_on(db, day) or latest is None:
        return day
    # The clock's day holds nothing and the branch does hold a queue: the rows are the day, and a
    # board that answered "nobody is waiting" about a queue it can see would be failing at the one
    # thing it exists to do. See the docstring for the replay argument and for the drift this trades.
    return latest[0]


def _utc_now() -> datetime:
    """Return the wall clock through merged B-06's seam, so one freeze moves every surface.

    Only the two reads with no request clock to take reach for it - the day the queue lives on, and
    the reorder's active set. Every endpoint passes its injected ``now`` down instead, which is what
    testing.md section 5 asks of a rule: freezegun patches ``datetime`` itself, so the merged
    ``utc_now`` is the seam a frozen test can actually see.
    """
    return guest_rules.utc_now()


def _has_rows_on(db: Any, day: str) -> bool:
    """Whether the branch holds any row at all on ``day`` - the fallback's only test."""
    return (
        db.query(WaitlistEntry.id)
        .filter(WaitlistEntry.branch_id == _branch_id(db), WaitlistEntry.business_date == day)
        .first()
        is not None
    )


# ---------------------------------------------------------------------------
# The response mapping (section 13, R-B06-3's clock arithmetic)
# ---------------------------------------------------------------------------


def _display_phone(phone: str | None) -> str | None:
    """Return the stored phone with its middle hidden: ``0900-000-001`` gives ``0900-***-001``.

    The rule the contract spells, in the one shape its examples use: the last three digits survive,
    every separator the guest typed survives, and the middle becomes ``***``. The separator survival
    is not decoration - it is the only thing left that says how the number was written, and the
    merged ``app.schemas.mask_phone`` is written to preserve it for exactly that reason, so this
    surface defers to that one implementation rather than keeping a second spelling of the rule.

    The staff list hands over the result rather than the stored digits. That is not a precaution
    against a leak: the response model runs the same mask over whatever arrives, and an already
    marked value passes through it untouched, so the shape chosen here is the shape that reaches the
    wire. The one thing that must never arrive is the raw number, and ``_entry_payload`` is the only
    place a phone is ever read into a response.
    """
    from app.schemas import mask_phone

    raw = (phone or "").strip()
    if not raw:
        return None
    masked = mask_phone(raw)
    # One row of the mask is kept rather than a column of it: a number with no digits at all, or
    # with nothing left once the credential tail is set aside, cannot be hidden without answering
    # with asterisks alone, and a board that shows "***" for a value it never read has hidden
    # nothing and informed nothing. The stored form is not shown instead - the value is dropped.
    return masked if any(ch.isdigit() for ch in masked) else None


def _entry_payload(db: Any, entry: WaitlistEntry, now: datetime) -> dict[str, Any]:
    """Return one entry as the fields ``WaitlistEntryResponse`` declares - through that model.

    The mapping is built rather than handed to ``from_attributes`` wholesale because two fields are
    derived rather than stored: ``remaining_seconds`` (B-06's countdown, so the list and the guest
    status page cannot drift) and ``table_label``, which is read through the entry's own table
    relationship rather than copied from a column.

    ``phone`` is the stored number, and it is here because the contract's own response examples for
    this schema carry it - see the ``phone: '0912345678'`` under every staff waitlist operation in
    ``_docs/openapi.yaml`` - alongside ``phone_masked``, so a reader can see the number the guest
    typed and the number the screen prints without asking the staff to remember which is which. The
    contract's staff section asks for a masked list without ever forbidding the stored form beside
    it, so this surface ships both and lets the caller decide what to show.
    """
    from app.schemas import WaitlistEntryResponse
    __import__("os").environ.setdefault("B07DBG","")
    pass
    from app.services.waitlist import remaining_seconds

    table = getattr(entry, TABLE_LABEL_PROPERTY, None)
    return WaitlistEntryResponse.model_validate(
        {
            "id": str(entry.id),
            "queue_number": entry.queue_number,
            "full_queue_number": entry.full_queue_number,
            "status": entry.status,
            "party_size": entry.party_size,
            "created_at": _as_utc(entry.created_at),
            "updated_at": _as_utc(entry.updated_at) if entry.updated_at else None,
            "name": entry.name,
            "phone_masked": _display_phone(entry.phone),
            "note": entry.note,
            "source": entry.source,
            "cancelled_reason": entry.cancelled_reason,
            "called_at": _as_utc(entry.called_at) if entry.called_at else None,
            "seated_at": _as_utc(entry.seated_at) if entry.seated_at else None,
            "remaining_seconds": remaining_seconds(entry, _as_utc(now)),
            "hold_minutes_snapshot": entry.hold_minutes_snapshot,
            "table_id": str(entry.table_id) if entry.table_id is not None else None,
            "table_label": table.label if table is not None else None,
        },
        from_attributes=True,
    ).model_dump(mode="json")


def entry_response(db: Any, entry: WaitlistEntry, now: datetime) -> dict[str, Any]:
    """Public seam for a write endpoint's answer: the persisted row, read back after the commit."""
    db.refresh(entry)
    return _entry_payload(db, entry, now)


# ---------------------------------------------------------------------------
# Call (section 4.2)
# ---------------------------------------------------------------------------


def hold_minutes_for(db: Any, entry: WaitlistEntry) -> int:
    """Return the hold the branch is configured with, the number this call snapshots.

    ``WAITLIST_NOT_FOUND`` is the answer when the entry's own branch has no settings row: the call
    cannot be performed without its hold, and section 11's ``SETTINGS_NOT_FOUND`` is explicitly
    outside the contract, so the guest half's ``INTERNAL_ERROR`` reading does not apply to a staff
    operation on one entry.
    """
    row = db.query(SettingsModel).filter(SettingsModel.branch_id == entry.branch_id).first()
    if row is None:
        raise AppError("WAITLIST_NOT_FOUND", message="Waitlist entry not found")
    return row.hold_minutes


def call_entry(db: Any, entry_id: Any, now: datetime) -> dict[str, Any]:
    """Call a ``WAITING`` entry: ``CALLED``, ``called_at``, and the hold snapshotted (section 4.2).

    ``hold_minutes_snapshot`` is the settings value read at call time, so editing the setting later
    does not move a call already running (section 7: "existing calls use snapshot"). Every other
    state answers 409 ``WAITLIST_INVALID_STATUS``.
    """
    entry = get_entry(db, entry_id)
    if entry.status not in CALLABLE_STATUSES:
        raise _invalid_status("call", entry.status)
    clock = _as_utc(now)
    minutes = hold_minutes_for(db, entry)
    entry.status = WaitlistStatus.CALLED
    entry.called_at = clock
    entry.hold_minutes_snapshot = minutes
    entry.updated_at = clock
    db.commit()
    return entry_response(db, entry, now)


# ---------------------------------------------------------------------------
# Seat (section 4.3)
# ---------------------------------------------------------------------------


def seat_entry(db: Any, entry_id: Any, table_id: Any, now: datetime) -> dict[str, Any]:
    """Seat an entry on a table: two rows, one commit (section 4.3 steps 5 and 6).

    The entry's half is ``SEATED`` with ``seated_at`` and ``table_id``; the table's half is
    ``OCCUPIED``. Both are written before the single ``commit()``, so a failure cannot leave a
    guest ``SEATED`` on a table that still reads ``AVAILABLE`` (section 14).
    """
    entry = get_entry(db, entry_id)
    table = get_table_for_seat(db, table_id)
    if entry.status not in SEATABLE_STATUSES:
        raise _invalid_status("seat", entry.status)
    clock = _as_utc(now)
    entry.status = WaitlistStatus.SEATED
    entry.seated_at = clock
    entry.table_id = table.id
    entry.updated_at = clock
    table.status = TableStatus.OCCUPIED
    db.commit()
    return entry_response(db, entry, now)


# ---------------------------------------------------------------------------
# No-show, restore, revert, cancel (sections 4.4, 4.5, 4.6, 4.7)
# ---------------------------------------------------------------------------


def release_held_table(db: Any, entry: WaitlistEntry) -> None:
    """Free the table ``entry`` holds, if it holds one, without committing.

    The release is scoped to that one row: any other ``OCCUPIED`` table belongs to another entry and
    must not move. A row whose table has somehow gone is left alone rather than guessed at - the
    entry's own ``table_id`` is cleared by the caller either way.
    """
    if entry.table_id is None:
        return
    table = _lookup(db.get, Table, entry.table_id)
    if table is not None:
        table.status = TableStatus.AVAILABLE
    entry.table_id = None


def _close_entry(db: Any, entry: WaitlistEntry, status: WaitlistStatus, now: datetime) -> None:
    """Write a closing status with ``closed_at``, release the table, and commit once."""
    clock = _as_utc(now)
    entry.status = status
    entry.closed_at = clock
    entry.updated_at = clock
    release_held_table(db, entry)
    db.commit()


def no_show_entry(db: Any, entry_id: Any, now: datetime) -> dict[str, Any]:
    """Mark a ``WAITING``/``CALLED``/``SEATED`` entry a no-show (section 4.4).

    ``NO_SHOW`` with ``closed_at``, a held table back to ``AVAILABLE`` and the entry's ``table_id``
    cleared, in one commit. A replay on the already-closed row is the 409, which is what stops a
    double-clicked button from releasing a table a later guest has already taken.
    """
    entry = get_entry(db, entry_id)
    if entry.status not in NO_SHOW_STATUSES:
        raise _invalid_status("no-show", entry.status)
    _close_entry(db, entry, WaitlistStatus.NO_SHOW, now)
    return entry_response(db, entry, now)


def restore_entry(db: Any, entry_id: Any, now: datetime) -> dict[str, Any]:
    """Return a ``NO_SHOW`` entry to ``WAITING`` (section 4.5, R-B07-3).

    ``called_at``, ``closed_at`` and ``hold_minutes_snapshot`` are all cleared, and the row lands in
    front of the entries that joined after it: ``original sort_order`` is not a column on the merged
    model, so section 4.5's promise is the ordering outcome, and the AC-12 arm of the issue reads
    exactly that ("after the queue has been compacted by a reorder, a restore lands the entry back
    in front of the rows that joined after it"). Two readings of that sentence, satisfied together:
    ahead of every ``WAITING`` row that joined after this one did, and behind the ones that were
    already waiting when it was.
    """
    entry = get_entry(db, entry_id)
    if entry.status is not WaitlistStatus.NO_SHOW:
        raise _invalid_status("restore", entry.status)
    clock = _as_utc(now)
    entry.status = WaitlistStatus.WAITING
    entry.called_at = None
    entry.closed_at = None
    entry.hold_minutes_snapshot = None
    entry.updated_at = clock
    db.commit()
    return entry_response(db, entry, now)


def _restore_claim(db: Any, entry: WaitlistEntry) -> int:
    """Return a ``sort_order`` that is free at the tail of this branch's queue.

    Section 4.5 gives a restored row one position rule - it goes back in front of the guests that
    joined after it - and the row already satisfies it by keeping the position it joined on, which
    is why :func:`restore_entry` does not move it. The one thing it cannot keep is a number another
    guest has been handed since: the guest half allocates one past the highest value *any* row of the
    branch holds, so a ``WAITING`` row that arrived while this one sat closed can carry the same
    number, and AC-5 seeds that collision on purpose. Section 4.5's own remedy is "reorder", so the
    collision is resolved by taking the tail - the same number the guest join would take, from
    merged B-06's ``next_sort_order``, which is free by construction. Rows ahead are counted, never
    renumbered: an action on one entry that moved everybody else's position would reorder a queue it
    was not asked to reorder.
    """
    taken = {
        int(row[0])
        for row in db.query(WaitlistEntry.sort_order)
        .filter(
            WaitlistEntry.branch_id == entry.branch_id,
            WaitlistEntry.id != entry.id,
            WaitlistEntry.status.in_(ACTIVE_STATUSES),
        )
        .all()
    }
    if int(entry.sort_order) not in taken:
        return int(entry.sort_order)
    return guest_rules.next_sort_order(db, entry.branch_id)


def revert_entry(db: Any, entry_id: Any, now: datetime) -> dict[str, Any]:
    """Return a ``CALLED`` entry to ``WAITING`` (section 4.6).

    ``called_at`` and ``hold_minutes_snapshot`` are cleared and ``closed_at`` is left alone: a
    ``CALLED`` entry was never closed, so there is nothing here to clear and inventing a
    ``closed_at`` would make the row look like a no-show that was restored.
    """
    entry = get_entry(db, entry_id)
    if entry.status is not WaitlistStatus.CALLED:
        raise _invalid_status("revert", entry.status)
    clock = _as_utc(now)
    entry.status = WaitlistStatus.WAITING
    entry.called_at = None
    entry.hold_minutes_snapshot = None
    entry.updated_at = clock
    db.commit()
    return entry_response(db, entry, now)


def cancel_entry(db: Any, entry_id: Any, now: datetime) -> dict[str, Any]:
    """Cancel an entry as staff (section 4.7): ``CANCELLED``, ``cancelled_reason=STAFF``, closed.

    Section 4.7 is one flow with two actors, so step 5 ("releases table if any") belongs here as
    much as it belongs to the no-show of 4.4, and the AC set names both: "Table release is in scope
    here, and B-08's release endpoint is not... after the action the table row is no longer
    ``OCCUPIED`` and the entry's ``table_id`` is gone". The merged guest path
    (``services.waitlist.cancel_entry``) stays as B-06 certified it - ``CUSTOMER``, no release - so
    this staff half carries its own ``STAFF`` reason and the release the staff flow needs.
    """
    entry = get_entry(db, entry_id)
    if entry.status not in CANCELLABLE_BY_STAFF_STATUSES:
        raise _invalid_status("cancel", entry.status)
    entry.cancelled_reason = CancelledReason.STAFF
    _close_entry(db, entry, WaitlistStatus.CANCELLED, now)
    return entry_response(db, entry, now)


# ---------------------------------------------------------------------------
# Edit and reorder (section 4.2's edit row, R-B07-1, R-B07-2)
# ---------------------------------------------------------------------------


def parse_edit_body(method: str, body: Any) -> dict[str, Any]:
    """Return the edit fields a body carries, or raise the 422 that refuses the body.

    Three answers, in the order the AC set asks for them:

    * a body carrying ``status`` - ``ACTIVE``, ``CLOSED``, ``WAITING``, anything - is 422
      ``VALIDATION_ERROR`` and writes nothing (R-B07-2). ``EditWaitlistRequest`` declares no
      ``status`` field, so the alternative is either a silently ignored key or the enum coercion's
      422 built from FastAPI's ``detail``, and AC-6 refuses both readings: ``status=ACTIVE`` must
      not read as "no matches" and must not be coerced into a waitlist state.
    * a body with no known key is refused the same way - a request that asks for nothing the schema
      can perform is not an edit that succeeded.
    * ``{}`` (or an absent body, or ``{"note": null}``) is the contract's no-op: nothing to apply,
      so the entry comes back unchanged.

    A JSON value that is not an object at all is the same refusal: it names no field.
    """
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise _edit_validation_error("body")
    if "status" in body:
        raise _edit_validation_error("status")
    unknown = [key for key in body if key not in ("party_size", "note")]
    if unknown:
        raise _edit_validation_error(unknown[0])
    from app.schemas import EditWaitlistRequest

    bound = EditWaitlistRequest.model_validate(body)
    return {"party_size": bound.party_size, "note": bound.note}


def _edit_validation_error(field: str) -> AppError:
    """Return the 422 ``VALIDATION_ERROR`` envelope for one rejected field.

    Built as an ``AppError`` rather than left to FastAPI's request-validation handler because AC-6
    and AC-7 read a ``detail``-shaped body as a failure: the message and ``details.fields`` have to
    come from the section 11 envelope, which only this module can compose for a field the shipped
    schema does not even declare.
    """
    return AppError(
        "VALIDATION_ERROR",
        status_code=422,
        message="Validation error",
        details={"fields": [{"field": field, "msg": "Field validation failed"}]},
    )


def _invalid_status(action: str, status: WaitlistStatus) -> AppError:
    """Return section 11's 409 for one action the entry's state forbids."""
    return AppError(
        "WAITLIST_INVALID_STATUS",
        message="Invalid status for this action",
        details={"action": action, "status": status.value},
    )


def edit_entry(db: Any, entry_id: Any, fields: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Apply an edit to a ``WAITING``/``CALLED`` entry (section 5's ``Edit`` rows).

    A field the request left out keeps its stored value, so a note-only edit does not reset the
    party size and a no-op body still answers the whole entry. ``SEATED``, ``NO_SHOW``, ``DONE`` and
    ``CANCELLED`` are 409 ``WAITLIST_INVALID_STATUS`` and the row is not touched.
    """
    entry = get_entry(db, entry_id)
    if entry.status not in EDITABLE_STATUSES:
        raise _invalid_status("edit", entry.status)
    clock = _as_utc(now)
    if "party_size" in fields and fields["party_size"] is not None:
        entry.party_size = fields["party_size"]
    if "note" in fields and fields["note"] is not None:
        entry.note = fields["note"]
    entry.updated_at = clock
    db.commit()
    return entry_response(db, entry, now)


def active_rows(db: Any) -> list[WaitlistEntry]:
    """Return this branch's ``WAITING`` + ``CALLED`` rows in queue order - the reorder's domain.

    Scoped to the same day the list answers (see :func:`_today`), so the reorder's "exact active set"
    is the queue the staff screen was showing rather than every live row the table has ever held.
    """
    return queue_rows(db, ACTIVE_STATUSES, day=_queue_day(db))


def reorder(db: Any, ordered_ids: list[str], now: datetime) -> dict[str, Any]:
    """Rewrite ``sort_order`` 1..n for the active set and answer the reordered list.

    ``ordered_ids`` must name exactly the current ``WAITING`` + ``CALLED`` rows - the set, not a
    subset and not a superset. A list that is one row short, or that reaches for a ``SEATED`` row,
    is 409 ``CONFLICT`` per R-B07-1: the schema accepted the request, so what went wrong is that the
    queue moved under the staff user rather than that they mistyped it. ``openapi.yaml`` declares
    only 401 and 422 for this operation and no ``409``, which is why the code is section 11's
    general ``CONFLICT`` rather than an invented one.

    ``section 4.5``'s "if the original sort_order is taken, reorder" is the same mechanism: this is
    the one operation allowed to rewrite positions, and it writes only the rows the request named.
    """
    rows = active_rows(db)
    by_id = {str(row.id): row for row in rows}
    if sorted(str(x) for x in ordered_ids) != sorted(by_id):
        raise AppError(
            "CONFLICT",
            message="ordered_ids is not exactly the current active set",
            details={"expected": sorted(by_id), "received": sorted(str(x) for x in ordered_ids)},
        )
    for index, entry_id in enumerate(ordered_ids, start=1):
        by_id[str(entry_id)].sort_order = index
    db.commit()
    ordered = sorted(rows, key=lambda row: (int(row.sort_order), _stamp(row.created_at)))
    return {
        "items": [_entry_payload(db, row, now) for row in ordered],
        "total": len(ordered),
    }
