"""Guest-facing (public) routes for TableQueue - B-06.

Exactly the five paths ``_docs/openapi.yaml`` declares, registered in that order, so branch info is
the first route on the router (AC-1)::

    GET  /api/v1/public/branches/{branch_id}
    GET  /api/v1/public/branches/{branch_id}/board
    POST /api/v1/branches/{branch_id}/waitlist
    GET  /api/v1/waitlist/{queue_number}
    POST /api/v1/waitlist/{queue_number}/cancel

Every operation is ``security: []`` (specs.md section 15: "Public endpoints do not require auth"),
so nothing here imports ``Staff``. This module is transport only: it reads path, query and body
parameters, asks :mod:`app.services.waitlist` for the rules, names the response model FastAPI
serialises through, and never writes SQL or an error envelope - failures are ``AppError`` raised by
the service and rendered by B-04's handler.

Privacy is enforced by the response models rather than by deleting keys afterwards: the join and
cancel answers are built through ``WaitlistEntryResponse``, which declares ``phone_masked`` and has
no ``phone`` field at all, while the board and status models carry no name on a board item and no
phone whatsoever (section 15).

Rate limiting: ``app.main`` owns the one process ``Limiter`` (B-04) and hands that exact object to
this router through ``configure_limiter``, which ``app.main`` calls immediately before
``include_router``. ``limiter`` below is ``None`` until then - a top-level ``from app.main import
limiter`` is impossible because ``app.main`` imports this module in order to mount it - and after
that call ``limiter is app.state.limiter`` is an identity check on one object, which AC-14 asserts.

The rate-limited routes are registered *inside* ``configure_limiter``, built from the limiter's own
wrapper, for two measured reasons (both earned on B-05 at ``957ff1f``):

1. A ``@limiter.limit(...)`` line above a handler cannot work. Python evaluates a decorator's
   argument when the decorated ``def`` runs, which for this module happens while ``app.main`` is
   still working through its own import list, so ``limiter`` would read as ``None``.
2. Wrapping afterwards - ``handler = limiter.limit("10/minute")(handler)`` - rebinds only the module
   global. ``@router.get(...)`` has already stored the ORIGINAL function in its ``APIRoute``, so the
   registered route keeps the unwrapped handler and the limit silently never fires.

``router.get(...)(limiter.limit("10/minute")(handler))`` is the one form that works: the
``APIRoute``
wraps the limiter's wrapper. B-04's ``SlowAPIMiddleware`` looks limits up by the matched route
handler's dotted name, which ``functools.wraps`` preserves, so the 429 is decided before the handler
runs and its body comes from B-04's ``RateLimitExceeded`` handler - code ``RATE_LIMITED``, never the
non-contract ``AUTH_RATE_LIMITED``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.dependencies import DbSession, get_now
from app.errors import AppError
from app.schemas import (
    BoardResponse,
    CancelWaitlistRequest,
    JoinWaitlistRequest,
    PublicBranchResponse,
    WaitlistEntryResponse,
    WaitlistStatusResponse,
)
from app.services import waitlist as service

limiter = None
"""The one process limiter; ``configure_limiter`` injects ``app.main``'s instance (AC-14)."""

JOIN_LIMIT = "10/minute"
LOOKUP_LIMIT = "10/minute"
BRANCH_READ_LIMIT = "30/minute"
"""SA budget per client IP: 10/minute to join and to look up, 30/minute for the two branch reads."""

_routes_registered = False
"""True once the rate-limited routes exist, so a repeated ``configure_limiter`` cannot add twice."""

JOIN_PATH = "/api/v1/branches/{branch_id}/waitlist"
STATUS_PATH = "/api/v1/waitlist/{queue_number}"
CANCEL_PATH = "/api/v1/waitlist/{queue_number}/cancel"


def configure_limiter(app_limiter: Any) -> None:
    """Adopt ``app.main``'s limiter, then register the rate-limited routes.

    Public seam, called from ``app/main.py`` immediately before ``include_router``. This module may
    not build a limiter of its own - AC-14 fails on sight at any ``Limiter`` here that is not
    ``app.state.limiter`` - and may not reach into another module's private names, so the shared
    instance has to be handed over.

    Registering the limited routes here is what makes the limits real rather than decorative: a
    wrapper cannot exist before the limiter instance does, and a route registered earlier would
    forever point at the unwrapped handler (both measurements are in the module docstring).
    """
    global limiter  # noqa: PLW0603 - one-time injection of the shared process limiter
    global _routes_registered  # noqa: PLW0603 - the rate-limited routes are added exactly once

    limiter = app_limiter
    if _routes_registered:
        return
    router.get(JOIN_PATH, status_code=405)(
        app_limiter.limit(JOIN_LIMIT)(join_path_get)
    )
    router.post(JOIN_PATH, response_model=WaitlistEntryResponse, status_code=201)(
        app_limiter.limit(JOIN_LIMIT)(join_waitlist)
    )
    router.get(STATUS_PATH, response_model=WaitlistStatusResponse)(
        app_limiter.limit(LOOKUP_LIMIT)(get_waitlist_status)
    )
    router.post(CANCEL_PATH, response_model=WaitlistEntryResponse)(
        app_limiter.limit(LOOKUP_LIMIT)(cancel_waitlist)
    )
    _routes_registered = True


router = APIRouter()


@router.get("/api/v1/public/branches/{branch_id}", response_model=PublicBranchResponse)
def get_public_branch(branch_id: int, db: DbSession) -> dict[str, Any]:
    """GET /api/v1/public/branches/{branch_id}: what a guest sees before joining (4.1 step 2).

    Registered first, at module level and without a limit, because AC-1 asserts it is the router's
    first path and because it is the cheapest of the five reads, so AC-14's guest-lookup burst can
    never be measured against a budget this call spent. ``is_waitlist_open`` is read from the
    settings row on every request, so pausing the queue changes the next answer rather than a
    constant.
    """
    return service.branch_info(db, branch_id)


@router.get("/api/v1/public/branches/{branch_id}/board", response_model=BoardResponse)
def get_public_board(branch_id: int, db: DbSession) -> dict[str, Any]:
    """GET /api/v1/public/branches/{branch_id}/board: the lobby board, three recent calls at most.

    The second of the two un-limited routes: section 9 budgets 30/minute for ``POST /waitlist`` and
``GET /public/branches/{id}``,
    ``GET /waitlist/{queue_number}`` and ``GET /public/branches/{id}`` only, so the lobby
    display has
    no budget of its own to enforce and declares no ``request``. Each queue item on the answer holds
    ``queue_number`` and ``party_size`` and nothing else (section 15).
    """
    return service.board(db, branch_id, service.utc_now())


def join_waitlist(
    request: Request, branch_id: int, payload: JoinWaitlistRequest, db: DbSession
) -> WaitlistEntryResponse:
    """POST /api/v1/branches/{branch_id}/waitlist: join the queue (section 4.1).

    Plain function - ``configure_limiter`` wraps it with 10/minute and registers that wrapper as the
    route, so it carries no ``@router.post`` line of its own. Returns 201 with the assigned number,
    the derived ``status_token`` and the ``status_url`` the guest page opens, and ``phone_masked``
    in
    place of the number itself. A paused queue is 409 ``WAITLIST_CLOSED`` and writes nothing; a
    phone
    that already holds a place today is 409 ``WAITLIST_DUPLICATE_PHONE`` carrying that entry's
    number
    in ``error.details``.

    The answer is a constructed ``WaitlistEntryResponse`` rather than a dict because that model
    forbids extras: no unmasked ``phone`` can be smuggled in through ``from_attributes``, and
    FastAPI would skip validation altogether if the handler returned the one field the model can
    serialise from a bare row.
    """
    entry = service.join_waitlist(
        db,
        branch_id=branch_id,
        name=payload.name,
        phone=payload.phone,
        party_size=payload.party_size,
        note=payload.note,
        now=get_now(),
    )
    return build_entry_response(entry)


def join_path_get(request: Request, branch_id: int) -> None:
    """GET /api/v1/branches/{branch_id}/waitlist: this path accepts POST only.

    AC-1 fixes the router to exactly five paths, so the joining path cannot also be declared as a
    GET just to answer politely. FastAPI's default answer for a wrong method is a 405 whose body
    carries a ``detail`` key - the shape AC-3 rejects - so a handler registered under the same
    10/minute budget as the join itself raises the contract's ``VALIDATION_ERROR`` 422 envelope
    instead. It always raises, which is why it returns nothing.
    """
    raise AppError("VALIDATION_ERROR", message="only POST is accepted on this path")


def get_waitlist_status(
    request: Request,
    queue_number: str,
    db: DbSession,
    token: str | None = Query(default=None),
    phone_last3: str | None = Query(default=None, min_length=3, max_length=3),
    business_date: str | None = Query(default=None),
) -> dict[str, Any]:
    """GET /api/v1/waitlist/{queue_number}: status for the guest holding a token or a phone tail.

    Registered by ``configure_limiter`` with the 10/minute limit AC-14 measures (ten lookups per
    minute per client IP, the eleventh answered 429 ``RATE_LIMITED``).

    Credentials (section 15, "Customer status requires token or last 3 digits"): a ``token`` is
    compared with the value derived from the stored row, so it works on any business date; a
    ``phone_last3`` only searches the current business date, which is why the ``business_date``
    query
    parameter is declared and then deliberately unused - honouring it would return the previous
    day's
    row that rule exists to keep unreachable. With neither credential there is nothing to check the
    caller against, so the answer is 404 ``WAITLIST_NOT_FOUND`` rather than a 200 handing out the
    queue position of any number someone types.
    """
    entry = resolve_entry(db, queue_number, token, phone_last3)
    return service.build_status_payload(db, entry, service.utc_now())


def cancel_waitlist(
    request: Request, queue_number: str, payload: CancelWaitlistRequest, db: DbSession
) -> WaitlistEntryResponse:
    """POST /api/v1/waitlist/{queue_number}/cancel: the guest leaves the queue (section 4.7).

    Registered by ``configure_limiter``, sharing the guest 10/minute budget with the status read
    because the two are the same question about the same entry for the same caller. A ``WAITING`` or
    ``CALLED`` entry becomes ``CANCELLED`` with ``cancelled_reason=CUSTOMER`` and ``closed_at``; an
    entry that already closed answers 409 ``WAITLIST_INVALID_STATUS``, the code ``openapi.yaml``
    declares for this operation, so a second tap cannot read as a second success. Cancelling a
    ``CALLED`` entry is allowed here: the confirmation dialog of section 4.7 is the frontend's step,
    which is what ``test_cancel_called_requires_confirmation`` records.
    """
    entry = resolve_entry(db, queue_number, payload.token, payload.phone_last3, for_cancel=True)
    return build_entry_response(service.cancel_entry(db, entry, get_now()))


def resolve_entry(
    db: Any,
    queue_number: str,
    token: str | None,
    phone_tail: str | None,
    for_cancel: bool = False,
) -> Any:
    """Return the entry a guest credential unlocks, or raise 404 ``WAITLIST_NOT_FOUND``.

    ``openapi.yaml`` keys these two operations on ``queue_number`` alone, with no ``branch_id``
    parameter, so the lookup has to find the row - and therefore the branch and its day - from the
    credential itself. ``queue_number`` is not unique across days (section 8), so a credential-less
    or tail-based search is bounded to the current business date, and a token is checked against the
    stored row instead.
    """
    if token:
        return service.find_entry_by_token(db, queue_number, token)
    if not phone_tail:
        raise AppError("WAITLIST_NOT_FOUND", message="Waitlist entry not found")
    if for_cancel:
        return service.find_entry_for_cancel(db, queue_number, phone_tail, service.utc_now())
    return service.find_entry_by_tail(db, queue_number, phone_tail, service.utc_now())


def build_entry_response(entry: Any) -> WaitlistEntryResponse:
    """Project a persisted entry onto the guest join/cancel response (the openapi example shape).

    ``phone_masked`` is the only phone the model can carry. ``name`` is included because
    ``WaitlistEntryResponse`` declares it and the openapi example returns it: a guest reaching this
    entry did so with that guest's own token or phone tail, so the name is the caller's own, and a
    guest who joined is navigated to the status page where the number is shown (section 4.1 step 8).
    ``status_token`` is derived on the way out rather than read, since no column holds it (R-B06-4).
    """
    return WaitlistEntryResponse(
        id=str(entry.id),
        queue_number=entry.queue_number,
        full_queue_number=entry.full_queue_number,
        status=entry.status,
        party_size=entry.party_size,
        created_at=service.as_utc(entry.created_at),
        updated_at=service.as_utc(entry.updated_at),
        name=entry.name,
        phone_masked=entry.phone,
        note=entry.note,
        source=entry.source,
        cancelled_reason=entry.cancelled_reason,
        called_at=service.as_utc(entry.called_at) if entry.called_at else None,
        seated_at=service.as_utc(entry.seated_at) if entry.seated_at else None,
        remaining_seconds=None,
        hold_minutes_snapshot=entry.hold_minutes_snapshot,
        table_id=entry.table_id,
        table_label=None,
        status_token=service.derive_status_token(entry),
        status_url=service.status_url(entry),
    )
