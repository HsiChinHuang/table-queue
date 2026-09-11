"""Dependency utilities for TableQueue backend.

Exports:
- `bearer_scheme`: HTTPBearer instance (auto_error=False).
- `DbSession`: ``Annotated`` alias for ``Session`` injected via ``Depends(get_db)``.
- `get_current_staff`: validates JWT, raising ``AppError('AUTH_TOKEN_EXPIRED')`` on any problem.
- `Staff`: ``Annotated`` alias for the dict payload from ``get_current_staff``.
- `get_now`: returns timezone‑aware UTC datetime.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.database import Session, get_db
from app.errors import AppError

# ---------------------------------------------------------------------------
# Authentication scheme
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Dependency aliases
# ---------------------------------------------------------------------------

DbSession = Annotated[Session, Depends(get_db)]

# ---------------------------------------------------------------------------
# Current staff extraction
# ---------------------------------------------------------------------------

def get_current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, str]:
    """Validate JWT and return its payload.

    On any validation error an ``AppError('AUTH_TOKEN_EXPIRED')`` is raised. The
    global error handler converts this to a 401 JSON envelope.
    """
    if not credentials:
        raise AppError('AUTH_TOKEN_EXPIRED') from None
    token = credentials.credentials
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
    except JWTError:
        raise AppError('AUTH_TOKEN_EXPIRED') from None
    now = int(time.time())
    exp = payload.get('exp')
    if exp is None or now > int(exp):
        raise AppError('AUTH_TOKEN_EXPIRED') from None
    if 'sub' not in payload:
        raise AppError('AUTH_TOKEN_EXPIRED') from None
    return payload

# Export a convenient annotation for route signatures.
Staff = Annotated[dict[str, str], Depends(get_current_staff)]

# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------

def get_now() -> datetime:
    """Return a timezone‑aware UTC datetime instance."""
    return datetime.now(UTC)

