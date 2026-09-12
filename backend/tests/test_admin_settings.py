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
# AC-13 asks two things, and only one of them is a property of this module. The first - that
# ``app/routers/admin.py`` registers no budget of its own - is asserted below from the module text,
# and it holds. The second - that two hundred logged calls to the settings path answer no 429 with
# the guest budget switched on - is a property of the shared component in ``app/main.py``, and on
# this branch it does NOT hold: ``app/main.py`` builds the limiter with a ``default_limits`` value,
# and at this lock (slowapi 0.1.10, ``key_style="url"``) a default prices every request whose
# handler carries no per-route entry of its own, which is exactly what the first half enforces here.
#
# Three ways out were built on this branch and measured, and none of them was green:
#   * ``Limiter.exempt(handler)`` files the handler's dotted name, but the same call prices by path
#     at ``key_style="url"``, so nothing matches and the eleventh refresh is a 429.
#   * an entry in ``Limiter._route_limits`` is consulted by the per-route check and not by the
#     middleware, which assembles what it applies without reading that table; once the middleware is
#     told to skip the surface it reads back which budget applied in order to price the response
#     headers, and no record exists for a request it never measured - the refresh answers 500 on the
#     way out of having been served correctly.
#   * a request filter does decline the default, and hits that same header wall, because the flag
#     that declines is process-wide rather than per path.
# The two doors that would keep the middleware quiet instead - ``headers_enabled`` off for the
# process, or ``default_limits`` narrowed to the paths section 9 names - each take a budget away
# from B-05's login or B-06's four guest counters, whose green tests are this repository's own. So
# the exclusion is a decision for the owner of that component rather than a fact this branch can
# earn, and what is asserted here is the half that is this module's to hold. The measured record of
# all three doors is in ``_docs/issues/B-10.md``.
#
# What the two tests below that DO make requests therefore show, read together, is the boundary of
# the defect rather than its repair: a burst against the guest login is priced, and the settings
# surface is priced by the same default and reaches no 429 only because nothing here measures it to
# the tenth call and past. ----------


def test_settings_half_of_the_router_names_no_limiter():
    """The settings half of the router registers no budget of its own (AC-13).

    AC-13 reads ``app/routers/admin.py`` as plain text and fails it for carrying a budget, and the
    obvious way to satisfy the AC while failing its intent is a decorator that prices the surface
    somewhere other than here - so the search runs over the whole module rather than stopping at a
    marker. The module also holds B-11's four table operations below the settings ones, and a slice
    that stopped at a marker would leave that half unexamined: a budget on a table route would be
    reported as clean.

    Deliberately absent is any assertion about the shared budget's registry, which an earlier
    revision
    of this file carried. It asserted that the surface's two operations are filed in
    ``limiter._route_limits`` under exactly the names the meter derives for them - a structural
    claim
    that reads well and is false in a way nobody reading the test could see, because filing an entry
    does not take a surface out of a ``default_limits`` budget at this lock: the middleware
    assembles
    the limits it applies without consulting that table when no entry matches, and an entry that
    does
    match is handed to a code path that then reads a request attribute it never set. A green
    assertion
    over a registry that has no say is the worst kind of green, and the mechanism it described is
    gone
    from this branch. What AC-13 measures is two hundred calls answering no 429 - a
    request-and-response fact - and that half belongs to
    ``test_the_settings_surface_is_priced_by_nothing_of_its_own`` below.
    """
    from app.routers import admin

    source = inspect.getsource(admin)
    assert "limiter" not in source, "app/routers/admin.py applies a limiter decorator of its own"
    assert "shared_limit" not in source


def test_settings_surface_answers_200_two_hundred_times(client, db):
    """Two hundred logged GETs answer no 429 with the limiter switched off (AC-13, half of it).

    The AC's own 200-call run is with the guest budget ENABLED, and that run is red on this branch
    for the reason named in the banner above; asserting 200 here with the budget disabled is the
    half that is this module's - the pair answers, and answers 200, and the 429 the AC expects to be
    absent is not coming from anything declared in ``app/routers/admin.py``. The enabled run is left
    red rather than written as a passing test, because a test that switches the budget off and then
    reports the budget off is exactly the green that AC-13 exists to refuse.
    """
    limiter.reset()
    assert limiter.enabled is False, "this run measures the surface, not the budget"
    seen: dict[int, int] = {}
    for _ in range(200):
        response = client.get(PATH, headers=staff_headers())
        seen[response.status_code] = seen.get(response.status_code, 0) + 1
    assert seen == {200: 200}, seen


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


def test_the_staff_surface_survives_the_headers_flag_being_switched_on(client, db):
    """A declined request has no budget record, and the limiter's headers ask for one.

    Kept although this branch declines nothing: it is the measurement that says why a request filter
    is not a free answer to AC-13 at this lock, and it is one line of behaviour rather than a
    paragraph of comment.

    ``headers_enabled`` is off in ``app/main.py`` and off on the library's own constructor, so the
    only
    way this fails is someone switching it on for a deployment - at which point the middleware
    starts
    reading back which budget applied to a response, and a request that no budget was ever applied
    to
    has no such record to read. The assertion is deliberately on the status code rather than on the
    flag: a flag asserted off is a comment, and a screen that answers 200 with the flag on is a
    behaviour, which is the thing the comment above that flag is trying to protect.
    """
    previous = limiter._headers_enabled  # noqa: SLF001 - the flag this test is about
    limiter._headers_enabled = True  # noqa: SLF001
    limiter.enabled = True
    try:
        assert client.get(PATH, headers=staff_headers()).status_code == 200
    finally:
        limiter._headers_enabled = previous  # noqa: SLF001
        limiter.enabled = False


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
