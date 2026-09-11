"""Error handling module for TableQueue.

Provides:
- `ERROR_CODES`: mapping of error code string to HTTP status (derived from specs.md).
- `AppError`: exception class carrying an error code, optional custom message, status_code, details.
- `register_error_handlers(app)`: registers FastAPI exception handlers for `AppError`,
  `RequestValidationError` (422 VALIDATION_ERROR), `RateLimitExceeded` (429 RATE_LIMITED),
  and generic `Exception` (500 INTERNAL_ERROR).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load error catalogue from specs.md (section 11). The spec lives two levels above
# this file (repository root) under `_docs/specs.md`.
# ---------------------------------------------------------------------------

def _load_error_codes() -> dict[str, int]:
    specs_path = Path(__file__).resolve().parents[2] / "_docs" / "specs.md"
    if not specs_path.is_file():
        raise FileNotFoundError(f"specs.md not found at {specs_path}")
    text = specs_path.read_text(encoding="utf-8")
    m = re.search(r"## 11\. Error Codes(.*?)Error response shape", text, re.S)
    if not m:
        raise RuntimeError("Error Codes section not found in specs.md")
    section = m.group(1)
    pattern = re.compile(r"^([A-Z][A-Z_]+)\s+(\d{3})\s", re.M)
    return {code: int(status) for code, status in pattern.findall(section)}

ERROR_CODES: Mapping[str, int] = _load_error_codes()


class AppError(Exception):
    """Application‑level error.

    Parameters
    ----------
    code: str
        The error code defined in ``ERROR_CODES``.
    message: str | None
        Optional custom message; defaults to the code name.
    status_code: int | None
        Override the HTTP status derived from ``ERROR_CODES``.
    details: dict | None
        Additional payload data.
    """

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        if code not in ERROR_CODES:
            raise ValueError(f"Unknown error code: {code}")
        self.code = code
        self.message = message or code.replace("_", " ")
        self.status_code = status_code or ERROR_CODES[code]
        self.details = details or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}

    def __repr__(self) -> str:  # pragma: no cover – debugging helper
        return (
            f"AppError(code={self.code!r}, status_code={self.status_code}, "
            f"message={self.message!r}, details={self.details!r})"
        )


def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


# The fixed message the contract's own example carries. It is a constant rather than a
# translation of the code name because `_docs/specs.md` section 11 fixes the shape of the
# envelope and `_docs/openapi.yaml` `components.responses.ValidationError` fixes its message.
VALIDATION_MESSAGE = "Validation failed"


def _flatten_field_names(loc: tuple[Any, ...]) -> str:
    """Name a rejected field the way the envelope names it: a dotted path without indices.

    ``RequestValidationError`` locates an error with a mixed path such as
    ``('body', 'notification_templates', 'extra')``. The contract's `details.fields` is a
    flat ``field -> message`` map, so the numeric list indices a nested error carries are
    dropped - they address an array element the flat map cannot name - and the rest is joined.
    ``body.`` is stripped because AC-10 compares the keys against the request body's own keys.
    """
    parts = [str(p) for p in loc if isinstance(p, str) and p != "body"]
    return ".".join(parts) if parts else "body"


def _field_message(err: dict[str, Any]) -> str:
    """Render one pydantic error entry as the one-line message the flat map carries.

    ``type`` and ``ctx`` are the machine-readable half of a pydantic error; the message alone
    would drop the boundary that failed (``Input should be greater than or equal to 5`` reads
    the same for two different fields). The context values are scalars taken from the request
    schema rather than from user data, so nothing sensitive rides them, and no phone number,
    name or token can reach them on this surface.
    """
    ctx = err.get("ctx") or {}
    detail = ", ".join(f"{k}={v}" for k, v in sorted(ctx.items()) if isinstance(v, (int, float, str)))
    msg = str(err.get("msg") or "Invalid value")
    return f"{msg} ({detail})" if detail else msg


def _validation_details(exc: RequestValidationError) -> dict[str, Any]:
    """The only builder of ``error.details`` for a request-body rejection.

    Shared by FastAPI's own ``RequestValidationError`` path and by the route-level check that
    has to reject a field the request schema cannot see inside (``notification_templates`` is
    typed ``dict[str, Any] | None``), so a rejected body is the same envelope whichever side
    raised it.
    """
    fields: dict[str, str] = {}
    for err in exc.errors():
        field = _flatten_field_names(tuple(err.get("loc") or ()))
        # One message per field: the contract map names each rejected key once, and the first
        # complaint about a key is the one that describes its declared constraint.
        fields.setdefault(field, _field_message(err))
    return {"fields": fields}


def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": VALIDATION_MESSAGE,
            "details": _validation_details(exc),
        }
    }
    return JSONResponse(status_code=422, content=payload)


def _handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Convert SlowAPI limit exception to our error envelope.
    err = AppError("RATE_LIMITED")
    return JSONResponse(status_code=err.status_code, content=err.to_payload())


def _handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception: %s", exc)
    generic = AppError("INTERNAL_ERROR")
    return JSONResponse(status_code=generic.status_code, content=generic.to_payload())


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers used by the B‑04 tests."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit)
    app.add_exception_handler(Exception, _handle_generic_exception)

