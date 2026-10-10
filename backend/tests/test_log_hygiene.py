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

    The store is corrupted between the seed and the probe - the same move the AC makes against a
    live server. The corruption target is a DEDICATED scratch file with its own engine, and the
    app's shared engine is redirected onto that scratch file for the test's duration (t35 AC-3):
    the startup lifespan (``create_all`` + ``bootstrap_defaults``, which run on ``app.main.engine``)
    and the probe request both hit the scratch file, so the shared engine's ``test.db`` is never
    touched - it stays byte- and mtime-identical and no ``test.db-wal``/``test.db-shm`` sidecars of
    it are left behind. The lifespan is let to run on the healthy scratch file first, the scratch
    file is corrupted only afterwards, and the scratch sessions are closed, the scratch engine
    disposed and the shared engine references restored on the way out.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as _Session
    from sqlalchemy.pool import NullPool

    from app import main as main_module
    from app.database import get_db

    scratch_dir = Path(__file__).resolve().parent / "_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_file = scratch_dir / "t35_hygiene.db"
    for _suffix in ("", "-wal", "-shm"):
        Path(str(scratch_file) + _suffix).unlink(missing_ok=True)
    # A scratch engine of its own: the file this test corrupts is never the shared engine's file.
    # NullPool (a connection per checkout) matches the shared engine and is safe across the worker
    # thread the TestClient serves the request on.
    scratch_engine = create_engine(
        f"sqlite:///{scratch_file}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    database.Base.metadata.create_all(bind=scratch_engine)

    # Redirect the app's shared engine onto the scratch file for the test's duration, so nothing in
    # the app - the startup lifespan included - ever opens the shared engine's test.db.
    original_engine = database.engine
    database.engine = scratch_engine
    main_module.engine = scratch_engine
    # The request sessions the override hands out, kept so teardown can close them: on Windows a
    # still-checked-out connection keeps the scratch file handle open and the unlink fails (WinError
    # 32), and dispose alone does not close a connection an open session still holds.
    scratch_sessions: list[_Session] = []
    try:
        db = _Session(bind=scratch_engine)
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

        def _scratch_db():
            session = _Session(bind=scratch_engine)
            scratch_sessions.append(session)
            return session

        app.dependency_overrides[get_db] = _scratch_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            with client:  # the startup lifespan runs here, on the healthy scratch file
                # Corrupt only after the lifespan has already booted: the probe request then hits a
                # corrupted scratch file, never the shared engine's file.
                scratch_file.write_text("t21 probe: not a sqlite database file", encoding="utf-8")
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
            app.dependency_overrides.pop(get_db, None)
    finally:
        # Restore the shared engine references, close the scratch request sessions, dispose the
        # scratch engine, and remove the scratch file (and any sidecars it left). Nothing here
        # reopens the shared engine's file.
        database.engine = original_engine
        main_module.engine = original_engine
        for session in scratch_sessions:
            session.close()
        scratch_sessions.clear()
        scratch_engine.dispose()
        for _suffix in ("", "-wal", "-shm"):
            Path(str(scratch_file) + _suffix).unlink(missing_ok=True)
        # Defense in depth (t35): dispose the shared engine so no pooled connection of the process
        # can outlive the file churn. NullPool makes this cheap; nothing here reopens it.
        original_engine.dispose()
