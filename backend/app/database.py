"""Database configuration and session management."""

import contextlib
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# Create SQLAlchemy engine.
#
# ``connect_args`` is SQLite's own: what ``check_same_thread=False`` permits is one connection being
# handed to another thread, and the test client runs the application on a worker thread, so
# it has to stay False. What is NOT here is a pool, and that absence is the part worth reading
# twice.
#
# SQLite's default pool for a file-backed database is a single connection held for the life of the
# process. One property follows that a reader cannot see in the code above it: a session built
# elsewhere on the same URL - ``backend/tests/conftest.py``, or the throwaway settings route a B-10
# acceptance block builds over ``app.main.app`` - runs its ``CREATE TABLE`` on a connection of its
# own, and the request that then asks for those rows answers "no such table". Nothing about that
# failure is a fact about the route under test, and the product never notices the difference because
# it is the only writer in production.
#
# So: a connection per checkout, which sees whatever any writer committed. Production semantics are
# unchanged by that - the store is one SQLite file, this application is its only writer, and a
# connection that ends when the request ends is if anything the more conservative reading of a store
# that cannot be shared across processes anyway. The cost is opening a connection per request rather
# than reusing one, which for a file of this size is not worth arranging around; the alternative,
# keeping the pool and teaching the application to see a harness's tables, needs a second engine, a
# second name, and a rule about which one a request reads through, all to reproduce what the writer
# already committed.
#
# The per-request SQLite busy timeout, in seconds (t19): how long a request waits on a locked
# store - the SQLite file held by a concurrent writer - before the driver gives up with
# "database is locked". That error is a contract outcome, not a crash: the error layer
# (app/errors.py) answers it with the typed 503 STORE_BUSY plus a Retry-After header, never the
# silent 500 INTERNAL_ERROR the legacy 30s park used to produce. The value is documented here at
# the binding site: 5s sits inside the 0.5..10s window the issue names as reasonable - long
# enough that a brief contention between the application's own per-request connections resolves
# itself, short enough that a genuinely held lock fails the request fast instead of parking the
# worker for 30s. The error layer reuses the same constant for the Retry-After it advertises.
SQLITE_BUSY_TIMEOUT = 5.0

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT},
    poolclass=NullPool,
    # D-3 (audit A-3): echo answers its OWN flag, never the environment label. The label used
    # to decide this, so a process that simply never named an environment resolved to the
    # permissive default and printed every bound parameter - guest names and phone numbers
    # included - to the process log.
    echo=settings.sql_echo,
)

@event.listens_for(engine, "connect")
def _enable_wal_journal_mode(dbapi_connection, connection_record):  # noqa: ANN001
    """Put the store in WAL journal mode on every connection (t19, AC-3).

    The decision is explicit rather than SQLite's default ``delete``: under ``delete`` a reader
    blocks behind the writer for the whole busy timeout, while WAL lets reads proceed while a
    writer - the application, or a concurrent external writer the AC-1 503 mapping handles -
    holds the write lock. Journal mode is a property of the database file, so the pragma is a
    no-op on connections that find the file already in WAL; it is issued on every connect
    because the engine pools no connections (NullPool), so no earlier connection's choice can
    be assumed to have been made on this one.

    The pragma is best-effort by design: a file that is not a SQLite database has no journal
    mode to enable, and the first statement on this connection fails with the same driver error
    through the app's normal 500 path. Raising from the connect event instead would change that
    error's timing and, in this SQLAlchemy build, leak the DBAPI connection the pool never closes
    after a failed connect event - which on Windows keeps the file locked past the connection's
    death.
    """
    # Not a database (or otherwise unusable at open time): nothing to enable. The
    # statement-level error is the one that surfaces, exactly as before WAL existed.
    with contextlib.suppress(sqlite3.Error):
        dbapi_connection.execute("PRAGMA journal_mode=wal")


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Session:
    """Dependency for getting a database session.

    Yields:
        Session: A SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
