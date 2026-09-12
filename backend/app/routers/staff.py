"""Staff endpoints for TableQueue (issue B-08's tables, issue B-09's dashboard).

Four operations, exactly the ones ``_docs/openapi.yaml`` declares for this module:

- ``GET  /api/v1/staff/tables`` - active tables, each ``OCCUPIED`` row carrying its live party.
- ``PATCH /api/v1/staff/tables/{id}`` - ``AVAILABLE`` <-> ``CLEANING`` only.
- ``POST /api/v1/staff/tables/{id}/release`` - release an occupied table.
- ``GET  /api/v1/staff/dashboard`` - the one dashboard read (B-09).

This module is transport only: the auth dependency, the status codes, the response models and the
injection of the clock. Every rule (lookup, transitions, the ``SEATED`` party, ``elapsed_minutes``,
the one-transaction release, the dashboard's counters) lives in ``app.services.tables`` /
``app.services.dashboard`` - no SQL and no ORM query appears here.

Auth: all four ride on ``app.dependencies.Staff`` (B-04/B-05's ``get_current_staff``), so a
missing, non-bearer, forged or expired token is 401 ``AUTH_TOKEN_EXPIRED`` before any handler runs.

Rate limiting: none. ``_docs/specs.md`` section 15 limits login, join and lookup only, openapi
declares no 429 for these operations, and B-06 owns limiter identity, so no decorator is applied
and no ``Limiter`` is built here (R-B08-6). ``configure_limiter`` accepts ``app.main``'s shared
instance without constructing a second one, and registers nothing - unlike the auth router, this
router has no route that needs the limiter's wrapper.

B-07 (#33) added the staff waitlist operations in their own module
(:mod:`app.routers.staff_waitlist`) rather than this one, so the only addition here after B-08 is
B-09's dashboard read.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import DbSession, Staff, get_now
from app.schemas import (
    DashboardResponse,
    TableListResponse,
    TableResponse,
    UpdateTableStatusRequest,
)
from app.services import dashboard as dashboard_svc
from app.services import tables as svc

router = APIRouter()

# Kept as a module attribute so a future limiter-based route can use app.main's instance. Nothing
# here constructs a Limiter: AC-11 asserts the shared app.state.limiter stays the only one.
limiter = None


def configure_limiter(app_limiter) -> None:
    """Adopt ``app.main``'s one process limiter (called from ``app/main.py`` before mounting).

    The staff table surface declares no limit (R-B08-6), so this hook stores the shared instance
    and registers nothing. It exists so ``app.main`` can mount this router with the same
    configure-then-include pattern the auth router uses.
    """
    global limiter  # noqa: PLW0603 - one-time adoption of the shared process limiter
    limiter = app_limiter


@router.get("/api/v1/staff/tables", response_model=TableListResponse)
def list_tables(
    include_inactive: bool = False,
    staff: Staff = None,
    db: DbSession = None,
) -> Any:
    """GET /api/v1/staff/tables: active tables, ordered by sort_order then label.

    ``include_inactive`` also returns rows whose ``is_active`` is false. Every ``OCCUPIED`` row
    carries the four-field ``current_waitlist``; every other state is null even when a waitlist row
    still points at it.
    """
    now = get_now()
    rows = svc.list_tables(db, include_inactive)
    items = [svc.to_response(db, row, now) for row in rows]
    return {"items": items, "total": len(items)}


@router.patch("/api/v1/staff/tables/{id}", response_model=TableResponse)
def update_table_status(
    id: str,
    payload: UpdateTableStatusRequest,
    staff: Staff = None,
    db: DbSession = None,
) -> Any:
    """PATCH /api/v1/staff/tables/{id}: AVAILABLE <-> CLEANING, persisted and read back.

    ``UpdateTableStatusRequest.status`` is ``Literal["AVAILABLE", "CLEANING"]``, so a body asking
    for ``OCCUPIED`` is rejected by B-04's validation handler as 422 ``VALIDATION_ERROR`` before
    this body runs - the enum is the whole of R-B08-1 and this operation declares no 409.
    """
    return svc.update_table_status(db, id, payload.status, get_now())


@router.post("/api/v1/staff/tables/{id}/release", response_model=TableResponse)
def release_table(
    id: str,
    staff: Staff = None,
    db: DbSession = None,
) -> Any:
    """POST /api/v1/staff/tables/{id}/release: 200 ``AVAILABLE`` or 409 ``TABLE_NOT_AVAILABLE``.

    The table write and the ``SEATED`` -> ``DONE`` write happen in one service call and one commit
    (specs section 14). Releasing an already-released table is the 409, not a second 200 and not a
    404.
    """
    return svc.release_table(db, id, get_now())


@router.get("/api/v1/staff/dashboard", response_model=DashboardResponse)
def get_dashboard(
    staff: Staff = None,
    db: DbSession = None,
) -> Any:
    """GET /api/v1/staff/dashboard: live queue and table counts plus today's rollups (B-09).

    The handler is transport in the same shape the three table routes are: it injects the clock
    through ``get_now`` and hands the whole read to :func:`app.services.dashboard.collect`, which
    applies the section 4.10 lazy no-show and then counts. No query, no SQL and no arithmetic live
    here.

    The route is a plain ``def`` and reads no request body - the contract declares this operation
    with no parameters and no request body at all (``_docs/openapi.yaml``'s ``getDashboard``), so
    there is no ``Request`` to await. B-07 measured what happens when a sync handler touches the
    body API: ``Request.body()`` returns a coroutine, and an un-awaited call reaches ``.strip()``
    as a coroutine object, so every body-carrying request answers 500 ``INTERNAL_ERROR``. A future
    body-reading route in this module must therefore be ``async def`` with an awaited read, which
    is what ``app/routers/staff_waitlist.py`` does for its PUT.

    ``DashboardResponse`` is the response model rather than a hand-built dict shape, so a stray key
    is a response-model error (``extra="forbid"``) and the payload can never grow a field the
    contract does not declare - which is the surface B-12's completeness test grades.
    """
    return dashboard_svc.collect(db, get_now())
