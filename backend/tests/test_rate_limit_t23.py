"""T23: the rate limit reaches mounted routes, the change-pin budget, XFF trust, the cap.

The four behaviours this module pins are the four things the audit measured as broken at HEAD:

* the 10/minute default never reached an ``include_router``-mounted ``/api/v1`` route, because
  slowapi's top-level-only handler lookup names no handler for a container and its exemption rule
  then exempts the route (AC-1);
* the staff change-pin route was never handed to the limiter, so one IP spent unlimited bcrypt
  CPU on it (AC-2);
* the client key was the address uvicorn rewrote from ``X-Forwarded-For`` for a local peer, with
  no setting to say which proxy may be believed (AC-3);
* the counter store was slowapi's default ``MemoryStorage`` with no stated bound (AC-4).

Each test that expects a 429 enables the shared limiter and installs a FRESH counter store for
the block: the limiter is module-level, so a burst one test spends must not be the burst the next
test inherits, and the fresh store is also what makes the boundary assertions exact (the first N
answers 200/401, the (N+1)st answers 429) rather than "somewhere in the burst". The store swap
mirrors the one ``app.main`` performs at import, and is undone in teardown.
"""

from __future__ import annotations

import contextlib
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tq_b06_pytest.db")
os.environ.setdefault("JWT_SECRET", "tq-test-jwt-secret-value-0123456789abcdef")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

if os.sep == "/":  # WSL: the Windows drive is not writable by the venv's platform check
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from limits.strategies import STRATEGIES  # noqa: E402
from starlette.datastructures import Address, Headers  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app, limiter  # noqa: E402
from app.models import Settings as SettingsModel  # noqa: E402
from app.services.rate_limit import (  # noqa: E402
    COUNTER_KEY_CAP,
    BoundedFrozenClockMemoryStorage,
    get_rate_limit_key,
)
from tests import public_fixtures as fx  # noqa: E402

LOGIN = "/api/v1/auth/login"
CHANGE_PIN = "/api/v1/auth/change-pin"
BRANCH_READ = "/api/v1/public/branches/1"


@contextlib.contextmanager
def limiter_on_fresh_store():
    """Enable the shared limiter on a fresh counter store, then restore both.

    Enabling alone is not enough for an exact boundary: the store is process-wide, so a burst an
    earlier test spent inside the same window is still spent. The swap installs the same class
    ``app.main`` installs at import, rebuilt around it the same way, and teardown puts the
    original instance and the original enabled flag back.
    """
    previous_enabled = limiter.enabled
    previous_storage = limiter._storage  # noqa: SLF001
    previous_strategy = limiter._limiter  # noqa: SLF001
    storage = BoundedFrozenClockMemoryStorage()
    limiter._storage = storage  # noqa: SLF001
    limiter._limiter = STRATEGIES[limiter._strategy or "fixed-window"](storage)  # noqa: SLF001
    limiter.enabled = True
    try:
        yield limiter
    finally:
        limiter.enabled = previous_enabled
        limiter._storage = previous_storage  # noqa: SLF001
        limiter._limiter = previous_strategy  # noqa: SLF001


@contextlib.contextmanager
def trusted_proxies(value: str):
    """Point the cached settings' ``TRUSTED_PROXIES`` at ``value`` for the block, then restore."""
    settings = get_settings()
    previous = settings.trusted_proxies
    settings.trusted_proxies = value
    try:
        yield
    finally:
        settings.trusted_proxies = previous


def _seeded_client() -> TestClient:
    """Return a client over a schema holding branch 1 and a staff PIN row (``1234``)."""
    db = fx.fresh_session()
    fx.seed_branch(db, branch_id=1)
    row = db.query(SettingsModel).first()
    row.staff_pin_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode()
    db.commit()
    db.close()
    return TestClient(app)


def _login(client: TestClient, xff: str | None = None) -> int:
    headers = {"Content-Type": "application/json"}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    return client.post(LOGIN, headers=headers, json={"pin": "1234"}).status_code


def _change_pin(client: TestClient, token: str) -> int:
    return client.post(
        CHANGE_PIN,
        headers={"Authorization": f"Bearer {token}"},
        json={"current_pin": "000000", "new_pin": "111111", "confirm_new_pin": "111111"},
    ).status_code


def test_default_limit_reaches_mounted_api_v1_route():
    """AC-1: a burst on an include_router-mounted /api/v1 route 429s, and is counted once.

    The branch read carries no limit of its own, so the 10/minute default prices it. Exactly ten
    200s then 429s is the single-count proof: a request counted on both sides of the
    middleware/wrapper boundary would empty the budget at five.
    """
    with limiter_on_fresh_store():
        client = _seeded_client()
        codes = [client.get(BRANCH_READ).status_code for _ in range(45)]
    assert codes[:10] == [200] * 10
    assert codes[10:] == [429] * 35


def test_change_pin_is_budgeted():
    """AC-2: wrong-PIN change-pin attempts reach the handler until the budget is spent, then 429.

    The route carries no limit of its own, so the 10/minute default prices it: ten attempts run
    the bcrypt check and answer 401, the eleventh is refused before the handler.
    """
    with limiter_on_fresh_store():
        client = _seeded_client()
        token = client.post(LOGIN, json={"pin": "1234"}).json()["access_token"]
        codes = [_change_pin(client, token) for _ in range(25)]
    n401 = codes.count(401)
    n429 = codes.count(429)
    assert n401 == 10
    assert n429 == 15
    assert codes[:10] == [401] * 10
    assert codes[10:] == [429] * 15


def test_xff_not_honoured_when_trusted_proxies_unset():
    """AC-3: with the setting empty, a spoofed XFF cannot rotate a client around the budget.

    Twelve logins each carrying a different XFF value all spend the ONE 5/minute login budget of
    the address the process is connected from: five 200s, then 429.
    """
    with trusted_proxies(""), limiter_on_fresh_store():
        client = _seeded_client()
        codes = [_login(client, xff=f"10.66.{i}.1") for i in range(12)]
    assert codes.count(200) == 5
    assert codes.count(429) == 7


def test_xff_honoured_when_trusted_proxies_names_the_proxy():
    """AC-3: a named proxy's XFF is honoured, and distinct XFF values get distinct budgets.

    ``TestClient`` connects as ``testclient``, so naming that address is naming the proxy. Twelve
    logins under one XFF value spend that value's 5/minute budget (five 200s, then 429), and the
    FIRST login under a second XFF value still answers 200.
    """
    with trusted_proxies("testclient"), limiter_on_fresh_store():
        client = _seeded_client()
        codes = [_login(client, xff="203.0.113.5") for _ in range(12)]
        second_value_first_request = _login(client, xff="198.51.100.7")
    assert codes.count(200) == 5
    assert codes.count(429) == 7
    assert second_value_first_request == 200


def test_xff_not_honoured_when_trusted_proxies_names_a_different_proxy():
    """AC-3: naming a proxy the request did not come from honours nothing.

    The connecting address (``testclient``) is not in the list, so the header is ignored and the
    rotating-XFF burst spends one shared 5/minute budget: five 200s, then 429.
    """
    with trusted_proxies("10.9.9.9"), limiter_on_fresh_store():
        client = _seeded_client()
        codes = [_login(client, xff=f"10.66.{i}.1") for i in range(12)]
    assert codes.count(200) == 5
    assert codes.count(429) == 7


def test_rate_limit_key_honours_only_a_named_proxy():
    """AC-3, at the key function: the leftmost XFF hop wins only for a named connecting address."""

    class _Request:
        def __init__(self, host: str | None, xff: str | None = None):
            self.client = None if host is None else Address(host, 1234)
            self._headers = Headers({"x-forwarded-for": xff} if xff else {})

        @property
        def headers(self):
            return self._headers

    with trusted_proxies(""):
        assert get_rate_limit_key(_Request("127.0.0.1", "10.66.1.1")) == "127.0.0.1"
        assert get_rate_limit_key(_Request(None, "10.66.1.1")) == "unknown"
    with trusted_proxies("127.0.0.1"):
        assert get_rate_limit_key(_Request("127.0.0.1", "10.66.1.1")) == "10.66.1.1"
        assert get_rate_limit_key(_Request("127.0.0.1", "10.66.1.1, 10.66.2.2")) == "10.66.1.1"
        assert get_rate_limit_key(_Request("127.0.0.1")) == "127.0.0.1"
    with trusted_proxies("10.9.9.9"):
        assert get_rate_limit_key(_Request("127.0.0.1", "10.66.1.1")) == "127.0.0.1"
    with trusted_proxies("10.9.9.9, 127.0.0.1"):
        assert get_rate_limit_key(_Request("127.0.0.1", "10.66.1.1")) == "10.66.1.1"


def test_counter_store_carries_a_stated_per_process_cap():
    """AC-4: the store behind the one limiter states its bound, and the bound holds.

    The cap is a positive int on the storage class (``max_keys``), equal to the module constant,
    and ``incr`` enforces it: a store whose cap is lowered sheds its oldest counters rather than
    growing past the bound.
    """
    assert isinstance(limiter._storage, BoundedFrozenClockMemoryStorage)  # noqa: SLF001
    assert BoundedFrozenClockMemoryStorage.max_keys == COUNTER_KEY_CAP
    assert isinstance(BoundedFrozenClockMemoryStorage.max_keys, int)
    assert BoundedFrozenClockMemoryStorage.max_keys > 0

    store = BoundedFrozenClockMemoryStorage()
    store.max_keys = 5
    for i in range(12):
        store.incr(f"client-{i}", 60)
    assert len(store.storage) <= 5
    # the eviction drops the OLDEST counters, so the newest keys are the ones that survive
    assert "client-11" in store.storage
    assert "client-0" not in store.storage
