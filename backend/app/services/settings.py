"""Settings rules for B-10 - the single-row store configuration behind ``/admin/settings``.

The router in ``app/routers/admin.py`` is transport only. Everything that decides - which
row is THE row, which column a request field may write, what a notification-template object
has to carry, how the stored JSON string becomes the response's object - lives here and
raises ``AppError`` or ``RequestValidationError`` so B-04's handlers render the envelope.
No SQL expression language leaks into the router, and no HTTP object reaches this module.

Four rulings the AC set pins, restated where they are enforced:

* **One row per branch, and it is the configured branch.** ``Settings.branch_id`` is
  ``unique=True`` in ``app/models.py``, so there is nothing id-addressable to be missing
  (R-B10-1). The row is read by ``settings.default_branch_id``, never by a path or query
  parameter - the contract gives neither operation a parameter.
* **Twelve writable fields, thirteen readable ones.** Five live on ``settings``, five on the
  branch, one on the restaurant. The two time fields are branch columns because the branch
  row owns opening hours; ``settings`` carries no time column at all.
* **``staff_pin_hash`` is not writable and is never read out.** It is not in
  ``UpdateSettingsRequest``, the service never assigns it, and the only thing the response
  assembly takes from it is the boolean ``has_pin`` (AC-3). A body that names it is dropped
  with the rest of the schema's non-fields rather than applied.
* **The template object is replaced wholesale and must carry all three keys.** AC-6 rejects
  one-, two-, empty- and four-key bodies. The shipped schema types the field
  ``dict[str, Any] | None`` and cannot see inside it, so the check belongs to this service
  and travels as a ``RequestValidationError`` so the 422 envelope is B-04's, not a copy.

Timestamps are the model's: ``created_at`` has a default and ``updated_at`` an ``onupdate``,
both ``lambda: datetime.now(UTC)``. This module never writes either one, which is what makes
AC-7's frozen clock the only clock in the picture.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.config import get_settings
from app.errors import AppError
from app.models import Branch, Restaurant, Settings
from app.schemas import SettingsResponse, UpdateSettingsRequest

TEMPLATE_KEYS = ("joined", "called", "no_show")
"""The three notification templates `_docs/specs.md` section 6 names.

``_docs/openapi.yaml`` declares all three as optional ``properties`` of the object, so the
shape that the contract can express is a superset of these three with nothing missing:
exactly these keys, each a string. AC-6 measures the five bodies that break that.
"""

TEMPLATE_MIN_LENGTH = 2000
"""``Settings.notification_templates`` is ``String(2000)``; a longer object cannot be stored."""

SETTINGS_FIELD_ORDER: tuple[str, ...] = (
    "hold_minutes",
    "avg_seat_minutes",
    "queue_prefix",
    "is_waitlist_open",
    "sound_enabled_default",
    "notification_templates",
)
"""The six request fields that address a ``settings`` column, in write order.

Order is not decoration here. AC-4's rejection message prints "partial PATCH clobbered
branch_name to 07-000-0000", which is the branch phone sitting in the branch name column, and
that is only possible when one write is applied after another onto the same column. The request
model declares its fields alphabetically and ``model_dump`` preserves that order, so ``address``
appears before ``branch_name``; an ``elif`` chain keyed on the request field name then routes
several of the five branch fields at a column that is not theirs, and whichever one is applied
last wins the row. The write loop below therefore walks these fixed orders and resolves each
field against its own column.
"""

SETTINGS_FIELDS = frozenset(SETTINGS_FIELD_ORDER)
"""The six request fields that address a ``settings`` column."""

BRANCH_COLUMN_ORDER: tuple[tuple[str, str], ...] = (
    ("branch_name", "name"),
    ("address", "address"),
    ("phone", "phone"),
    ("open_time", "open_time"),
    ("close_time", "close_time"),
)
"""The five request fields that address the branch row, each with its ``branches`` column.

``branch_name`` is the one field whose column is not its own name - ``branches.name`` is what
the settings row's branch is called - and assuming the request key is the column for all five is
what puts the phone number in the name.
"""

BRANCH_FIELDS = frozenset(field for field, _column in BRANCH_COLUMN_ORDER)
"""The five request fields that address the branch row the settings row belongs to."""

RESTAURANT_FIELDS = frozenset({"restaurant_name"})
"""The one request field that addresses the restaurant above the branch."""

WRITABLE_FIELDS = SETTINGS_FIELDS | BRANCH_FIELDS | RESTAURANT_FIELDS
"""The twelve fields AC-4 names. Anything else in a body is not a field and is dropped."""


def _parse_templates(raw: str | None) -> dict[str, Any]:
    """Decode the stored JSON string into the object the response declares.

    ``SettingsResponse.notification_templates`` is ``dict[str, Any] | None`` while the column
    is a ``String(2000)``, so the decode is the service's job (AC-3's third bullet). A stored
    value that is not JSON is data damage rather than a client error: it answers 500
    ``INTERNAL_ERROR`` through the shipped handler rather than inventing a code the contract
    does not carry.
    """
    if raw is None:
        return {}
    try:
        decoded = json.loads(raw)
    except (ValueError, TypeError):
        raise AppError("INTERNAL_ERROR") from None
    if not isinstance(decoded, dict):
        raise AppError("INTERNAL_ERROR")
    return decoded


def _template_error(templates: Any) -> AppError:
    """The 422 a template object that is not exactly the three keys earns.

    An ``AppError('VALIDATION_ERROR', details=...)`` rather than a hand-built envelope, and
    with the same ``fields`` shape B-04's handler builds for a schema rejection, so AC-6's five
    rejected bodies and AC-10's four indistinguishable ones all leave through one door: code
    ``VALIDATION_ERROR``, no ``detail`` key, and ``error.details.fields`` naming the rejected
    request key.
    """
    return AppError(
        "VALIDATION_ERROR",
        details={
            "fields": {
                "notification_templates": f"expected exactly {', '.join(TEMPLATE_KEYS)}; got {templates!r}"
            }
        },
    )


def _templates_are_valid(templates: Any) -> bool:
    """Is ``templates`` exactly the three template keys, each a string that fits the column?

    ``{"joined": "x"}`` validates clean against the shipped schema (measured), which is why
    this lives here rather than in ``app/schemas.py``: the contract describes the shape in
    prose and in ``_docs/testing.md``'s test name, not in a schema keyword the model carries.
    """
    if not isinstance(templates, dict):
        return False
    if set(templates) != set(TEMPLATE_KEYS):
        return False
    if not all(isinstance(value, str) for value in templates.values()):
        return False
    return len(json.dumps(templates, ensure_ascii=False)) <= TEMPLATE_MIN_LENGTH


def settings_row(db: Any) -> Settings:
    """The one settings row of the configured branch, created on startup or not.

    ``app/main.bootstrap_defaults`` inserts it on every boot and ``models.Settings.branch_id``
    is unique, so a booted process always has it (R-B10-1). A row that is genuinely absent is
    an unhandled state, and the honest answer from the shipped catalogue is 500
    ``INTERNAL_ERROR`` rather than the 404 ``SETTINGS_NOT_FOUND`` that
    `_docs/specs.md` section 11 lists under "codes outside the API contract".
    """
    branch_id = get_settings().default_branch_id
    row = db.query(Settings).filter(Settings.branch_id == branch_id).first()
    if row is None:
        raise AppError("INTERNAL_ERROR")
    return row


def read_settings(db: Any) -> SettingsResponse:
    """Assemble the thirteen ``SettingsResponse`` fields from the three tables.

    Both hops go through the ORM relationships, and every row is re-read from the session on each
    call rather than remembered on the module: a caller hands this service a session it did not
    build (a request session, or a test's own session that it commits behind our back), and the
    relationship hop re-queries where a stale identity-map entry would answer from memory. ``has_pin`` is the only thing that looks at ``staff_pin_hash``, and it looks at
    its truthiness rather than its value (AC-3). The response model is ``extra="forbid"``, so the
    dict below is the whole surface: nothing else can ride along if a column is ever added.
    """
    row = settings_row(db)
    branch = row.branch
    restaurant = branch.restaurant if branch is not None else None
    payload: dict[str, Any] = {
        "restaurant_name": restaurant.name if restaurant is not None else "",
        "branch_name": branch.name if branch is not None else "",
        "address": branch.address if branch is not None else None,
        "phone": branch.phone if branch is not None else None,
        "open_time": branch.open_time if branch is not None else None,
        "close_time": branch.close_time if branch is not None else None,
        "hold_minutes": row.hold_minutes,
        "avg_seat_minutes": row.avg_seat_minutes,
        "queue_prefix": row.queue_prefix,
        "is_waitlist_open": row.is_waitlist_open,
        "sound_enabled_default": row.sound_enabled_default,
        "notification_templates": _parse_templates(row.notification_templates),
        "has_pin": bool(row.staff_pin_hash),
    }
    return SettingsResponse.model_validate(payload)


def apply_update(db: Any, payload: UpdateSettingsRequest) -> SettingsResponse:
    """Write the twelve allowed fields and answer with the same shape GET gives.

    Two orders matter here, and both are AC-pinned rather than stylistic:

    * **Validate first, then write.** AC-6 asks that none of its five rejected bodies touches
      the stored templates, so the template object is checked before a single ``setattr`` and
      the request that is going to fail cannot half-apply the fields that share its body.
    * **``exclude_unset=True``.** That is what makes a one-field body a one-field write:
      AC-4's second half PATCHes ``{"hold_minutes": 7}`` onto a row whose other eleven values
      it just set, and every one of them has to survive. ``notification_templates`` is
      replaced whole rather than merged, because the contract declares an object and not a
      merge patch.

    Nothing here writes ``created_at`` or ``updated_at``: the model's ``default`` and
    ``onupdate`` lambdas own them, which is what lets AC-7 pin the instant with a frozen clock
    instead of a sleep, and what keeps AC-7's rejected PATCH from moving the stamp.
    """
    body = payload.model_dump(exclude_unset=True)
    unknown = sorted(set(body) - WRITABLE_FIELDS)
    if unknown:
        # `extra="forbid"` on the request model turns an invented name into FastAPI's own 422
        # before this line, so reaching it means a relaxation elsewhere; saying which key is
        # worse than 500-ing quietly, and it says nothing about the column it might have hit.
        raise AppError(
            "VALIDATION_ERROR",
            details={"fields": {name: "not a settings field" for name in unknown}},
        )
    if "notification_templates" in body and not _templates_are_valid(
        body["notification_templates"]
    ):
        raise _template_error(body["notification_templates"])
    row = settings_row(db)
    # Two fixed-order passes rather than one pass over the body, and every branch write names
    # its column: see SETTINGS_FIELD_ORDER for why a body's arrival order corrupts the row.
    for field in SETTINGS_FIELD_ORDER:
        if field not in body:
            continue
        if field == "notification_templates":
            row.notification_templates = json.dumps(body[field], ensure_ascii=False)
        else:
            setattr(row, field, body[field])
    branch = row.branch
    for field, column in BRANCH_COLUMN_ORDER:
        if field in body:
            setattr(branch, column, body[field])
    if "restaurant_name" in body:
        branch.restaurant.name = body["restaurant_name"]
    db.commit()
    return read_settings(db)
