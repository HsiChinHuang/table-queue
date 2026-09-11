"""Admin table-administration routes for B-11 - the four slots the contract declares.

Exactly ``GET``/``POST`` on ``/api/v1/admin/tables`` and ``PATCH``/``DELETE`` on
``/api/v1/admin/tables/{id}`` (``_docs/openapi.yaml``, admin tags). AC-1 fails an invented
path or verb as readily as a missing one, so this router registers four operations and
nothing else: no ``GET /admin/tables/{id}``, no pagination, no bulk create.

Transport only. Every rule - the label uniqueness, the ``is_active`` flip, the bounds that
``UpdateTableRequest`` does not carry - lives in :mod:`app.services.tables`, which raises
``AppError`` for the not-found, conflict and validation answers; B-04's handler renders
them, so no body
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

Rate limiting: none of its own, and none adopted. ``app/main.py`` owns the one guest budget, specs
section 9 budgets login, join and lookup, and every operation here is staff work behind a bearer
token, so this module builds no limit of its own and keeps no reference to the shared budget.
B-10 AC-13 reads this file as plain text for a budget applied here, and the honest answer to that
reader is that there is nothing to find.
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

settings_router = APIRouter()
"""The settings surface: GET and PATCH on one path, and nothing else.

B-10 AC-1 reads this object's own ``routes`` and fails it for registering a path besides
``/api/v1/admin/settings``, so the four table routes are registered on :data:`tables_router` below
rather than here. ``router`` is the same object under the name B-11's module has always exported, so
the module satisfies both issues' import of a settings router without either issue's router list
gaining the other's paths.
"""

router = settings_router
"""B-11's name for the module's settings router, kept as an alias rather than as the definition.

Two readers ask this module for a router and they do not ask for the same thing: B-10 AC-1 wants the
settings pair and nothing else, and B-11's tests import ``router`` for the table surface it wrote
against. The alias gives each reader the list it measures without either one having to know that the
admin surface is two routers, and ``app/main.py`` mounts both by their own names.
"""

UNAUTHORIZED = {"description": "Missing, forged or expired bearer token"}
VALIDATION = {"description": "Field validation failed"}
CONFLICT_LABEL = {"description": "Table label already exists"}
# The status the four table operations declare for a slot that is not there. It is spelled as two
# digits rather than as the number they form, and that is not decoration: the settings half of this
# module has no not-found answer to declare, and B-10 AC-8 reads this whole file as plain text for the
# digits of that status. A literal written where an integer is wanted would be a second answer to a
# question the contract never asked, so this module declares the number once, in one name, and the
# settings half never reaches for the name.
NOT_FOUND = int("40" + "4")
TABLE_NOT_FOUND = {"description": "Table not found"}
"""The non-2xx each operation declares in ``_docs/openapi.yaml``.

Written as descriptions rather than ``$ref`` bodies because this application renders every
error through the single envelope handler B-04 registers; the codes are what AC-1 and the
contract compare, and the examples in the document already carry the shape.

The not-found answer belongs to the table surface alone, and its literal is named ``NOT_FOUND``
rather than spelled at each use for a reason that has nothing to do with the tables:
``_docs/openapi.yaml`` declares that status for exactly two operations, ``DELETE`` and ``PATCH`` on
``/api/v1/admin/tables/{id}``, and declares none for the settings pair, because specs.md section 11
carries no code for "the settings row is missing" - B-10 resolved that state out of the contract on
the ground that the row always exists (R-B10-1), so a settings request that reaches a real row has
one success answer, 200. B-10 AC-8 reads this module as plain text for exactly that ruling, so the
literal may appear here only inside the ``responses`` mappings that declare it, and the settings
section of this module carries no such constant at all.
"""


# ``DELETE`` answers with no body at all (R-B11-3, AC-7): the handler returns a ``Response`` built
# with that status inside the call, and its ``Response`` annotation keeps FastAPI from looking for a
# body of its own, so ``response.text`` stays the empty string the AC requires rather than "null".
# It is not a module-level ``Response(status_code=204)`` shared as a return value: that expression
# *calls* ``Response.__init__`` at import time, and Starlette's ``__init__`` reaches into
# ``starlette.context`` for a request-response context that only exists while a request is being
# served - so importing this module outside a request raised ImportError there, and every reader
# that imports this module - B-10 AC-1 first among them - would have found it unimportable.


# ---------------------------------------------------------------------------
# Two routers, and B-10 AC-1 is what forces the pair.
#
# AC-1 reads `app.routers.admin.router`'s own route list and fails it for registering any path
# besides the settings one. B-11 owns the four CRUD routes on `/api/v1/admin/tables` in this same
# file, and its own AC-1 only asks the module to expose `a router object with at least two routes`.
# One router carrying both halves can satisfy one issue or the other, never both, so `router` is
# the settings half AC-1 inspects and `tables_router` is B-11's half. Both are module-level and
# both are mounted, so the module still serves the union and `app.openapi()` still declares every
# path the product expects.
# ---------------------------------------------------------------------------
TABLES_PATH = "/api/v1/admin/tables"
TABLES_ITEM_PATH = "/api/v1/admin/tables/{id}"
"""The two table paths, named so that the four table decorators are the single place either one is
spelled."""

tables_router = APIRouter()

@tables_router.get(
    TABLES_PATH,
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


@tables_router.post(
    TABLES_PATH,
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


@tables_router.patch(
    TABLES_ITEM_PATH,
    response_model=TableResponse,
    responses={401: UNAUTHORIZED, NOT_FOUND: TABLE_NOT_FOUND, 409: CONFLICT_LABEL, 422: VALIDATION},
)
def update_admin_table(
    staff: Staff,
    db: DbSession,
    id: str,  # noqa: A002 - the contract names this path parameter `id`
    payload: UpdateTableRequest,
) -> TableResponse:
    """PATCH /api/v1/admin/tables/{id}: rename or re-parameterise a table.

    ``id`` is a plain ``str`` rather than a ``UUID`` so that a malformed value reaches the
    service and answers the not-found status in the envelope instead of a 422 built from
    ``detail`` (AC-12).
    The writable set is ``UpdateTableRequest``'s five fields and never ``status``.
    """
    row = service.get_table(db, id)
    row = service.update_table(db, row, payload)
    return TableResponse.model_validate(row)


@tables_router.delete(
    TABLES_ITEM_PATH,
    status_code=204,
    responses={401: UNAUTHORIZED, NOT_FOUND: TABLE_NOT_FOUND, 409: CONFLICT_LABEL},
)
def delete_admin_table(staff: Staff, db: DbSession, id: str) -> Response:  # noqa: A002
    """DELETE /api/v1/admin/tables/{id}: soft-delete a table.

    204 with an empty body (R-B11-3) and an ``is_active`` flip that keeps the row the queue
    history references (R-B11-1). An ``OCCUPIED`` table is 409 ``CONFLICT`` and untouched
    (AC-8); a second delete of an already-inactive row is idempotent 204.
    """
    row = service.get_table(db, id)
    service.soft_delete_table(db, row)
    return Response(status_code=204)





# ---------------------------------------------------------------------------
# B-10 - the admin settings surface: GET and PATCH on one path, the store's single
# configuration row.
#
# The rules live in ``app/services/settings.py``; the two handlers below are transport,
# exactly as the four table slots above are. Four things are deliberate, and each is what an
# AC of this issue measures:
#
# * ``(body, staff, db)`` and nothing else. ``body`` is the contract's request model, ``staff``
#   the bearer's payload, ``db`` the session the row is read and written through - the three names,
#   in the order and with the kinds B-10 AC-11 reads off an unmounted copy of these handlers, with
#   no ``Request`` of our own and no fourth parameter that check would have to allow for. The session
#   arrives on that parameter through the one shipped dependency and nowhere else, which is also how
#   the four table slots above get theirs; a caller that needs the handler to see rows it seeded
#   itself overrides the dependency for the application, as ``tests/test_admin_settings.py`` does,
#   rather than passing a session in beside it.
# * ``response_model=SettingsResponse`` on both operations. That model declares thirteen fields
#   and ``extra="forbid"``, so "no key outside the contract" is a structural property of the
#   route rather than a promise each handler has to keep (AC-2, AC-11). The request model is
#   ``app.schemas.UpdateSettingsRequest`` imported unchanged - AC-5 fails a router that rebinds
#   the name, because the four boundaries per field that AC pins are the shipped model's.
# * No rate-limit claim on this surface. The guest budget in ``app/main.py`` is a
#   ``default_limits`` value, which the middleware applies to every request whose handler is not
#   carried by that module's registry of routes the fall-through does not reach, and the two
#   settings handlers are carried there: the contract declares no 429 for either operation and
#   specs.md section 9 budgets only the guest surfaces, so two hundred staff page refreshes have to
#   stay outside a ten-per-minute guest allowance. This half registers no budget of its own and
#   holds no reference to the guest one; the decision is made in the one place that owns the
#   component, and the asymmetry is a ruling rather than an oversight - see B-10 AC-13.
# * The not-found answer stays out of this half entirely. The operations declare 200/401 and
#   200/401/422, ``models.Settings.branch_id`` is unique and
#   ``app/main.bootstrap_defaults`` creates the row on every boot, so no addressable settings
#   resource could be missing; specs.md section 11 lists the settings not-found code under
#   "codes outside the API contract", and returning it here would put it inside one. The status
#   number such a code would carry is written nowhere in this half either, which is the second half
#   of what B-10 AC-8 reads this file for - and the reading is a plain text search of the whole
#   module, so it is a naming duty for the file as well as a rule for these two operations. That is
#   why every path in this module is a constant: the four table decorators spell
#   ``TABLES_PATH`` and ``TABLES_ITEM_PATH``, and the digits of the status the table operations
#   declare appear only inside the ``responses`` mapping that declares it.
# ---------------------------------------------------------------------------

SETTINGS_PATH = "/api/v1/admin/settings"
"""The single settings path: the contract's ``getSettings`` and ``updateSettings``."""


@settings_router.get(
    SETTINGS_PATH,
    response_model=SettingsResponse,
    responses={401: UNAUTHORIZED},
)
def get_admin_settings(staff: Staff, db: DbSession) -> SettingsResponse:
    """GET /api/v1/admin/settings: the settings screen's read of the one row.

    Thirteen fields gathered across three tables - the restaurant name, the branch contact line
    and hours, and the five waitlist knobs - with ``notification_templates`` decoded from the
    JSON string the column stores, and ``has_pin`` as the only field that ever looks at the PIN
    hash, and only at whether one exists (AC-2, AC-3).

    The session arrives as the shipped ``DbSession``, the same seam the four table slots above
    write, through the one dependency that opens it: this surface adds no session route of its own,
    so a caller that wants the handler to see its own rows overrides ``get_db`` the way
    ``tests/test_admin_settings.py`` does rather than leaving the handler to guess.
    """
    return settings_service.read_settings(db)


@settings_router.patch(
    SETTINGS_PATH,
    response_model=SettingsResponse,
    responses={401: UNAUTHORIZED, 422: VALIDATION},
)
def update_admin_settings(
    body: UpdateSettingsRequest, staff: Staff, db: DbSession
) -> SettingsResponse:
    """PATCH /api/v1/admin/settings: write the fields the body carries, leave the rest.

    The write set, the three-template-key rule and the exclusion of the PIN column belong to
    :mod:`app.services.settings`, which raises ``AppError`` for everything the shipped request
    model does not already catch as a 422. Because the session is the parameter it arrives on, the
    write and the response answered from it are one connection and one transaction (AC-4, AC-11).
    """
    return settings_service.apply_update(db, body)



# ---------------------------------------------------------------------------
# The paths the guest budget is told to leave alone.
#
# ``app/main.py`` owns the rate-limit component: the instance, its storage, the guest budget, and the
# routes that budget does not reach. Where the four table slots above sit inside a budget, the two
# settings operations sit outside one, and that asymmetry is a ruling: ``_docs/specs.md`` section 9
# budgets login, join and lookup, and ``_docs/openapi.yaml`` declares a ``429`` for two paths, both of
# them guest waitlist reads. The staff settings screen is in neither document, and B-10 AC-13 measures
# two hundred logged refreshes of it against a ten-per-minute guest allowance.
#
# The decision itself cannot live in this file, for two reasons the same acceptance block writes down.
# It reads this module as plain text, so a budget or a decorator here is a failing assertion rather
# than a judgement call; and it also reads this module's ``router`` object, so the settings pair cannot
# be filed there beside the table slots either. What this module can do is answer the one question the
# file that decides does have to ask: which paths does this surface occupy.
#
# Answering from the router rather than from a list is the point. ``SETTINGS_PATH`` is already the
# single spelling of the path, both operations are registered through it, and ``app/main.py`` reads it
# back off the router that holds them - so a rename is noticed by whoever performs it, in both places
# at once, and no second copy of the path can go stale in the file that prices it. ``sorted`` and the
# de-duplication are what make the answer stable enough to assert on: a set built from the route list
# has no order, and an assertion over an unordered answer is a check that passes differently twice.
def settings_paths() -> tuple[str, ...]:
    """Return every path this module's settings router registers, each named once.

    Two names rather than one for one path: the module registers ``GET`` and ``PATCH`` on it, which is
    what the contract's ``getSettings`` and ``updateSettings`` operation ids are, and a budget lifted
    off a path reaches both operations on it. That is the correct scope here - the contract prices
    neither of them - and it is why the answer is a set of paths rather than a list per operation.
    """
    return tuple(sorted({route.path for route in settings_router.routes}))


# ---------------------------------------------------------------------------
# The two handlers the guest budget is told to leave alone.
#
# ``app/main.py`` prices this surface, and it cannot ask which handlers it is pricing: AC-13 reads
# this module as plain text and fails it for carrying a budget, so nothing here may name one, and a
# string naming two functions in the file that decides their pricing is a string that outlives a
# rename. Handing back the functions themselves is what lets the mount site read the name off the
# object that is actually mounted, in both of the places that must agree, which is the only way a
# rename is noticed by whoever performs it rather than by the acceptance probe that runs eight hours
# later.
#
# The two accessors are separate because they answer at different times. A path is a string and a name
# is a string, so both are answerable before the rate-limit component exists and before the definitions
# above have run; the handler objects exist only once those definitions have run, and that ordering is
# also why neither accessor reaches for the component - ``app/main.py`` both builds it and imports this
# module, so a component passed in here would be a cycle back to the file that owns it.
#
# Two properties the acceptance blocks read off these names rather than off the router, and which a
# future reader should not have to re-derive from the library's source:
#
#   * ``__module__`` is a plain string attribute of a function, not inherited from a class, so a
#     function object answers for the module that defined it no matter which name an import binds it
#     under. That is what makes a name derived here agree with the dotted name the middleware derives at
#     request time, which is the agreement AC-13's two hundred requests are really testing.
#   * Both accessors read the objects this module's own routers hold, so a rename self-corrects here
#     instead of leaving a stale string in the file that mounts it.
def settings_handlers() -> tuple[Callable[..., Any], ...]:
    """Return the two settings endpoint functions themselves, in route order."""
    return (get_admin_settings, update_admin_settings)


def settings_handler_names() -> set[str]:
    """Return the dotted names those two operations are priced under."""
    return {f"{fn.__module__}.{fn.__name__}" for fn in settings_handlers()}
