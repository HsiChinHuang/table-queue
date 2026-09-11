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


def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {"fields": []}
    for err in exc.errors():
        loc = err.get("loc", [])
        field = ".".join(str(p) for p in loc if isinstance(p, (str, int)))
        details["fields"].append({"field": field, "msg": err.get("msg")})
    payload = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": details,
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

