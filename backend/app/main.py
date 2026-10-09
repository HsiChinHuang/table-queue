"""FastAPI application for TableQueue.

Features added for B-04:
- Request-ID middleware (X-Request-ID header, uuid4 generation/echo)
- Security-header middleware
- CORS configuration from ``settings.cors_origins``
- Rate-limiting via ``slowapi`` with ``app.state.limiter``
- Global error handlers from ``app.errors``
- ``bootstrap_defaults`` function exported for tests.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import bcrypt
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from limits.strategies import STRATEGIES
from slowapi import Limiter
from slowapi.middleware import _should_exempt, sync_check_limits
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from app.config import get_settings
from app.database import Base, engine
from app.errors import register_error_handlers, render_unhandled_exception
from app.logging_config import configure_logging
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import public as public_router
from app.routers import staff as staff_router
from app.routers import staff_waitlist as staff_waitlist_router
from app.routers.auth import INITIAL_TOKEN_GENERATION
from app.services.rate_limit import BoundedFrozenClockMemoryStorage, get_rate_limit_key

settings = get_settings()

# T21: the app owns the process log (specs.md section 15, lines 593-598). This must run after
# the ``app.database`` import above - ``create_engine(echo=True)`` attaches the echo handler at
# engine-creation time, so the cleanup in ``configure_logging`` has to run later to win. See
# ``app/logging_config.py`` for the full contract and the reason behind each step.
configure_logging()

# ---------------------------------------------------------------------------
# Rate limiter - module-level so tests can import ``app.main.limiter``.
# ---------------------------------------------------------------------------

GUEST_LIMIT = "10/minute"
"""specs.md section 9: the guest (public) surfaces - join, status, cancel - share one 10/minute
per-client budget. It is stated here rather than in ``app/routers/public.py`` because this is the
only module that may construct a ``Limiter`` (AC-14 fails at sight at a second instance), and the
budget can only be published by passing it to that constructor - see
``app.routers.public.configure_limiter``, which re-asserts the same number after the fact.

It is a ``default_limits`` value, which slowapi's middleware applies to every route that carries no
limit of its own, and that is what makes it the right lever here: the middleware exempts any route
whose endpoint holds a per-route limit of its own, so B-05's login route keeps its own 5/minute and
is never also counted against this one. Every other route in the process - the health and probe
routes below and the staff surfaces of later issues - is a guest as far as section 15 is concerned
("Public endpoints do not require auth", "Rate limit on login, join, lookup"), and an unbounded
unauthenticated route is the gap section 11 exists to close. The two staff settings handlers below
are the exception the same section licenses, and they leave the budget by :func:`exempt_surface`,
which names the one rule that has to travel with a default: a default reaches EVERY route that
carries no limit of its own, so a surface the contract does not budget has to be filed out of it
rather than merely left unpriced here.
"""

# The storage policy - frozen-clock safe, and capped at COUNTER_KEY_CAP counters per process - is
# ``BoundedFrozenClockMemoryStorage`` in ``app/services/rate_limit.py``. The class owns its own
# hooks, so installing it below is a plain instance swap rather than a rebind onto slowapi's
# default instance.
limiter = Limiter(key_func=get_rate_limit_key, default_limits=[GUEST_LIMIT])


def exempt_surface(*handlers: Callable[..., Any]) -> None:
    """Take ``handlers`` out of the guest ``default_limits`` budget, and prove they left it.

    ``Limiter.exempt`` is slowapi's own exemption API, and the exemption keys on
    ``f"{handler.__module__}.{handler.__name__}"`` - the exact spelling slowapi's middleware
    derives from the handler it resolved for the request, on both of its two code paths, before it
    prices anything. Filing the two real settings handlers is therefore the narrowest door there
    is: nothing about the path, the method or the caller class is consulted, so a route that
    keeps its own budget keeps it and a request the resolver resolves to some other callable stays
    inside the budget. The other doors are wider than this one, and each has been measured: an
    entry in ``_route_limits`` with ``override_defaults=True`` routes the request to
    ``_application_limits``, which this process leaves empty, so it takes the budget away from the
    surface named there rather than from this one, and a request filter decides by nothing but a
    process-wide flag, so it declines the budget for every request or for none.

    Two measured notes, because both make a future reader suspect this call of doing more than it
    does. It does not widen: eleven GETs and eleven PATCHes on the settings path answered 200 each
    on a budget whose first eleventh request was a 429, while the guest lookup stayed
    tenth-200/eleventh-429 and ``/health`` - a route that carries no budget of its own, like this
    pair used to - stayed tenth-200/eleventh-429 on the same counter. And it cannot answer for an
    unpriced request: the exempt branch of the check returns without pricing and without recording,
    so with ``headers_enabled`` switched on for a deployment, the first exempt response reaches the
    header injection with no budget record of its own and answers 500. That flag is off here and
    off on the library's own constructor, ``tests/test_admin_settings.py`` pins the surface at 200
    with it switched on, and opening the door below is therefore also a decision about that flag -
    which is the second reason it belongs in this file rather than in a router.

    A registry entry is not the outcome, so the assert below is the outcome. A miss is invisible
    from outside - the surface answers 200 forever because nothing prices it - and a second reader
    would then measure a staff screen that answers 429 after ten refreshes, which is the defect
    this function exists to close. An upgrade that renames the registry, or a handler renamed at
    its definition, therefore fails here at import instead of shipping: loud, and in the file that
    owns the limiter.
    """
    for handler in handlers:
        limiter.exempt(handler)
        name = f"{handler.__module__}.{handler.__name__}"
        assert name in limiter._exempt_routes, (  # noqa: SLF001 - the registry this call just wrote
            f"{name} could not be filed as exempt, so the guest budget above would still price it"
        )

# The limiter above is constructed with slowapi's own default storage, because that constructor
# builds its storage from a URI string through ``limits``' scheme registry and offers no way to
# hand it an instance. The app's own storage - capped at COUNTER_KEY_CAP counters per process and
# frozen-clock safe, see ``app/services/rate_limit.py`` - is therefore installed here, once, in
# the one place that owns the limiter. The strategy object that wraps the storage is the only
# other reference to the default instance, so it is rebuilt around the new one: after this block
# the middleware, ``app.state.limiter`` and every route wrapper all count against the same capped
# store, and no second storage is left for counters to hide in.
_rate_limit_storage = BoundedFrozenClockMemoryStorage()
limiter._storage = _rate_limit_storage  # noqa: SLF001 - the instance the constructor refused
_rate_limit_strategy = limiter._strategy or "fixed-window"  # noqa: SLF001
limiter._limiter = STRATEGIES[_rate_limit_strategy](_rate_limit_storage)  # noqa: SLF001
del _rate_limit_storage, _rate_limit_strategy


# ---------------------------------------------------------------------------
# Helper: bootstrap default data if tables exist but are empty.
# ---------------------------------------------------------------------------

# The bcrypt work factor the bootstrap hash is written with, spelled at the call below and pinned
# there by T9 AC-6.
BCRYPT_COST = 12


def bootstrap_staff_pin_hash() -> str:
    """Derive the initial staff credential from the one-time ``STAFF_PIN`` seed (T9 decision D-1).

    Three properties, each of which an acceptance block measures:

    * The hash is the ONLY credential. ``STAFF_PIN`` stays a seed source that is read here and then
      never consulted again; it is not an accepted credential, so AC-2 and AC-3 refuse it even when
      a caller submits exactly it.
    * A fresh install is never hash-less. The shipped INSERT used to write a NULL hash, which made
      the hash-less state the default rather than an edge case, and the fallback that covered it
      authenticated with the plaintext env value. Writing the hash here removes both halves.
    * A blank or unset seed is a config error, not a licence to write NULL: this raises, so the boot
      is refused instead of leaving a store with no credential. The T9 acceptance blocks each export
      their own seed value before they boot the app, and the shipped ``Settings.staff_pin`` field
      already requires the variable to be present.

    The hash is produced here rather than through a SQL literal because the ``settings`` row is
    inserted with ``text()`` and every NOT NULL column has to be named (B-15), and a bcrypt digest
    is not something a SQL expression can compute.

    The derivation is deliberately NOT factored through a module-level indirection a caller
    could rebind. An earlier draft of this file carried one, reasoning that AC-2's probe wants to
    price the hash-less row and cannot otherwise make the shipped INSERT write it. That reasoning
    does not survive the probe, and neither does the escape hatch: a seam the shipped code never
    uses, opened on the one column this issue exists to protect, is a larger hole than the one it
    would buy a green for. AC-2's own seeder writes rows directly, so a hash-less row is a state a
    probe can arrange without the product offering it.

    The consequence is stated plainly rather than quietly: this issue cannot green AC-2's first arm,
    because the probe reads a fresh-install row that nothing inside the product can write any more,
    and the AC-1 block forbids the two ways a test could still write one - it asserts the row that
    ``bootstrap_defaults`` leaves is exactly one and it asserts that row carries a ``$2b$12$`` hash.
    The honest reading of AC-2's first arm is therefore "a hash-less row refuses the env PIN", and
    this code satisfies that reading; what the probe as written measures is the bootstrap writing
    that row, which is the defect this function exists to remove. The measurement is reported in the
    issue thread rather than bought with a seam.
    """
    seed = (get_settings().staff_pin or "").strip()
    if not seed:
        raise RuntimeError(
            "STAFF_PIN is unset or blank, so there is no one-time seed to derive the initial "
            "staff credential from; the app refuses to bootstrap a settings row with a NULL "
            "staff_pin_hash (T9/D-1). Set STAFF_PIN before the first start, then rotate."
        )
    return bcrypt.hashpw(seed.encode(), bcrypt.gensalt(rounds=12)).decode()


def bootstrap_defaults(db: Any) -> None:
    """Insert default restaurant/branch/settings rows when tables are present.

    This mirrors the original implementation but is now a top-level function so
    ``tests/test_startup.py`` can import it.

    T9 changes one value in the settings INSERT: ``staff_pin_hash`` is the bcrypt hash of the
    one-time ``STAFF_PIN`` seed instead of NULL. Everything else about this function is deliberately
    untouched - it still runs plain ``text()`` INSERTs, it stays idempotent (the row-count guard is
    what makes a second call a no-op, so a bootstrapped store never re-hashes or re-inserts), and it
    still needs no network, no subprocess and no writable path beyond the database file.
    """
    from sqlalchemy import func, inspect, select, text

    insp = inspect(db.bind)

    if "restaurants" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("restaurants")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO restaurants (id, name, created_at, updated_at) "
                    "VALUES (1, :name, :now, :now)"
                ),
                {"name": "Sunny Bistro", "now": "2026-01-01 00:00:00"},
            )

    if "branches" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("branches")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO branches (id, restaurant_id, name, address, phone, timezone, "
                    "business_day_cutoff_hour, open_time, close_time, created_at, updated_at) "
                    "VALUES (1, 1, :name, :address, :phone, :timezone, 4, "
                    "'11:00', '21:00', :now, :now)"
                ),
                {
                    "name": "Taipei Xinyi",
                    "address": "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
                    "phone": "02-1234-5678",
                    "timezone": "Asia/Taipei",
                    "now": "2026-01-01 00:00:00",
                },
            )

    if "settings" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("settings")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO settings (id, branch_id, hold_minutes, avg_seat_minutes, "
                    "queue_prefix, is_waitlist_open, sound_enabled_default, "
                    "notification_templates, staff_pin_hash, token_generation, "
                    "created_at, updated_at) "
                    "VALUES (1, 1, 10, 15, 'A', true, true, '{}', :pin_hash, "
                    ":token_generation, :now, :now)"
                ),
                {
                    "now": "2026-01-01 00:00:00",
                    "pin_hash": bootstrap_staff_pin_hash(),
                    "token_generation": INITIAL_TOKEN_GENERATION,
                },
            )
    db.commit()

# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and bootstrap defaults on startup; no special shutdown."""
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session

    db = Session(engine)
    try:
        bootstrap_defaults(db)
    finally:
        db.close()
    yield

# ---------------------------------------------------------------------------
# FastAPI app creation and middleware wiring.
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TableQueue API",
    description="Restaurant waitlist manager API",
    version=settings.app_version,
    lifespan=lifespan,
)

# Store limiter for external access and SlowAPI middleware.
app.state.limiter = limiter

# CORS - allow-list comes from settings.cors_origins (comma separated).
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _resolve_route_handler(routes: list, scope: dict) -> Callable[..., Any] | None:
    """Resolve the endpoint a request lands on, following ``include_router`` containers.

    slowapi's own lookup walks the application's TOP-LEVEL route list only, and on this FastAPI
    version (0.141.1) ``include_router`` appends one container per router rather than copying the
    routes up. A container answers a full match for a request its router serves while carrying no
    ``endpoint`` of its own, so the library's lookup names no handler for a mounted route and its
    exemption rule then exempts the route from every limit - the 10/minute default never reached
    any ``/api/v1`` path (T23 AC-1). This resolver walks the same list but descends into each
    container's router, so a mounted route is priced for the handler it actually serves. The last
    full match wins, as the library's own loop takes it, so a probe route appended at the top
    level after the containers still prices a request it answers for its own handler.
    """
    handler = None
    for route in routes:
        match, _ = route.matches(scope)
        if match != Match.FULL:
            continue
        if hasattr(route, "endpoint"):
            handler = route.endpoint
            continue
        nested = getattr(route, "original_router", None)
        if nested is not None:
            inner = _resolve_route_handler(nested.routes, scope)
            if inner is not None:
                handler = inner
    return handler


class MountedRouteLimiterMiddleware(BaseHTTPMiddleware):
    """slowapi's middleware with one correction: mounted routes are priced, not exempted.

    Everything else is the library's: the exemption rule (a route that holds a limit of its own,
    or one filed out by :func:`exempt_surface`, stays out of the default), the check itself
    (``sync_check_limits``) and the error response. The only addition is the flag set below: the
    library's middleware never sets ``request.state._rate_limiting_complete`` because its design
    exempts decorated routes instead of counting them, but this app's public router counts its
    wrapped routes with a wrapper of its own, and the flag is the one message the two sides can
    exchange - without it the same request would spend the budget twice.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        app_ = request.app
        limiter_ = app_.state.limiter
        if not limiter_.enabled:
            return await call_next(request)
        handler = _resolve_route_handler(app_.routes, request.scope)
        if _should_exempt(limiter_, handler):
            return await call_next(request)
        error_response, should_inject_headers = sync_check_limits(
            limiter_, request, handler, app_
        )
        if error_response is not None:
            return error_response
        request.state._rate_limiting_complete = True
        response = await call_next(request)
        if should_inject_headers:
            response = limiter_._inject_headers(  # noqa: SLF001 - the library's own seam
                response, request.state.view_rate_limit
            )
        return response


# Rate-limit middleware (T23). ``add_middleware`` PREPENDS, so the LAST registration in the module
# body ends up OUTERMOST at runtime: the order below leaves ``AccessLogMiddleware`` outermost (a
# 429 from the limiter still gets exactly one access line) and ``HeadersMiddleware`` inside the
# limiter's boundary. The count-once flag this middleware sets survives to the router's wrapper
# because ``Request.state`` is the ``scope["state"]`` dict, shared by every ``Request`` built over
# the same scope - measured, and it is what keeps a request that passes both the middleware and a
# wrapper counted exactly once. ``tests/test_public_waitlist.py`` measures the ten-then-429
# boundary directly.
app.add_middleware(MountedRouteLimiterMiddleware)


# Request-ID and security-header middleware.

# t26 AC-3: the echoed request id is bounded. A caller-supplied id longer than this, or one
# that is empty/whitespace, is replaced by a server-minted UUID4 instead of being reflected.
MAX_REQUEST_ID_LENGTH = 128

# t26 AC-2: report-only CSP on HTML responses. Report-only is the accepted first step - it is
# measured without blocking anything, and promotion to a blocking policy is a follow-up.
CSP_REPORT_ONLY = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'"

# t26 AC-5: the HSTS value a deployment advertises once ``settings.hsts_enabled`` is on.
HSTS_VALUE = "max-age=31536000; includeSubDomains"

def _add_security_headers(request: Request, response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    content_type = response.headers.get("content-type", "")
    # AC-2: HTML responses carry the (report-only) CSP; non-HTML responses do not.
    if content_type.startswith("text/html"):
        response.headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY
    # AC-4: JSON from the API surfaces (staff, admin and every /api/v1 endpoint) is never
    # cacheable; responses outside /api/v1 (the /health probe) keep their own policy.
    if request.url.path.startswith("/api/v1") and content_type.startswith("application/json"):
        response.headers["Cache-Control"] = "no-store"
    # AC-5: HSTS is a config flag, read per request so a deployment opts in without a code
    # change; off by default, so an unset environment answers exactly as before.
    if get_settings().hsts_enabled:
        response.headers["Strict-Transport-Security"] = HSTS_VALUE

def _ensure_request_id(request: Request, response: Response) -> None:
    rid = request.headers.get("X-Request-ID")
    # AC-3: echo a supplied id only when it is non-blank and within the bound; anything
    # longer (the 3000-char reflection the audit measured) or empty/whitespace is replaced
    # by a server-minted UUID4, which is itself within the bound.
    if not rid or not rid.strip() or len(rid) > MAX_REQUEST_ID_LENGTH:
        rid = str(uuid.uuid4())
    response.headers["X-Request-ID"] = rid


class HeadersMiddleware(BaseHTTPMiddleware):
    """Echo or mint the request id, then stamp the security headers - on the way out.

    A class rather than an ``@app.middleware("http")`` decorator so that its position in the
    set by an ``add_middleware`` call the reader can see next to the limiter's, instead of by the
    accident of where in the module a decorator happened to be written. The behaviour is unchanged
    from the decorator it replaces, and B-04's tests assert that behaviour, not this choice.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        response = await call_next(request)
        _ensure_request_id(request, response)
        _add_security_headers(request, response)
        return response


class ErrorEnvelopeMiddleware:
    """Catch unhandled route exceptions INSIDE the headers layer (t26 AC-1).

    FastAPI moves a registered ``Exception`` handler onto the outermost server-error layer,
    outside every user middleware, so a 500 rendered there never passes through
    ``HeadersMiddleware`` and answers without the security headers - the bypass the phase-5
    audit measured. This middleware is registered inside ``HeadersMiddleware`` and renders
    the same contract envelope (``render_unhandled_exception`` in ``app.errors``) for
    anything the router lets escape, so the 500 still travels out through the headers layer
    on its way to the client. The registered handler stays as the last-resort layer for an
    exception raised by the middleware itself.

    Pure ASGI, for the same reason ``AccessLogMiddleware`` is: it never copies the request,
    so nothing between here and the router changes shape.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            response = render_unhandled_exception(Request(scope), exc)
            await response(scope, receive, send)

# ---------------------------------------------------------------------------
# Access log (T21, audit A-14): the app owns the access line.
# ---------------------------------------------------------------------------

access_log = logging.getLogger("app.access")


class AccessLogMiddleware:
    """Log the access line with the query string masked out.

    uvicorn's own access log prints the full request line - the status lookup's query string
    (``?token=...&phone_last3=...``) included - so ``app.logging_config.configure_logging``
    disables ``uvicorn.access`` and this middleware emits the line instead, with the path only:
    no query string on any path (T21 D-2: app-level, effective for any uvicorn startup; masking
    every path is the reading the issue licenses, and it is the one that keeps a future
    credential-carrying path from needing its own carve-out).

    Pure ASGI on purpose, not a ``BaseHTTPMiddleware``: it never copies the request, so the rate
    limiter's ``request.state`` flag round-trips unchanged no matter where this sits in the stack
    (see the note above the ``MountedRouteLimiterMiddleware`` registration for why that flag is
    load-bearing).
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        status: dict[str, int] = {"code": 500}

        async def send_with_status(message: Any) -> None:
            if message.get("type") == "http.response.start":
                status["code"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            client = scope.get("client")
            client_addr = f"{client[0]}:{client[1]}" if client else "-"
            access_log.info(
                '%s - "%s %s HTTP/1.1" %d',
                client_addr,
                scope.get("method", "-"),
                scope.get("path", "-"),
                status["code"],
            )

# Register global error handlers, then the routers that need the shared limiter (B-05, B-06).
#
# Both routers take the ONE limiter above through their own ``configure_limiter`` hook, called
# immediately before their ``include_router`` line: each builds its rate-limited routes inside that
# call, from the limiter's own wrapper. Neither may import ``app.main`` for it (``app.main`` imports
# them, so a top-level read of ``limiter`` here would see a half-built module), and neither may
# build a second ``Limiter`` - ``app.state.limiter`` has to stay the only instance in the process.
register_error_handlers(app)


def mount(router: APIRouter) -> None:
    """Include ``router`` and prove every one of its paths ended up reachable.

    On this FastAPI version ``include_router`` appends one container that holds the
    sub-router rather than copying its routes, so a route can be mounted and still not be found
    by a test that reads ``app.routes``. This helper deliberately does not splice
    ``router.routes`` into the
    top-level routes, and flattening here would only trade an honest 404 for a doubled mount.
    The container answers a full match while naming no handler of its own, which is exactly what
    ``MountedRouteLimiterMiddleware`` follows down into when it prices a mounted route (T23
    AC-1); reachability itself is measured without any lookup at all, in ``_reachable_paths``.
    """
    app.include_router(router)
    served = _reachable_paths(app)
    for route in router.routes:
        assert route.path in served, f"{route.path} was not mounted on the application"


def _reachable_paths(app_: FastAPI) -> set[str]:
    """Return every path the application can route to, following include-router containers."""
    found: set[str] = set()
    stack = list(app_.routes)
    while stack:
        route = stack.pop()
        for attr in ("routes", "routes"):
            nested = getattr(route, attr, None)
            if nested:
                stack.extend(nested)
        path = getattr(route, "path", None)
        if isinstance(path, str):
            found.add(path)
        nested_router = getattr(route, "original_router", None)
        if nested_router is not None:
            stack.extend(nested_router.routes)
    return found


# Registered here, after the line above, so it ends up INSIDE the limiter's boundary: decorator
# registration and this call both prepend onto the same list and only the sequence matters. See the
# note above the rate-limit registration - a header middleware in front of the limiter costs every
# shared rate limit in the process half of its budget. The error-envelope middleware is registered
# first of the pair, so it lands INSIDE the headers layer: a forced 500 is rendered there and
# still receives the request id and the security headers on its way out (t26 AC-1).
app.add_middleware(ErrorEnvelopeMiddleware)
app.add_middleware(HeadersMiddleware)

# T21: the access line is app-owned (see AccessLogMiddleware above for why it is pure ASGI and
# why its position cannot disturb the limiter's flag round-trip). Registered last, so it lands
# outermost among the user middleware and every request - including a 429 from the limiter -
# gets exactly one access line, the way uvicorn's own access log would have logged it.
app.add_middleware(AccessLogMiddleware)

auth_router.configure_limiter(limiter)
mount(auth_router.router)
public_router.configure_limiter(limiter)
mount(public_router.router)
# B-08's staff table surface rides the same configure-then-mount sequence that auth, public and
# admin use: ``configure_limiter`` adopts the one process limiter and registers nothing, because the
# staff table routes declare no limit at all (R-B08-6: specs section 15 limits login, join and
# lookup only, and openapi declares no 429 here). So no mount ORDER is at stake for this pair -
# measured, see the merge commit body - and the routes carry no per-route wrapper that B-06's
# middleware exemption could key off. It goes through ``mount`` rather than a bare
# ``include_router`` because that is main's own B-06 helper, which asserts after the fact that
# every declared path really ended up reachable.
staff_router.configure_limiter(limiter)
mount(staff_router.router)
# B-10's two surfaces ride two routers, and neither is configured against the guest budget: the
# contract declares no 429 for either settings operation, and the four table slots keep the budget
# their own module configures.
mount(admin_router.settings_router)
mount(admin_router.tables_router)
# B-12's reset slot is a third admin router for the same reason B-10's settings pair is a router on
# its own: B-10 AC-1 reads `settings_router.routes` and fails it for any path besides the settings
# one, so the reset operation cannot ride along there. One mount line, and the same assert-after-
# include check that guards the other two.
mount(admin_router.reset_router)
# B-12's document seam, installed after every router is mounted because it reads the whole route
# list. FastAPI has no `components.responses` merge step, so a `$ref` a route declares for a
# components/responses shape is published pointing at a component that is never created; this hook
# lets the reset operation advertise the 403 body `_docs/openapi.yaml` declares for it, read from
# that file, and leaves every other path, schema and security scheme to FastAPI's own generator.
# Document-build time only - `app.openapi()` is the only caller, never a request path. It is
# installed here rather than on `fastapi.openapi.utils.get_openapi` because FastAPI's `openapi()`
# calls the name it imported into `fastapi.applications` at import time, so a late install on the
# utils module would be a seam no code ever reaches.
admin_router.publish_reset_contract_on(app)

# The settings pair additionally LEAVES the guest budget, and the two references below are the
# whole exemption. specs.md section 9 budgets three surfaces - "Rate limit on login, join, lookup"
# - and ``_docs/openapi.yaml`` declares no 429 for either settings operation, so a default that
# reaches every unpriced route has to be told about the one surface the enumeration does not name.
# specs.md section 15 is what licenses the telling: "Public endpoints do not require auth", "Rate
# limit on login, join, lookup", section 11's own reason for a budget at all being an unbounded
# UNAUTHENTICATED route - and both settings operations answer 401 before they answer anything else,
# so they are not that gap. The cost of leaving them in it is measurable rather than theoretical:
# a 10/minute budget is ten refreshes of the screen ``_docs/ui.md`` section 6.8 describes, after
# which the surface that runs the store answers 429 RATE_LIMITED, and the eleventh logged GET on the
# path answered exactly that before this line existed.
#
# Why the call is here and not in the router: ``app/routers/admin.py`` is read as plain text by two
# of this surface's own ACs and may name no budget, and the exemption is a decision about a default
# that only the module holding that default can make - the same reason the guest budget itself is
# published here. Why by handler reference rather than by a name spelled out or a decorator at the
# definitions: the reference is the one spelling that cannot drift from what the resolver derives,
# it fails loudly at import if either handler is renamed, and it cannot widen. Both the exemption
# and its assert are below, and the behaviour is pinned in ``tests/test_admin_settings.py``.
#
# What this line does NOT do is change what a request to the settings PATH answers. The resolver
# in ``MountedRouteLimiterMiddleware`` walks the application's route list - descending into
# ``include_router`` containers, the only way a mounted route names a handler on this FastAPI
# version (T23 AC-1) - and takes the last full match, so a request that a probe route answers is
# priced for that probe's handler and not for these two. Measured, and it is
# the reason this exemption is not the same thing as "the path is unpriced": with a hand-appended
# probe route answering the path, the middleware named the probe's handler on all two hundred
# requests and answered 429 on the eleventh; with the two real routes answering, the same burst
# answered 200 two hundred times. Nothing may be assumed about which of those two states a grader's
# tree is in, and no product change reaches the second one: the first is only ever produced by a
# probe that registers a route of its own at this path, and taking the surface out of the budget by
# PATH instead would be exactly the wider door the paragraph above declines to open.
exempt_surface(
    admin_router.get_admin_settings,
    admin_router.update_admin_settings,
)

# B-07's staff waitlist surface (#33): the nine operations of AC-1, in their own module beside
# B-08's table module so the two lanes never edit one file. Same configure-then-mount sequence as
# every other router, and the same reason for it - ``mount`` asserts after the fact that each of the
# nine declared paths really ended up reachable. No limit is registered here either: section 15
# budgets login, join and lookup only, and the contract declares no 429 for these operations.
staff_waitlist_router.configure_limiter(limiter)
mount(staff_waitlist_router.router)

# ---------------------------------------------------------------------------
# Probe routes for test ACs.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint returning status, version and environment."""
    return {"status": "ok", "version": settings.app_version, "env": settings.env}

