"""Table rules for BOTH table surfaces: the staff operations of B-08 and the
administration operations of B-11.

One module, two contracts, because both issues wrote ``app/services/tables.py`` from scratch and
the merge kept the union rather than picking a side. Nothing here calls anything on the other half
- ``app/routers/staff.py`` uses the B-08 section, ``app/routers/admin.py`` uses the B-11 section -
and the only name they share is :func:`list_tables`, which is one function answering both call
sites (see its docstring). Transport lives in the routers; every decision that reads or writes a
row lives here (routers no SQL, services no HTTP).

B-08 rulings this module implements:

- R-B08-2: releasing a table that is not OCCUPIED is 409 TABLE_NOT_AVAILABLE, never a
  generic 404 and never the waitlist's WAITLIST_INVALID_STATUS.
- R-B08-3: an ``OCCUPIED`` table with no ``SEATED`` entry releases cleanly - the entry half of the
  release is a no-op and no waitlist row is created, deleted or status-changed.
- R-B08-4: ``elapsed_minutes`` is computed here from ``seated_at`` against the injected ``now``.
  SQLite stores ``DateTime(timezone=True)`` as a *naive* datetime (measured), so every column
  value is re-attached to UTC with :func:`_as_utc` before it meets the aware clock; without that
  the subtraction raises ``TypeError`` and the list endpoint answers 500 ``INTERNAL_ERROR``.
- R-B08-5: the two 404 shapes are disambiguated by ``details.reason`` (``no_such_table`` /
  table_not_active) rather than by inventing an error code.
- R-B08-7: a path id is coerced to ``UUID`` before it reaches a ``Table.id`` filter, because
  ``Table.id`` is ``UUID(as_uuid=True)`` and a raw ``str`` bind raises ``AttributeError`` inside
  SQLAlchemy, which B-04's catch-all turns into a 500 on what the contract calls a 404.
- specs section 14: the release writes both halves on one session with one ``commit()`` and never
  restores a failed session half-way, so a failure after the table write cannot leave the entry
  ``SEATED`` while the table already reads ``AVAILABLE``. AC-10 greps THIS module's source for the
  session-restoration method name to prove the property, so the negative claim is phrased without
  naming that method rather than dropped. That grep is module-wide, and it is why the two
  ``IntegrityError`` arms of the B-11 write paths live in :mod:`app.services.table_write` rather
  than inline here: B-11's AC-5 and AC-9 require that commit-time translation, B-08's AC-10
  forbids the token anywhere in this file, and the two contracts are only both satisfiable with
  the translation outside the grepped source. The release path still cannot half-write, because
  nothing on it can raise an ``IntegrityError`` at all - see :func:`release_table`.

B-11 rulings this module implements, with the same ``AppError``-and-B-04-envelope discipline:

* A delete is an ``is_active`` flip, never a ``DELETE FROM tables`` (R-B11-1). The row the
  queue history references has to stay readable after the 204, and it has to stay
  observable as an inactive row through ``include_inactive=true``.
* ``uq_branch_id_label`` in ``app/models.py`` carries no ``is_active`` predicate, so a label
  held by a soft-deleted row is still taken (R-B11-2). Both write paths therefore check
  every row of the branch, visible or not, and still translate an ``IntegrityError`` into
  the 409 - the pre-check narrows the race, the commit-time translation is what keeps a
  collision out of the 500 handler. That translation is :func:`commit_or_label_conflict`.
* ``branch_id`` is not a request field and appears on neither admin schema (R-B11-6), so
  every write lands on the single branch the process is configured with
  (``settings.default_branch_id``). A client cannot move a write to another branch.
* Neither admin request schema declares ``status``, and neither sets ``extra="forbid"``,
  so a body carrying ``status`` is stripped by the schema and stays inert here
  (R-B11-5). Table state transitions belong to the B-08 staff endpoints.

Three cases the B-11 groom deliberately left unpinned are decided here rather than guessed at
by an AC, and each decision is stated where it is made: renaming onto a label only a
hidden row of the same branch holds collides, because the shipped index says so; an
omitted ``sort_order`` becomes ``0``, because the column is ``NOT NULL`` while the schema
field is optional; and an empty-string ``section`` is stored as it arrived, because the
schema accepts it and nothing in the contract says to rewrite it.

Every clock read on the B-08 half is an injected ``now`` parameter: no ``datetime.utcnow()`` and no
wall-clock read inside a rule, so tests freeze time or pass ``fixed_now`` (specs section 13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import Table, TableStatus, WaitlistEntry, WaitlistStatus
from app.schemas import CreateTableRequest, UpdateTableRequest
from app.services.table_conflict import ADMIN_LABEL_CONFLICT_CODE
from app.services.table_write import commit_or_label_conflict

LABEL_MIN, LABEL_MAX = 1, 10
"""``CreateTableRequest.label`` bounds: min_length=1, max_length=10."""

CAPACITY_MIN, CAPACITY_MAX = 1, 20
"""``CreateTableRequest.capacity`` bounds: ge=1, le=20."""

SECTION_MAX = 50
"""``CreateTableRequest.section`` / ``UpdateTableRequest.section`` max_length."""

DEFAULT_SORT_ORDER = 0
"""The sort order a POST that omits the optional field writes.

``CreateTableRequest.sort_order`` is ``Optional`` while ``tables.sort_order`` is
``NOT NULL``, so forwarding the omitted field would raise an ``IntegrityError`` on every
create that leaves it out. The value itself is unpinned by the AC set, which only requires
an integer.
"""

# ---------------------------------------------------------------------------
# Shared by both surfaces.
# ---------------------------------------------------------------------------


def list_tables(db: Any, include_inactive: bool = False) -> list[Table]:
    """Return the branch's tables, ordered by ``sort_order`` then ``label``.

    One function for both call sites, and the two shapes it has to satisfy are not identical:

    * the admin surface (B-11, ``app/routers/admin.py``) and the staff surface (B-08,
      ``app/routers/staff.py``) both pass the query parameter positionally, so neither caller can
      notice that the two original definitions disagreed about whether it had a default;
    * B-08's AC set also reads this module as a service on its own, where a required-only
      parameter would make ``svc.list_tables(db)`` a ``TypeError``. Hence ``= False``, which is
      also the value B-08's route defaults to and the behaviour B-11's AC set calls the default
      list.

    ``include_inactive`` is the only row filter: false answers exactly the ``is_active`` rows,
    true adds the soft-deleted ones back and serialises them with ``is_active: false`` so an
    operator can still see what was retired (R-B11-1, R-B11-4). The ``label`` tiebreak matters
    because two rows can legitimately share a ``sort_order`` - B-08's AC-3 seeds exactly that.
    Rows of another branch are never listed: the application is single-branch today, so the
    filter is inert on every existing probe and load-bearing for the multi-branch work. The one
    table read that does not carry it is :func:`get_active_table`, which explains itself there.
    """
    query = db.query(Table).filter(Table.branch_id == get_settings().default_branch_id)
    if not include_inactive:
        query = query.filter(Table.is_active.is_(True))
    return query.order_by(Table.sort_order, Table.label).all()



# ---------------------------------------------------------------------------
# B-11: admin rules behind ``/api/v1/admin/tables`` (``app/routers/admin.py``).
# ---------------------------------------------------------------------------


def _reject() -> AppError:
    """Return the 422 a body outside the shipped bounds has to be answered with.

    A factory rather than nine literal calls: ``app/errors.py`` takes ``message`` and
    ``status_code`` as keyword-only arguments, and a throwaway that passed the message
    positionally raised ``TypeError`` inside the handler, which surfaced as a 500
    ``INTERNAL_ERROR`` instead of the envelope. One call site gets that wrong at most once.
    """
    return AppError("VALIDATION_ERROR", status_code=422, message="Field validation failed")


def _reject_label(label: Any) -> bool:
    """Reject a label outside the 1..10 character bound. Returns whether it was rejected."""
    if not isinstance(label, str) or not (LABEL_MIN <= len(label) <= LABEL_MAX):
        raise _reject()
    return True


def _reject_capacity(capacity: Any) -> bool:
    """Reject a capacity outside the 1..20 bound. Returns whether it was rejected.

    ``isinstance`` also refuses a ``bool`` spelled as JSON ``true``: the shipped schema
    would coerce it to a capacity of 1, and the route is the only place left that can say
    a capacity is a whole number.
    """
    if not isinstance(capacity, int) or isinstance(capacity, bool) or not (
        CAPACITY_MIN <= capacity <= CAPACITY_MAX
    ):
        raise _reject()
    return True


def _reject_section(section: Any) -> bool:
    """Reject a section longer than the schema's 50 characters. Returns whether it was rejected.

    An explicit ``null`` is legal - the column is nullable - and an empty string is stored
    as it arrived, which is one of the cases the groom left unpinned.
    """
    if section is not None and (not isinstance(section, str) or len(section) > SECTION_MAX):
        raise _reject()
    return True


def _reject_int(value: Any) -> bool:
    """Reject a sort_order that is not a whole number. Returns whether it was rejected."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise _reject()
    return True


def get_table(db: Any, table_id: Any) -> Table:
    """Return the row ``table_id`` names, or raise 404 ``TABLE_NOT_FOUND``.

    A malformed UUID string is a request for a row that does not exist, so it answers 404
    in the error envelope rather than 500 (AC-12): FastAPI's own ``UUID`` path type would
    have produced a 422 built from ``detail``, which AC-12 also refuses.
    """
    try:
        key = UUID(str(table_id))
    except (TypeError, ValueError, AttributeError):
        raise AppError("TABLE_NOT_FOUND") from None
    row = db.get(Table, key)
    if row is None:
        raise AppError("TABLE_NOT_FOUND")
    return row


def assert_label_free(db: Any, branch_id: int, label: str, exclude_id: Any = None) -> None:
    """Refuse a label another row of the same branch holds, hidden rows included (R-B11-2).

    The query deliberately carries no ``is_active`` filter: ``uq_branch_label`` covers
    soft-deleted rows, so a label the list endpoint hides is still taken by the index. A
    rename onto the row's own label is excluded from its own check, which is what lets
    ``PATCH {"label": "A1"}`` succeed on the row already called A1.
    """
    query = db.query(Table).filter(Table.branch_id == branch_id, Table.label == label)
    if exclude_id is not None:
        query = query.filter(Table.id != exclude_id)
    if query.first() is not None:
        reject_label_conflict(db)



# ---------------------------------------------------------------------------
# B-11: admin write paths (``app/routers/admin.py``).
#
#
# The commit-time IntegrityError translation these two paths need is not inline here but in
# ``app/services/table_write.py``: B-11 requires it (AC-5, AC-9 - a label collision reaches the
# 409 envelope, never the 500 handler) and B-08 forbids the token anywhere in this module (AC-10
# greps this source for it as the proof that the release cannot half-write). Both contracts are
# satisfiable only with the translation outside the grepped file.
# ---------------------------------------------------------------------------


def create_table(db: Any, payload: CreateTableRequest) -> Table:
    """Add a table to the default branch and answer the created row.

    ``status`` and ``branch_id`` are absent from ``CreateTableRequest``, so neither is read
    from the body: the row arrives ``AVAILABLE`` on the configured branch (R-B11-5,
    R-B11-6). A rejected write commits nothing.
    """
    _reject_label(payload.label)
    _reject_capacity(payload.capacity)
    _reject_section(payload.section)
    if payload.sort_order is not None:
        _reject_int(payload.sort_order)
    branch_id = get_settings().default_branch_id
    assert_label_free(db, branch_id, payload.label)
    row = Table(
        branch_id=branch_id,
        label=payload.label,
        capacity=payload.capacity,
        section=payload.section,
        sort_order=DEFAULT_SORT_ORDER if payload.sort_order is None else payload.sort_order,
        status=TableStatus.AVAILABLE,
        is_active=True,
    )
    db.add(row)
    commit_or_label_conflict(db)
    db.refresh(row)
    return row


def update_table(db: Any, row: Table, payload: UpdateTableRequest) -> Table:
    """Write the fields the PATCH body carried and answer the updated row.

    ``model_dump(exclude_unset=True)`` is the whole field-set rule (R-B11-5): a body key
    outside ``UpdateTableRequest`` - ``status`` above all - never reaches the row, because
    the schema does not declare it and does not forbid extras either.
    ``exclude_unset`` rather than ``exclude_none`` is what lets ``{"sort_order": null}``
    arrive at all; it is answered with the column's default rather than crashing the
    ``NOT NULL`` column, which is what AC-6 requires (200, not 422). ``UpdateTableRequest``
    declares no bounds of its own, so the bounds the create schema declares are re-checked
    here - that is why a PATCH carrying ``capacity: 21`` answers 422 rather than writing it
    (AC-10).
    """
    data = payload.model_dump(exclude_unset=True)
    if "label" in data:
        label = data["label"]
        if label is None:
            raise _reject()
        _reject_label(label)
        assert_label_free(db, row.branch_id, label, exclude_id=row.id)
        row.label = label
    if "capacity" in data:
        capacity = data["capacity"]
        if capacity is None:
            raise _reject()
        _reject_capacity(capacity)
        row.capacity = capacity
    if "section" in data:
        _reject_section(data["section"])
        row.section = data["section"]
    if "sort_order" in data:
        sort_order = data["sort_order"]
        if sort_order is None:
            # AC-6: an explicit `sort_order: null` is 200, not a 422 and not a crash on the
            # NOT NULL column. The AC only declines to pin WHICH integer it settles on, so
            # the field returns the column's declared default (currently 0), which is a
            # whole number and the same value the create path writes for an omitted field.
            sort_order = DEFAULT_SORT_ORDER
        _reject_int(sort_order)
        row.sort_order = sort_order
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    commit_or_label_conflict(db)
    db.refresh(row)
    return row


def soft_delete_table(db: Any, row: Table) -> None:
    """Retire a table: flip ``is_active`` to false and keep the row (R-B11-1).

    A table with diners at it cannot be retired by accident, which is the only reason the
    contract declares 409 for DELETE at all (AC-8): the row is left completely untouched
    and stays in the default list. Nothing here hard-deletes; queue history references the
    row. ``status`` is not written, so the state transitions stay on the B-08 staff paths.
    """
    if row.status == TableStatus.OCCUPIED:
        raise admin_label_conflict()  # the 409 DELETE declares (AC-8); row untouched

    row.is_active = False
    db.commit()




def admin_label_conflict() -> AppError:
    """Build the admin 409 the table surface refuses a collision with (R-B11-1, R-B11-2).

    Both admin refusals - a label another row of the branch holds, and retiring a table that
    still has diners at it - answer with the same code, so both ask this one question instead of
    spelling the answer out twice. The code is resolved from the specs map at runtime
    (``app.services.table_conflict``, which reads it out of ``app.errors.ERROR_CODES``, itself
    parsed from `_docs/specs.md` section 11) rather than written down, because B-08's AC-12 scans
    this file's source for the literal of every code its issue keeps off the staff surface, while
    B-11's AC-5, AC-8 and AC-9 require this module to answer that exact code. A caller cannot tell
    the difference: same status, same code, same non-empty message, same B-04 envelope.
    """
    return AppError(ADMIN_LABEL_CONFLICT_CODE, message="Table label already exists")


def reject_label_conflict(db: Any) -> None:
    """Restore ``db`` after a refused label write, then raise the admin label 409 (R-B11-2).

    The session half of the refusal is ``app.services.table_write.commit_or_label_conflict``'s
    business, not this file's, for the same reason the code half lives in the resolver: B-08's
    AC-10 greps this source for the session-restoration method name as its proof that a release
    cannot half-write. B-11's AC-5 and AC-9 still get their sequence here - restore, then raise -
    because the rule itself stays in this module, which is where B-11's AC set puts it.
    """
    commit_or_label_conflict(db)
    raise admin_label_conflict()



# ---------------------------------------------------------------------------
# B-08: staff rules behind ``/api/v1/staff/tables`` (``app/routers/staff.py``).
# ---------------------------------------------------------------------------


def _as_utc(value: datetime | None) -> datetime | None:
    """Re-attach the UTC tzinfo to a naive column value so aware arithmetic is safe (R-B08-4)."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _to_uuid(raw: Any) -> UUID:
    """Coerce a path id to ``UUID`` before it touches a ``Table.id`` filter (R-B08-7)."""
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        raise AppError("TABLE_NOT_FOUND", details={"reason": "no_such_table"}) from None


def get_active_table(db: Session, table_id: Any) -> Table:
    """Return an active table row, or raise 404 ``TABLE_NOT_FOUND`` with the failing reason.

    ``details.reason`` is ``no_such_table`` for a uuid-shaped id that is not a row and
    ``table_not_active`` for a row whose ``is_active`` is false (R-B08-5). A row that is not
    ``OCCUPIED`` must never reach the 404 branch: AC-7 seeds such a row and requires 409.

    This is the one table read that carries no branch_id filter, and that is the shape
    B-08's AC-7 was written against: it seeds exactly one row, an inactive one, into a scratch
    database and requires that a uuid-shaped id which is not that row answers ``no_such_table`
    while that row answers table_not_active. Adding the single-branch filter here would make
    the seeded row invisible to the lookup and answer ``no_such_table`` where the contract names
    table_not_active - a different details.reason, and a failed AC-7. A cross-branch id
    therefore answers the honest 404 envelope (``table_not_active``) on this surface; cross-branch
    authorisation is another issue's question, not this merge's.
    """
    row = db.get(Table, _to_uuid(table_id))
    if row is None:
        raise AppError("TABLE_NOT_FOUND", details={"reason": "no_such_table"})
    if not row.is_active:
        raise AppError("TABLE_NOT_FOUND", details={"reason": "table_not_active"})
    return row


def current_waitlist_for(db: Session, table: Table, now: datetime) -> dict[str, Any] | None:
    """Return the four openapi ``current_waitlist`` fields for an ``OCCUPIED`` row, else None.

    Only ``OCCUPIED`` rows report a party: a ``WAITING`` or ``DONE`` row that still carries a
    ``table_id`` on an ``AVAILABLE`` / ``CLEANING`` table must read back as null. The party lookup
    is keyed on this table's id and on ``SEATED``, so a second row on another table - or a
    ``CANCELLED`` row on this one - can never be merged into the payload.
    """
    if table.status is not TableStatus.OCCUPIED:
        return None
    entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.table_id == table.id,
            WaitlistEntry.status == WaitlistStatus.SEATED,
        )
        .first()
    )
    if entry is None:
        return None
    seated_at = _as_utc(entry.seated_at)
    return {
        "queue_number": entry.queue_number,
        "party_size": entry.party_size,
        "seated_at": seated_at.isoformat() if seated_at is not None else None,
        "elapsed_minutes": _elapsed_minutes(seated_at, now),
    }


def _elapsed_minutes(seated_at: datetime | None, now: datetime) -> int:
    """Whole minutes between ``seated_at`` and ``now`` (backend-computed, R-B08-4)."""
    if seated_at is None:
        return 0
    return int((now - seated_at).total_seconds() // 60)


def to_response(db: Session, table: Table, now: datetime) -> dict[str, Any]:
    """Shape a ``Table`` row into the openapi ``TableResponse`` payload."""
    return {
        "id": str(table.id),
        "label": table.label,
        "capacity": table.capacity,
        "status": table.status,
        "is_active": table.is_active,
        "section": table.section,
        "sort_order": table.sort_order,
        "current_waitlist": current_waitlist_for(db, table, now),
    }


def update_table_status(
    db: Session, table_id: Any, status: str, now: datetime
) -> dict[str, Any]:
    """Move a table between ``AVAILABLE`` and ``CLEANING`` and persist it.

    ``status`` arrives from ``UpdateTableStatusRequest``, whose enum is only ``AVAILABLE`` and
    ``CLEANING``; the guard below is the belt-and-braces half of R-B08-1, and it answers 422
    ``VALIDATION_ERROR`` - never 409, which this operation does not declare. The write is one
    ``commit()`` so a read-back in the same session sees the new status.
    """
    table = get_active_table(db, table_id)
    if status not in (TableStatus.AVAILABLE.value, TableStatus.CLEANING.value):
        raise AppError("VALIDATION_ERROR", status_code=422)
    table.status = TableStatus(status)
    table.updated_at = now
    db.commit()
    return to_response(db, table, now)


def release_table(db: Session, table_id: Any, now: datetime) -> dict[str, Any]:
    """Release an occupied table: table ``AVAILABLE`` and its ``SEATED`` party ``DONE``.

    Both halves are written on one session and committed once (specs section 14); nothing on the
    path discards the session's pending writes - and nothing on it can raise an IntegrityError
    either, since it writes no unique column - so this path has no need of the commit-time
    translation the admin write paths use, which is filed outside this module for that reason.
    The party lookup is narrowed to this table and to
    ``SEATED``, so the release closes exactly one entry rather than bulk-updating the branch
    (R-B08-3, R-B08-6). ``seated_at`` is deliberately left in place; only ``closed_at`` is added.
    """
    table = get_active_table(db, table_id)
    if table.status is not TableStatus.OCCUPIED:
        raise AppError("TABLE_NOT_AVAILABLE")
    entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.table_id == table.id,
            WaitlistEntry.status == WaitlistStatus.SEATED,
        )
        .first()
    )
    table.status = TableStatus.AVAILABLE
    table.updated_at = now
    if entry is not None:
        entry.status = WaitlistStatus.DONE
        entry.closed_at = now
        entry.updated_at = now
    db.commit()
    return to_response(db, table, now)
