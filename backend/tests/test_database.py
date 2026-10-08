# ruff: noqa
"""Tests for the sqlite-only startup guard (t24, AC-2).

The guard is the enforcement half of the SQLite-only decision: a non-sqlite
``DATABASE_URL`` must be refused at import, before ``create_engine``, with an
error whose message carries the three contract phrases - that only SQLite is
supported, the ``DATABASE_URL`` env var name, and the actionable ``sqlite:////``
direction. These tests exercise the guard directly, the way an operator's
misconfiguration would reach it.
"""

import pytest

from app.database import ensure_sqlite_only


def _assert_contract_phrases(message: str) -> None:
    """The refusal must be actionable: state the limit, name the knob, show the shape."""
    low = message.lower()
    assert "only sqlite" in low or "sqlite-only" in low
    assert "database_url" in low
    assert "sqlite:///" in low


def test_ensure_sqlite_only_refuses_psycopg_url_with_contract_error():
    with pytest.raises(RuntimeError) as excinfo:
        ensure_sqlite_only("postgresql+psycopg://tq:***@localhost:5432/tq")
    _assert_contract_phrases(str(excinfo.value))


def test_ensure_sqlite_only_refuses_psycopg2_url_with_contract_error():
    with pytest.raises(RuntimeError) as excinfo:
        ensure_sqlite_only("postgresql+psycopg2://tq:***@localhost:5432/tq")
    _assert_contract_phrases(str(excinfo.value))


def test_ensure_sqlite_only_accepts_sqlite_urls():
    # The shipped relative form and the absolute four-slash form both pass.
    assert ensure_sqlite_only("sqlite:///./test.db") is None
    assert ensure_sqlite_only("sqlite:////absolute/path/to/dev.db") is None
