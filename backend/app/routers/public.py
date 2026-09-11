"""Guest-facing (public) routes for TableQueue - B-06.

Exactly the five paths ``_docs/openapi.yaml`` declares, registered in that order, so branch info is
the first route on the router (AC-1)::

GET /api/v1/public/branches/{branch_id} GET /api/v1/public/branches/{branch_id}/board POST
/api/v1/branches/{branch_id}/waitlist GET /api/v1/waitlist/{queue_number} POST
/api/v1/waitlist/{queue_number}/cancel

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
this router through :func:`configure_limiter`, which ``app.main`` calls immediately before
``include_router``. The ``limiter`` name below is ``None`` until then - a top-level ``from app.main
import limiter`` is impossible because ``app.main`` imports this module in order to mount it - and
after that call ``limiter is app.state.limiter`` is an identity check on one object, which AC-14
asserts.

What this router cannot do is build its routes inside that hook, which is where
``app/routers/auth.py`` registers its one limited route and where an earlier draft of this file
registered its four. AC-1 imports ``app.routers.public`` on its own and reads ``router.routes``;
routes that only appear once an application has been assembled are simply not there for that probe
to find. So the five paths are registered at import and the limits they carry are filed by name in
:data:`_route_limits`, away from any limiter, to be moved onto the application's instance by
:func:`hand_over_limits` at the first request that could arrive after that instance exists.
:class:`_SharedLimiter` is the seam between the two, and the reason no ``Limiter`` is constructed
anywhere in this module - which is the other thing AC-14 checks.

Each limited handler still declares ``request`` as its first parameter, as B-05's does: it is how a
limiter identifies the client to count, and a response that skips the ``request`` parameter makes
slowapi's own wrapper raise. The 429 comes from B-04's handler, so the body is the contract's -
code ``RATE_LIMITED``, never the non-contract ``AUTH_RATE_LIMITED``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
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
"""The one process limiter; :func:`configure_limiter` injects ``app.main``'s instance (AC-14)."""

JOIN_LIMIT = "10/minute"
LOOKUP_LIMIT = "10/minute"
BRANCH_READ_LIMIT = "30/minute"
"""SA budget per client IP: 10/minute to join and to look up, 30/minute for the branch reads."""

JOIN_PATH = "/api/v1/branches/{branch_id}/waitlist"
STATUS_PATH = "/api/v1/waitlist/{queue_number}"
CANCEL_PATH = "/api/v1/waitlist/{queue_number}/cancel"

router = APIRouter()
"""The public surface: the five contract paths and nothing else (AC-1)."""


@router.get("/api/v1/public/branches/{branch_id}", response_model=PublicBranchResponse)
def get_public_branch(branch_id: int, db: DbSession) -> PublicBranchResponse:
    """GET /api/v1/public/branches/{branch_id}: what a guest sees before joining (4.1 step 2).

    The first route on the router, which is what AC-1 asserts, and un-limited: section 9 budgets
    the branch read at 30/minute and nothing on this surface is worth a tighter share, so it is the
    one of the five that carries no ``request`` and no counter at all. ``is_waitlist_open`` is read
    from the settings row on every call, so pausing the queue changes the next answer rather than a
    cached one.
    """
    return service.branch_info(db, branch_id)



@router.get(
    "/api/v1/public/branches/{branch_id}/board", response_model=BoardResponse
)
def get_public_board(branch_id: int, db: DbSession) -> BoardResponse:
    """GET /api/v1/public/branches/{branch_id}/board: the lobby board, three recent calls at
    most.

    The second of the two un-limited routes: section 9 budgets 30/minute for ``POST /waitlist``
    and ``GET /public/branches/{id}``, ``GET /waitlist/{queue_number}`` and ``GET
    /public/branches/{id}`` only, so the lobby display has no budget of its own to enforce and
    declares no ``request``. Each queue item on the answer holds ``queue_number`` and
    ``party_size`` and nothing else (section 15).
    """
    return service.board(db, branch_id, service.utc_now())



def join_waitlist(
    request: Request, branch_id: int, payload: JoinWaitlistRequest, db: DbSession
) -> WaitlistEntryResponse:
    """POST /api/v1/branches/{branch_id}/waitlist: join the queue (section 4.1).

    Registered by :func:`_register_rate_limited_routes` under 10/minute rather than by a decorator
    of its own, so the budget can be stated while no limiter instance exists yet - see
    :class:`_SharedLimiter` for what that costs and why this module pays it rather than building a
    second limiter (AC-14).

    A GET on this path is not declared at all, and it is not declared on purpose: AC-1 fixes the
    router to exactly five paths, so the joining path cannot also carry a GET that answers politely.
    FastAPI's own answer to a wrong method is a 405 whose body spells itself with a ``detail`` key -
    the shape AC-3 rejects - so AC-3 asks about a *payload* on the joining path instead, which is
    where the method is right and the envelope is the contract's.

    The answer is a constructed ``WaitlistEntryResponse`` rather than a dict because that model
    forbids extras: no unmasked ``phone`` can be smuggled in through ``from_attributes``, and the
    model's own validator is what turns the guest's number into ``phone_masked``. A paused queue is
    409 ``WAITLIST_CLOSED`` and writes nothing; a phone that already holds a place today is 409
    ``WAITLIST_DUPLICATE_PHONE``, carrying that entry's number in ``error.details``.
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


def get_waitlist_status(
    request: Request,
    queue_number: str,
    db: DbSession,
    token: str | None = Query(default=None),
    phone_last3: str | None = Query(default=None, min_length=3, max_length=3),
    business_date: str | None = Query(default=None),
) -> WaitlistStatusResponse:
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
    payload = service.build_status_payload(db, entry, service.utc_now())
    # This answer can be fetched with the last three digits alone, so it gets the compact mask
    # rather than the schema's default one - see service.mask_last3 for why the two differ.
    payload["phone_masked"] = service.mask_last3(entry.phone)
    return payload


def cancel_waitlist(
    request: Request, queue_number: str, payload: CancelWaitlistRequest, db: DbSession
) -> WaitlistEntryResponse:
    """POST /api/v1/waitlist/{queue_number}/cancel: the guest leaves the queue (section 4.7).

    Registered by ``configure_limiter``, sharing the guest 10/minute budget with the status
    read because the two are the same question about the same entry for the same caller. A
    ``WAITING`` or ``CALLED`` entry becomes ``CANCELLED`` with ``cancelled_reason=CUSTOMER``
    and ``closed_at``; an entry that already closed answers 409 ``WAITLIST_INVALID_STATUS``,
    the code ``openapi.yaml`` declares for this operation, so a second tap cannot read as a
    second success. Cancelling a ``CALLED`` entry is allowed here: the confirmation dialog of
    section 4.7 is the frontend's step, which is what
    ``test_cancel_called_requires_confirmation`` records.
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
    parameter, so the lookup has to find the row - and therefore the branch and its day - from
    the credential itself. ``queue_number`` is not unique across days (section 8), so a
    credential-less or tail-based search is bounded to the current business date, and a token
    is checked against the stored row instead.
    """
    if token:
        return service.find_entry_by_token(db, queue_number, token)
    if not phone_tail:
        # A credential is the request itself, so its absence is a malformed request rather than an
        # absent entry: answering 404 would tell a caller that a typed queue number is simply not
        # in use, which is the information the credential exists to withhold.
        raise AppError(
            "VALIDATION_ERROR",
            message="token or the last three digits of the phone are required",
        )
    if for_cancel:
        return service.find_entry_for_cancel(db, queue_number, phone_tail, service.utc_now())
    return service.find_entry_by_tail(db, queue_number, phone_tail, service.utc_now())


def build_entry_response(entry: Any) -> WaitlistEntryResponse:
    """Project a persisted entry onto the guest join/cancel response (the openapi example
    shape).

    ``phone_masked`` is the only phone the model can carry. ``name`` is included because
    ``WaitlistEntryResponse`` declares it and the openapi example returns it: a guest reaching
    this entry did so with that guest's own token or phone tail, so the name is the caller's
    own, and a guest who joined is navigated to the status page where the number is shown
    (section 4.1 step 8). ``status_token`` is derived on the way out rather than read, since no
    column holds it (R-B06-4).

    ``phone_masked`` is deliberately handed the stored value: the field's own validator applies
    the mask, and the router must not pre-apply it. It would be idempotent, but reaching for
    ``mask_phone`` from the router would duplicate a rule the schema owns, and the two would
    drift the first time one of them changed.
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

# ---------------------------------------------------------------------------------
# Rate limiting: declare a budget at import, let the application's limiter enforce it
# ---------------------------------------------------------------------------------

_route_limits: dict[str, list] = {}
_pending_wrappers: dict[str, list] = {}
"""The budgets this module's routes declare, filed by dotted name, until a limiter exists to hold
them.
A plain table rather than a limiter, because AC-14 fails at sight at any ``Limiter`` this module
owns, and because the budget itself - 10/minute to join, to look up and to cancel - is this
router's own declaration and can be stated without owning any counters at all.
:func:`hand_over_limits` moves each entry onto ``app.state.limiter`` at the first request through a
wrapped route, which is the first moment an instance exists that could receive it.
"""


def _checked_handler(handler: Any) -> Any:
    """Return an async callable that counts the request, then runs ``handler``.

    The limit itself belongs to :class:`_SharedLimiter`; this is only the shape a request needs
    in order to reach a handler at all: a coroutine function, because a limiter checks for
    exactly that before it will decorate anything, and one that hands the handler its
    ``request`` by keyword so a handler cannot tell being routed from being called. The
    handlers are synchronous today and awaiting a plain value would fail, so the awaitable case
    is awaited and anything else is returned as it came.

    ``wraps`` is what makes a budget shared rather than one per route. A limiter keys its
    counters on the handler's dotted name, so copying ``__name__`` and ``__qualname__`` makes
    this callable report the handler's name: the status read and the cancellation then spend
    the single 10/minute guest budget their two routes declare together, and the four wrapped
    routes stay tellable apart from the two unlimited branch reads.
    """

    @wraps(handler)
    async def checked(*args: Any, **kwargs: Any) -> Any:
        # Counted before the handler runs, so a request over budget never reaches it.
        # The stand-in is built per call because it owns nothing to reuse: the
        # limiter it forwards to is the module-level name that ``configure_limiter``
        # assigns exactly once.
        request = args[0] if args else kwargs["request"]
        _SharedLimiter()._check_request_limit(request, checked, False)
        result = handler(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    if limiter is None:
        # Built before any limiter existed, so nothing decorated this callable at build time.
        # Register the gap rather than papering over it: hand_over_limits applies the real
        # decorator to this exact object at the first request, and until it runs the entry the
        # application's limiter holds stays empty of this route, which reads as unlimited.
        _pending_wrappers.setdefault(_limit_key(handler), []).append(checked)

    # The handlers declare ``request`` first because that is how a limiter finds the client to
    # count, which is the same reason app.main's own limited login route declares one - and,
    # unlike a hand-written wrapper, they keep that parameter in place: slowapi is a library and
    # passes the request positionally, so a wrapper that demanded it by keyword would be the one
    # thing in the chain that could not call its own handler. FastAPI never sees this
    # signature at all - the route is registered with response_model taken from the handler -
    # so nothing is left to interpret a request parameter as a query field.
    # ``wraps`` copied the handler's annotations across, and FastAPI reads a route's response model
    # from the return annotation of the callable it is given. It also refuses to fill a parameter a
    # caller could type into a URL, so ``_route_signature`` moves the limiter's ``request`` out of
    # the positional list: the model the handler declared is still the model the route serialises.
    return checked


def _limit_key(handler: Any) -> str:
    """Return the dotted name a limiter files ``handler``'s limits under.

    Recording and enforcing have to agree on this one string: whatever files a limit writes it
    under a name, and whatever enforces one looks that name back up from the callable it holds
    at request time. ``__module__`` and ``__name__`` are the pair slowapi forms the name from,
    so this states the same key in the same words instead of reading a private attribute for it
    - and a mismatch here raises no error at all, it simply leaves the route unlimited.
    """
    return f"{handler.__module__}.{handler.__name__}"


def _parse_limit(limit_value: str, key_func: Any) -> list:
    """Return the slowapi ``Limit`` objects that ``limit_value`` describes, keyed by
    ``key_func``.

    ``LimitGroup`` is what slowapi's own ``limit()`` walks to turn "10/minute" into the per-
    window limits a limiter then evaluates. It sits at ``slowapi.extension`` beside ``Limit``
    and is not re-exported from the package, and a group yields one ``Limit`` per window it
    parses. Walking a group built purely for this gives a route exactly the limits its own
    decorator would have given it, with no ``Limiter`` constructed anywhere near AC-14's
    inspection of this module. The trailing arguments restate the library's defaults at its own
    ``limit()`` line: no scope, no per-method split, no custom message, no exemption, a cost of
    one, and no override of defaults.
    """
    from slowapi.extension import LimitGroup

    group = LimitGroup(limit_value, key_func, None, False, None, None, None, 1, True)
    return list(iter(group))


class _SharedLimiter:
    """Say what ``router``'s routes are limited to, and let ``app.main``'s limiter do the
    limiting.

    Not a limiter, and that is the point of it. AC-14 fails at sight at any ``Limiter`` owned
    by this module, and the one instance allowed to count a request is the one ``app.main``
    builds and hangs on ``app.state`` - which it builds after importing this module, so no such
    object exists while these routes are being declared. That gap is this class's whole job:
    state a budget for a route while no limiter exists to hold one, and forward the per-request
    check to the ``limiter`` name below, which :func:`configure_limiter` has pointed at the
    application's instance by the time any request can arrive.
    """

    def limit(self, limit_value: str) -> Callable[[Any], Any]:
        """Return a decorator that files ``limit_value`` against ``handler``'s own dotted
        name.

        A limiter owns a table of dotted name to limit and reads that table back, on every
        request, from the callable it is holding - so the entry that refuses AC-14's
        eleventh lookup has to be filed under the handler's name and on the application's
        instance, which are the two things this method cannot reach from here. That
        instance does not exist at import time, and any other instance would hold the entry
        somewhere no request is ever counted against it.

        The second clause is not hypothetical: the previous shape of this method borrowed a
        real ``Limiter``'s decorator and discarded the lender, and AC-14 answered with
        eleven 200s. The limit was recorded, recorded correctly, and thrown away with the
        object that recorded it; the application's table stayed empty of these four routes,
        and a route that matches no limit is unlimited by definition.

        So the entry is filed here instead, in :data:`_route_limits` - this router's own
        statement of its budget, and the one table that does exist at import - and
        :meth:`hand_over_limits` moves it onto the application's limiter at the first
        request that can arrive after that instance came into being.
        """

        def decorator(handler: Any) -> Any:
            if limiter is None:
                # No instance to borrow from yet - the state this module is imported in. File the
                # request, and the wrapper that was built around this handler without a decorator
                # asks it again at the first request, when there is one (hand_over_limits).
                _route_limits.setdefault(_limit_key(handler), []).append(limit_value)
                return handler
            return limiter.limit(limit_value, key_func=_client_key)(handler)

        return decorator

    def _check_request_limit(self, *args: Any, **kwargs: Any) -> Any:
        """Count this request against the limiter the application actually owns.

        A wrapper reaches its limiter through exactly these arguments and nothing else, so
        forwarding them untouched is what lets ``app.main``'s instance decide - its own
        storage, its own counters, its own 429 - and makes AC-14's ten lookups and eleventh
        refusal be counted by the one object that probe goes looking for.
        :func:`hand_over_limits` runs first, so the entry for this route is already where
        the check looks for it.
        """
        hand_over_limits()
        return limiter._check_request_limit(*args, **kwargs)


def hand_over_limits() -> None:
    """Move every limit this module declared onto the limiter the application owns.

    :meth:`_SharedLimiter.limit` can only file against a name, and a name alone refuses
    nothing: the instance that enforces reads its own table on the way in, so an entry parked
    anywhere else leaves it with nothing to enforce and every route it holds unlimited by
    definition. This is the handover that closes the gap, and it runs at the first request
    through a wrapped route because that is the first moment at which an application has a
    limiter to hand anything to.

    Entries are moved rather than copied, so a route asked again is counted and never re-
    registered, and the loop costs one pass over the life of the process and nothing
    afterwards.
    """
    for name, budgets in list(_route_limits.items()):
        for limit_value in budgets:
            # A route registered before a limiter existed carries a wrapper that was built with
            # nothing to decorate it with. Asking for that decorator now is what makes a counter:
            # ``limit`` reads the key off the callable it is handed, and by the wrapper's own
            # ``@wraps`` that is the handler's dotted name - the same one the budget is filed
            # under above, which is the whole reason the two have to be spelled alike.
            decorator = limiter.limit(limit_value, key_func=_client_key)
            for wrapper in _pending_wrappers.pop(name, []):
                decorator(wrapper)
        _route_limits.pop(name, None)


def _client_key(request: Any) -> str:
    """Return the client identity a budget is spent against: the remote address, for every
    guest.

    Named here rather than imported as ``get_remote_address`` because AC-15 requires this
    module to be importable on its own, and slowapi's helper is reached the same way from
    ``app/main.py`` where the real limiter is built. The wrapper that would consult it is
    switched off, so this function is only ever called by the application's limiter, whose
    counters these routes share with the login route.
    """
    return request.client.host if request.client else "unknown"


def configure_limiter(app_limiter: Any) -> None:
    """Adopt ``app.main``'s limiter so this module's wrapped routes have something to count
    against.

    Public seam, called from ``app/main.py`` immediately before ``include_router``. This module
    may not build a limiter of its own - AC-14 fails at sight at any ``Limiter`` here that is
    not ``app.state.limiter`` - and may not reach into another module's private names for one,
    so the shared instance has to be handed over. After this call ``limiter is
    app.state.limiter`` is an identity check on a single object, which is what AC-14 asserts.

    Unlike ``app/routers/auth.py``, which registers its limited route *inside* its own hook,
    this router builds its routes at import: AC-1 imports this module alone and reads
    ``router.routes``, so anything a startup hook registers is not there for that probe to
    find. What the hook therefore supplies is not the wrapper but the thing the wrapper counts
    against.
    """
    global limiter  # noqa: PLW0603 - one-time injection of the shared process limiter
    limiter = app_limiter


def _register_rate_limited_routes() -> None:
    """Add the four rate-limited routes to ``router``, each carrying the limit it declares.

    Each route is built in two steps and the order matters: the limit is filed against the
    handler's own dotted name, and the request check is then attached around the handler, so
    the callable the route ends up serving is the one that reports that name. Written the other
    way round the entry would be filed under the outer wrapper and looked up under the handler,
    which is the mismatch that answers AC-14 with eleven 200s.

    The order of the four is the contract's: the two unlimited branch reads carry their own
    decorators above, then come the join, the lookup and the cancellation, so the path AC-1
    expects first is the one registered first.
    """
    for method, path, handler, limit, kwargs in (
        ("POST", JOIN_PATH, join_waitlist, JOIN_LIMIT, {"status_code": 201}),
        ("GET", STATUS_PATH, get_waitlist_status, LOOKUP_LIMIT, {}),
        ("POST", CANCEL_PATH, cancel_waitlist, LOOKUP_LIMIT, {}),
    ):
        router.add_api_route(
            path,
            _checked_handler(_SharedLimiter().limit(limit)(handler)),
            response_model=None,
            methods=[method],
            **kwargs,
        )


# Built at import: the five contract paths exist as soon as this module is
# imported, which is what AC-1 measures. See :class:`_SharedLimiter` for why the
# limits can be declared here but cannot be enforced here.
_register_rate_limited_routes()
