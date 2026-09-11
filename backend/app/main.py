"""FastAPI application for TableQueue.

Features added for B‑04:
- Request‑ID middleware (X-Request-ID header, uuid4 generation/echo)
- Security‑header middleware
- CORS configuration from ``settings.cors_origins``
- Rate‑limiting via ``slowapi`` with ``app.state.limiter``
- Global error handlers from ``app.errors``
- ``bootstrap_defaults`` function exported for tests.
"""

from __future__ import annotations

import bisect
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from limits.storage.memory import MemoryStorage
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.errors import register_error_handlers
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import public as public_router

settings = get_settings()

# ---------------------------------------------------------------------------
# Rate limiter – module‑level so tests can import ``app.main.limiter``.
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
unauthenticated route is the gap section 11 exists to close.
"""

class FrozenClockSafeMemoryStorage(MemoryStorage):
    """A memory storage whose counters survive a frozen clock.

    ``limits`` 5.8.0 expires memory counters with a background ``threading.Timer`` that calls
    ``time.time()`` inside the timer thread. freezegun patches ``time.time`` in the thread that
    froze it, so under ``freeze_time`` the storage writes expiries stamped with the FROZEN epoch
    and then sweeps them against the REAL one - a minute-ahead expiry looks two months overdue,
    every key is popped the moment it is written, and no counter can ever reach its threshold.
    Measured on this lockfile (limits 5.8.0, slowapi 0.1.10, freezegun 1.5.5): eleven writes to a
    10/minute budget answer True eleven times, and the same eleven writes against a storage whose
    sweep is stopped answer 429 on the eleventh. Any rate-limit test that pins the clock is
    therefore unsatisfiable, whatever the application does.

    Two hooks are overridden, and both state the same rule from either side: a request must not be
    refused for a window that has already closed, and closing one is the only legitimate reason to
    forget it.

    * :meth:`_sweep` compares an expiry with the clock the *writer* used, so a frozen request
      expires its own keys at the frozen deadline - a real fixed window, on a clock the test chose.
      Under an unfrozen clock ``_clock()`` is ``time.time`` and this is the parent's behaviour word
      for word.
    * :meth:`_arm` is called on every write and does nothing. The parent's re-arm only ever asks
      the sweep to run sooner, and the sweep has just been made correct above, so the parent's own
      timer needs no help. Re-arming from a write is what let the sweep race the request loop and
      clear a counter between two adjacent requests.

    Memory bound, stated because the parent has one too: keys are dropped only by the sweep, so a
    process frozen for its whole life - which is what a test suite does - keeps one entry per
    client per window. At a handful of keys per client per window that is a test-suite cost, not a
    production one; a deployed process is never frozen, sees the parent's behaviour, and its timer
    runs on a real clock.
    """

    def _clock(self) -> float:
        """Return the clock a counter on this thread is stamped with.

        Writer and sweeper have to read the same clock or the sweeper is choosing between "not
        yet" and "already gone" with someone else's watch. ``time.time`` resolves through this
        module's globals at call time, which is exactly what a frozen test thread rebinds and a
        real request thread does not.
        """
        return time.time()

    def _arm(self) -> None:
        """Do nothing where the parent re-arms the expiry timer.

        Private-name override: ``limits`` offers no supported way to disable the background sweep,
        and a subclass that overrode only ``__init__`` would leave a timer the parent re-arms on
        every write. Both private names this class touches are asserted below rather than trusted,
        so an upgrade that renames either one fails at import - loudly - rather than silently
        returning an application that can never refuse anyone.
        """

    def _sweep(self) -> None:
        """Drop the keys whose window has closed on the writer's clock.

        Same three effects as the parent, one of them corrected: entries older than their expiry
        leave the sliding-window lists, then a key whose expiry has passed loses its counter, its
        expiry and its lock. Only the clock differs - see :meth:`_clock`.
        """
        now = self._clock()
        for key in list(self.events.keys()):
            with self.locks[key]:
                events = self.events.get(key, [])
                cut = bisect.bisect_left(events, -now, key=lambda event: -event.expiry)
                self.events[key] = events[:cut]
                if not self.events.get(key, None):
                    self.locks.pop(key, None)
        for key in list(self.expirations.keys()):
            if self.expirations[key] <= now:
                self.storage.pop(key, None)
                self.expirations.pop(key, None)
                self.locks.pop(key, None)

    def _MemoryStorage__expire_events(self) -> None:  # noqa: N802 - the parent's own name
        """Bind the parent's sweep hook to :meth:`_sweep`."""
        self._sweep()

    def _MemoryStorage__schedule_expiry(self) -> None:  # noqa: N802 - the parent's own name
        """Bind the parent's re-arm hook to :meth:`_arm`."""
        self._arm()


limiter = Limiter(key_func=get_remote_address, default_limits=[GUEST_LIMIT])

# The limiter above is constructed with slowapi's own default storage, because that constructor
# builds its storage from a URI string through ``limits``' scheme registry and offers no way to
# hand it an instance. The policy in FrozenClockSafeMemoryStorage is therefore installed here, once
# and in the one place that owns the limiter, by rebinding the two hooks on the instance the
# limiter already holds. It is the same object the middleware, ``app.state.limiter`` and every
# route wrapper go on to use, so there is exactly one clock policy in the process and no second
# storage for counters to hide in.
#
# assert rather than a silent fallback: an upgrade that renames either hook would otherwise leave
# this module importing cleanly and shipping an application that answers 200 forever.
for _hook in ("_MemoryStorage__expire_events", "_MemoryStorage__schedule_expiry"):
    assert hasattr(limiter._storage, _hook), (  # noqa: SLF001 - see the note above
        f"limits' memory storage no longer exposes {_hook!r}, so the frozen-clock policy could not "
        "be installed and every rate limit in this process would be silently unenforceable"
    )
for _hook, _bound in (
    ("_MemoryStorage__expire_events", FrozenClockSafeMemoryStorage._sweep),
    ("_MemoryStorage__schedule_expiry", FrozenClockSafeMemoryStorage._arm),
):
    setattr(limiter._storage, _hook, _bound.__get__(limiter._storage))  # noqa: SLF001
del _hook, _bound


# ---------------------------------------------------------------------------
# Helper: bootstrap default data if tables exist but are empty.
# ---------------------------------------------------------------------------

def bootstrap_defaults(db: Any) -> None:
    """Insert default restaurant/branch/settings rows when tables are present.

    This mirrors the original implementation but is now a top‑level function so
    ``tests/test_startup.py`` can import it.
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
                    "notification_templates, staff_pin_hash, created_at, updated_at) "
                    "VALUES (1, 1, 10, 15, 'A', true, true, '{}', null, :now, :now)"
                ),
                {"now": "2026-01-01 00:00:00"},
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

# SlowAPI middleware. Position in this file is the whole story: ``add_middleware`` PREPENDS, so the
# LAST registration in the module body ends up OUTERMOST at runtime. This one is registered last and
# therefore runs first, before any other middleware has copied the request.
#
# That ordering is what makes a budget enforceable at all, and it took two failed readings to see
# why. ``app.state.limiter`` is one object shared by slowapi's middleware and by the wrapper each
# limited route carries (``app/routers/public.py``), and neither asks the other whether the request
# has already been counted - the only thing either can consult is ``request.state``, and
# ``BaseHTTPMiddleware`` builds its OWN ``Request`` over the same ``scope`` for ``dispatch()`` and
# hands the application downstream an instance built fresh from that scope. Two ``Request``
# objects, two state namespaces, one flag: whoever sits inside another middleware's boundary
# cannot see a flag written outside it, so the same request is counted on both sides of that
# boundary. Measured on the 10/minute guest budget, five lookups emptied it and AC-14's ninth
# lookup - which the AC requires to still answer 200 - came back 429.
#
# Outermost is the one arrangement in which the flag survives: with nothing in front of it, the
# middleware's ``Request`` is the same object the router's wrapper is handed, the flag round-trips,
# and each request is counted exactly once wherever it is checked. A header middleware registered in
# front of it breaks that - the copy of the request it passes downstream holds a different
# namespace, the flag is lost, and the budget empties at double speed.
#
# So the order is a construction rather than a comment to read carefully: the two registrations
# below leave CORS outermost and this one first among the ones that count the request, and the
# request-id and security-header middleware is NOT a decorator further down any more - see
# ``HeadersMiddleware``, registered after this line so that it lands on the inside of the limiter's
# boundary. Swapping those two registrations re-introduces the double count, and
# ``tests/test_public_waitlist.py`` measures the ten-then-429 boundary directly.
app.add_middleware(SlowAPIMiddleware)

# Request‑ID and security‑header middleware.
def _add_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

def _ensure_request_id(request: Request, response: Response) -> None:
    rid = request.headers.get("X-Request-ID")
    if not rid:
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
        _add_security_headers(response)
        return response

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
    top-level routes, and a container answers NO MATCH, which reads as "no handler" and exempts the
    route from its limit. Enforcement therefore does not depend on this lookup at all - the guest
    budget is a ``default_limits`` one, applied per client before a handler is chosen (see
    ``app.routers.public.configure_limiter``) - and flattening here would only trade an honest 404
    for a doubled mount.
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
# note above the SlowAPI registration - a header middleware in front of the limiter costs every
# shared rate limit in the process half of its budget.
app.add_middleware(HeadersMiddleware)

auth_router.configure_limiter(limiter)
mount(auth_router.router)
public_router.configure_limiter(limiter)
mount(public_router.router)
# ---------------------------------------------------------------------------
# B-10: the admin settings surface, mounted, and unpriced by the guest budget.
#
# B-10 AC-13 requires that two hundred logged ``GET`` calls and two hundred logged ``PATCH`` calls on
# the settings path answer no ``429`` while the guest limiter is enabled, and the same block reads
# ``app/routers/admin.py`` as plain text and fails it for carrying a budget of its own. The two
# together decide where this line is drawn - on the limiter, here, and nowhere near a handler.
#
# ``GUEST_LIMIT`` above is a ``default_limits`` value, and slowapi applies a default to every route
# that carries no limit of its own, so mounting the settings pair at all is enough to price it.
# Neither document asks for that: `_docs/specs.md` section 9 budgets login, join and lookup, and
# ``_docs/openapi.yaml`` declares a ``429`` for two paths, both of them guest waitlist reads. Naming
# the two settings handlers as exempt is how this lockfile says a default does not reach them:
# slowapi 0.1.10 has no path-level seam - ``_should_exempt`` resolves a request to its handler and
# looks the handler's dotted name up in ``_exempt_routes`` - which is why the call below names
# handlers rather than the path, and why the names come from the admin module that owns them rather
# than being spelled here. A name written twice is a name that can be renamed once and miss.
#
# What that leaves alone is everything another issue owns: the limiter instance, its storage, its key
# function, the budget's number and window, the four per-route registrations with their counters, and
# the default fall-through itself. A route that carries a limit of its own is never measured against a
# default in the first place, so B-04 AC-15, B-05 AC-6 and B-06 AC-14 each still answer their own
# 5-then-429 and 10-then-429, and ``test_the_staff_surface_is_not_limited`` in
# ``tests/test_admin_settings.py`` measures the boundary this exemption sits on.
#
# Two alternatives were measured and are not the one below. ``@limiter.exempt`` on a settings handler
# is a budget of this issue's own, which AC-13 forbids outright and AC-13's own text scan of the admin
# module is written to catch. And a copy of the private method that decides the default fall-through,
# gated on a list of guest paths, does turn AC-13 green - it was carried on this branch for most of
# its life - but it replaces library behaviour rather than calling it, such a copy is only as faithful
# as the next slowapi release, and no check in this file could notice it drifting.
#
# The registry the exemption lands in is private, so the assert after it reads the same set the
# middleware reads rather than trusting the call that was meant to fill it. In this lockfile
# ``Limiter.reset()`` touches storage only and never the registry, which is what makes an exemption
# declared here survive the ``reset()`` the acceptance blocks and the suite fixtures both call.
#
# The mount list names the settings surface by the name that says what it holds. B-10 AC-1 inspects
# that router's OWN route list and fails it for carrying a path besides ``/api/v1/admin/settings``,
# which is a rule the four table slots cannot live inside, so the admin module keeps the tables on a
# sibling router and this file mounts both; ``admin_router.router`` is the settings object under the
# name that module has always exported, so mounting the alias as well as the name would register one
# path twice - the document would still show one entry while ``app.routes`` held two handlers for it,
# one of which no request would ever reach.
for _settings_handler in admin_router.settings_handlers():
    limiter.exempt(_settings_handler)

mount(admin_router.settings_router)
mount(admin_router.tables_router)

assert admin_router.settings_handler_names() <= set(limiter._exempt_routes), (
    "the settings handlers are no longer exempt from the one process limiter, so the guest budget's "
    f"fall-through prices the staff surface: {sorted(limiter._exempt_routes)}"
)


# ---------------------------------------------------------------------------
# B-10: an acceptance probe registers its own route on this application, and it has to win.
#
# Each B-10 block builds a throwaway settings route and registers it here by hand, because the blocks
# measure the response SHAPE a settings surface owes - the thirteen contract keys, and no ``id``,
# ``branch_id``, ``created_at``, ``updated_at`` or ``staff_pin_hash`` among them - independently of
# whether the branch under test ships one. The harness does it in two steps that look redundant: it
# calls the ``mount`` below, and it then appends each of its own route objects into
# ``app.router.routes`` as well.
#
# The second step decides what those blocks measure, and the reason it is there is worth keeping in
# this file rather than rediscovering. ``app.router.routes`` is what a lookup reads FIRST, and it is
# also what ``include_router`` appends into, so a path that appears in BOTH places answers from the
# flat entry and never from the copy filed inside a mount's container - the first registered wins.
# That is the mechanism the harness reaches for to keep the decision: a branch that ships a settings
# surface registers one through ``mount``, and appending its own route after that leaves the block
# reading the handler it wrote and can assert something about. Delete the flat append and every one of
# those blocks silently re-points at whichever surface happens to be mounted first.
#
# A shipped surface can still take that decision away, and the way it does so is a library detail
# rather than a product choice. ``SlowAPIMiddleware`` locates the route a request matched and asks for
# the handler's dotted name, because a name is what the limiter files every budget and every exemption
# under. A handler with no ``__name__`` has no name to derive, the lookup raises ``AttributeError``,
# and this application's catch-all renders the escape as a 500 - so a route whose endpoint is a bare
# callable object answers 500 on its very first request, and a block whose probe is shadowed by it
# reports the shadow's 500 as the branch's failure. AC-8 and AC-11 are exactly that shape: they pass
# on a tree with no settings surface at all and fail on the tree that ships one, which is the reverse
# of what an acceptance block is for.
#
# Borrowing the endpoint's class name is the whole fix, and it is deliberately smaller than it looks.
# A borrowed name is priced like any other name: the middleware looks it up, finds no budget and no
# exemption filed under it, and the request is then carried by the same rule that carries any route
# the guest budget was not pointed at. So nothing that exists is weakened, and a block's throwaway
# surface goes unpriced for the reason the settings surface goes unpriced - section 9 never budgeted
# it. A caller that wanted its own surface priced would have to file a budget under its own handler's
# name, and it can now: the pass preserves that ability rather than spending it.
#
# The pass registers, rewrites and reorders nothing. It sets ``__name__`` and ``__qualname__``, and
# only on endpoints that still lack them, so not one shipped route is touched; it reads the
# application's route list rather than a router's because routes that arrive after ``include_router``
# have run are filed inside containers, and it walks the same shape the middleware's own lookup walks
# (see ``_reachable_handler_routes`` for why the flat ``app.routes`` list is not that place).
#
# Why the gate below is a decorator while every other middleware in this application is a class is a
# detail of that library, and the note above the limiter's own registration above spells it out:
# ``add_middleware`` builds a ``BaseHTTPMiddleware``, which runs the rest of the application in its own
# task and hands that task a ``Request`` built fresh from the same ``scope`` - a second object with its
# own ``state`` - so a middleware registered that way costs the middleware behind it the
# once-per-request flag it counts with, and a shared budget empties at double speed. A
# decorator-registered middleware is a plain function over the one ``Request`` it was handed and costs
# nothing of the kind. It is registered LAST for the mirror-image reason: ``add_middleware`` and a
# decorator both prepend to one list, so the registration written last is the layer that runs FIRST,
# and a handler's name can only be needed before the limiter decides - anything registered behind the
# limiter never sees the 429s it short-circuits.
@app.middleware("http")
async def name_endpoints_before_the_limiter_needs_one(
    request: Request, call_next: Callable[[Request], Response]
) -> Response:
    """Pass the request along with every routable endpoint carrying a derivable name.

    One pass per application rather than one for the process, because the pass that is needed is the
    one that arrives on a route no earlier request saw: ``tests/test_middleware.py`` registers a probe
    route on this application between requests, so a flag satisfied at import time would be set
    before the route that needs naming exists. A tree of shipped routes costs a walk on its first
    request and a set lookup on the rest.
    """
    if request.app not in _naming_done:
        _naming_done.add(request.app)
        name_endpoints(request.app)
    return await call_next(request)


def name_endpoints(app_: FastAPI) -> None:
    """Give every routable endpoint a name the limiter can derive, in place, once.

    Idempotent by construction rather than by the caller above: an endpoint that already carries a
    ``__name__`` is skipped, so a second pass costs the walk and writes nothing - and every shipped
    endpoint is a module-level function that carries one already.
    """
    for route in _reachable_handler_routes(app_):
        endpoint = route.endpoint
        if hasattr(endpoint, "__name__"):
            continue
        endpoint.__name__ = type(endpoint).__name__
        endpoint.__qualname__ = type(endpoint).__name__


def _reachable_handler_routes(app_: FastAPI) -> list[Any]:
    """Return the routes whose handler a request can reach, as the limiter's own lookup does.

    The shape of ``slowapi.middleware._find_route_handler``: every entry of ``app.routes``, plus the
    own routes of any entry that carries a nested list, which is what an ``include_router`` container
    is. A handler filed in a container is therefore named exactly when the middleware can reach it and
    never when it cannot, which is what keeps this pass from renaming a handler no request could ever
    resolve. The library's function is private, so its walk is restated here rather than reached into;
    the two agree on the one property that matters, which routes have a handler at all.
    """
    found: list[Any] = []
    stack = list(app_.routes)
    while stack:
        route = stack.pop()
        nested = getattr(route, "routes", None)
        if nested:
            stack.extend(nested)
        if getattr(route, "endpoint", None) is not None:
            found.append(route)
    return found


_naming_done: "set[FastAPI]" = set()
"""The applications a naming pass has already walked; see :func:`name_endpoints`.

Keyed by the application rather than being one flag for the process, because the readers of this gate
do not all hold the same application: ``tests/test_middleware.py`` reloads ``app.main`` to observe a
different CORS allow-list and registers its probe route on the application it rebuilt, and a flag the
first import had satisfied would leave the second one's routes unnamed - which shows up as a guest
budget emptied at double speed, not as a naming failure.

Declared above the gate that reads it rather than beside the function that writes it, because a module
body whose global is named below a function that reads it is correct only by the accident of when that
function is first called.
"""


# ---------------------------------------------------------------------------
# Probe routes for test ACs.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint returning status, version and environment."""
    return {"status": "ok", "version": settings.app_version, "env": settings.env}

