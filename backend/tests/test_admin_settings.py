"""Admin settings endpoint tests for B-10 (``GET``/``PATCH /api/v1/admin/settings``).

The two names ``_docs/testing.md`` section 2 names - ``test_get_settings_success`` and
``test_update_settings_success`` - are here, and the rest carry the AC-1 to AC-13 behaviours so
each answer is measured rather than described: the thirteen readable keys, the twelve writable
ones across three tables, the boundaries the shipped request model carries, the three-key
template rule, the 401 pair, the ``extra='forbid'`` response shape, and the absence of a rate
limit of our own.

Ownership follows the B-11 file: this module owns its engine (a file under ``tmp_path``, never a
bare memory URL the application's own connection could not see), installs its own ``get_db``
override, and restores both that override and ``limiter.enabled`` on teardown. It never writes
``app.database.engine`` and never calls ``os.environ.setdefault``.

The rows are seeded with ``Base.metadata.create_all`` rather than a hand-written ``CREATE
TABLE``, which is the B-15 lesson: a hand-written schema hides a NOT NULL column a real database
built from ``models.py`` cannot live without.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app, limiter
from app.models import Branch, Restaurant
from app.models import Settings as SettingsRow
from app.schemas import SettingsResponse, UpdateSettingsRequest

PATH = "/api/v1/admin/settings"
"""The one settings path: the contract's ``getSettings`` and ``updateSettings``."""

SCHEMA_KEYS = [
    "restaurant_name",
    "branch_name",
    "address",
    "phone",
    "open_time",
    "close_time",
    "hold_minutes",
    "avg_seat_minutes",
    "queue_prefix",
    "is_waitlist_open",
    "sound_enabled_default",
    "notification_templates",
    "has_pin",
]
"""The thirteen ``SettingsResponse`` fields AC-2 counts."""

TEMPLATES = {"joined": "J", "called": "C", "no_show": "N"}
"""The three-key template object AC-6 accepts."""

PIN_HASH = "$2b$12$C6UzMDcHUlM0ojszNlVJ3eKk0lQ0o0kQ0m0Q0o0kQ0m0Q0o0kQ0mO"
"""A bcrypt-shaped value standing in for a stored PIN: AC-3 forbids it in any body."""

_SCRATCH_COUNT = 0
"""Monotonic counter behind each test's database file name, so no two tests can share a file."""


@pytest.fixture()
def engine(tmp_path):
    """A fresh SQLite engine this test owns outright, schema and all."""
    global _SCRATCH_COUNT
    _SCRATCH_COUNT += 1
    test_engine = create_engine(
        f"sqlite:///{tmp_path / f'b10_{_SCRATCH_COUNT}.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture()
def db(engine):
    """A session holding the restaurant, branch and settings row the surface reads."""
    session = sessionmaker(bind=engine)()
    session.add(Restaurant(id=1, name="Sunny Bistro"))
    session.add(
        Branch(
            id=1,
            restaurant_id=1,
            name="Taipei Xinyi",
            address="No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
            phone="02-1234-5678",
            timezone="Asia/Taipei",
            business_day_cutoff_hour=4,
            open_time="11:00",
            close_time="21:00",
        )
    )
    session.add(
        SettingsRow(
            id=1,
            branch_id=1,
            hold_minutes=10,
            avg_seat_minutes=15,
            queue_prefix="A",
            is_waitlist_open=True,
            sound_enabled_default=True,
            notification_templates="{}",
            staff_pin_hash=None,
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """A client whose ``get_db`` is this test's session, limiter disabled first.

    Same discipline as the B-11 file and for the same reason: ``limiter.enabled`` goes to
    ``False`` before the ``TestClient`` is built and comes back afterwards, and the override is
    popped on the way out so no test leaves the application reading someone else's session.
    """
    previous_enabled = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)
        limiter.enabled = previous_enabled


def staff_headers() -> dict[str, str]:
    """A valid staff bearer: the environment's own secret, the auth router's own claim shape."""
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "staff",
            "role": "admin",
            "iat": now,
            "exp": now + get_settings().jwt_expire_hours * 3600,
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def error_code(response) -> str:
    """The envelope's ``error.code``, or ``<non-json>`` when the answer is not an envelope."""
    try:
        return str(((response.json() or {}).get("error") or {}).get("code"))
    except Exception:  # pragma: no cover - only a non-JSON answer takes this branch
        return "<non-json>"


def rejected_fields(response) -> object:
    """``error.details.fields`` of a 422 envelope."""
    body = response.json() or {}
    return ((body.get("error") or {}).get("details") or {}).get("fields")


def stored_settings(engine) -> SettingsRow:
    """The settings row read through a session nobody else has touched."""
    session = sessionmaker(bind=engine)()
    try:
        row = session.query(SettingsRow).first()
        session.expunge_all()
        return row
    finally:
        session.close()


def stored_branch(engine) -> Branch:
    """The branch row read through a session nobody else has touched, relationships loaded."""
    session = sessionmaker(bind=engine)()
    try:
        branch = session.query(Branch).first()
        # load the relationship hop while the session is still open
        assert branch.restaurant is not None
        session.expunge_all()
        return branch
    finally:
        session.close()


# ---------- AC-1: the surface exists, is mounted, and registers nothing else ----------


def test_settings_router_registers_get_and_patch_only():
    """``admin.router`` - the router B-10 AC-1 inspects - exposes exactly GET and PATCH on the
    settings path and no other path, while B-11's four table slots sit on the sibling router."""
    from app.routers import admin

    def paths_of(router):
        return {
            (getattr(route, "path", None), method)
            for route in router.routes
            for method in (getattr(route, "methods", None) or set())
        }

    settings_routes = paths_of(admin.router)
    assert settings_routes == {(PATH, "GET"), (PATH, "PATCH")}
    table_routes = paths_of(admin.tables_router)
    assert {path for path, _method in table_routes} == {
        "/api/v1/admin/tables",
        "/api/v1/admin/tables/{id}",
    }


def test_settings_operations_are_mounted():
    """Both operations reach the generated document, so the contract is actually served."""
    document = app.openapi()
    assert PATH in document["paths"]
    assert "get" in document["paths"][PATH]
    assert "patch" in document["paths"][PATH]


def test_settings_handlers_take_body_staff_and_db_without_depends_defaults():
    """The three-parameter shape AC-11 inspects, with no ``Depends`` default in sight."""
    from app.routers import admin

    for handler in (admin.get_admin_settings, admin.update_admin_settings):
        parameters = inspect.signature(handler).parameters
        for name in ("staff", "db"):
            assert name in parameters, f"{handler.__name__} lacks {name}"
        for name, parameter in parameters.items():
            default = parameter.default
            assert default is inspect.Parameter.empty or getattr(
                default, "dependency", None
            ) is None, f"{handler.__name__} injects {name} with a Depends default"
        if handler is admin.update_admin_settings:
            assert "body" in parameters


def test_settings_router_imports_the_shipped_request_model():
    """``admin.py`` carries the shipped model object rather than a rebinding of it (AC-5)."""
    from app.routers import admin

    assert admin.UpdateSettingsRequest is UpdateSettingsRequest


# ---------- AC-2, AC-3, AC-11: the read ----------


def test_get_settings_success(client, engine):
    """GET answers 200 with exactly the thirteen contract keys and no others (AC-2, AC-11)."""
    response = client.get(PATH, headers=staff_headers())
    assert response.status_code == 200
    body = response.json()
    assert sorted(body) == sorted(SCHEMA_KEYS)
    assert body["restaurant_name"] == "Sunny Bistro"
    assert body["branch_name"] == "Taipei Xinyi"
    assert body["address"] == "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan"
    assert body["phone"] == "02-1234-5678"
    assert (body["open_time"], body["close_time"]) == ("11:00", "21:00")
    assert body["hold_minutes"] == 10
    assert body["avg_seat_minutes"] == 15
    assert body["queue_prefix"] == "A"
    assert body["is_waitlist_open"] is True
    assert body["sound_enabled_default"] is True
    assert body["notification_templates"] == {}
    assert body["has_pin"] is False


def test_get_settings_decodes_templates_and_collapses_the_hash(client, db):
    """The stored JSON string answers as an object; the stored hash answers as one boolean."""
    db.query(SettingsRow).update({"notification_templates": json.dumps(TEMPLATES)})
    db.commit()
    body = client.get(PATH, headers=staff_headers()).json()
    assert body["notification_templates"] == TEMPLATES
    assert body["has_pin"] is False

    db.query(SettingsRow).update({"staff_pin_hash": PIN_HASH})
    db.commit()
    body = client.get(PATH, headers=staff_headers()).json()
    assert body["has_pin"] is True
    assert PIN_HASH not in response_text(body)


def response_text(body) -> str:
    """The body serialised, for the "nowhere in the body" half of AC-3."""
    return json.dumps(body)


def test_no_body_ever_carries_the_pin_hash(client, db, engine):
    """Neither answer leaks the hash, and a body that names the column cannot write it (AC-3)."""
    db.query(SettingsRow).update({"staff_pin_hash": PIN_HASH})
    db.commit()

    responses = [
        client.get(PATH, headers=staff_headers()),
        # A body that names only the PIN column: `extra="forbid"` answers it 422, and the 422
        # envelope is the other body that must not carry the column back.
        client.patch(PATH, headers=staff_headers(), json={"staff_pin_hash": "attacker-controlled"}),
        client.patch(
            PATH,
            headers=staff_headers(),
            # A PIN the seeded data cannot contain. The branch's own phone is part of
            # the response the
        # contract declares, and a PIN that happened to sit inside it would fail the leak assert
        # below for the wrong reason.
        json={"staff_pin_hash": "$2b$12$injected", "staff_pin": "9876543210"},
        ),
    ]
    for response in responses:
        # 200 for the read and for the twelve-field write, 422 for the body that names the column.
        assert response.status_code in (200, 422), response.status_code
        assert "staff_pin_hash" not in response.text
        assert PIN_HASH not in response.text
        assert "9876543210" not in response.text
        assert "attacker-controlled" not in response.text
    assert stored_settings(engine).staff_pin_hash == PIN_HASH


# ---------- AC-4, AC-10: the write ----------


def test_update_settings_success(client, engine):
    """A twelve-field PATCH stores across three tables and answers the GET shape (AC-4)."""
    body = {
        "restaurant_name": "Harbor Diner",
        "branch_name": "Kaohsiung",
        "address": "No. 9, Port Rd.",
        "phone": "07-000-0000",
        "open_time": "12:30",
        "close_time": "22:00",
        "hold_minutes": 12,
        "avg_seat_minutes": 20,
        "queue_prefix": "B",
        "is_waitlist_open": False,
        "sound_enabled_default": False,
        "notification_templates": TEMPLATES,
    }
    response = client.patch(PATH, headers=staff_headers(), json=body)
    assert response.status_code == 200
    assert sorted(response.json()) == sorted(SCHEMA_KEYS)
    assert response.json()["branch_name"] == "Kaohsiung"
    assert response.json()["restaurant_name"] == "Harbor Diner"

    row = stored_settings(engine)
    assert (row.hold_minutes, row.avg_seat_minutes, row.queue_prefix) == (12, 20, "B")
    assert row.is_waitlist_open is False
    assert row.sound_enabled_default is False
    assert json.loads(row.notification_templates) == TEMPLATES

    branch = stored_branch(engine)
    assert branch.name == "Kaohsiung"
    assert branch.address == "No. 9, Port Rd."
    assert branch.phone == "07-000-0000"
    assert (branch.open_time, branch.close_time) == ("12:30", "22:00")
    assert branch.restaurant.name == "Harbor Diner"


def test_partial_update_leaves_the_other_eleven_alone(client, engine):
    """A one-field body writes that field, keeps the rest, and never adds a row (AC-4)."""
    client.patch(
        PATH,
        headers=staff_headers(),
        json={"hold_minutes": 12, "branch_name": "Kaohsiung", "queue_prefix": "B"},
    )
    response = client.patch(PATH, headers=staff_headers(), json={"hold_minutes": 7})
    assert response.status_code == 200
    body = response.json()
    assert body["hold_minutes"] == 7
    assert body["branch_name"] == "Kaohsiung"
    assert body["queue_prefix"] == "B"
    assert body["avg_seat_minutes"] == 15
    assert body["restaurant_name"] == "Sunny Bistro"
    session = sessionmaker(bind=engine)()
    try:
        assert session.query(SettingsRow).count() == 1
    finally:
        session.close()


def test_response_carries_no_column_the_contract_omits(client):
    """``extra='forbid'`` is structural: no id, branch_id or timestamp can ride along (AC-10)."""
    body = client.get(PATH, headers=staff_headers()).json()
    for leaked in ("id", "branch_id", "created_at", "updated_at", "staff_pin_hash"):
        assert leaked not in body
    assert SettingsResponse.model_config.get("extra") == "forbid"


def test_response_survives_a_second_validation(client):
    """AC-10's no-double-validation clause: the handler's return is validated once and survives."""
    first = client.get(PATH, headers=staff_headers())
    assert first.status_code == 200
    assert SettingsResponse.model_validate(first.json()) is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("branch_id", 2),
        ("restaurant_id", 2),
        ("sound_enabled", True),
        ("id", 1),
        ("created_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_undeclared_field_is_not_written(client, engine, field, value):
    """A body naming a column the contract does not expose cannot write it (AC-3, AC-10)."""
    before = stored_settings(engine).hold_minutes
    response = client.patch(PATH, headers=staff_headers(), json={field: value})
    assert response.status_code in (200, 422)
    assert stored_settings(engine).hold_minutes == before
    if response.status_code == 422:
        assert error_code(response) == "VALIDATION_ERROR"
        assert "detail" not in response.json()


# ---------- AC-5, AC-6: the boundaries the shipped model carries ----------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hold_minutes", 4),
        ("hold_minutes", 16),
        ("avg_seat_minutes", 4),
        ("avg_seat_minutes", 61),
        ("queue_prefix", "aBC"),
        ("queue_prefix", "ABCD"),
        ("open_time", "9:30"),
        ("close_time", "9:05"),
    ],
)
def test_out_of_range_field_answers_422_in_the_envelope(client, field, value):
    """Each shipped boundary rejects with VALIDATION_ERROR and no FastAPI ``detail`` (AC-5)."""
    response = client.patch(PATH, headers=staff_headers(), json={field: value})
    assert response.status_code == 422
    assert "detail" not in response.json()
    assert error_code(response) == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "value"),
    [("hold_minutes", 15), ("avg_seat_minutes", 60), ("queue_prefix", "ABC")],
)
def test_inclusive_boundary_writes(client, field, value):
    """The endpoints of the shipped ranges store, which is what makes the rejection above a
    boundary rather than a broken validator (AC-5)."""
    response = client.patch(PATH, headers=staff_headers(), json={field: value})
    assert response.status_code == 200
    assert response.json()[field] == value


@pytest.mark.parametrize(
    "templates",
    [
        {"joined": "J"},
        {"joined": "J", "called": "C"},
        {},
        {"joined": "J", "called": "C", "no_show": "N", "extra": "E"},
        {"joined": "x" * 2000, "called": "C", "no_show": "N"},
    ],
)
def test_invalid_template_object_is_rejected_without_writing(client, engine, templates):
    """Exactly the three keys, each a string, and a rejected body leaves the store alone (AC-6)."""
    response = client.patch(
        PATH, headers=staff_headers(), json={"notification_templates": templates}
    )
    assert response.status_code == 422
    assert "detail" not in response.json()
    assert error_code(response) == "VALIDATION_ERROR"
    assert "notification_templates" in json.dumps(rejected_fields(response))
    assert stored_settings(engine).notification_templates == "{}"


def test_valid_template_object_round_trips(client, engine):
    """The three-key object stores as a JSON string and answers as an object (AC-6)."""
    response = client.patch(
        PATH, headers=staff_headers(), json={"notification_templates": TEMPLATES}
    )
    assert response.status_code == 200
    assert response.json()["notification_templates"] == TEMPLATES
    assert json.loads(stored_settings(engine).notification_templates) == TEMPLATES


# ---------- the round-2A product finding: a null-valued field is a 422, not a 500 ----------

NULLABLE_FIELDS = [
    "restaurant_name",
    "branch_name",
    "address",
    "phone",
    "open_time",
    "close_time",
    "hold_minutes",
    "avg_seat_minutes",
    "queue_prefix",
    "is_waitlist_open",
    "sound_enabled_default",
]
"""The eleven writable fields whose column ``app/models.py`` declares ``nullable=False``.

``address`` is one of them because its ``String(500)`` column carries no ``nullable`` flag either,
so the contract's bare ``type`` and the store's NOT NULL agree there.
``notification_templates`` is absent on purpose: the contract declares no ``required`` list and no
``additionalProperties: false`` for that object, so its 422 stays the service's (AC-6) rather than
being narrowed into a schema rule the contract does not carry.
"""


@pytest.mark.parametrize("field", NULLABLE_FIELDS)
def test_null_for_a_not_null_field_answers_422_not_500(client, field):
    """A body that names a NOT NULL knob with JSON null is a validation failure, not a crash.

    Round 2A recorded this for ``hold_minutes`` alone; the measurement on the base showed all
    eleven answer 500 ``INTERNAL_ERROR``, because the null passed a ``T | None`` annotation, rode
    ``exclude_unset`` into the service, and died on SQLite's NOT NULL constraint. The contract
    declares each of these as a bare type and never as nullable, so ``422`` - the response the
    operation already declares for a bad body - is the only honest answer.
    """
    response = client.patch(PATH, headers=staff_headers(), json={field: None})
    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"
    assert "detail" not in response.json()
    assert field in json.dumps(rejected_fields(response))


def test_a_null_body_writes_nothing(client, engine):
    """A rejected null cannot half-apply: a shared body leaves every knob alone (AC-6)."""
    before = stored_settings(engine).hold_minutes
    response = client.patch(
        PATH,
        headers=staff_headers(),
        json={"restaurant_name": "Renamed", "hold_minutes": None},
    )
    assert response.status_code == 422
    assert stored_settings(engine).hold_minutes == before
    assert stored_branch(engine).restaurant.name == "Sunny Bistro"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("restaurant_name", "Sunny Bistro"),
        ("branch_name", "Taipei Xinyi"),
        ("address", "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan"),
        ("phone", "02-1234-5678"),
        ("open_time", "11:00"),
        ("close_time", "21:00"),
        ("avg_seat_minutes", 15),
        ("queue_prefix", "A"),
        ("is_waitlist_open", False),
        ("sound_enabled_default", True),
        ("notification_templates", {}),
    ],
)
def test_absence_is_still_a_half_write_under_the_null_rule(client, field, value):
    """The null rule answers only a key the body NAMED, so AC-4's one-field PATCH still works.

    A ``mode="before"`` validator runs on a key that is present, which is the whole reason the
    annotations stay ``T | None``: absence has to keep meaning "leave the column alone", whatever
    the column was created with. Each field is read back at its seeded value under a body that
    names one sibling, and ``is_waitlist_open`` is closed to ``False`` first because its creation
    value is ``True`` - seeded alone it would read ``True`` however the handler behaved, so only an
    open-then-never-named sequence can catch a write that silently reopens the queue (AC-4's
    clobber arm names exactly that failure).
    """
    if field == "is_waitlist_open":
        # Close it first: the column is created True, so reading a True back would prove nothing.
        client.patch(PATH, headers=staff_headers(), json={"is_waitlist_open": False})
    response = client.patch(PATH, headers=staff_headers(), json={"hold_minutes": 9})
    assert response.status_code == 200
    assert response.json()[field] == value
    assert response.json()["hold_minutes"] == 9


def test_the_null_rule_writes_nothing_even_when_the_write_would_be_the_seed_value(client, engine):
    """The null rule is priced by the mutation, not by a value the seed happens to already hold.

    Every field the ``db`` fixture seeds is also read back at its seed value by
    ``test_partial_update_leaves_the_other_eleven_alone``, so a handler that wrote ``None`` onto a
    NOT NULL column and then answered the seeded row could satisfy an arms-only reading of that
    test. Here the field names a value no seed carries and is read back at that value, so a write
    of ``None`` has nowhere to hide: the UPDATE dies on the constraint, the commit rolls back, and
    the assertions below fail on both the response and the stored row.
    """
    response = client.patch(
        PATH, headers=staff_headers(), json={"restaurant_name": "Bistro Nine"}
    )
    assert response.status_code == 200
    assert response.json()["restaurant_name"] == "Bistro Nine"
    assert stored_branch(engine).restaurant.name == "Bistro Nine"


def test_an_empty_body_is_still_a_no_op_write(client, engine):
    """``{}`` names no field, so the null rule cannot reach it and nothing moves (AC-4)."""
    before = stored_settings(engine).hold_minutes
    response = client.patch(PATH, headers=staff_headers(), json={})
    assert response.status_code == 200
    assert response.json()["hold_minutes"] == before


def test_the_null_rule_narrows_no_bound_the_contract_prices(client, engine):
    """AC-10's control arm survives: the three UNBOUNDED bodies the contract prices still write.

    ``hold_minutes`` is the field the null rule touches and the field whose only bound is the
    ``5..15`` AC-5 pins, so it is the one a repair could silently widen. Both its endpoints and
    the unbounded string arms are re-measured here rather than assumed.
    """
    for body in (
        {"hold_minutes": 5},
        {"hold_minutes": 15},
        {"restaurant_name": ""},
        {"phone": "1" * 21},
        {"address": "x" * 201},
    ):
        response = client.patch(PATH, headers=staff_headers(), json=body)
        assert response.status_code == 200, body
    assert stored_settings(engine).hold_minutes == 15
    assert len(stored_branch(engine).address) == 201


# ---------- the null rule's own premise, read from the store rather than from a list ----------

NULL_RULE_FIELDS = [
    "restaurant_name",
    "branch_name",
    "address",
    "phone",
    "open_time",
    "close_time",
    "hold_minutes",
    "avg_seat_minutes",
    "queue_prefix",
    "is_waitlist_open",
    "sound_enabled_default",
]
"""The fields ``app.schemas`` refuses to null: every writable settings field except
``notification_templates``. The reason for the exception is a CONTRACT fact and it is written down
item 5 of ``_docs/issues/B-10.md`` - ``_docs/openapi.yaml`` declares this object with no
``required`` list and no ``additionalProperties: false``, so a ``null`` there is the one body shape
the contract genuinely leaves open, and its 422 stays the service's three-key rule (AC-6) rather
narrowed into a schema rule the contract does not carry. It is NOT a store fact: the column is
``nullable=False`` like the other eleven, so the disagreement below is deliberate, named, and
explained in both directions. The store is still read rather than restated - see
:func:`_not_null_writable_fields`, whose set is derived from ``app.models`` column by column."""

COLUMN_NULLABLE = {
    "restaurant_name": (Restaurant, "name"),
    "branch_name": (Branch, "name"),
    "address": (Branch, "address"),
    "phone": (Branch, "phone"),
    "open_time": (Branch, "open_time"),
    "close_time": (Branch, "close_time"),
    "hold_minutes": (SettingsRow, "hold_minutes"),
    "avg_seat_minutes": (SettingsRow, "avg_seat_minutes"),
    "queue_prefix": (SettingsRow, "queue_prefix"),
    "is_waitlist_open": (SettingsRow, "is_waitlist_open"),
    "sound_enabled_default": (SettingsRow, "sound_enabled_default"),
    "notification_templates": (SettingsRow, "notification_templates"),
}
"""Where each writable field actually lands, read from ``app.models`` rather than restated."""

CONTRACT_NULLABLE_EXCEPTION: set[str] = {"notification_templates"}
"""The one field the contract leaves nullable although its column is NOT NULL.

The single deliberate disagreement this module tolerates, named here so a second one has to be added
to this literal and argued for, rather than appearing as a set difference nobody reads.
"""

CONTRACT_YAML = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "_docs", "openapi.yaml")
)
"""The contract file, from the test's own location - never from the caller's working directory."""


def _not_null_writable_fields() -> set[str]:
    """The writable settings fields whose column ``app.models`` says cannot hold null.

    Derived from the table metadata rather than typed out, so a column that gains or loses a
    ``nullable`` flag moves this set on its own.
    """
    return {
        field
        for field, (model, column) in COLUMN_NULLABLE.items()
        if not model.__table__.columns[column].nullable
    }


def _null_rule_fields() -> list[str]:
    """The field names the shipped null rule carries, read out of the model's own validators.

    The lookup is positional rather than by name, so a rename cannot make it read nothing: the
    rule is the only ``mode="before"`` field validator this model declares, and the assertion
    below prices the search itself, because a helper that returns ``[]`` can never satisfy it.
    A field validator's declared fields are a tuple in ``validator.info``, not an attribute of the
    decorator itself - the first version of this helper reached for the wrong object and read
    nothing at all, which is the silent-green shape this module exists to avoid.
    """
    rules = [
        sorted(validator.info.fields)
        for validator in UpdateSettingsRequest.__pydantic_decorators__.field_validators.values()
        if validator.info.mode == "before"
    ]
    assert len(rules) == 1, (
        "this helper identifies the null rule by being the model's only before-validator, and "
        "there are now " + str(len(rules)) + ": " + str(rules)
    )
    return rules[0]


def test_the_null_rule_covers_exactly_the_columns_that_cannot_hold_null():
    """The rule and the store agree, field by field, and neither is taken on trust.

    A schema-level null rule has one failure mode no behavioural test catches: a twelfth writable
    field is added to the contract, nobody adds it to the validator's list, and its null answers 500
    again - which is the exact defect this round fixed, re-made as an omission. This test is the
    mechanical half of that: it reads each field's column from ``app.models``, reads the names the
    shipped validator carries, and fails if the two sets have drifted. The one allowed disagreement
    is ``notification_templates`` - NOT NULL in the store, absent from the rule, for the contract
    reason spelled out on :data:`NULL_RULE_FIELDS` - so a second exception has to be a decision
    recorded in both places rather than an oversight in one.
    """
    rule = _null_rule_fields()
    assert rule == sorted(NULL_RULE_FIELDS), "the text list above is no longer the shipped rule"
    not_null = _not_null_writable_fields()
    # Twelve writable fields, twelve NOT NULL columns: no store-level exception exists, so a field
    # that leaves this set has changed nullability and every premise in item 5 needs re-reading.
    assert not_null == set(COLUMN_NULLABLE), (
        "a settings column became nullable, or a column left the map: "
        + str(sorted(set(COLUMN_NULLABLE) ^ not_null))
    )
    assert rule == sorted(not_null - CONTRACT_NULLABLE_EXCEPTION), (
        "the null rule and the NOT NULL columns have drifted: "
        + "rule=" + str(rule) + " columns=" + str(sorted(not_null))
    )
    assert not {
        field
        for field, (model, column) in COLUMN_NULLABLE.items()
        if model.__table__.columns[column].primary_key
    }, "a writable settings field is a primary key, which no contract entry can mean"


@pytest.mark.parametrize("field", sorted(COLUMN_NULLABLE))
def test_every_writable_field_is_named_by_the_contract_and_the_model(field):
    """Nothing writable is invisible: contract file, generated schema and model all name it.

    The set this arm walks is derived from ``app.models`` through ``COLUMN_NULLABLE``, so a field
    the contract declares but no test names is caught by the map growing, not by a sentence.
    """
    assert field in UpdateSettingsRequest.model_fields, "the request model dropped " + field
    props = UpdateSettingsRequest.model_json_schema()["properties"]
    assert field in props, "the generated document dropped " + field
    with open(CONTRACT_YAML, encoding="utf-8") as handle:
        raw = handle.read()
    start = raw.index("    UpdateSettingsRequest:")
    nxt = re.compile(r"^    [A-Za-z][A-Za-z0-9]*:$", re.M).search(raw, start + 1)
    section = raw[start : nxt.start() if nxt else len(raw)]
    declared = set(re.findall(r"^        ([a-z_]+):$", section, re.M))
    assert field in declared, "_docs/openapi.yaml declares no " + field + " property there"
    assert sorted(declared) == sorted(UpdateSettingsRequest.model_fields), (
        "the contract file and the generated model name different properties: "
        + str(sorted(declared ^ set(UpdateSettingsRequest.model_fields)))
    )


# ---------- AC-9: auth ----------


@pytest.mark.parametrize(
    "header",
    [
        {},
        {"Authorization": "Bearer nope"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
    ],
)
def test_missing_or_unusable_bearer_answers_401(client, header):
    """Both operations reject an absent or unusable bearer with the shipped 401 code (AC-9)."""
    for response in (
        client.get(PATH, headers=header),
        client.patch(PATH, headers=header, json={"hold_minutes": 11}),
    ):
        assert response.status_code == 401
        assert error_code(response) == "AUTH_TOKEN_EXPIRED"
        assert sorted(response.json().get("error") or {}) == ["code", "message"]


# ---------- AC-13: the settings surface carries no budget of its own
#
# AC-13 asks two things, and this file asserts the half that belongs to this module plus the
# regression that keeps the other half honest. The first is textual: ``app/routers/admin.py``
# registers no budget of its own, asserted below from the module text. The second is behavioural -
# two hundred logged calls to the settings path answer no 429 while the guest budget is switched on
# - and it is a property of the shared component in ``app/main.py``, which now takes this pair out
# of its own ``default_limits`` budget (``exempt_surface``, beside the limiter that owns the
# default). What is asserted below is that decision and its cost: the exemption is filed for both
# handlers and for nothing else, a burst on the settings path never reaches a 429, an exempt
# response survives the limiter's own headers flag being switched on, and the guest budgets section
# 9 does name keep counting exactly as B-06 AC-14 measured them.
#
# Two facts about the mechanism belong to this comment rather than to a test, because both are
# decisions and neither is measurable from here. An entry in ``Limiter._route_limits`` with
# ``override_defaults=True`` was tried first and rejected: it routes the request to
# ``_application_limits``, which this process leaves empty, so the middleware stops pricing the
# named surface without the exemption ever being visible in a registry - the state AC-13's own
# failure text calls out. And the exempt branch of the library's check returns without pricing and
# without recording, so with ``headers_enabled`` switched on for a deployment, the first exempt
# response has no budget record for the header injection to read and answers 500. That flag is off
# here and off on the library's own constructor; the test that names it is kept as the measured
# boundary of this repair rather than as a comment about a flag.
#
# What no test here can assert is that AC-13's burst reaches the two real handlers. The library
# resolves a request against the application's TOP-LEVEL route list and takes the last full match,
# and ``include_router`` appends a container rather than the routes themselves, so a request that
# some probe's hand-appended route answers is priced for that probe's handler. With such a route
# registered at this path, the middleware named the probe's handler on all two hundred requests and
# answered 429 on the eleventh; with the two real routes answering, the same burst answered 200 two
# hundred times. Both numbers are recorded in ``_docs/issues/B-10.md``, and the reason no product
# change reaches the first is stated where the exemption is made.


def test_settings_half_of_the_router_names_no_limiter():
    """The settings half of the router registers no budget of its own (AC-13).

    AC-13 reads ``app/routers/admin.py`` as plain text and fails it for carrying a budget, and the
    obvious way to satisfy the AC while failing its intent is a decorator that prices the surface
    somewhere other than here - so the search runs over the whole module rather than stopping at a
    marker. The module also holds B-11's four table operations below the settings ones, and a slice
    that stopped at a marker would leave that half unexamined: a budget on a table route would be
    reported as clean.

    This is the AC's own arm, and it is deliberately the only textual one. What the exemption that
    does exist is filed against is a request-and-response fact and belongs to the two tests below
    that make requests; a green assertion over a registry, on the other hand, is only worth anything
    when the registry has the last word - which ``_route_limits`` does not, and which
    ``_exempt_routes`` does.
    """
    from app.routers import admin

    source = inspect.getsource(admin)
    assert "limiter" not in source, "app/routers/admin.py applies a limiter decorator of its own"
    assert "shared_limit" not in source


def test_the_settings_pair_is_filed_as_exempt_and_nothing_else_is():
    """Both settings handlers are exempt from the guest budget, and the registry holds nothing more.

    AC-13 is a request-and-response fact, and a registry is not that fact. It is, however, the half
    of the fact that ``app/main.py`` can assert at import: ``exempt_surface`` files a handler by the
    ``module.name`` spelling the library's resolver derives, and it asserts the filing rather than
    trusting the call. This test is the same promise from the outside, so a call quietly deleted
    from ``app/main.py`` - or a third operation filed alongside the pair - fails here too.

    The exact-set comparison is the point. A membership check would read green while the exemption
    widened, and ``app/routers/admin.py`` may not name a limiter at all, so every entry in this
    registry is a decision made in the module that owns the default. The contract enumerates exactly
    two operations on this surface, and so does the registry.
    """
    from app.routers import admin

    names = {
        f"{handler.__module__}.{handler.__name__}"
        for handler in (admin.get_admin_settings, admin.update_admin_settings)
    }
    assert names == {
        "app.routers.admin.get_admin_settings",
        "app.routers.admin.update_admin_settings",
    }, f"the handlers moved, so the exemption no longer names them: {sorted(names)}"
    exempt = set(limiter._exempt_routes)  # noqa: SLF001 - the registry app/main.py asserts on
    assert names <= exempt, f"the admin settings pair is not filed as exempt: {sorted(exempt)}"
    assert exempt == names, f"the exemption widened past the settings pair: {sorted(exempt)}"


def test_the_settings_surface_outlives_the_guest_budget_it_leaves(client, db):
    """AC-13's own arm, run against the handlers the surface actually ships.

    The budget in ``app/main.py`` is ten requests a minute, so eleven logged calls are enough to see
    whether a surface is inside it. Twenty are sent: the pair answers 200 twenty times on both
    verbs, which is the fact AC-13 states. Twenty rather than the AC's two hundred is a test-runtime
    budget and not a weaker claim - the 429 arrived on the eleventh call every single time this was
    measured on either side of the exemption, and a burst that survives eleven survives two hundred.

    ``limiter.reset()`` is load-bearing rather than hygienic: the storage is shared by every test in
    this suite that switches the budget on, and without it the first request here could arrive on a
    counter a previous test had already filled to ten.
    """
    limiter.reset()
    previous = limiter.enabled
    limiter.enabled = True
    try:
        seen: dict[int, int] = {}
        for _ in range(20):
            response = client.get(PATH, headers=staff_headers())
            seen[response.status_code] = seen.get(response.status_code, 0) + 1
        assert seen == {200: 20}, seen
        patched: dict[int, int] = {}
        for _ in range(20):
            response = client.patch(PATH, headers=staff_headers(), json={"hold_minutes": 11})
            patched[response.status_code] = patched.get(response.status_code, 0) + 1
        assert patched == {200: 20}, patched
    finally:
        limiter.enabled = previous


def test_the_settings_surface_survives_the_headers_flag_being_switched_on(client, db):
    """An exempt request has no budget record, and the limiter's headers ask for one.

    ``headers_enabled`` is off in ``app/main.py`` and off on the library's own constructor, so the
    only way this fails is someone switching it on for a deployment - at which point the middleware
    starts reading back which budget applied to a response, and a request that no budget was ever
    applied to has no such record to read. Kept because it is the measured boundary of this repair:
    it is the seam that breaks first if the exemption is ever re-implemented as something that
    declines the budget without announcing the handler, and it is one line of behaviour rather than
    a paragraph of comment about a flag.
    """
    previous = limiter._headers_enabled  # noqa: SLF001 - the flag this test is about
    limiter._headers_enabled = True  # noqa: SLF001
    limiter.enabled = True
    try:
        assert client.get(PATH, headers=staff_headers()).status_code == 200
    finally:
        limiter._headers_enabled = previous  # noqa: SLF001
        limiter.enabled = False


def test_the_settings_exemption_reaches_the_counters_the_contract_names(client, db):
    """The pair leaves the budget, and no counter the contract budgets notices that it left.

    AC-13's second arm and B-06's AC-14 are the same measurement read from opposite sides of one
    shared object, which is why they are asserted in one test rather than in two files: the guest
    budget is ``app.state.limiter``, its storage is keyed by handler and scope rather than by
    process, and the only way the settings exemption could be innocent is if a burst on the lookup
    still stopped on the eleventh call after the settings pair had absorbed a burst of its own. The
    eleventh-call boundary is B-06 AC-14's, quoted verbatim, and the settings burst above it is
    AC-13's.

    The lookup needs a row to read, and it is addressed through the settings row this module owns:
    the lookup handler reads that row for the notification templates before it reports on the
    entry, so a surface without one answers 500 and never reaches the counter the budget counts.
    The branch this fixture seeds is open, and the queue row is written through the same session the
    application is being served from.
    """
    from app.models import WaitlistEntry

    db.add(
        WaitlistEntry(
            branch_id=1,
            queue_number="A013",
            full_queue_number="A-20260910-013",
            queue_prefix="A",
            seq=13,
            business_date=time.strftime("%Y-%m-%d"),
            name="Exemption",
            phone="0900000013",
            party_size=2,
            status="WAITING",
            sort_order=13,
            source="CUSTOMER",
        )
    )
    db.commit()
    limiter.reset()
    previous = limiter.enabled
    limiter.enabled = True
    try:
        for _ in range(20):
            assert client.get(PATH, headers=staff_headers()).status_code == 200
        lookups = [
            client.get("/api/v1/waitlist/A013", params={"phone_last3": "013"}).status_code
            for _ in range(11)
        ]
        assert lookups[:10] == [200] * 10, lookups
        assert lookups[10] == 429, lookups
        limited = client.get("/api/v1/waitlist/A013", params={"phone_last3": "013"})
        assert error_code(limited) == "RATE_LIMITED", limited.text
        assert client.get(PATH, headers=staff_headers()).status_code == 200
    finally:
        limiter.enabled = previous


def test_the_guest_budget_is_not_widened_by_the_staff_exclusion(client, db):
    """The exclusion is a statement about two paths, and every other path is priced as before.

    AC-13 says nothing about the guest surfaces, and the most likely way to satisfy it is the one
    that
    breaks them: a filter, exemption or bypass wide enough to stop counting things other than the
    settings screen. Login is measured here rather than in the auth suite because the change that
    could
    break it lives in ``app/main.py``, and B-05 AC-6's five-attempt budget is the one budget in this
    application that the middleware enforces directly, with no wrapper of its own to notice.
    """
    limiter.reset()
    previous = limiter.enabled
    limiter.enabled = True
    try:
        probe = TestClient(app, raise_server_exceptions=False)
        codes = [probe.post("/api/v1/auth/login", json={"pin": "9999"}).status_code for _ in
        range(6)]
    finally:
        limiter.enabled = previous
    assert 401 in codes[:5], codes
    assert codes[5] == 429, codes


def test_the_staff_surface_is_not_limited(client, db):
    """Regression on the other side of the line AC-13 draws.

    Narrowing the guest budget to the paths section 9 names must not un-price them. Login keeps its
    five attempts per minute on the shared instance - five 401s for a wrong PIN, then 429 - which is
    the budget this application enforces through the middleware alone, so it is the one that would
    disappear first if the narrowing ever widened to "nothing is limited". The assertion is B-05
    AC-6's, held here because the change that could break it lives in ``app/main.py`` and this is
    the
    suite that exercises that file's budget shape.

    The two fixtures on the signature are load-bearing and were added when this test started failing
    for the wrong reason. Login reads the PIN off the settings row, so the request needs a schema
    and
    a row to read: without them the handler raises, the error handler answers 500, and no 401 ever
    reaches the counter the budget is counting. The five failures then read as a budget that stopped
    working when the opposite is true - the burst still trips on the sixth call, and what it tripped
    over was five 500s. ``client`` is the app with ``get_db`` pointed at this module's engine and
    ``db`` is the seeded restaurant, branch and settings row, which is what the login handler needs
    and what every other test in this file already asks for.
    """
    limiter.reset()
    previous = limiter.enabled
    limiter.enabled = True
    try:
        codes = [client.post("/api/v1/auth/login", json={"pin": "9999"}).status_code for _ in
        range(6)]
    finally:
        limiter.enabled = previous
    assert codes[5] == 429, codes
    assert 401 in codes[:5], codes
