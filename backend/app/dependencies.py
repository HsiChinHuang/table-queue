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
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings  # noqa: F401  - re-exported, see get_current_staff
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
"""Every router's database parameter, unchanged from the shipped alias.

It is worth naming what that means for a caller, because B-10's settings surface is reached in two
ways and this is the seam between them. A handler reached through the application that owns its
router gets the session ``get_db`` yields, opened on ``app.database.engine``, and closed by
``get_db``'s own ``finally`` when the response is written - which is the same session the response
was read from, the property AC-4's "PATCH then GET sees it" and AC-11's "one session per request"
both measure. A caller that reaches the handler some other way has one supported route to the same
outcome and no other: ``app.dependency_overrides[get_db]``, which replaces ``get_db`` for the
application and therefore for this alias too, so the caller's session is the session the handler
sees and the caller's teardown is what closes it. That is what ``backend/tests`` does - every
module that owns an engine overrides this name rather than passing a session beside it - and it is
why the alias carries no wrapper of its own: a wrapper would give an override a second dependency
to know about, and a handler that resolved one and not the other would read a database its caller
never wrote to.
"""


# ---------------------------------------------------------------------------
# Current staff extraction
# ---------------------------------------------------------------------------

def get_current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Validate JWT and return its payload.

    On any validation error an ``AppError('AUTH_TOKEN_EXPIRED')`` is raised. The
    global error handler converts this to a 401 JSON envelope.

    T9 (decision D-2) changes WHICH key the signature is checked against, not what a failure costs:
    the key is ``jwt_secret`` plus the generation value stored in the settings row, so a token
    minted before a PIN rotation was signed with the generation that rotation replaced, lands in the
    same ``JWTError`` branch, and answers 401 ``AUTH_TOKEN_EXPIRED`` - no new code, status or
    field, which is what keeps ``_docs/openapi.yaml`` untouched.

    The settings object is read HERE, at the call, rather than imported at module scope or captured
    at import time: ``jwt_secret`` is a configuration value, and the harnesses that point the
    application at a scratch store rebind ``get_settings`` to do it. Passing the object into
    :func:`_verify` is what guarantees the secret and the generation value are read for one store by
    one verifier, in one pass, while that rebind is still the answer.

    ``get_settings`` also stays importable from this module: the shipped reset suite rebinds exactly
    this attribute on purpose, so the name has to be here for the seam to have anything to rebind.
    """
    if not credentials:
        raise AppError('AUTH_TOKEN_EXPIRED') from None
    # The store arrives as the SAME dependency the route handlers read through, so the generation
    # value the signing key is built from and the rows the request serves come from one place.
    return _verify(credentials.credentials, get_settings(), db)


def _verify(token: str, settings: Any, db: Session) -> dict[str, Any]:
    """The verification body: signature against the store's key, then the claim checks.

    Split out so :func:`get_current_staff` can state the one rule the verifier exists to enforce:
    the signing key, the credential-presence read and the settings object the horizon comes from
    all describe ONE store, read inside one session. T9 decision D-2 moved the store's
    token-generation value into the key, so a verifier that read the generation from one database
    and the secret from another would either reject a token the request earned or accept one for
    the wrong store - AC-1's tampered store and AC-5's rotation are both only meaningful when the
    two reads are the same read.

    ``db`` is a parameter rather than a session this function opens itself, because the application
    reaches its store through ``get_db`` and the two reads have to be one read: a harness that hands
    the application a scratch store by overriding that dependency has to hand the verifier the same
    one, or the generation value in the key describes a database the request never touched.
    Modules that rebind ``app.database.SessionLocal`` instead still work, since ``get_db`` builds
    its session from that attribute at call time. ``settings`` is a parameter for the mirror-image
    reason: the
    caller read it through this module's own getter, which is what a harness rebinds to redirect
    ``jwt_secret``, and the secret has to be the one it answers for.
    """
    from app.routers.auth import credential_is_configured, token_generation_value

    try:
        if not credential_is_configured(db):
            # No credential configured is no access, even for a token that is still well-signed: the
            # row this token was minted against has since lost its hash, and a signature cannot
            # expire on its own (AC-1's tampered-store reading).
            raise AppError('AUTH_TOKEN_EXPIRED') from None
        key = settings.jwt_secret.strip() + token_generation_value(db)
        payload = jwt.decode(token, key, algorithms=['HS256'])
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

