"""The process rate-limit store and the client key it counts against (T23).

Two decisions live here because both belong to the single limiter ``app.main`` builds, and both
were wrong at the audit:

* The counter store is per-process memory with a STATED CAP (audit D-6, T23 AC-4): the counters
  live in ``BoundedFrozenClockMemoryStorage``, which cannot grow past ``COUNTER_KEY_CAP``
  (10000) distinct keys per process. There is no shared storage in v1, so the bound is per
  worker: each uvicorn worker holds its own store of at most ``COUNTER_KEY_CAP`` counters, and
  the budgets are therefore per-worker - N workers give every client N independent budgets
  (T23 AC-5). The eviction that enforces the cap is documented on the class.
* The client key honours ``X-Forwarded-For`` ONLY when the ``TRUSTED_PROXIES`` setting names the
  address the process is connected from (audit A-7, T23 AC-3). Off by default: with the setting
  empty, the key is always the connecting address and a spoofed header changes nothing. The
  shipped run commands additionally pass ``--no-proxy-headers`` so uvicorn itself never rewrites
  the connecting address from the header before this setting gets to decide.
"""

from __future__ import annotations

import bisect
import time

from fastapi import Request
from limits.storage.memory import MemoryStorage

from app.config import get_settings

COUNTER_KEY_CAP = 10_000
"""The per-process cap on the number of distinct rate-limit counters (T23 AC-4, audit D-6).

The store is in-process memory, so without a cap a flood of distinct client addresses inside one
open window would grow the process unboundedly. ``BoundedFrozenClockMemoryStorage`` enforces the
cap on every increment; see that class for the eviction it performs when the cap is reached.
"""


class BoundedFrozenClockMemoryStorage(MemoryStorage):
    """A memory storage whose counters survive a frozen clock and cannot grow past ``max_keys``.

    Frozen-clock half: ``limits``' ``MemoryStorage`` schedules expiry with ``threading.Timer``
    against the wall clock and, once that timer has fired, never schedules another. A test that
    pins the wall clock (freezegun) makes the timer fire at the frozen instant and stay dead, so
    every counter that existed before the freeze is swept and never re-armed - the budget resets
    under the freeze and the rate-limit tests stop measuring the limit. The hooks that touch the
    wall clock are re-pointed at no-ops (``_arm``) or at the clock the app itself reads
    (``_clock``), and the sweep they drive runs on the same clock, so a frozen wall clock leaves
    the counters exactly where the app's clock says they belong.

    Bound half: keys drop out of the store when their window closes (the sweep), but a window
    that is still open keeps its keys, so a flood of distinct client addresses inside one open
    window would otherwise grow ``self.storage`` without limit. ``incr`` therefore enforces
    ``max_keys`` after every increment: the sweep runs first (expired keys are free to drop),
    and if the store is still over the cap the OLDEST counters are evicted - one per loop, by
    insertion order - until the cap holds again. Evicting a live counter resets that client's
    budget for the open window: the cap buys a memory bound, and the eviction is the stated
    price of it. The bound is per process, so the counter store of N uvicorn workers holds at
    most N x ``max_keys`` counters in total, and each worker enforces the budgets on its own
    counters (T23 AC-5).
    """

    # The stated per-process cap (T23 AC-4). A positive int on the class, so the cap is part of
    # the storage's contract rather than a tuning knob read from nowhere.
    max_keys = COUNTER_KEY_CAP

    def _clock(self) -> float:
        return time.time()

    def _arm(self) -> None:
        return None

    def _sweep(self) -> None:
        # Same sweep the parent's expiry timer would run, on the app's clock: drop the expired
        # entries of the moving-window store and the expired counters of the fixed-window store.
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

    def incr(self, key: str, expiry: float, amount: int = 1) -> int:
        result = super().incr(key, expiry, amount)
        self._enforce_cap()
        return result

    def _enforce_cap(self) -> None:
        self._sweep()
        while len(self.storage) > self.max_keys:
            oldest = next(iter(self.expirations), None)
            if oldest is None:
                break
            self.clear(oldest)

    # The parent reaches these two hooks through name-mangled names from its expiry timer and
    # from ``incr``; defining them here (instead of rebinding them onto an instance) keeps the
    # frozen-clock behaviour with the class that owns it.
    def _MemoryStorage__expire_events(self) -> None:  # noqa: N802
        self._sweep()

    def _MemoryStorage__schedule_expiry(self) -> None:  # noqa: N802
        self._arm()


def get_rate_limit_key(request: Request) -> str:
    """The client identity a request spends budget under (T23 AC-3, audit A-7).

    The default is the address the process is connected from - the only identity a bare server
    can verify. ``X-Forwarded-For`` is honoured ONLY when the ``TRUSTED_PROXIES`` setting names
    that connecting address: then the leftmost hop of the header is the client the named proxy
    says it spoke for, and the key becomes that hop. With the setting empty (the default) or
    naming a different address, the header is ignored entirely, so a client that forges the
    header per request cannot rotate its way around the budget.
    """
    client = request.client
    host = client.host if client is not None else "unknown"
    trusted = {part.strip() for part in get_settings().trusted_proxies.split(",") if part.strip()}
    if host in trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    return host
