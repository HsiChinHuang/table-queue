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
admin_router.configure_limiter(limiter)
mount(admin_router.router)

# ---------------------------------------------------------------------------
# Probe routes for test ACs.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint returning status, version and environment."""
    return {"status": "ok", "version": settings.app_version, "env": settings.env}

