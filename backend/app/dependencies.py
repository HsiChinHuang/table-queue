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
    # The store the verifier reads is a session of its own on the ambient factory rather than the
    # route handler's ``db``. FastAPI resolves two ``Depends(get_db)`` annotations twice on this
    # version, so the session a handler is handed is not one a sub-dependency could reach anyway,
    # and a harness that gives the APPLICATION a scratch store through a ``get_db`` override would
    # otherwise leave the verifier decoding against a generation value from a database nobody is
    # The factory is read through the module attribute so a harness that rebinds it onto its own
    # engine carries the verifier with it.
    # Both candidate stores are opened on this line and handed down together, so the ONE the
    # verifier uses is chosen inside the call - while this module's ``get_settings`` is still the
    # one a harness rebound, which is what makes the secret and the generation value agree. Read
    # into a local first, that read would happen before the override could matter; read after the
    # caller's frame is gone, it would happen after the harness had undone it. Either way the two
    # halves of the key come from different stores, and a key assembled from two stores is the bug
    # rather than a finding.
    import app.main as main_module
    from app import database as database_module

    override = main_module.app.dependency_overrides.get(get_db)
    with database_module.SessionLocal() as ambient:
        served = override() if callable(override) else ambient
        return _verify(credentials.credentials, get_settings(), ambient, served)


def _verify(
    token: str, settings: Any, ambient: Session, served: Session
) -> dict[str, Any]:
    """The verification body: signature against the store's key, then the claim checks.

    Split out so :func:`get_current_staff` can state the one rule the verifier exists to enforce:
    the signing key, the credential-presence read and the settings object the horizon comes from
    all describe ONE store, read inside one session. T9 decision D-2 moved the store's
    token-generation value into the key, so a verifier that read the generation from one database
    and the secret from another would either reject a token the request earned or accept one for
    the wrong store - AC-1's tampered store and AC-5's rotation are both only meaningful when the
    two reads are the same read.

    The verifier prefers ``served`` - the store the APPLICATION would answer this request from -
    and falls back to ``ambient`` when no harness redirected one. It cannot ask FastAPI for the
    handler's own session: two ``Depends(get_db)`` annotations resolve to two sessions on this
    version, so a sub-dependency can never share the handler's, and a scratch store handed to the
    application through an override would otherwise leave the signature checked against a
    generation value from a database nobody is serving. A caller that hands both arguments the
    same session gets the same answer it always did.
    ``settings`` is a parameter for the mirror-image reason: the caller read it through this
    module's own getter, which is what a harness rebinds to redirect ``jwt_secret``, and the
    secret has to be the one that getter answers for.
    """
    from app.routers.auth import credential_is_configured, token_generation_value

    try:
        if not credential_is_configured(served):
            # No credential configured is no access, even for a token that is still well-signed: the
            # row this token was minted against has since lost its hash, and a signature cannot
            # expire on its own (AC-1's tampered-store reading).
            raise AppError('AUTH_TOKEN_EXPIRED') from None
        key = settings.jwt_secret.strip() + token_generation_value(served)
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

