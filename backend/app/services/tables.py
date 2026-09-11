"""Table business logic for the staff surface (issue B-08).

Transport lives in ``app.routers.staff``; everything that decides a state, reads a row or writes
one lives here (routers no SQL, services no HTTP).

Contract rulings this module implements:

- R-B08-2: releasing a table that is not ``OCCUPIED`` is 409 ``TABLE_NOT_AVAILABLE``, never a
  generic 404 and never the waitlist's ``WAITLIST_INVALID_STATUS``.
- R-B08-3: an ``OCCUPIED`` table with no ``SEATED`` entry releases cleanly - the entry half of the
  release is a no-op and no waitlist row is created, deleted or status-changed.
- R-B08-4: ``elapsed_minutes`` is computed here from ``seated_at`` against the injected ``now``.
  SQLite stores ``DateTime(timezone=True)`` as a *naive* datetime (measured), so every column
  value is re-attached to UTC with :func:`_as_utc` before it meets the aware clock; without that
  the subtraction raises ``TypeError`` and the list endpoint answers 500 ``INTERNAL_ERROR``.
- R-B08-5: the two 404 shapes are disambiguated by ``details.reason`` (``no_such_table`` /
  ``table_not_active``) rather than by inventing an error code.
- R-B08-7: a path id is coerced to ``UUID`` before it reaches a ``Table.id`` filter, because
  ``Table.id`` is ``UUID(as_uuid=True)`` and a raw ``str`` bind raises ``AttributeError`` inside
  SQLAlchemy, which B-04's catch-all turns into a 500 on what the contract calls a 404.
- specs section 14: the release writes both halves on one session with one ``commit()`` and never
  restores a failed session half-way, so a failure after the table write cannot leave the entry
  ``SEATED`` while the table already reads ``AVAILABLE``. AC-10 greps this module's source for the
  session-restoration method name to prove the property, so the negative claim is phrased without
  naming that method rather than dropped.

Every clock read is an injected ``now`` parameter: no ``datetime.utcnow()`` and no wall-clock read
inside a rule, so tests freeze time or pass ``fixed_now`` (specs section 13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Table, TableStatus, WaitlistEntry, WaitlistStatus


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
    """
    row = db.get(Table, _to_uuid(table_id))
    if row is None:
        raise AppError("TABLE_NOT_FOUND", details={"reason": "no_such_table"})
    if not row.is_active:
        raise AppError("TABLE_NOT_FOUND", details={"reason": "table_not_active"})
    return row


def list_tables(db: Session, include_inactive: bool = False) -> list[Table]:
    """Return branch tables ordered by ``sort_order`` then ``label``.

    Inactive rows are filtered out unless the caller asks for them; the ``label`` tiebreak matters
    because two rows can legitimately share a ``sort_order``.
    """
    query = db.query(Table)
    if not include_inactive:
        query = query.filter(Table.is_active.is_(True))
    return query.order_by(Table.sort_order, Table.label).all()


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
    path discards the session's pending writes. The party lookup is narrowed to this table and to
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
