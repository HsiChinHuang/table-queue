"""Tests for startup bootstrap functionality."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

# app.models is imported first so every mapped class is registered on Base.metadata
# before create_all runs (AC-7: the test schema comes from models.py, never from a
# hand-written CREATE TABLE that hides columns models.py has added).
import app.models  # noqa: F401
from app.database import Base


def create_test_tables(engine):
    """Build the schema from models.py, never from a hand-written CREATE TABLE.

    A hand-written table silently drops columns that models.py has since added,
    so the bootstrap INSERT could succeed in tests while failing against a real
    database. AC-7 of B-15 pins this.
    """
    Base.metadata.create_all(engine)


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    create_test_tables(engine)
    session_local = sessionmaker(bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def test_startup_bootstraps_defaults(test_db: Session):
    """Verify default Restaurant, Branch, Settings are created on startup."""
    # Verify tables exist
    inspector = inspect(test_db.bind)
    table_names = inspector.get_table_names()

    assert "restaurants" in table_names
    assert "branches" in table_names
    assert "settings" in table_names

    # Verify tables are empty before bootstrap
    result = test_db.execute(text("SELECT COUNT(*) FROM restaurants"))
    assert result.scalar() == 0

    result = test_db.execute(text("SELECT COUNT(*) FROM branches"))
    assert result.scalar() == 0

    result = test_db.execute(text("SELECT COUNT(*) FROM settings"))
    assert result.scalar() == 0

    # Run bootstrap
    from app.main import bootstrap_defaults
    bootstrap_defaults(test_db)

    # Verify defaults were created
    result = test_db.execute(text("SELECT COUNT(*) FROM restaurants"))
    assert result.scalar() == 1

    result = test_db.execute(text("SELECT name FROM restaurants WHERE id = 1"))
    assert result.scalar() == "Sunny Bistro"

    result = test_db.execute(text("SELECT COUNT(*) FROM branches"))
    assert result.scalar() == 1

    result = test_db.execute(text("SELECT name FROM branches WHERE id = 1"))
    assert result.scalar() == "Taipei Xinyi"

    result = test_db.execute(text("SELECT COUNT(*) FROM settings"))
    assert result.scalar() == 1

    # Verify second bootstrap doesn't duplicate
    bootstrap_defaults(test_db)

    result = test_db.execute(text("SELECT COUNT(*) FROM restaurants"))
    assert result.scalar() == 1

    result = test_db.execute(text("SELECT COUNT(*) FROM branches"))
    assert result.scalar() == 1

    result = test_db.execute(text("SELECT COUNT(*) FROM settings"))
    assert result.scalar() == 1
