"""Database configuration and session management."""

from sqlalchemy import create_engine
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
# The 30 seconds is SQLite's own busy-wait. With per-request connections the writer that holds the
# file lock becomes a caller that commits between statements, so "database is locked" is now a
# timeout to wait out rather than a conflict to fail on.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=NullPool,
    echo=settings.env == "development",
)

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
