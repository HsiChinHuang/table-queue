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
def tq_isolated():
    """Give every test its own SQLite file, and remove it again on ``teardown``.

    Why the database needs isolating at all: ``app.database.engine`` is built once, at import
    time, from ``DATABASE_URL``. A test that calls ``monkeypatch.setenv(DATABASE_URL, ...)``
    therefore changes nothing for the application - the engine it already holds keeps pointing
    wherever the environment pointed when it was built - and every row that test writes is left
    in the file the next test reads. That is the cross-test pollution hazard B-17 tracks, and it
    is why modules such as ``test_admin_tables.py`` and ``test_admin_settings.py`` own an engine
    of their own and override ``get_db``: a module that does so needs the shared engine to be
    somewhere harmless in the meantime, which is what the ``tq_test_`` file below is.

    The file is named rather than a bare in-memory URL on purpose: a memory URL gives every
    connection its own empty database, and the application opens its own connection per request,
    so a schema created on one connection is invisible to the request that has to read it.

    What this fixture deliberately does NOT do is call ``Base.metadata.create_all`` on that file.
    It looks like two lines of insurance and it is a second writer into every test's database: the
    model registry is shared, so one run here builds every table for every test, including the ones
    whose subject is an empty table and the ones that seed a known row and count it. Measured at
    this
    lock, adding it turned twenty-nine green tests red, and not one of the twenty-nine failed on the
    assertion it was written for - each failed on an ``IntegrityError`` about a restaurant that
    already existed, from a seed that had just inserted it, landing in a module that never mentioned
    the table. The schema is built by the module that can also say which rows belong in it; every
    self-building module in this suite already does exactly that on its own engine. A module that
    forgets answers "no such table", which is loud and lands in the right place, and that is the
    cheaper failure.

    The URL is set for the duration of the test and restored on ``teardown``, so nothing here
    outlives the test that asked for it, and the shared engine is never handed a second name.
    """
    previous = os.environ.get("DATABASE_URL")
    scratch = f"tq_test_{abs(hash(id(object())))}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch}"
    try:
        yield
    finally:  # teardown: put the environment back exactly as this test found it
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        for candidate in (scratch, f"./{scratch}"):
            if os.path.exists(candidate):
                os.remove(candidate)


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
