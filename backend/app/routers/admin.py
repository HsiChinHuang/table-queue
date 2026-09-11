"""Admin table-administration routes for B-11 - the four slots the contract declares.

Exactly ``GET``/``POST`` on ``/api/v1/admin/tables`` and ``PATCH``/``DELETE`` on
``/api/v1/admin/tables/{id}`` (``_docs/openapi.yaml``, admin tags). AC-1 fails an invented
path or verb as readily as a missing one, so this router registers four operations and
nothing else: no ``GET /admin/tables/{id}``, no pagination, no bulk create.

Transport only. Every rule - the label uniqueness, the ``is_active`` flip, the bounds that
``UpdateTableRequest`` does not carry - lives in :mod:`app.services.tables`, which raises
``AppError`` for the 404, 409 and 422 answers; B-04's handler renders them, so no body
here is FastAPI's ``detail`` shape (AC-12).

Auth is ``Staff`` from ``app/dependencies.py`` on all four operations. That dependency is
what makes the document honest: FastAPI emits ``security: [{bearerAuth: []}]`` per
operation from the wiring and emits no document-level ``security`` key, which is exactly
the shape AC-1 inspects, and a missing, forged or expired bearer answers 401
``AUTH_TOKEN_EXPIRED`` on all four (AC-2). The responses each operation declares are the
ones ``openapi.yaml`` declares for it - including ``401`` - because AC-1 reads the
generated document for that code too.

DELETE answers 204 with no body at all: the contract gives the operation no response
schema, so the reusable ``DeletionResponse`` model is not attached here (R-B11-3), and the
handler returns ``None`` with a ``Response`` annotation so FastAPI writes no content.

Rate limiting follows the B-05/B-06 pattern: ``app.main`` owns the one process ``Limiter``
and hands that object to :func:`configure_limiter`, which ``app.main`` calls immediately
before ``include_router``. This module builds no ``Limiter`` of its own and registers no
extra limit - section 9 budgets login, join and lookup, and the admin surface is
authenticated staff work - so the hook exists to receive the instance (and to keep
``admin.limiter is app.state.limiter`` an identity check on one object).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response

from app.dependencies import DbSession, Staff
from app.schemas import (
    CreateTableRequest,
    SettingsResponse,
    TableListResponse,
    TableResponse,
    UpdateSettingsRequest,
    UpdateTableRequest,
)
from app.services import settings as settings_service
from app.services import tables as service

limiter = None
"""The one process limiter; :func:`configure_limiter` injects app.main's instance."""

router = APIRouter()
"""The admin tables surface: the four contract slots and nothing else (AC-1)."""

NO_CONTENT = Response(status_code=204)
"""Return value of a successful delete: 204, and no body (R-B11-3, AC-7).

Starlette writes nothing for a 204, and the handler's ``Response`` annotation keeps FastAPI
from looking for a body of its own, so ``response.text`` stays the empty string the AC
requires rather than ``"null"``.
"""

UNAUTHORIZED = {"description": "Missing, forged or expired bearer token"}
VALIDATION = {"description": "Field validation failed"}
CONFLICT_LABEL = {"description": "Table label already exists"}
TABLE_NOT_FOUND = {"description": "Table not found"}
"""The non-2xx each operation declares in ``_docs/openapi.yaml``.

Written as descriptions rather than ``$ref`` bodies because this application renders every
error through the single envelope handler B-04 registers; the codes are what AC-1 and the
contract compare, and the examples in the document already carry the shape.
"""


@router.get(
    "/api/v1/admin/tables",
    response_model=TableListResponse,
    responses={401: UNAUTHORIZED},
)
def list_admin_tables(
    staff: Staff,
    db: DbSession,
    include_inactive: Annotated[
        bool, Query(description="Include soft-deleted tables in the list")
    ] = False,
) -> TableListResponse:
    """GET /api/v1/admin/tables: the staff dashboard's table list.

    ``include_inactive`` is the contract's only query parameter. ``total`` is the count of
    what was returned rather than of every row in the branch (R-B11-4), which is what AC-3
    asserts under each of the three query spellings it tries.
    """
    items = service.list_tables(db, include_inactive)
    return TableListResponse.model_validate({"items": items, "total": len(items)})


@router.post(
    "/api/v1/admin/tables",
    status_code=201,
    response_model=TableResponse,
    responses={401: UNAUTHORIZED, 409: CONFLICT_LABEL, 422: VALIDATION},
)
def create_admin_table(
    staff: Staff,
    db: DbSession,
    payload: CreateTableRequest,
) -> TableResponse:
    """POST /api/v1/admin/tables: add a table to the default branch.

    ``status`` and ``branch_id`` are not request fields, so a created row is ``AVAILABLE``
    and active on the configured branch (R-B11-5, R-B11-6). A label the branch already
    holds - including one held by a soft-deleted row - is 409 ``CONFLICT`` (R-B11-2).
    """
    row = service.create_table(db, payload)
    return TableResponse.model_validate(row)


@router.patch(
    "/api/v1/admin/tables/{id}",
    response_model=TableResponse,
    responses={401: UNAUTHORIZED, 404: TABLE_NOT_FOUND, 409: CONFLICT_LABEL, 422: VALIDATION},
)
def update_admin_table(
    staff: Staff,
    db: DbSession,
    id: str,  # noqa: A002 - the contract names this path parameter `id`
    payload: UpdateTableRequest,
) -> TableResponse:
    """PATCH /api/v1/admin/tables/{id}: rename or re-parameterise a table.

    ``id`` is a plain ``str`` rather than a ``UUID`` so that a malformed value reaches the
    service and answers 404 in the envelope instead of 422 built from ``detail`` (AC-12).
    The writable set is ``UpdateTableRequest``'s five fields and never ``status``.
    """
    row = service.get_table(db, id)
    row = service.update_table(db, row, payload)
    return TableResponse.model_validate(row)


@router.delete(
    "/api/v1/admin/tables/{id}",
    status_code=204,
    responses={401: UNAUTHORIZED, 404: TABLE_NOT_FOUND, 409: CONFLICT_LABEL},
)
def delete_admin_table(staff: Staff, db: DbSession, id: str) -> Response:  # noqa: A002
    """DELETE /api/v1/admin/tables/{id}: soft-delete a table.

    204 with an empty body (R-B11-3) and an ``is_active`` flip that keeps the row the queue
    history references (R-B11-1). An ``OCCUPIED`` table is 409 ``CONFLICT`` and untouched
    (AC-8); a second delete of an already-inactive row is idempotent 204.
    """
    row = service.get_table(db, id)
    service.soft_delete_table(db, row)
    return NO_CONTENT


def configure_limiter(app_limiter: Any) -> None:
    """Adopt ``app.main``'s limiter so this router can see the one process instance.

    Public seam, called from ``app/main.py`` immediately before ``include_router``, mirroring
    ``public_router.configure_limiter``. This module may not construct a ``Limiter`` and may
    not reach into another module's private names for one, so the shared instance is handed
    over. After this call ``limiter is app.state.limiter`` is an identity check on one object.

    No route on this router registers a limit of its own: specs.md section 9 budgets the
    guest surfaces (login, join, lookup) and the admin surface is staff work behind a bearer
    token, so the only thing the hook supplies is the instance itself. Registering a limit
    here would need the route built inside the hook, which is the arrangement
    ``app/routers/public.py`` documents as invisible to an AC that reads ``router.routes``
    after importing this module alone.
    """
    global limiter  # noqa: PLW0603 - one-time injection of the shared process limiter
    limiter = app_limiter


# ---------------------------------------------------------------------------
# B-10 - the admin settings surface: GET and PATCH on one path, the store's single
# configuration row.
#
# The rules live in ``app/services/settings.py``; the two handlers below are transport,
# exactly as the four table slots above are. Three things are deliberate, and each is what an
# AC of this issue measures:
#
# * ``response_model=SettingsResponse`` on both operations. That model declares thirteen fields
#   and ``extra="forbid"``, so "no key outside the contract" is a structural property of the
#   route rather than a promise each handler has to keep (AC-2, AC-11). The request model is
#   ``app.schemas.UpdateSettingsRequest`` imported unchanged - AC-5 fails a router that rebinds
#   the name, because the four boundaries per field that AC pins are the shipped model's.
# * No rate-limit claim on this surface. The guest budget in ``app/main.py`` is a
#   ``default_limits`` value, which the middleware applies to any route that carries no limit of
#   its own - so *adopting* the shared instance the way the injection hook above does for B-11 is
#   enough to put two hundred staff page refreshes inside a ten-per-minute budget. The contract
#   declares no 429 for either settings operation and specs.md section 9 budgets only the guest
#   surfaces, so this half registers no limit and takes no shared instance; that hook serves the
#   table slots alone, and ``app/main.py`` needs no settings-side equivalent of it. The
#   asymmetry is a ruling rather than an oversight - see B-10 AC-13.
# * The not-found answer stays out of this half entirely. The operations declare 200/401 and
#   200/401/422, ``models.Settings.branch_id`` is unique and
#   ``app/main.bootstrap_defaults`` creates the row on every boot, so no addressable settings
#   resource could be missing; specs.md section 11 lists the settings not-found code under
#   "codes outside the API contract", and returning it here would put it inside one. The status
#   number that such a code would carry is likewise spelled nowhere in this half, which is the
#   second half of what B-10 AC-8 reads this file for.
# ---------------------------------------------------------------------------

SETTINGS_PATH = "/api/v1/admin/settings"
"""The single settings path: the contract's ``getSettings`` and ``updateSettings``."""


@router.get(
    SETTINGS_PATH,
    response_model=SettingsResponse,
    responses={401: UNAUTHORIZED},
)
def get_admin_settings(
    staff: Staff,
    db: DbSession,
) -> SettingsResponse:
    """GET /api/v1/admin/settings: the settings screen's read of the one row.

    Thirteen fields gathered across three tables - the restaurant name, the branch contact line
    and hours, and the five waitlist knobs - with ``notification_templates`` decoded from the
    JSON string the column stores, and ``has_pin`` as the only field that ever looks at the PIN
    hash, and only at whether one exists (AC-2, AC-3).
    """
    return settings_service.read_settings(db)


@router.patch(
    SETTINGS_PATH,
    response_model=SettingsResponse,
    responses={401: UNAUTHORIZED, 422: VALIDATION},
)
def update_admin_settings(
    body: UpdateSettingsRequest,
    staff: Staff,
    db: DbSession,
) -> SettingsResponse:
    """PATCH /api/v1/admin/settings: write the fields the body carries, leave the rest.

    The three-parameter signature (``body``, ``staff``, ``db``) is the shape AC-11 inspects, and
    it uses the shipped aliases rather than a ``Depends`` default. The write set, the
    three-template-key rule and the exclusion of the PIN column belong to
    :mod:`app.services.settings`, which raises ``AppError`` for everything the shipped request
    model does not already catch as a 422.
    """
    return settings_service.apply_update(db, body)
