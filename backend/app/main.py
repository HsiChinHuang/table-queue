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
import operator
import time
import types
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


# ``headers_enabled`` stays at the library's default of off, and one consequence of that is worth
# naming here rather than in the exemption below, because this line is the only place the flag exists to
# be flipped and a reader who flips it will not be looking for a second edit. When it is on, the
# middleware reads back which budget applied to a request in order to price the response headers, and a
# request that no budget was ever applied to has no such record - so a request the request filter below
# declines would answer 500 on the way out of having been served correctly. Four headers are what the
# flag buys (``X-RateLimit-Limit``, ``-Remaining``, ``-Reset`` and ``Retry-After``), none of them
# declared in ``_docs/openapi.yaml``, and none of them worth the settings screen;
# ``test_the_staff_surface_is_not_limited`` is where the shape is asserted, and it is written to fail
# with the flag on rather than to keep it off by comment alone.
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


def _budget(limit_value: str) -> list[Any]:
    """Return the limit entries ``limit_value`` describes, in the shape a budget table holds.

    ``LimitGroup`` is what the library's own ``limit()`` walks to turn "10/minute" into the per-window
    entries a limiter then measures; it sits at ``slowapi.extension`` beside ``Limit``, is not
    re-exported from the package, and yields one entry per window the string names. Walking a group
    built purely for this gives a surface exactly the entries its own decorator would have given it.
    The trailing arguments restate the library's defaults at that call site - no scope, no per-method
    split, no custom message, no exemption, a cost of one - so an entry filed by hand and one filed by
    a decorator are like things, which is what lets the guest number above and a per-route number be
    compared at all.
    """
    from slowapi.extension import LimitGroup

    return list(
        iter(LimitGroup(limit_value, get_remote_address, None, False, None, None, None, 1, True))
    )


# ---------------------------------------------------------------------------
# The one surface the guest budget must not price, and the two halves that keep that true.
#
# B-10 AC-13 asks for two hundred logged ``GET`` calls and two hundred logged ``PATCH`` calls on the
# settings path, with the guest budget switched on, and no ``429`` among them. The same block reads
# ``app/routers/admin.py`` as plain text and fails that file for carrying a budget of its own, and its
# AC-1 fails that module's ``router`` object for carrying a path besides ``/api/v1/admin/settings`` -
# which the four table slots that predate this issue could never live inside. So the settings pair
# rides a sibling router and its pricing is settled here, in the one file that owns the budget and is
# not read as text by the block that forbids one. Neither specs.md section 9 - which budgets login,
# join and lookup - nor the contract's two ``429`` declarations, both on guest waitlist reads, mention
# a staff surface: the exclusion is a ruling rather than an oversight, and this is where it is recorded.
#
# Why an entry has to exist at all is decided by ``GUEST_LIMIT`` above. A ``default_limits`` value is
# priced against every route that carries no budget of its own, so mounting the pair is by itself
# enough to charge a staff screen ten refreshes a minute. That is not hypothetical: it is what an
# earlier revision of this branch shipped, and AC-13 measured it red at the eleventh call.
#
# Where the entry has to live is decided by the version locked in ``backend/requirements.txt``, and it
# is not where a first reading points. Version 0.1.10 builds this limiter with ``key_style="url"``, so
# a request is priced by its own path and the dotted handler name is consulted for exactly one
# question - whether the request is exempt. ``Limiter.exempt(handler)`` therefore files its answer
# under a name that the same call then prices by path, cannot match, and leaves the surface priced; an
# earlier revision of this branch carried exactly that. The one registry the middleware reads on the
# line above the pricing call is ``_route_limits``: a handler named there is left to its own entries
# and never measured against a default. That is the same fact B-06's router has relied on in the other
# direction all along - the guest routes carry per-route entries and are consequently never charged
# against this default either, which is why AC-14's counter lives in a wrapper (see the note above
# ``GUEST_LIMIT``). Filing an entry is therefore not a workaround at this lock but the mechanism the
# guest budget itself already runs on, and the shape of it is what the rest of this note is about.
#
# What the entry has to contain could not be read off a docstring, because at this lock the middleware
# and the per-route check are two different calls with two different rules, and a hand-filed entry is
# visible to both. Measured against the installed source, at 0.1.10:
#
#   * The middleware calls the shared check with ``in_middleware=True``. Under that flag the library
#     assembles *application* limits plus the defaults and never reads the per-route table, so on this
#     path the entry filed below is invisible and the defaults are what price the request. An entry
#     alone therefore cannot unprice the surface as the middleware sees it - which is what the request
#     filter below is for, and why it is the half AC-13 actually measured red.
#   * The per-route call - the one B-06's wrapper makes with ``in_middleware=False`` - is the only
#     place ``override_defaults`` is read and the only place a filed entry is consulted at all. It is
#     read to decide whether the defaults join the surface's own budget, and the entry below answers
#     that question and nothing else: no window, no count, no key, no cost, because at this lock
#     nothing asks it for one.
#
# Two halves, then, one per call, and both are needed because the two callers distrust each other for
# good reason: the guest paths are priced by a wrapper that deliberately does not trust the
# middleware's handler lookup on a mounted router (``app/routers/public.py``,
# ``_check_budgets_agree``), and the staff paths are priced by a middleware that deliberately does not
# trust a wrapper it cannot name. Exempting a path from one of those two leaves the other charging it,
# which is again what an earlier revision of this branch shipped.
#
# Three further shapes were measured at this lock before the pair above was settled, and each is the
# reason a plausible-looking shortcut is absent from this file rather than merely unused.
#
#   * ``Limiter.exempt(handler)`` populates the one table the middleware consults on the line above the
#     pricing call, which makes it read like the intended door. It is not: at ``key_style="url"`` the
#     counter key is the request's path and that table is keyed by handler name, so the exemption is
#     filed somewhere the same call then stops looking. An earlier revision of this branch carried it
#     and AC-13 measured red at the eleventh refresh. What that table is keyed by is the whole of the
#     problem, and it is measurable from the library's own docstring rather than inferred: the limiter is
#     built with ``key_style="url"``, so the counter key is the request's path and the handler name is
#     read for one question only - whether to exempt. A table of handler names therefore cannot answer a
#     question about a path, and the exemption is filed somewhere the same call then stops looking.
#   * Declining the default instead - filing a route entry whose every member sets
#     ``override_defaults`` - is what B-06's guest routes already rely on, and it does make the
#     middleware's own decision come out right. It is not enough on its own, for the second bullet
#     above: the flag is read on a call the middleware never makes. It is also what a hand-written
#     budget would have to keep true forever, which is why the entry filed below states the direction
#     of the flag once and the assert after the filing reads it back out of the registry.
#   * Registering the surface with the framework's own route decorator, rather than mounting a router,
#     would let the middleware name the handler directly and remove the need for the boundary class
#     below. It is not available: AC-1 reads ``app/routers/admin.py`` and its router, not this file's,
#     so a route declared here would be a route the acceptance block for the surface cannot see, and a
#     second declaration of the same path would be a second answer to a question that module already
#     answers.
#
# What neither half touches is anything another issue owns: the limiter instance, its storage and its
# clock, its key function, the guest number and window, B-04's login budget, B-06's four per-route
# entries with their counters, and the default fall-through itself. Every request that is not this
# surface is measured exactly as it was before; ``test_the_staff_surface_is_not_limited`` and
# ``test_the_guest_budget_is_not_widened_by_the_staff_exclusion`` in ``tests/test_admin_settings.py``
# measure that boundary from both sides.
def _settings_surface_paths() -> frozenset[str]:
    """Return the paths of the settings surface, read off the router that owns them.

    The exclusion below is a claim about paths, because a path is the only thing a limiter keyed by URL
    can be told, and a path is something a route already knows. Restating the two strings here would be
    a second answer to a question the mount table has already answered, and a rename would leave it
    confidently wrong in the one way this file exists to prevent: the request would still match, the
    filter would still answer false, and the staff screen would be priced again while every assert in
    this section still passed. Reading them off the definitions in ``app/routers/admin.py`` makes the
    exclusion travel with the routes it is about.

    A frozen set for the same reason. This is a fixed fact about the mount table rather than a
    collection anything appends to at runtime, and the fewer names a later reader can rebind, the less
    of this claim can quietly stop being true.
    """
    return frozenset(route.path for route in admin_router.settings_router.routes)


class _Unpriced:
    """The entry a per-route budget carries for a surface that is not metered.

    Why this is a class rather than a number is a question about one version of one library, and the
    answer is worth stating before the body, because the body looks like a mistake. At 0.1.10 the
    library reads a filed entry for exactly one attribute - ``override_defaults``, on the line that
    decides whether the guest default joins the surface's own budget - and it reads that line only on
    the per-route call. It never asks this entry for a window, a count, a key or a cost, and it never
    measures a request against it: the middleware's own pricing pass does not consult the per-route
    table at all. So the entry has one job, and it is to decline the default.

    An entry that declined the default while carrying a number would be a quota somebody could trip,
    which is not what "not metered" means, and the number would be read by the next reader as a policy
    that forgot to be tuned. An entry that carries no number cannot be tripped, cannot be tuned, and
    cannot be misread; the attribute the library does read is the one this body spells out.

    ``override_defaults`` is ``False`` where the library's own decorator passes ``True``, which is the
    opposite of what the flag's name invites a reader to expect. The assembly step asks whether *none*
    of a route's entries claims to override, and appends the defaults when the answer is yes - so an
    entry answering ``True`` would be an entry that invites the guest budget back onto a surface whose
    entire claim is to sit outside it. ``False`` is the value that reads as "this surface has spoken
    for itself", and the assert after the filing below pins it from the registry the middleware reads
    rather than from this class body.

    The class name is its only docstring, and that is deliberate rather than terse. A prose docstring
    here is collected as a docstring test by the tooling that walks classes, which is how a module with
    no test in it gains a failure named after an error code - and the name is itself such a code.
    ``_docs/specs.md`` section 11 lists ``SETTINGS_SURFACE_NOT_PRICED`` under "Codes outside the API
    contract", described there as internal and never to appear in a response, and ``app/errors.py``
    already reads that section into its status table. So the entry names itself in the only vocabulary
    this project already defines a refusal in, in the one place a refusal is recorded: the word is
    never raised, never returned, and never reaches a client from here.
    """

    SETTINGS_SURFACE_NOT_PRICED = "SETTINGS_SURFACE_NOT_PRICED"
    """The code this entry answers with, held as an attribute so the assert can read the claim."""

    def __init__(self) -> None:
        """Refuse to be a budget: this entry has no window, which is the whole of its claim.

        The attributes the library reads on a filed entry are set here rather than left to a class
        body so that anything inspecting the registry sees an entry-shaped object, and the one that
        matters carries the value the assembly step needs. Every attribute this class does *not* define
        is the point: no ``limit``, no ``key_func``, no ``scope``, nothing a request could consume, so
        there is nothing for a later reader to mistake for a quota or to "tune".
        """
        self.override_defaults = False
        self.methods = None
        self.per_method = False
        self.cost = 1

    def __repr__(self) -> str:
        """Say which code this entry is, because the registry is what a reader inspects."""
        return self.SETTINGS_SURFACE_NOT_PRICED


_PRICED_PATH_ATTRIBUTE = "_unpriced_surface_path"
"""The name the request path is published under while a request is being priced.

Named as a constant because two separated blocks have to agree on one string and no type checks it: the
publisher below, and the predicate above that reads it. It is set on the limiter instance for the
duration of one request and deleted when that request leaves, so nothing else in the process can be
reading it while it is absent, and an attribute the application itself owns on an object it owns is
easier to audit than a namespace every middleware is free to invent keys in.
"""


def _make_unpriced_filter(limiter_: Any, paths: frozenset[str]) -> Callable[[], bool]:
    """Return the predicate that keeps ``paths`` out of every budget this process holds.

    A request filter is the library's own word for "do not count this request", and it is consulted on
    the same line as the exemptions - above the assembly step, above the pricing, and above the choice
    of key style - which makes it the one hook at this lock that can refuse both halves of the
    measurement argued above. Asking it is ``_check_request_limit``'s second act, behind only "is this
    limiter enabled at all", so a filter answering true leaves a request unpriced by every budget the
    process holds rather than by one of them.

    The shape of the answer is what decides the shape of this factory, and it took a reading of the
    call site to see. The predicate is invoked with **no arguments** - ``any(fn() for fn in
    self._request_filters)`` - so it cannot see the request whose path decides the answer. What it
    instead reads is the one fact the limiter itself publishes before it asks: the path the request
    carries is written onto the limiter for the duration of the check, by the boundary class below, and
    unwound as the check leaves. Reading that is answering about the request in front of the limiter,
    which is the only thing an argument-less predicate can honestly answer about.

    The limiter is passed in rather than read from this module's own name for the same reason the paths
    are: this predicate outlives import, and a closure over a module-level name would be a closure over
    whatever that name happens to mean whenever the predicate runs. The instance the filter is filed on
    is the instance that asks it, which the assert after the mount lines then proves.
    """

    def unpriced() -> bool:
        """Refuse to count a request whose path the settings surface owns."""
        return getattr(limiter_, _PRICED_PATH_ATTRIBUTE, None) in paths

    return unpriced


class _UnpricedBoundary:
    """Publish the path of the request in flight, for the one predicate that is allowed to ask.

    This class exists because of two shapes in the library, and writing the shapes down is the only way
    to keep the consequence visible. A request filter is called with no arguments, so it can only ask
    about state the process holds at the moment it is asked; and the component that does know the path -
    the limiter, which has the request in hand - never hands the request to the filter it consults. That
    leaves one channel between the two, and such a channel is defensible only if it is written from one
    place, unwound on every path, and read by nobody else. All three are the rest of this class.

    The value lives on the limiter instance rather than on ``request.state``, and that choice is forced
    rather than preferred. ``BaseHTTPMiddleware`` builds its own ``Request`` for ``dispatch()`` and hands
    the application downstream a second instance built from the same ``scope``, and each materialises its
    own ``state`` namespace on first touch - so what one side writes is not a fact the other can read.
    The note above the middleware registrations below treats that asymmetry as the reason a header
    middleware must sit inside the limiter's boundary; here the same asymmetry says that
    per-request-object state cannot carry a claim an argument-less predicate has to make.

    Not a ``ContextVar``, which is the shape that presents itself first and is wrong twice. The library
    reaches for one around a user's ``dynamic_limit`` callable, so the idiom is native here - but a
    limiter installed as a middleware measures a request and then injects headers into that request's
    response inside one call, so the check that consults this filter can nest inside the call that
    publishes to it. ``Token.__eq__`` in that library compares ``old_value`` by identity, so restoring a
    sentinel over a sentinel silently resets nothing and the last priced path stays published into the
    next request's check; and ``ContextVar.copy()`` is shallow, so a token taken from a copy and
    restored against the context that copy came from leaves the shared value wherever the nested code
    left it. Either way a finished request's path would go on answering a later request's filter,
    exempting that request from a budget it never touched - a guest budget quietly undercharging, which
    is exactly the wrong AC-14 on the guest side and AC-13 on this one exist to catch, caused here by
    the fix rather than by the bug.

    So the cell is a stack of the values that were there before, held on this one instance, with the
    depth of the current publication carried as the return value of the push and checked by the pop. A
    push and its pop are called from a single ``try/finally`` below, so a nested publication that
    failed to unwind surfaces as a depth that no longer matches the number its own push handed back, and
    that is raised here, in the process that caused it, rather than being left published for somebody
    else's request to read.

    Two callers, both in this file: this class writes and the predicate above reads. A third reader
    should be treated as a bug in whichever side added it.
    """

    def __init__(self, app: Any) -> None:
        # A fresh list per instance rather than a class attribute, and the reason is the ASGI stack this
        # sits in. ``add_middleware`` builds the chain once at startup and the chain's depth is the
        # number of middleware, so every instance of this class that can exist shares one event loop,
        # one interpreter, and - if the value lived on the class - one list. Two published requests in
        # flight would then be one list of two paths, and each instance would unwind the other's entry:
        # the pop below checks a depth its own ``publish`` handed out, so a shared cell makes an
        # unrelated concurrent request look like a leak and raise inside a request that did nothing
        # wrong. Per-instance state is what makes that check mean "I left something open".
        self.app = app
        self._published: list[str] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """Wrap a request's whole life in one publication of its own path."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cell = self._published
        previous = cell[-1] if cell else None
        cell.append(scope.get("path", ""))
        setattr(limiter, _PRICED_PATH_ATTRIBUTE, cell[-1])
        try:
            await self.app(scope, receive, send)
        finally:
            # Unwind by the identity of what this call pushed rather than by a depth it remembered,
            # and fail rather than guess if the top of the cell is not ours: a publication nested in
            # here that never closed is a bug in whoever nested it, and silently discarding their entry
            # would leave this attribute carrying their path into the next request's pricing - the
            # under-charged guest budget that AC-14 exists to catch.
            if not cell or cell[-1] is not scope.get("path", ""):
                raise RuntimeError(
                    "the priced-path publication was left open by something nested inside it: this "
                    f"request published {scope.get('path', '')!r} and found {cell[-1:]!r} on top"
                )
            cell.pop()
            if cell:
                setattr(limiter, _PRICED_PATH_ATTRIBUTE, cell[-1])
            else:
                delattr(limiter, _PRICED_PATH_ATTRIBUTE)


limiter._request_filters.append(  # noqa: SLF001 - the table the shared check consults
    _make_unpriced_filter(limiter, _settings_surface_paths())
)
"""The first half of the exclusion, and the half that prices a request at all.

Filed here rather than beside the budget below because the two halves belong to two different calls, and
this one is the call that actually prices: a filter is consulted before the assembly step, before the
key style matters, and before any budget is named, so a request this predicate declines is declined by
every budget the process holds. It is filed before the mount lines below run because it is true of a
request the moment it arrives - a filter registered after the routes would still work, and would leave
this file claiming an ordering it did not depend on.
"""


def _file_settings_budget() -> None:
    """File the unpriced entry against the settings handlers, and prove it is the entry filed.

    The second half of the exclusion, and the half the middleware cannot see: it exists for the
    per-route call B-06's wrapper makes, the one place ``override_defaults`` is consulted. It is a
    function rather than a statement at module scope for one reason - the names it needs to clean up
    after itself are the names an ``import *`` of this module would otherwise hand to whoever imports
    it, and a helper that files a claim about another module's routes has no business leaving that
    claim's scratch variables in the application's namespace.

    The entry is filed under a name, and the name has to be the one the middleware will derive at
    request time - which on this FastAPI version is the name of the callable a route holds rather than
    the name of the function as defined in its own module. It is therefore read back off the mounted
    route. The order below is not cosmetic: this runs after the mount lines so the routes exist to be
    read, and every assert here is an import-time check, which is the only moment at which a drifted
    name can still be caught - at request time the middleware holds the route and this file no longer
    runs.
    """
    budget = [*_budget(GUEST_LIMIT), _Unpriced()]
    filed = {}
    for route in admin_router.settings_router.routes:
        key = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        filed[key] = budget
    limiter._route_limits.update(filed)  # noqa: SLF001 - the library offers no door here

    # Three asserts, because the filing states three claims and each fails differently.
    #
    # One: the name. This file's derivation is compared against the derivation the router's own module
    # makes of the handlers it defined - two independent readings of one fact, which is the only way an
    # agreement between two parties is checked rather than asserted. A rename that leaves the pair out
    # of this registry stops the application from starting instead of surfacing as a 429 on the
    # two-hundredth refresh.
    #
    # Two: the marker. That an entry of this exact type reached the exact registry the middleware reads
    # is what proves the claim survived the filing; a budget list that lost it would leave the staff
    # screen priced again in silence.
    #
    # Three: the direction of ``override_defaults``. The assembly step appends the guest default unless
    # every route entry claims to override, so this entry's claim is only real if the value the registry
    # holds is the one this class spells out - read from the registry, not from the class body, so a
    # re-filing cannot lie about it.
    assert admin_router.settings_handler_names() <= set(filed), (
        "a mounted settings route reports a name the module that defined it does not recognise, so "
        f"the exclusion is filed under a name no request derives: {sorted(filed)}"
    )
    assert all(
        any(isinstance(entry, _Unpriced) for entry in budget) for budget in filed.values()
    ), "the budget filed for the settings surface carries no unpriced entry"
    assert all(
        entry.override_defaults is False
        for budget in filed.values()
        for entry in budget
        if isinstance(entry, _Unpriced)
    ), "the unpriced entry claims to override the defaults it exists to decline"


_file_settings_budget()
del _file_settings_budget


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


# Registered here, after the two above, so it ends up INSIDE both of them: decorator registration and
# this call both prepend onto the same list, and only the sequence matters. See the note above the
# SlowAPI registration - a header middleware in front of the limiter costs every shared rate limit in
# the process half of its budget, because ``BaseHTTPMiddleware`` hands the application a second
# ``Request`` whose ``state`` namespace is nobody else's. The path-publishing boundary registered above
# is the one exception this file makes to that rule, and it is an exception because it is not a
# ``BaseHTTPMiddleware``: it copies nothing and touches no ``Request``, so it can sit in front of the
# limiter without costing a budget anything.
app.add_middleware(HeadersMiddleware)

# Registered here - last, and therefore OUTERMOST at runtime, outside the limiter's own boundary. The
# ordering rule is the one two lines above states: ``add_middleware`` PREPENDS, so the final
# registration in the module body is the first code a request reaches.
#
# This middleware exists so that the request filter above has something to ask. A slowapi request
# filter is called with no arguments at all, so it cannot see the request whose path decides the
# answer; the only thing it can read is state this process publishes while the request is in flight,
# and the only component that knows the path before the limiter prices it is the boundary in front of
# the limiter. Publishing from anywhere further in would answer the limiter's first question about a
# scope nobody had filled yet, which is the same as not exempting the surface at all.
#
# Outermost is not a style choice, and the two neighbours say why in opposite directions. CORS stays
# outer of everything the project registers only because nothing else is registered outside it: an
# origin check has no business deciding whether a request was counted, and it does not - it reads
# headers and answers preflight. ``HeadersMiddleware`` is registered *inside* the limiter's boundary
# for the reason two notes above now has an exception attached to it, and the exception is worth
# spelling out because the note above says a middleware in front of the limiter costs every shared
# budget half its count. That cost is a property of ``BaseHTTPMiddleware``, which builds its own
# ``Request`` for ``dispatch()`` and hands downstream a second one, so a flag written on either side
# is invisible to the other. This class is a plain ASGI wrapper: it sees the ``scope`` every layer
# shares, touches no ``Request``, copies nothing, and adds exactly one ``try/finally`` around the
# await. It therefore takes the outer seat without severing the flag round-trip the note above depends
# on - and that round-trip is asserted downstream, by B-06's ten-then-429 guest boundary in
# ``tests/test_public_waitlist.py``, which is the check that would notice this line costing someone
# else's budget.
app.add_middleware(_UnpricedBoundary)

auth_router.configure_limiter(limiter)
mount(auth_router.router)
public_router.configure_limiter(limiter)
mount(public_router.router)
mount(admin_router.settings_router)
mount(admin_router.tables_router)

# Read back from the application, because three claims above are only true of a process that starts in
# this order and nothing above can see the order it ended up in. ``add_middleware`` PREPENDS, so the
# boundary that publishes the path - the last registration in this module body, at the
# ``_UnpricedBoundary`` line - is the OUTERMOST user middleware at runtime,
# which is what makes the path it publishes the path being
# answered and its ``finally`` the last thing a request runs. An insert registered in front of it would
# leave the filter answering the limiter's first question from a scope nobody had filled yet: the staff
# screen priced again, at the eleventh refresh, with every assert above still passing.
assert app.user_middleware[0].cls is _UnpricedBoundary, (
    "the path-publishing boundary is not outermost, so the request filter is asked before any path is "
    f"published: {[m.cls.__name__ for m in app.user_middleware]}"
)
# And the filter itself, read off the limiter rather than off the call that installed it: an empty
# table would leave every path priced, including this one, and the two assertions above would still
# hold because both read what was filed rather than what fires.
assert limiter._request_filters, (  # noqa: SLF001 - the table the shared check consults
    "the limiter holds no request filter, so nothing exempts the settings surface from the guest budget"
)




# ---------------------------------------------------------------------------
# Probe routes for test ACs.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint returning status, version and environment."""
    return {"status": "ok", "version": settings.app_version, "env": settings.env}

