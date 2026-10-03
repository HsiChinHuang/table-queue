"""T21 log hygiene: no PII or tracebacks to stdout, no credentials in query strings.

Regression suite behind the five AC blocks of ``_docs/issues/T21.md``: the statement-logger pin,
the binding redaction, the masked access line, and the 500 path's redacted traceback. The AC
blocks are the executable contract (live server, canary credentials); these tests are the
in-process half of the same contract, so a regression is caught by the suite, not only by a
re-run of the AC probes.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "tq-test-jwt-secret-value-0123456789abcdef")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.logging_config import redact_sql_bindings  # noqa: E402
from app.main import app  # noqa: E402
from app.models import WaitlistStatus  # noqa: E402
from tests.public_fixtures import (  # noqa: E402
    fresh_session,
    seed_branch,
    seed_entry,
    token_for,
)

STATUS_PATH = "/api/v1/waitlist"


def _raised_value_error() -> ValueError:
    """A ValueError that was actually raised, so it carries a real traceback."""
    try:
        raise ValueError(
            "lookup failed [SQL: SELECT phone FROM guests] [parameters: ('0912345987',)]"
        )
    except ValueError as exc:
        return exc


@contextmanager
def _quiet_httpx():
    """Keep the TestClient's httpx transport out of caplog.

    httpx logs the full request URL - query string included - at INFO. It is a test-harness
    artifact, not the app's process log (a live uvicorn server has no httpx client in-process;
    the AC probes with curl), so a caplog assertion about the app's log must not see it.
    """
    logger = logging.getLogger("httpx")
    previous = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous)


def test_statement_loggers_pinned_at_warning_or_above():
    """AC-1/AC-2 offline arm: importing app.main pins the SQLAlchemy statement loggers.

    The pin is what keeps echo-level records out of the log through normal propagation,
    whatever the ``SQL_ECHO`` flag says (T21 D-4); the echo machinery's own bypass is covered
    by the discard filter, measured live by AC-1's ``echo_on`` arm.
    """
    import app.main  # noqa: F401 - importing is the act under test

    for name in (
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
    ):
        logger = logging.getLogger(name)
        assert logger.getEffectiveLevel() >= logging.WARNING, (
            f"{name} effective level {logger.getEffectiveLevel()} < WARNING: "
            "SQL echo could reach the process log"
        )


def test_redaction_strips_binding_segments_and_keeps_the_traceback(caplog):
    """AC-2: the [SQL: ...]/[parameters: ...] segments go (tag and value), the traceback stays."""
    sample = (
        "db failed [SQL: SELECT name, phone FROM guests WHERE id = ?] "
        "[parameters: ('QHygieneProbeGuest', '0912345987')] (Background on this error)"
    )
    redacted = redact_sql_bindings(sample)
    assert "[SQL:" not in redacted
    assert "[parameters:" not in redacted
    assert "QHygieneProbeGuest" not in redacted
    assert "0912345987" not in redacted
    assert "db failed" in redacted
    assert "Background on this error" in redacted

    # Record level, through the app.errors logger the 500 handler logs on: the traceback must
    # survive the redaction (diagnosability is a constraint, T21 D-3), the binding segments must
    # not. The exception is raised, not merely constructed, so it carries a real traceback.
    exc = _raised_value_error()
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        logging.getLogger("app.errors").error("probe %s", "failed", exc_info=exc)
    assert "Traceback (most recent call last):" in caplog.text
    assert "ValueError: lookup failed" in caplog.text
    assert "[SQL:" not in caplog.text
    assert "[parameters:" not in caplog.text
    assert "0912345987" not in caplog.text


def test_access_line_masks_the_lookup_query_string(caplog):
    """AC-3: a lookup-family request's token/phone_last3 never reach the log (caplog)."""
    db = fresh_session()
    try:
        seed_branch(db)
        entry = seed_entry(
            db,
            queue_number="A001",
            seq=1,
            status=WaitlistStatus.WAITING,
            sort_order=1,
        )
        token = token_for(entry)
    finally:
        db.close()

    client = TestClient(app, raise_server_exceptions=False)
    with _quiet_httpx(), caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get(f"{STATUS_PATH}/A001", params={"token": token, "phone_last3": "001"})
    assert resp.status_code == 200
    assert token not in caplog.text
    assert "phone_last3=001" not in caplog.text
    # The access line itself is still emitted - path only, no query string.
    assert "GET /api/v1/waitlist/A001 HTTP/1.1" in caplog.text


def test_500_traceback_is_redacted(caplog):
    """AC-2 live arm, in-process: a forced DB error logs a traceback without binding lines.

    The store is corrupted between the seed and the probe - the same move the AC makes against
    a live server - and the schema is rebuilt on the way out so the rest of the suite sees the
    shared engine's file the way it found it.
    """
    db = fresh_session()
    try:
        seed_branch(db)
        entry = seed_entry(
            db,
            queue_number="A001",
            seq=1,
            status=WaitlistStatus.WAITING,
            sort_order=1,
        )
        token = token_for(entry)
    finally:
        db.close()

    db_file = Path("test.db")
    try:
        db_file.write_text("t21 probe: not a sqlite database file", encoding="utf-8")
        client = TestClient(app, raise_server_exceptions=False)
        with _quiet_httpx(), caplog.at_level(logging.ERROR, logger="app.errors"):
            resp = client.get(f"{STATUS_PATH}/A001", params={"token": token})
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
        # The traceback stays (T21 D-3), the binding segments do not.
        assert "Traceback (most recent call last):" in caplog.text
        assert "[SQL:" not in caplog.text
        assert "[parameters:" not in caplog.text
        assert "('A001',)" not in caplog.text
    finally:
        # Restore a usable schema for the rest of the suite: the shared engine points here.
        db_file.unlink(missing_ok=True)
        database.Base.metadata.create_all(bind=database.engine)
