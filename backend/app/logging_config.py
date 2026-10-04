"""Application-owned process log configuration (T21).

specs.md section 15 (lines 593-598) is the product-level contract for the backend process
log: "Phone not logged." / "Name not logged." / "Token not logged." This module is the single
place that makes the contract hold for every uvicorn startup (``make dev``, the README's bare
command, or a plain ``uvicorn app.main:app`` - T21 D-2: app-level, not flag-level):

* SQLAlchemy's statement loggers are pinned at WARNING **and** their echo records are
  discarded at the source. The pin alone is not enough on this lock: with ``echo=True``
  ``create_engine`` wraps the logger in an ``InstanceLogger`` that calls ``Logger._log``
  directly - bypassing the level check - and attaches its own stdout handler at engine-
  creation time (measured on sqlalchemy 2.0.52, ``sqlalchemy/log.py``). So a level pin by
  itself would not keep SQL/parameter echo out of the log (T21 D-4).
* uvicorn's raw access logger is disabled. It prints the full request line - the status
  lookup's query string (``?token=...&phone_last3=...``) included - and uvicorn 0.52.4 gates
  the access log on ``uvicorn.access.hasHandlers()`` at protocol start, so removing its
  handler before the first connection is enough. The access line is emitted by the
  application's access middleware (``app.main.AccessLogMiddleware``), which never writes a
  query string (T21 D-2).
* uvicorn's error log is routed through the root handler, so its "Exception in ASGI
  application" traceback passes the binding redaction below (T21 D-5: the duplicate copy may
  remain if both are redacted).
* the application's 500 log (``app.errors``) is redacted at the record level: the traceback
  stays diagnosable (frames, message, exception type) while the ``[SQL: ...]`` /
  ``[parameters: ...]`` segments - tag and value - are removed (T21 D-3).

``configure_logging()`` must run after the SQLAlchemy engine is created (``app.database``
import): the echo handler is attached at ``create_engine`` time, so the cleanup below has to
run later to win. It is idempotent.
"""

from __future__ import annotations

import logging
import re
import sys

# SQLAlchemy binding segments that must never reach the process log (T21 D-3): the tag and the
# value, both. The segments are matched non-greedily, so a bracket inside the statement text
# only truncates the removed segment - the tag itself is always gone, and the bound values live
# in the [parameters: ...] segment, which is removed on its own as well.
_BINDING_PAIR_RE = re.compile(r"\[SQL:.*?\]\s*\[parameters:.*?\]", re.DOTALL)
_SQL_RE = re.compile(r"\[SQL:.*?\]", re.DOTALL)
_PARAMETERS_RE = re.compile(r"\[parameters:.*?\]", re.DOTALL)

# Markers so configure_logging() stays idempotent (a process can import app.main through more
# than one path, and the filter must not be installed twice on the same logger/handler).
_REDACTING = "t21_redacting"
_DISCARDING = "t21_discard_echo"

# Loggers whose echo machinery (InstanceLogger) bypasses the level check: pin them at WARNING
# and discard their echo-level records at the source (see the module docstring for the
# measurement).
_ECHO_LOGGERS = ("sqlalchemy.engine.Engine", "sqlalchemy.pool")
# Class-level statement loggers: pinned at WARNING so no echo-level record from any SQLAlchemy
# logger can reach a handler through normal propagation, whatever the SQL_ECHO flag says.
_STATEMENT_LOGGERS = (
    "sqlalchemy.engine",
    "sqlalchemy.engine.Engine",
    "sqlalchemy.pool",
    "sqlalchemy.orm",
)


def redact_sql_bindings(text: str) -> str:
    """Remove ``[SQL: ...]`` and ``[parameters: ...]`` segments from ``text``.

    The surrounding traceback - frames, exception type and message, the
    ``(Background on this error at: ...)`` hint - is left intact, so a 500 stays diagnosable
    without the bound values (T21 D-3: the whole segment goes, tag and value; a placeholder
    does not satisfy the contract).
    """
    if not text or ("[SQL:" not in text and "[parameters:" not in text):
        return text
    text = _BINDING_PAIR_RE.sub("", text)
    text = _SQL_RE.sub("", text)
    text = _PARAMETERS_RE.sub("", text)
    return text


class SQLBindingRedactionFilter(logging.Filter):
    """Strip SQLAlchemy binding segments from a record, in place.

    The filter mutates the record (``msg`` and ``exc_text``) rather than returning False, so
    every handler that later sees the record - including handlers installed after this filter
    (pytest's caplog among them) - renders the redacted text. Pre-setting ``exc_text`` matters:
    a formatter that later renders the record reuses the stored ``exc_text`` instead of
    re-formatting the raw ``exc_info``, so the raw binding lines never reach a formatter.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "[SQL:" in message or "[parameters:" in message:
            record.msg = redact_sql_bindings(message)
            record.args = ()
        if record.exc_info is not None:
            record.exc_text = redact_sql_bindings(
                logging.Formatter().formatException(record.exc_info)
            )
        return True


class _EchoDiscardFilter(logging.Filter):
    """Discard echo-level (INFO and below) records from a SQLAlchemy statement logger.

    SQLAlchemy's ``InstanceLogger`` calls ``Logger._log`` directly, bypassing the level check,
    and attaches its own stdout handler at ``create_engine`` time - so a level pin alone cannot
    keep echo out of the log at any ``SQL_ECHO`` value (T21 D-4). Discarding at the source does.
    WARNING and above still propagate to the root handler, where the redaction filter applies.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno > logging.INFO


def _add_marked(logger: logging.Logger, new_filter: logging.Filter, marker: str) -> None:
    """Attach ``new_filter`` to ``logger`` at most once per process."""
    if any(getattr(existing, marker, False) for existing in logger.filters):
        return
    setattr(new_filter, marker, True)
    logger.addFilter(new_filter)


def configure_logging() -> None:
    """Make the process log honour specs.md 593-598 end to end.

    Must run after the SQLAlchemy engine is created (``app.database`` import) - see the module
    docstring for the ordering constraint. Idempotent.
    """
    # 1. Pin the statement loggers at WARNING: no echo-level record from any SQLAlchemy logger
    #    reaches a handler through normal propagation, whatever SQL_ECHO says.
    for name in _STATEMENT_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # 2. Silence the echo machinery itself: drop the stdout handler InstanceLogger attached at
    #    create_engine time, and discard echo-level records at the source (the pin above does
    #    not reach them - InstanceLogger bypasses the level check).
    for name in _ECHO_LOGGERS:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        _add_marked(logger, _EchoDiscardFilter(), _DISCARDING)

    # 3. Take over the access log: uvicorn's raw access logger prints the full request line
    #    (the status lookup's token/phone_last3 included), so it is disabled and the app's
    #    access middleware emits the line instead - path only, no query string.
    access = logging.getLogger("uvicorn.access")
    for handler in list(access.handlers):
        access.removeHandler(handler)
    access.propagate = False
    access.setLevel(logging.CRITICAL)

    # 4. Route uvicorn's error log through the root handler so the redaction filter sees its
    #    "Exception in ASGI application" traceback (the second copy of the 500 traceback, T21
    #    D-5: it may remain, redacted).
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        logger.propagate = True

    # 5. Redact the app's 500 log at the record level (see SQLBindingRedactionFilter).
    _add_marked(logging.getLogger("app.errors"), SQLBindingRedactionFilter(), _REDACTING)

    # 6. Root handler with the redaction filter: the last line of defence for every logger that
    #    reaches the root - uvicorn's re-routed loggers, third-party loggers, and WARNING+ from
    #    the statement loggers.
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(handler, _REDACTING, False) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handler.addFilter(SQLBindingRedactionFilter())
        setattr(handler, _REDACTING, True)
        root.addHandler(handler)
