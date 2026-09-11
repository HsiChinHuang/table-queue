"""Test environment defaults.

The app fails fast when required env vars are missing (B-01 AC-12), so the environment must be
complete before any ``app.*`` module is imported: ``app.main`` imports ``app.database``, which
calls ``get_settings()`` at import time. Every ``os.environ.setdefault`` call therefore precedes
the ``pytest`` and ``app.main`` imports below. The previous order - ``from app.main import
limiter`` above the ``setdefault`` calls - made pytest die during conftest collection with a
pydantic ``ValidationError`` for ``database_url`` / ``jwt_secret`` / ``staff_pin``.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

import pytest  # noqa: E402  # only stdlib may run above: the env bootstrap must precede app imports

from app.main import limiter  # noqa: E402  # app.main -> app.database -> get_settings()


@pytest.fixture(autouse=True)
def disable_limiter():
    """Disable the SlowAPI limiter for tests that do not exercise it.

    The limiter lives on ``app.state.limiter`` and is exported as ``app.main.limiter``; the auth
    router reuses that same instance (see ``app/routers/auth.py``). ``enabled = False`` is the
    mechanism that suppresses limiting here: ``limiter._storage.reset()`` does not undo a consumed
    burst (ruling R-B05-6). ``limiter`` stays importable so a test can re-enable it, and the
    previous value is restored afterwards.
    """
    previous = limiter.enabled
    limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = previous
