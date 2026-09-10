"""Tests for startup bootstrap functionality."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Create a local Base for testing that doesn't depend on app.database.Base
TestBase = declarative_base()


def create_test_tables(engine):
    """Create the required tables for testing."""
    with engine.connect() as conn:
        # Create restaurants table
        conn.execute(text(
            "CREATE TABLE restaurants ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "created_at TEXT, "
            "updated_at TEXT"
            ")"
        ))

        # Create branches table
        conn.execute(text(
            "CREATE TABLE branches ("
            "id INTEGER PRIMARY KEY, "
            "restaurant_id INTEGER, "
            "name TEXT NOT NULL, "
            "address TEXT, "
            "phone TEXT, "
            "timezone TEXT, "
            "business_day_cutoff_hour INTEGER, "
            "open_time TEXT, "
            "close_time TEXT, "
            "created_at TEXT, "
            "updated_at TEXT"
            ")"
        ))

        # Create settings table
        conn.execute(text(
            "CREATE TABLE settings ("
            "id INTEGER PRIMARY KEY, "
            "branch_id INTEGER, "
            "hold_minutes INTEGER, "
            "avg_seat_minutes INTEGER, "
            "queue_prefix TEXT, "
            "is_waitlist_open BOOLEAN, "
            "notification_templates TEXT, "
            "staff_pin_hash TEXT, "
            "created_at TEXT, "
            "updated_at TEXT"
            ")"
        ))
        conn.commit()


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
