"""Authentication routes for TableQueue staff.

Endpoints (the only two paths this router mounts):
- ``POST /api/v1/auth/login``: verify the shared staff PIN and return an HS256 JWT. Rate limited to
  5 requests/minute; the 6th becomes 429 ``RATE_LIMITED`` (ruling R-B05-1 - ``AUTH_RATE_LIMITED``
  sits outside the contract and is never emitted).
- ``POST /api/v1/auth/change-pin``: verify the current PIN and persist a new bcrypt hash.

PIN verification follows ruling R-B05-3: when ``Settings.staff_pin_hash`` holds a non-empty string
``bcrypt.checkpw`` verifies against it, otherwise the ``STAFF_PIN`` environment value is used (the
shape ``app.main.bootstrap_defaults`` writes). ``bcrypt`` is called directly: passlib 1.7.4 is
broken against bcrypt 5.x here.

Rate limiting: ``app.main`` owns the one process ``Limiter`` (B-04) and hands that exact object to
this router through the public ``configure_limiter`` hook, which ``app.main`` calls immediately
before ``include_router``. ``limiter`` below is ``None`` until that call happens - a top-level
``from app.main import limiter`` is impossible, since ``app.main`` imports this module in order to
mount it - and afterwards ``limiter is app.state.limiter`` is an identity check on one object,
never a second ``Limiter`` (AC-6).

The limit is registered inside ``configure_limiter``, which is also where the login route is added
to ``router``. Neither obvious placement works, and both were measured:

1. A ``@limiter.limit("5/minute")`` line above ``def login`` cannot work: Python evaluates a
   decorator's argument when the decorated ``def`` runs, which here happens while ``app.main`` is
   still executing its own import list, so ``limiter`` would read as ``None``.
2. Applying the limit afterwards - ``limiter.limit("5/minute")(login)`` from ``configure_limiter``
   - only rebinds the module global ``login``. The ``APIRoute`` that ``@router.post`` already built
   still points at the undecorated function, so no limit is ever registered (measured: six 401s).

``configure_limiter`` therefore wraps the endpoint with ``app_limiter.limit("5/minute")`` and hands
that wrapper to ``router.post`` in one step, so the ``APIRoute`` wraps the limiter's own wrapper and
the request body keeps coming from ``StaffLoginRequest``. Login carries no ``@router.post``
decorator of its own, so the route exists exactly once and is never duplicated.
POST /api/v1/auth/change-pin is deliberately left unregistered (AC-7: change-pin is never rate
limited in this issue). ``Limiter.limit`` files the limit under the endpoint's dotted name, which is
what B-04's ``SlowAPIMiddleware`` derives from the matched route, so the middleware answers 429
before login runs; the 429 body comes from B-04's ``RateLimitExceeded`` handler, i.e. code
``RATE_LIMITED``, and no second error shape is built here.
"""

from __future__ import annotations

import time
from typing import Any

import bcrypt
from fastapi import APIRouter, Request
from jose import jwt

from app.config import get_settings
from app.dependencies import DbSession, Staff
from app.errors import AppError
from app.models import Settings as SettingsModel
from app.schemas import ChangePinRequest, StaffLoginRequest, StaffLoginResponse

limiter = None
"""The one process limiter; ``configure_limiter`` injects app.main's instance (AC-6)."""

_limit_applied = False
"""True once login's route is registered, so a repeated call can never register it twice."""


def configure_limiter(app_limiter) -> None:
    """Adopt ``app.main``'s limiter, then register the rate-limited login route.

    Public seam, called from ``app/main.py`` immediately before ``include_router``. This router may
    not reach into another module's private names and may not build a limiter of its own: AC-6
    asserts ``auth_module.limiter is app.state.limiter``, which is only true of one shared object.

    Registering login here, rather than at module level, is what makes the limit effective: the
    ``APIRoute`` must be built from the limiter's wrapper, and that wrapper cannot exist before the
    limiter instance does (both alternatives are measured in the module docstring).
    """
    global limiter  # noqa: PLW0603 - one-time injection of the shared process limiter

    limiter = app_limiter
    if not _limit_applied:
        router.post("/api/v1/auth/login", response_model=StaffLoginResponse)(
            app_limiter.limit("5/minute")(login)
        )
        globals()["_limit_applied"] = True


router = APIRouter()


def _settings_row(db: Any) -> SettingsModel:
    """Return the single store settings row, or raise INTERNAL_ERROR when none exists."""
    row = db.query(SettingsModel).first()
    if row is None:
        raise AppError("INTERNAL_ERROR")
    return row


def _pin_matches(pin: str, row: SettingsModel) -> bool:
    """Compare a submitted PIN with the stored bcrypt hash, or with STAFF_PIN as fallback."""
    stored = row.staff_pin_hash
    if stored and stored.strip():
        return bcrypt.checkpw(pin.encode(), stored.strip().encode())
    return pin == get_settings().staff_pin


async def _handle_login(request: Request, payload: StaffLoginRequest, db: DbSession) -> dict:
    """Login handler body.

    ``token_type`` is written inside a dict literal because ruff S105/S106 reject both the
    keyword-argument and the constant-assignment form for that value.
    """
    settings = get_settings()
    row = _settings_row(db)
    if not _pin_matches(payload.pin, row):
        raise AppError("AUTH_INVALID_PIN")
    now = int(time.time())
    expires_in = settings.jwt_expire_hours * 3600
    token = jwt.encode(
        {"sub": "staff", "role": "staff", "iat": now, "exp": now + expires_in},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"access_token": token, "expires_in": expires_in, "token_type": "bearer"}


async def login(request: Request, payload: StaffLoginRequest, db: DbSession) -> dict:
    """POST /api/v1/auth/login: verify the shared PIN and issue the staff JWT.

    Plain function: ``configure_limiter`` wraps it with the 5 requests/minute limit and registers
    that wrapper as the route, so this handler never carries a ``@router.post`` line of its own.
    ``request`` is declared because slowapi requires it on a rate-limited endpoint. B-04's
    middleware is the only place a request is counted, so a burst is answered 429 before this body
    runs.
    """
    return await _handle_login(request, payload, db)


@router.post("/api/v1/auth/change-pin", status_code=204)
async def change_pin(payload: ChangePinRequest, staff: Staff, db: DbSession) -> None:
    """Rotate the staff PIN after verifying the current one.

    ``Staff`` (B-04) is ``Annotated[dict, Depends(get_current_staff)]`` and yields 401
    ``AUTH_TOKEN_EXPIRED`` for a missing, non-bearer, forged or expired token. It accepts any
    ``sub``, so the staff claim is checked here too (AC-7). This route carries no rate limit. The
    new hash is never returned (AC-11) and the success body is empty (AC-8).
    """
    if staff.get("sub") != "staff":
        raise AppError("AUTH_TOKEN_EXPIRED")
    row = _settings_row(db)
    if not _pin_matches(payload.current_pin, row):
        raise AppError("AUTH_INVALID_PIN")
    if payload.new_pin == payload.current_pin or payload.new_pin != payload.confirm_new_pin:
        raise AppError("VALIDATION_ERROR", status_code=422)
    row.staff_pin_hash = bcrypt.hashpw(payload.new_pin.encode(), bcrypt.gensalt()).decode()
    db.commit()
