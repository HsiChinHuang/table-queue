"""Authentication routes for TableQueue staff.

Endpoints (the only two paths this router mounts):
- ``POST /api/v1/auth/login``: verify the shared staff PIN and return an HS256 JWT. Rate limited to
  5 requests/minute; the 6th becomes 429 ``RATE_LIMITED`` (ruling R-B05-1 - ``AUTH_RATE_LIMITED``
  sits outside the contract and is never emitted).
- ``POST /api/v1/auth/change-pin``: verify the current PIN and persist a new bcrypt hash.

PIN verification is bcrypt-only (T9, superseding ruling R-B05-3): the stored
``Settings.staff_pin_hash`` column is the ONLY credential the staff surface accepts, and the only
comparison left is ``bcrypt.checkpw``. R-B05-3's fall-through to the ``STAFF_PIN`` environment value
was deleted by T9 (audit A-2/A-9): that env value is documented in the contract files and readable
by anyone who can read the process environment, so it was a live second credential rather than a
transitional one. ``app.main.bootstrap_defaults`` now hashes that one-time seed into the row it
inserts, so a fresh install never sits in the hash-less state the fallback used to cover, and a row
that is hash-less anyway (manual tampering, a half-migrated store) fails closed: every PIN
against it answers 401 ``AUTH_INVALID_PIN``. ``bcrypt`` is called directly: passlib 1.7.4 is
broken against bcrypt 5.x here.

Token revocation follows T9 decision D-2: the HS256 signature is computed over ``jwt_secret``
concatenated with the stored token-generation value, a settings COLUMN that
``POST /api/v1/auth/change-pin`` replaces on every rotation. A pre-rotation token then fails
signature verification in ``app.dependencies.get_current_staff`` and answers 401
``AUTH_TOKEN_EXPIRED``, so rotation is a revocation event without a per-request revocation-table
read. The generation value lives in the same SQLite row as the hash rather than in process memory,
which is what lets two workers (``_docs/deployment.md`` prescribes ``--workers 2``) sign and verify
with the same key.

Two consequences of D-2 are recorded here because they are contract changes, and a reader has to be
able to find them from the module that made them:

1. A bearer signed with the bare ``JWT_SECRET`` no longer verifies (AC-5 pins it). Every staff and
   admin caller must therefore hold a token login minted. The shipped suite hand-signed bearers in
   eight test modules against the ambient secret - the shape ruling R-B05-3 and B-05 AC-4 assumed -
   and those tokens die with the signature change by definition, so those helpers now call
   :func:`mint_staff_token` below rather than reconstruct a key they can no longer derive.
2. The hash column is now checked for PRESENCE on the staff/admin path as well as at login
   (:func:`credential_is_configured`). A signature cannot expire, so without that read a token
   minted while the row still had a hash would keep opening the API after the credential was
   removed, and AC-1's tampered store would answer 200.

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

import secrets
import time
from typing import Any

import bcrypt
from fastapi import APIRouter, Request
from jose import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import DbSession, Staff
from app.errors import AppError
from app.models import Settings as SettingsModel
from app.schemas import ChangePinRequest, StaffLoginRequest, StaffLoginResponse

BCRYPT_COST = 12
"""The bcrypt work factor every PIN hash in this application is written with, named once and passed
explicitly to every ``bcrypt.gensalt`` call (T9 AC-6). AC-6 sweeps each construction site in
``routers/auth.py``, ``app/main.py``, ``seed.py``, ``dependencies.py`` and
``services/settings.py`` and rejects any site that inherits the library default instead: a cost that
is a library default is a cost a dependency bump can move, and the ``$2b$12$`` factor audit C-18
rated clean is only a fact about new hashes while the constant that writes it is pinned.
"""

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


INITIAL_TOKEN_GENERATION = "initial"  # noqa: S105
"""The token-generation value a store carries before its first PIN rotation.

Two things make this a constant rather than a generated value, and AC-5 measures both:

* it must be the value EVERY worker derives for the same store, because a value generated at import
  time would differ per process and a token minted by worker A would then die on worker B (the
  shipped run shape is ``--workers 2``); and
* it must be derivable from a row that never names the column. ``token_generation`` is nullable, so
  an existing store, a store the shipped ``bootstrap_defaults`` wrote before this column existed, or
  a settings row inserted by a script that names only the older columns all read as this value
  instead of raising - and an unhandled exception on the verifier path would answer 500 where AC-5
  and AC-8 require 200.
"""


def token_generation_value(db: Session) -> str:
    """Read the store's current token-generation secret (T9 decision D-2).

    A single scalar SELECT, not an ORM row, so the read survives a store whose ``settings`` table
    predates the column: an ``OperationalError`` there would surface as 500 on every staff and admin
    request. The generation value lives here - in the same SQLite row as the PIN hash - precisely
    because the verifier has to see it in every worker, which is the property that rules out a
    process global and rules out the per-request revocation-table read D-2 rejected.
    """
    from sqlalchemy import text

    try:
        row = db.execute(
            text("select token_generation from settings order by id limit 1")
        ).fetchone()
    except Exception:  # noqa: BLE001 - a missing column means "never rotated", see the docstring
        return INITIAL_TOKEN_GENERATION
    stored = row[0] if row else None
    text_value = (stored or "").strip() if isinstance(stored, str) else ""
    return text_value or INITIAL_TOKEN_GENERATION


def token_signing_key(db: Session) -> str:
    """The HS256 key every staff token is signed with and verified with.

    ``jwt_secret`` alone cannot express revocation: a signature either verifies or it does not, and
    nothing short of changing the secret makes an already-minted signature stop verifying. Folding
    the generation value into the key gives exactly that, which is why ``app.dependencies`` rebuilds
    this same key to verify rather than decoding with the bare secret (AC-5 pins the consequence: a
    token signed with the bare ``JWT_SECRET`` answers 401).

    The generation value is key material only. It is never a claim: AC-8 pins the payload at exactly
    ``sub``/``role``/``iat``/``exp``, so adding a claim would be a contract change, while a key
    change is invisible to the schema.
    """
    return get_settings().jwt_secret + token_generation_value(db)


def mint_staff_token(db: Session, *, role: str = "staff", lifetime_seconds: int = 3600) -> str:
    """Mint a staff bearer through the same code path ``POST /api/v1/auth/login`` uses.

    A supported seam rather than a convenience: once a rotation folds the stored generation into the
    signature, a caller that is not login cannot reconstruct the signing key from configuration, so
    the only way to hold a current staff token - from a test harness, or from any future in-process
    caller - is to ask the module that owns the credential. AC-5's revocation property is what makes
    this necessary: it pins the payload at ``sub``/``role``/``iat``/``exp`` and refuses the bare
    ``jwt_secret`` signature, so the payload cannot carry a hint a caller could re-sign on its own.

    It is not a route, a field or a response code, so ``_docs/openapi.yaml`` does not move.

    The horizon is measured against the clock the VERIFIER will later read, which is the same
    ``time.time`` both sides call. A harness under ``freeze_time`` moves that clock for the mint and
    restores it before the request lands, so minting at the frozen instant hands the caller a token
    that is already expired when it is presented; the caller is expected to mint outside such a
    block. The ``exp`` claim stays the login response's own shape.
    """
    now = int(time.time())
    return jwt.encode(
        {"sub": "staff", "role": role, "iat": now, "exp": now + lifetime_seconds},
        token_signing_key(db),
        algorithm="HS256",
    )


def credential_is_configured(db: Session) -> bool:
    """Whether the store currently carries a usable staff credential (T9 decision D-1).

    The verifier asks this before it accepts a signature, and that one check is what makes a
    hash-less row fail CLOSED rather than fail OPEN. A signature cannot expire: a token minted while
    the row still held a hash keeps verifying forever, so AC-1's tampered store - the hash removed
    under a live session - would otherwise keep answering 200 for the old token and for a freshly
    minted one. Checking the credential's presence on the request path is therefore the only shape
    in which "no credential configured" can mean "no access".

    It is a single scalar SELECT on the same row the generation value is read from, not the
    per-request revocation table D-2 rejected: no rows are written, nothing is joined, and there is
    nothing to prune. D-2's objection was to a table that has to be consulted to learn whether a
    token is alive; this asks the store a question it can already answer, and it is the property the
    shipped ``has_pin`` flag reports for the operator.
    """
    from sqlalchemy import text

    try:
        row = db.execute(
            text("select staff_pin_hash from settings order by id limit 1")
        ).fetchone()
    except Exception:  # noqa: BLE001 - a store we cannot read is not a store to authorise against
        return False
    stored = row[0] if row else None
    return bool(isinstance(stored, str) and stored.strip())


def _pin_matches(pin: str, row: SettingsModel) -> bool:
    """Compare a submitted PIN with the stored bcrypt hash, the only credential that exists.

    Two properties AC-2/AC-3/AC-4 measure, and the order of the two statements carries the first:

    - Fail closed. A row whose hash is NULL, blank or whitespace carries NO credential, so no
      submitted string can match it and the answer is False without consulting any other source -
      not the environment, not a default, not a second column. The shipped code fell through to the
      plaintext env value here, which is the hole audit A-2 reported.
    - Bcrypt-only (T9 decision D-3). The one comparison left is ``bcrypt.checkpw``, whose work
      factor does not depend on where a submitted PIN differs from the stored one. The
      short-circuiting ``str ==`` it replaces is gone rather than wrapped in a constant-time
      helper: the transitional path the audit's fix direction allowed is the path this issue
      deletes, so AC-4 also asserts that no ``compare_digest`` call was introduced in its place.

    AC-3 reads this function's source and asserts its LAST statement is the bcrypt call, so the
    fail-closed guard has to sit above it rather than replace it.
    """
    if not (row.staff_pin_hash or "").strip():
        return False
    return bcrypt.checkpw(pin.encode(), row.staff_pin_hash.strip().encode())


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
        token_signing_key(db),
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
    row.staff_pin_hash = bcrypt.hashpw(
        payload.new_pin.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)
    ).decode()
    # T9 decision D-2: the rotation writes the new credential AND the new token generation in the
    # same commit, so there is no window in which the new PIN is live while old tokens still
    # verify. Every token minted before this line was signed with the old key and now answers 401
    # AUTH_TOKEN_EXPIRED from the existing verifier - AC-5's revocation event, with no new field,
    # endpoint or response code in the contract.
    row.token_generation = secrets.token_urlsafe(32)
    db.commit()
