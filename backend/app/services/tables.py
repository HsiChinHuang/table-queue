"""Table-administration rules for B-11 (the ``/api/v1/admin/tables`` surface).

This module owns every rule behind the four contract slots: the list filter, the
per-branch label rule, the soft delete and the field-set a PATCH may write. The router in
``app/routers/admin.py`` is transport only - it resolves the path parameter, names the
response model and never writes SQL or an error body. Failures leave here as ``AppError``
and are rendered by B-04's handler, so every 4xx on this surface is the contract's
``{"error": {"code", "message"}}`` envelope rather than FastAPI's ``detail`` shape.

Four rules the AC set pins and the contract states:

* A delete is an ``is_active`` flip, never a ``DELETE FROM tables`` (R-B11-1). The row the
  queue history references has to stay readable after the 204, and it has to stay
  observable as an inactive row through ``include_inactive=true``.
* ``uq_branch_label`` in ``app/models.py`` carries no ``is_active`` predicate, so a label
  held by a soft-deleted row is still taken (R-B11-2). Both write paths therefore check
  every row of the branch, visible or not, and still translate an ``IntegrityError`` into
  the 409 - the pre-check narrows the race, the commit-time translation is what keeps a
  collision out of the 500 handler.
* ``branch_id`` is not a request field and appears on neither admin schema (R-B11-6), so
  every write lands on the single branch the process is configured with
  (``settings.default_branch_id``). A client cannot move a write to another branch.
* Neither admin request schema declares ``status``, and neither sets ``extra="forbid"``,
  so a body carrying ``status`` is stripped by the schema and stays inert here
  (R-B11-5). Table state transitions belong to the B-08 staff endpoints.

Three cases the groom deliberately left unpinned are decided here rather than guessed at
by an AC, and each decision is stated where it is made: renaming onto a label only a
hidden row of the same branch holds collides, because the shipped index says so; an
omitted ``sort_order`` becomes ``0``, because the column is ``NOT NULL`` while the schema
field is optional; and an empty-string ``section`` is stored as it arrived, because the
schema accepts it and nothing in the contract says to rewrite it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.errors import AppError
from app.models import Table, TableStatus
from app.schemas import CreateTableRequest, UpdateTableRequest

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
        raise AppError("CONFLICT", message="Table label already exists")


def list_tables(db: Any, include_inactive: bool) -> list[Table]:
    """Return the branch's tables, ordered the way the staff dashboard lists them.

    ``include_inactive`` is the only filter the contract declares: false answers exactly the
    ``is_active`` rows, true adds the soft-deleted ones back and serialises them with
    ``is_active: false`` so an operator can still see what was retired (R-B11-1, R-B11-4).
    Rows of another branch are never listed - the admin surface is single-branch (R-B11-6).
    """
    query = db.query(Table).filter(Table.branch_id == get_settings().default_branch_id)
    if not include_inactive:
        query = query.filter(Table.is_active.is_(True))
    return query.order_by(Table.sort_order, Table.label).all()


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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("CONFLICT", message="Table label already exists") from None
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("CONFLICT", message="Table label already exists") from None
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
        raise AppError("CONFLICT", message="Cannot delete an occupied table")
    row.is_active = False
    db.commit()
