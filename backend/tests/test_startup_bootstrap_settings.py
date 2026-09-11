"""Regression test for B-15: the settings bootstrap INSERT must fill every column.

B-02 added ``settings.sound_enabled_default`` as ``nullable=False`` with a
SQLAlchemy *Python-side* default, and a Python-side default never applies to a
raw ``text()`` INSERT. The old test helper hand-wrote a ``CREATE TABLE settings``
without that column, so the NOT NULL violation was invisible: the suite stayed
green while a real database (built from ``models.py``) could not be bootstrapped.

This test therefore builds its schema with ``Base.metadata.create_all`` and
never with a hand-written ``CREATE TABLE``.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  - registers every mapped class on Base.metadata
from app.database import Base
from app.main import bootstrap_defaults
from app.models import Settings


def make_session() -> tuple[Session, object]:
    """Return a session on an in-memory database whose schema comes from models.py."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def test_bootstrap_defaults_sets_sound_enabled_default():
    """A fresh models.py schema bootstraps exactly one settings row, sound on."""
    db, engine = make_session()
    try:
        bootstrap_defaults(db)

        rows = db.query(Settings).all()
        assert len(rows) == 1, f"expected 1 bootstrapped settings row, got {len(rows)}"
        assert rows[0].sound_enabled_default is True
        assert rows[0].is_waitlist_open is True
        assert rows[0].hold_minutes == 10
        assert rows[0].avg_seat_minutes == 15
        assert rows[0].queue_prefix == "A"
        assert rows[0].notification_templates == "{}"

        # Bootstrapping twice must not duplicate the row.
        bootstrap_defaults(db)
        assert db.query(Settings).count() == 1
    finally:
        db.close()
        engine.dispose()
