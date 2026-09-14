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
    # The verifier reads the store the request is being ANSWERED from. It cannot share the handler's
    # session - two ``Depends(get_db)`` annotations resolve to two sessions on this version, so a
    # sub-dependency has no route to the one the handler holds - which leaves one question and one
    # answer: WHICH factory does the request's store live on?
    #
    #   * A suite that rebinds ``app.database.engine`` / ``SessionLocal`` (``test_staff_tables``,
    #     ``test_admin_reset``, the reset harness) puts its store on the ambient factory, and a
    #     session opened here is that store. Such a suite registers no override at all.
    #   * A suite that overrides the ``get_db`` DEPENDENCY with a session of its own
    #     (``test_admin_settings``, ``test_admin_tables``) never touches the factory, so a session
    #     opened here is a database nobody is serving - and after T9 decision D-2 that is a 401 on a
    #     correctly signed bearer, since the generation value the key needs lives in the row the
    #     handler will load. The override is a plain callable, and the session it hands back is the
    #     store under test, so the verifier asks it first.
    #
    # The order is not cosmetic, and the earlier draft inverted it. Opening the ambient factory
    # unconditionally is a WRITE to whatever file that name still carries: SQLite creates the
    # file on connect, so a suite whose store is an in-memory override would find an empty on-disk
    # settings table sitting beside it, the credential check would answer "none configured", and
    # every bearer in the module would be refused. Asking the override first and opening the factory
    # only when nothing answered keeps the verifier out of stores that are not serving the request.
    #
    # Both reads happen inside this frame while a harness's rebind is still in force: the settings
    # getter is this module's own attribute, which is exactly the name the shipped reset suite
    # rebinds to redirect ``jwt_secret``.
    import app.main as main_module
    from app import database as database_module

    override = main_module.app.dependency_overrides.get(get_db)
    served = override() if callable(override) else database_module.SessionLocal()
    try:
        return _verify(credentials.credentials, get_settings(), served)
    finally:
        served.close()


def _verify(
    token: str, settings: Any, served: Session
) -> dict[str, Any]:
    """The verification body: signature against the store's key, then the claim checks.

    Split out so :func:`get_current_staff` can state the one rule the verifier exists to enforce:
    the signing key, the credential-presence read and the settings object the horizon comes from
    all describe ONE store, read inside one session. T9 decision D-2 moved the store's
    token-generation value into the key, so a verifier that read the generation from one database
    and the secret from another would either reject a token the request earned or accept one for the
    wrong store - AC-1's tampered store and AC-5's rotation are both only meaningful when the two
    reads are the same read.

    ``served`` is the session the request's own ``get_db`` yielded, which is the whole reason one
    session argument is enough: the store it names is the store the handler answers from.
    ``settings`` is a parameter for the mirror-image reason - the caller read it through this
    module's own getter, which is what a harness rebinds to redirect ``jwt_secret``.
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

