"""Staff waitlist transport for TableQueue (issue B-07, Platform #33).

Nine operations and nothing else, all under ``/api/v1/staff/waitlist``:

- ``GET  /api/v1/staff/waitlist``                  - the queue list (filter, search, paging).
- ``PUT  /api/v1/staff/waitlist/{entry_id}``       - the single-entry edit (party size, note).
- ``POST /api/v1/staff/waitlist/reorder``          - rewrite ``sort_order`` for the active set.
- ``POST /api/v1/staff/waitlist/{entry_id}/<action>`` for ``call``, ``seat``, ``no-show``,
  ``restore``, ``revert`` and ``cancel``.

Transport only: the auth dependency, the query and body binding, the status codes and the
injection of the clock. Every rule - the filter groups, the phone-tail search, the lazy no-show,
the transition gates, the table release, the reorder set check - lives in
:mod:`app.services.staff_waitlist`, which raises ``app.errors.AppError``; B-04's handler renders
the section 11 envelope. No ``HTTPException`` appears in this module, because FastAPI's default
shape is ``{"detail": ...}`` and AC-2/AC-6 read that shape as a failure.

Auth: all nine ride on ``app.dependencies.Staff`` (B-04/B-05's ``get_current_staff``), so a
missing, non-bearer, forged or expired token is 401 ``AUTH_TOKEN_EXPIRED`` before any handler
runs - which is what AC-2 measures on all nine paths at once.

The edit route is the PUT and nothing else: ``_docs/specs.md`` section 12 and
``_docs/openapi.yaml`` name ``PUT /api/v1/staff/waitlist/{id}`` (``operationId editWaitlist``), and
AC-14 removed the older ``POST .../{id}/edit`` spelling from the contract. A route the contract does
not declare is the drift AC-14 exists to close, and it is the surface B-12's contract-completeness
test fails the suite for, so the POST spelling is not mounted here even as a compatibility alias.

Rate limiting: none, exactly as B-08's table surface does it. Section 15 budgets login, join and
lookup only, the contract declares no 429 here, and ``app.main`` owns the one process ``Limiter``;
:func:`configure_limiter` adopts that instance and registers nothing.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.dependencies import DbSession, Staff, get_now
from app.schemas import (
    ReorderWaitlistRequest,
    SeatWaitlistRequest,
    WaitlistEntryResponse,
    WaitlistListResponse,
)
from app.services import staff_waitlist as service

router = APIRouter()
"""The staff waitlist surface: the nine contract operations (AC-1)."""

limiter = None
"""The one process limiter; :func:`configure_limiter` injects app.main's instance."""


@router.get("/api/v1/staff/waitlist", response_model=WaitlistListResponse)
def list_waitlist(
    staff: Staff,
    db: DbSession,
    status: str = Query(default="ACTIVE", description="ACTIVE | CLOSED | ALL"),
    search: str | None = Query(default=None, description="Name or phone last 3 digits"),
    party_size: int | None = Query(default=None, ge=1, le=20),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
) -> Any:
    """GET /api/v1/staff/waitlist: the queue, ordered by ``sort_order`` then ``created_at``.

    ``status`` is the contract's group filter (R-B07-2): an omitted value is the ``ACTIVE``
    default, ``ACTIVE``/``CLOSED``/``ALL`` answer their group, a single entry status answers that
    status, and a comma-separated list answers the union. Anything the enum does not define is 422
    ``VALIDATION_ERROR``, never a silent empty list. ``total`` is the size of the filter and
    ``items`` the ``limit``/``offset`` page of it.

    The lazy no-show of section 4.10 runs inside the service and is persisted, so a ``CALLED`` row
    past its hold reads back ``NO_SHOW`` on this call and on the next one.
    """
    return service.list_waitlist(
        db,
        now=get_now(),
        status=status,
        search=search,
        party_size=party_size,
        limit=limit,
        offset=offset,
    )


@router.put("/api/v1/staff/waitlist/{entry_id}", response_model=WaitlistEntryResponse)
async def edit_waitlist(
    request: Request,
    entry_id: str,
    staff: Staff,
    db: DbSession,
) -> Any:
    """PUT /api/v1/staff/waitlist/{entry_id}: edit party size or note (AC-6, AC-7, AC-13).

    The body is bound here rather than through ``EditWaitlistRequest`` so the two answers the AC
    set demands can be told apart: a ``status`` key - ``ACTIVE``, ``CLOSED`` or any other - is 422
    ``VALIDATION_ERROR`` and writes nothing (R-B07-2), and a body with no known key is refused
    rather than silently accepted, while ``{}`` is a no-op 200 that returns the entry unchanged.
    A ``party_size`` outside the schema's own range is the same 422 from the bound model, and an
    entry that is not ``WAITING`` or ``CALLED`` is 409 ``WAITLIST_INVALID_STATUS``.

    This handler is ``async`` because reading the body is an await: ``Request.body()`` is a
    coroutine function, and a ``def`` handler runs on a worker thread with no loop to await on, so
    the un-awaited coroutine reaches ``bytes.strip()`` as a coroutine object and every
    body-carrying request answers 500 ``INTERNAL_ERROR`` - the defect AC-6, AC-7 and AC-13 measure.
    """
    return service.edit_entry(
        db,
        entry_id,
        service.parse_edit_body(request.method, await _json_body(request)),
        get_now(),
    )


@router.post("/api/v1/staff/waitlist/reorder", response_model=WaitlistListResponse)
def reorder_waitlist(
    payload: ReorderWaitlistRequest,
    staff: Staff,
    db: DbSession,
) -> Any:
    """POST /api/v1/staff/waitlist/reorder: rewrite ``sort_order`` 1..n for the active set.

    ``ordered_ids`` has to be exactly the current ``WAITING`` + ``CALLED`` set. A well-formed list
    that is not - one id short, or one that includes a ``SEATED`` row - is 409 ``CONFLICT``
    (R-B07-1), because it is the staff user asking for an order over a queue that moved under them
    rather than a malformed request. 422 ``VALIDATION_ERROR`` stays reserved for what
    ``ReorderWaitlistRequest`` itself rejects: a non-UUID member, or a missing ``ordered_ids``.
    """
    return service.reorder(db, payload.ordered_ids, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/call", response_model=WaitlistEntryResponse)
def call_waitlist(entry_id: str, staff: Staff, db: DbSession) -> Any:
    """POST .../{entry_id}/call: ``WAITING`` to ``CALLED`` with the hold snapshot (section 4.2).

    ``called_at`` is the injected clock and ``hold_minutes_snapshot`` is the settings value at call
    time, so a later settings edit does not move a call already in flight (section 7). Any other
    state is 409 ``WAITLIST_INVALID_STATUS`` and an id this branch does not have is 404
    ``WAITLIST_NOT_FOUND``.
    """
    return service.call_entry(db, entry_id, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/seat", response_model=WaitlistEntryResponse)
def seat_waitlist(
    entry_id: str,
    payload: SeatWaitlistRequest,
    staff: Staff,
    db: DbSession,
) -> Any:
    """POST .../{entry_id}/seat: bind the entry to a table and seat it (section 4.3).

    Legal from ``WAITING`` and ``CALLED``; 409 ``WAITLIST_INVALID_STATUS`` from the four states
    section 5 forbids a seat from. The table is looked up first - a table this branch does not have
    is 404 ``TABLE_NOT_FOUND``, one that is not ``AVAILABLE`` is 409 ``TABLE_NOT_AVAILABLE`` - and
    the entry write plus the table's ``OCCUPIED`` write share one commit (section 14).
    """
    return service.seat_entry(db, entry_id, payload.table_id, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/no-show", response_model=WaitlistEntryResponse)
def no_show_waitlist(entry_id: str, staff: Staff, db: DbSession) -> Any:
    """POST .../{entry_id}/no-show: close the entry and free its table in one commit (section 4.4).

    ``NO_SHOW`` with ``closed_at``, the held table back to ``AVAILABLE`` and the entry's
    ``table_id`` cleared - all in the same transaction, because a released table with an
    unreleased entry is a booking that can be taken twice. No other table moves.
    """
    return service.no_show_entry(db, entry_id, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/restore", response_model=WaitlistEntryResponse)
def restore_waitlist(entry_id: str, staff: Staff, db: DbSession) -> Any:
    """POST .../{entry_id}/restore: back to ``WAITING`` from ``NO_SHOW`` only (section 4.5).

    ``called_at``, ``closed_at`` and ``hold_minutes_snapshot`` are all cleared - the prose of 4.5,
    which R-B07-3 rules for and the openapi ``restore`` example contradicts - and the row lands in
    front of the entries that joined after it.
    """
    return service.restore_entry(db, entry_id, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/revert", response_model=WaitlistEntryResponse)
def revert_waitlist(entry_id: str, staff: Staff, db: DbSession) -> Any:
    """POST .../{entry_id}/revert: back to ``WAITING`` from ``CALLED`` only (section 4.6).

    ``called_at`` and ``hold_minutes_snapshot`` are cleared; ``closed_at`` stays null because a
    ``CALLED`` entry was never closed.
    """
    return service.revert_entry(db, entry_id, get_now())


@router.post("/api/v1/staff/waitlist/{entry_id}/cancel", response_model=WaitlistEntryResponse)
def cancel_waitlist(entry_id: str, staff: Staff, db: DbSession) -> Any:
    """POST .../{entry_id}/cancel: staff cancel (section 4.7).

    ``CANCELLED`` with ``cancelled_reason=STAFF`` and ``closed_at``, from ``WAITING``, ``CALLED``
    or ``SEATED``; a held table is released the same way the no-show releases one. The guest path's
    ``cancel_entry`` writes ``CUSTOMER`` and does not release, so this surface keeps its own
    service call.
    """
    return service.cancel_entry(db, entry_id, get_now())


async def _json_body(request: Request) -> Any:
    """Return the request body as a mapping, or ``None`` when there is none to parse.

    The read is awaited, and the caller must be an ``async def`` endpoint to make that possible.
    ``Request.body()`` returns a coroutine, so an un-awaited call compares a coroutine object with
    ``bytes`` below and the endpoint dies on ``AttributeError`` behind a 500.

    The edit route is the only one with a body a client may omit, and an absent body is the
    contract's no-op: ``{}`` edits nothing and answers 200. A body that is not JSON at all is left
    for the service to refuse.
    """
    raw = await request.body()
    if not raw or not raw.strip():
        return None
    import json

    try:
        return json.loads(raw)
    except ValueError:
        return ""


def configure_limiter(app_limiter: Any) -> None:
    """Adopt ``app.main``'s one process limiter (called from ``app/main.py`` before mounting).

    No route on this router declares a limit (section 15 budgets login, join and lookup; the
    contract declares no 429 for these nine operations), so the hook stores the shared instance and
    registers nothing - ``limiter is app.state.limiter`` stays an identity check on one object, and
    no second ``Limiter`` is built here.
    """
    global limiter  # noqa: PLW0603 - one-time adoption of the shared process limiter
    limiter = app_limiter
