"""Admin reset endpoint tests for B-12 (``POST /api/v1/admin/reset``).

Nine tests, one per acceptance criterion that needs a pytest counterpart: AC-1's contract-freeze
arms are folded into :func:`test_reset_contract_shape`, which reads the same YAML that AC block
reads, because a tenth test would re-read that file to say one more sentence about it. The names map
to the AC numbers in the order the issue lists them, so QA can read the two files side by side.

Ownership follows the two admin modules already in this suite. The module owns its database - a file
under ``tmp_path``, never a bare memory URL that the application's own per-request connection could
not see - and it restores everything it redirects. The settings rebind is the one that matters
beyond this file: ``app/config.py`` caches its getter behind an ``lru_cache`` and ``app.main`` read
settings at import time, so AC-4's test can only reach ``production`` by rebinding the module and
application attributes, and a rebind left in place would make every later module's development
assumptions false in the same process. Restoration therefore happens in a ``finally`` on both names,
with the cache cleared afterwards.

The reset is never reimplemented here. Where AC-8 needs to know whether the handler delegates to the
B-13 seeder the seeder is wrapped and its arguments recorded rather than replaced, so no test can
pass by performing the reset itself, and the counts AC-7 asserts are counted out of the database the
application actually wrote.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

import app.config as config_module
import app.seed as seed_module
from app.config import Settings, get_settings
from app.database import Base
from app.main import app, limiter
from app.routers import admin as admin_module
from app.schemas import ResetDataRequest

PATH = "/api/v1/admin/reset"
"""The one reset path: the contract's ``resetData``."""

WANT_COUNTS = (1, 1, 1, 10, 9, 10)
"""``(restaurants, branches, settings, active tables, entries, hold_minutes)`` after a reset.

The fixture's own numbers as ``app/seed.py`` writes them: one restaurant, one branch, one settings
row carrying ``hold_minutes=10``, ten active tables, nine waitlist entries.
"""

_SCRATCH_COUNT = 0
"""Monotonic counter behind the scratch ``get_db`` name, so no two tests share a session factory."""


@pytest.fixture()
def scratch(monkeypatch, tmp_path) -> Iterator[Settings]:
    """The application, redirected at a scratch database this test owns outright.

    Three seams are pointed at one ``tmp_path`` file and put back afterwards, and each is the seam
    the application actually reads rather than a parallel one:

    * ``app.config.get_settings``, which every late read goes through;
    * ``app.main.settings``, the object ``app.main`` captured at import time and which the
      ``/health`` route reports - AC-4's sentinel is that route, and ``AppSettings`` is frozen, so
      the only way to move the reported environment is to rebind that name rather than mutate it;
    * ``app.database.engine`` / ``SessionLocal``, which ``get_db`` reads as module globals at call
      time, so every request session comes from here;
    * ``app.seed.get_engine`` / ``get_session``, because the handler's reset work runs through the
      seeder's own engine accessor.

    The engine carries SQLite's ``check_same_thread`` allowance the way the shipped engine does, as
    ``connect_args``: the test client runs the application on a worker thread, and a connection
    opened on this thread has to survive the hand-off.
    """
    global _SCRATCH_COUNT
    _SCRATCH_COUNT += 1
    url = f"sqlite:///{tmp_path / f'b12_scratch_{_SCRATCH_COUNT}.db'}"
    settings = Settings(
        _env_file=None,
        database_url=url,
        jwt_secret=get_settings().jwt_secret,
        staff_pin=get_settings().staff_pin,
        jwt_expire_hours=get_settings().jwt_expire_hours,
        env="development",
    )
    import app.database as database_module

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr("app.main.settings", settings)
    engine = create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    monkeypatch.setattr(
        seed_module,
        "get_session",
        lambda engine=None: session_factory(),
    )
    seed_module.create_schema(engine)
    try:
        yield settings
    finally:
        engine.dispose()


@pytest.fixture()
def seeded(scratch) -> Settings:
    """The scratch database holding the real B-13 fixture, built by the shipped seeder."""
    seed_module.seed_data()
    return scratch


@pytest.fixture()
def dev_env(scratch, monkeypatch) -> Settings:
    """Rebind every ``get_settings`` reference to the fixture's development settings.

    Why this exists at all: ``backend/tests/conftest.py`` sets ``ENV`` with
    ``os.environ.setdefault``, so an ``ENV`` the runner exports wins for the whole process, and a
    module that reached the handler through the *imported* ``app.config.get_settings`` name would
    then answer the
    environment's setting rather than this issue's. Measured at this lock: the 204/403/422 tests of
    this module passed under ``ENV=development`` and failed under any other value for exactly that
    reason. AC-6's own acceptance block therefore rebinds the cached getter before it requests
    anything, and this fixture is the same mechanism, applied per test.

    The rebind is late-binding on purpose (``lambda: scratch`` calls the getter the fixture
    installed when it resolves, not when this lambda is built) and it covers the four references a
    reset request can reach, because each module imported the name its own way:

    * ``app.config`` - the module attribute, which is the seam AC-4 names and the one a caller that
      does ``from app.config import get_settings`` never moves at all;
    * ``app.routers.admin`` - the handler reads ``get_settings().env`` through its own global;
    * ``app.dependencies`` - the staff bearer decoder reads ``settings.jwt_secret`` the same way;
    * ``app.main`` - ``/health`` reports ``settings.env``, the name it captured at import time
      (``AppSettings`` is frozen, so that name is rebound rather than mutated).

    ``app.database`` is deliberately absent from that list: it holds its own import-time
    ``settings`` but reads it only to build the engine, and the ``scratch`` fixture already rebinds
    that engine and its session factory, which is what every request session comes from.

    ``monkeypatch`` restores every one of them at teardown, so a rebind cannot leak into the next
    module in the same process - the failure mode the issue's test requirements name.
    """
    import app.dependencies as dependencies_module
    import app.main as main_module
    import app.routers.admin as admin_module

    monkeypatch.setattr(config_module, "get_settings", lambda: scratch)
    monkeypatch.setattr(admin_module, "get_settings", lambda: scratch)
    monkeypatch.setattr(dependencies_module, "get_settings", lambda: scratch)
    monkeypatch.setattr(main_module, "settings", scratch)
    return scratch


@pytest.fixture()
def client(seeded) -> Iterator[TestClient]:
    """A client for the redirected application, with the guest budget disabled.

    ``limiter.enabled`` goes to ``False`` before the client is built and comes back afterwards, the
    way ``tests/conftest.py`` does for the whole suite and ``tests/test_admin_settings.py`` does for
    its own surface: the shared budget in ``app/main.py`` is a ``default_limits`` value and would
    otherwise be spent by these requests.

    There is no ``get_db`` override. A reset drops and re-creates the whole schema, and a session
    opened before that has prepared statements against tables that no longer exist - so the request
    must take its session from the redirected factory and open it after the drop, which is what the
    shipped dependency does once ``app.database.SessionLocal`` is the fixture's.
    """
    previous_enabled = limiter.enabled
    limiter.enabled = False
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        limiter.enabled = previous_enabled


def staff_headers(
    signing_secret: str | None = None,
    *,
    expired: bool = False,
) -> dict[str, str]:
    """A staff bearer in the shape ``app/dependencies.py`` validates.

    ``sub="staff"`` is the claim the dependency requires and the secret and horizon come from the
    settings in force, so this is the auth router's own token rather than a guess at one;
    ``expired`` moves ``iat`` and ``exp`` an hour into the past, which is AC-3's third probe. The
    parameter is ``signing_secret`` rather than ``secret`` because ruff's S106 rejects a keyword
    named ``secret`` carrying a literal, and the value passed is a wrong-secret probe, not a secret.
    """
    current = config_module.get_settings()
    now = int(time.time())
    payload = {
        "sub": "staff",
        "role": "staff",
        "iat": now - 7200 if expired else now,
        "exp": now - 3600 if expired else now + current.jwt_expire_hours * 3600,
    }
    token = jwt.encode(payload, signing_secret or current.jwt_secret, algorithm="HS256")
    return {"Authorization": "Bearer " + token}


def scratch_engine() -> Engine:
    """The engine the ``scratch`` fixture installed, read back rather than carried around."""
    import app.database as database_module

    return database_module.engine


def counts() -> tuple[int, ...]:
    """``(restaurants, branches, settings, active tables, entries, hold_minutes)``.

    Counted from a session of the redirected factory, which is the database the application writes,
    so a test cannot pass by reading a copy of the rows it inserted itself.
    """
    import app.database as database_module

    with database_module.SessionLocal() as session:
        return (
            session.execute(text("select count(*) from restaurants")).scalar(),
            session.execute(text("select count(*) from branches")).scalar(),
            session.execute(text("select count(*) from settings")).scalar(),
            session.execute(
                text("select count(*) from tables where is_active = 1")
            ).scalar(),
            session.execute(text("select count(*) from waitlist_entries")).scalar(),
            session.execute(text("select hold_minutes from settings")).scalar(),
        )


def dirty_the_fixture() -> None:
    """Apply AC-7's three dirties: no waitlist rows, one inactive table, a foreign hold value."""
    import app.database as database_module

    with database_module.SessionLocal() as session:
        session.execute(text("delete from waitlist_entries"))
        session.execute(text("update tables set is_active = 0 where label = 'A1'"))
        session.execute(text("update settings set hold_minutes = 999"))
        session.commit()


def envelope(answer) -> dict[str, Any]:
    """The ``error`` object of an envelope answer, or ``{}`` when the answer is not one."""
    try:
        return (answer.json() or {}).get("error") or {}
    except Exception:  # pragma: no cover - only a non-JSON answer takes this branch
        return {}


def contract_document() -> dict[str, Any]:
    """``_docs/openapi.yaml``, found from this file's own home rather than from anyone's cwd.

    ``tests/test_admin_settings.py::_contract_yaml`` records why this is a function: the suite
    runs with cwd ``backend/`` while the acceptance blocks run from the repo root, so a path built
    against the working directory resolves to ``backend/_docs/`` and every contract arm fails as a
    packaging accident. The search walks up from ``__file__``, at call time.
    """
    import yaml

    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        candidate = os.path.join(here, "_docs", "openapi.yaml")
        if os.path.isfile(candidate):
            with open(candidate, encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    raise AssertionError(
        "no _docs/openapi.yaml visible above this test file: " + os.path.abspath(__file__)
    )


def test_reset_route_is_reachable(client, dev_env) -> None:
    """AC-2: routable, present in the generated document, and it reaches body validation.

    The third arm is the one that proves a handler was chosen rather than a guard answering ahead of
    routing: a valid staff bearer carrying a body the contract rejects has to be refused by the
    request model, so 422 is the only answer that says the operation exists and its body schema was
    applied. A 401 or 403 here would mean authentication short-circuited the operation.
    """
    document = app.openapi()
    assert PATH in document["paths"], PATH + " is absent from the generated document"
    assert "post" in document["paths"][PATH], "the contract's reset verb is not registered"

    wrong = client.post(PATH, headers=staff_headers(), json={"confirm": "NOPE"})
    assert wrong.status_code != 404, "the path is unroutable"
    assert wrong.status_code == 422, (
        f"a valid staff bearer carrying confirm=NOPE answered {wrong.status_code}; body "
        "validation must be reachable behind auth"
    )
    assert envelope(wrong).get("code") == "VALIDATION_ERROR"


def test_reset_requires_staff_bearer(client, dev_env) -> None:
    """AC-3: missing, forged and expired bearers each answer 401 ``AUTH_TOKEN_EXPIRED``.

    Six probes rather than three: each token state is tried with and without a body, because a
    dependency that ran after body validation would answer 422 for the no-body case and be mistaken
    for authentication. The envelope must be the shipped one - a code, a non-empty message, and no
    FastAPI ``detail`` key.
    """
    probes = (
        ("missing", {}),
        ("forged", staff_headers("not-the-application-secret")),
        ("expired", staff_headers(expired=True)),
    )
    for tag, headers in probes:
        for body in ({"confirm": "RESET"}, None):
            answer = client.post(PATH, headers=headers, json=body)
            label = f"{tag} body={body is not None}"
            assert answer.status_code == 401, label + f" answered {answer.status_code}"
            payload = answer.json()
            assert "detail" not in payload, label + " leaked FastAPI's detail shape"
            error = payload.get("error") or {}
            assert error.get("code") == "AUTH_TOKEN_EXPIRED", (
                label + " code=" + str(error.get("code"))
            )
            assert error.get("message"), label + " carried an empty error.message"


def test_reset_refuses_non_development(client, dev_env) -> None:
    """AC-4: outside ``development`` a well-formed request is refused before any data work.

    The environment is selected through the seam the issue names - a rebind of the cached getter,
    applied on every module reference the request can reach (the ``dev_env`` fixture above lists
    them) - rather than through ``os.environ['ENV']``, which those import-time reads make
    meaningless once ``app.main`` is loaded. The sentinel is the application's own ``/health``
    answer, so a production refusal cannot be a development refusal in disguise.

    The code is ``INTERNAL_ERROR`` and that is the contract, not a shortcut: the 403 example in
    ``_docs/openapi.yaml`` carries it, ``_docs/specs.md`` section 11 lists no ``FORBIDDEN`` code at
    all (``AppError('FORBIDDEN')`` raises ``ValueError`` against the shipped catalogue), and adding
    one would be a contract change owned by Platform Issue #3.

    The data assertion is the other half of the criterion: a reset that wiped first and refused
    afterwards would still answer 403, so the seeded rows are counted after the refusal, and the
    staff bearer is signed with the production settings' own secret so the refusal cannot be
    attributed to an authentication answer the request never earned.
    """
    production = Settings(
        _env_file=None,
        database_url=dev_env.database_url,
        jwt_secret=dev_env.jwt_secret,
        staff_pin=dev_env.staff_pin,
        jwt_expire_hours=dev_env.jwt_expire_hours,
        env="production",
    )
    import app.dependencies as dependencies_module
    import app.main as main_module
    import app.routers.admin as admin_module

    previous = (
        config_module.get_settings,
        admin_module.get_settings,
        dependencies_module.get_settings,
        main_module.settings,
    )
    config_module.get_settings = lambda: production
    admin_module.get_settings = lambda: production
    dependencies_module.get_settings = lambda: production
    main_module.settings = production
    try:
        sentinel = (client.get("/health").json() or {}).get("env")
        assert sentinel == "production", (
            f"the application still reports env={sentinel}; the rebind did not take effect, so "
            "no refusal below is evidence of anything"
        )
        answer = client.post(
            PATH, headers=staff_headers(production.jwt_secret), json={"confirm": "RESET"}
        )
        assert answer.status_code == 403, (
            f"production answered {answer.status_code}; the contract prices 403"
        )
        error = envelope(answer)
        assert error.get("code") == "INTERNAL_ERROR", (
            "production 403 code=" + str(error.get("code"))
        )
        assert error.get("message"), "the 403 envelope carried an empty message"
    finally:
        (
            config_module.get_settings,
            admin_module.get_settings,
            dependencies_module.get_settings,
            main_module.settings,
        ) = previous
        get_settings.cache_clear()

    assert counts() == WANT_COUNTS, "the production refusal wiped the seeded data"


def test_reset_confirm_guard(client, dev_env) -> None:
    """AC-5: every wrong ``confirm`` is a 422 with populated ``details``, and touches no data.

    Four bodies - lowercase, over-long, empty object, absent - each answered 422 by the shipped
    request model. The counts are taken before and after every probe rather than once at the end, so
    a rejected request that wiped halfway is caught at the probe that did it rather than at the end
    of the loop.
    """
    for body in ({"confirm": "reset"}, {"confirm": "RESETT"}, {}, None):
        label = f"body={body if body is not None else 'none'}"
        assert counts() == WANT_COUNTS, label + " precondition counts " + str(counts())
        answer = client.post(PATH, headers=staff_headers(), json=body)
        assert answer.status_code == 422, label + f" answered {answer.status_code}"
        payload = answer.json()
        assert "detail" not in payload, label + " leaked FastAPI's detail shape"
        error = payload.get("error") or {}
        assert error.get("code") == "VALIDATION_ERROR", label + " code=" + str(error.get("code"))
        assert error.get("details"), label + " carried no error.details"
        assert counts() == WANT_COUNTS, label + " changed the seeded rows"


def test_reset_success_is_204_empty(client, dev_env) -> None:
    """AC-6: an accepted reset answers 204 and writes nothing at all.

    ``text == ''`` rather than a falsy check: a serialised ``"null"`` is also empty to
    ``assert not answer.text``, and it is the handler's ``Response`` annotation that keeps the body
    away from the serialiser. The content-type arm catches the variant that is empty and still
    advertises JSON.
    """
    answer = client.post(PATH, headers=staff_headers(), json={"confirm": "RESET"})
    assert answer.status_code == 204, f"status={answer.status_code} body={answer.text[:80]!r}"
    assert answer.text == "", f"204 with a non-empty body: {answer.text[:80]!r}"
    content_type = (answer.headers.get("content-type") or "").lower()
    assert "json" not in content_type, f"204 advertises content-type {content_type!r}"


def test_reset_restores_seed(client, dev_env) -> None:
    """AC-7: one accepted reset restores the fixture over a dirtied database, and is idempotent.

    The dirties are the criterion's own, and the assertion after each reset is a full six-value
    tuple rather than a waitlist count, so a reset that re-inserted without dropping (which would
    hit a unique constraint) or that answered 204 while leaving the dirties in place both fail. The
    second reset is what says the operation is repeatable rather than once-only.
    """
    dirty_the_fixture()
    dirtied = counts()
    assert dirtied[3] == 9 and dirtied[4] == 0 and dirtied[5] == 999, (
        f"the dirty step did not take: {dirtied}"
    )

    first = client.post(PATH, headers=staff_headers(), json={"confirm": "RESET"})
    assert first.status_code == 204, f"reset #1 answered {first.status_code} {first.text[:60]!r}"
    assert counts() == WANT_COUNTS, f"after reset #1: {counts()}"

    second = client.post(PATH, headers=staff_headers(), json={"confirm": "RESET"})
    assert second.status_code == 204, f"reset #2 answered {second.status_code}"
    assert counts() == WANT_COUNTS, f"after reset #2: {counts()} - reset is not idempotent"


def test_reset_delegates_to_seeder(client, dev_env) -> None:
    """AC-8: an accepted request calls the seeder once with ``reset=True``; a rejected one, never.

    ``app.seed.seed_data`` is wrapped rather than replaced: the wrapper records the flag and then
    performs the real reset, so this test cannot pass by doing the reset itself and cannot pass on a
    hand-written ``delete from`` loop that happens to leave the same counts. The patch is on the
    MODULE attribute, which is the seam the handler is written against - it reaches the seeder as
    ``seed.seed_data(...)``, so the wrapped name is the name the call actually goes through.
    """
    calls: list[bool] = []
    original = seed_module.seed_data

    def spy(reset: bool = False) -> int:
        calls.append(bool(reset))
        return original(reset=reset)

    seed_module.seed_data = spy
    try:
        calls.clear()
        accepted = client.post(PATH, headers=staff_headers(), json={"confirm": "RESET"})
        accepted_calls = list(calls)
        calls.clear()
        client.post(PATH, headers=staff_headers(), json={"confirm": "NOPE"})
        rejected_calls = list(calls)
    finally:
        seed_module.seed_data = original

    assert accepted.status_code == 204, f"the accepted reset answered {accepted.status_code}"
    assert accepted_calls == [True], (
        "an accepted reset called app.seed.seed_data with reset flags "
        + str(accepted_calls)
        + "; expected exactly [True]"
    )
    assert rejected_calls == [], (
        f"a request the endpoint rejects still called the seeder {len(rejected_calls)} time(s)"
    )


def test_reset_contract_shape(client, dev_env) -> None:
    """AC-9, with AC-1's arms: the generated document matches the contract for this operation.

    Read against the contract file rather than a restatement of it, on the axes AC-9 names - verb
    set, declared response codes, the 403 content schema resolving to the ``ErrorResponse``
    envelope, no content on the 204, a required body resolving to ``ResetDataRequest``, and a
    non-empty bearer requirement - plus AC-1's freeze facts: exactly one verb on the contract side,
    the ``resetData`` operation id, and the request body still marked required there.

    The comparison runs in the AC's direction on purpose: the generated document may carry FastAPI's
    own descriptions, and may not add a verb, a response code or a security scheme the contract does
    not declare.
    """
    contract_paths = contract_document()["paths"]
    contract_operation = contract_paths[PATH]["post"]
    assert sorted(contract_paths[PATH]) == ["post"], (
        "the contract declares verbs " + str(sorted(contract_paths[PATH]))
    )
    assert contract_operation.get("operationId") == "resetData", AC1_OPERATION_ID_MESSAGE

    generated_operation = app.openapi()["paths"][PATH]["post"]
    assert sorted(app.openapi()["paths"][PATH]) == ["post"], (
        "the application declares a verb besides post"
    )

    declared = sorted((contract_operation.get("responses") or {}).keys())
    advertised = sorted((generated_operation.get("responses") or {}).keys())
    assert advertised == declared, (
        f"the generated operation advertises {advertised}; the contract declares {declared}"
    )

    generated_204 = (generated_operation.get("responses") or {}).get("204") or {}
    assert not generated_204.get("content"), "the generated 204 advertises a response body"

    generated_403 = (
        ((generated_operation.get("responses") or {}).get("403") or {}).get("content") or {}
    ).get("application/json") or {}
    assert generated_403.get("schema") is not None, (
        "the generated 403 declares no application/json schema where the contract declares an "
        "ErrorResponse body"
    )
    assert "ErrorResponse" in str(generated_403["schema"]), (
        f"the generated 403 schema is {str(generated_403['schema'])[:70]} and is not the envelope"
    )

    body = (
        (generated_operation.get("requestBody") or {})
        .get("content", {})
        .get("application/json", {})
    ).get("schema")
    assert body, "the generated operation requires no JSON request body"
    assert "ResetDataRequest" in str(body), f"the request body is {str(body)[:70]}"
    assert (contract_operation.get("requestBody") or {}).get("required") is True, (
        "the contract no longer marks the request body required - the contract was edited"
    )
    assert generated_operation.get("security"), (
        "the generated operation carries no security requirement, so it is publicly reachable"
    )

    assert ResetDataRequest.model_fields["confirm"].is_required(), (
        "confirm must stay required: an omitted body is AC-5's 422 case"
    )
    assert str(admin_module.CONTRACT_PATH.resolve()) == str(admin_module.CONTRACT_PATH), (
        "the contract path this module reads must be absolute, not cwd-relative"
    )
    assert admin_module.RESET_PATH == PATH


def test_no_new_endpoints(client, dev_env) -> None:
    """AC-10: nothing outside the contract is served, and the reset slot is among what is.

    The route table is walked rather than the document, because a handler mounted with
    ``include_in_schema=False`` is invisible to the document and is still an invented endpoint.
    FastAPI's own documentation routes are exempt by name, and ``app.routes`` is not flat on this
    version - ``include_router`` appends a container - so the walk recurses ``routes`` and
    ``original_router`` exactly as ``app/main.py::_reachable_paths`` and AC-9's own block do.

    The three arms below are AC-10's own three, in the order its block writes them: no served
    path+verb outside the contract, ``POST /api/v1/admin/reset`` among the served pairs and routed,
    and ``/health`` answering 200 with its own pair in the served table. The block's PASS line names
    the same three, and its ``missing`` list - the contract paths this issue does not own - is
    printed but never gates it, which the issue says outright: the ``admin/settings``,
    ``admin/tables`` and ``staff/dashboard`` slots go green when B-10, B-11 and B-09 land, and
    "a red that names ONLY them is not this issue's failure". A fourth arm here would therefore
    assert another issue's scope and could not pass before that issue merges; what this module adds
    to the AC's own list is the live probe of the two surfaces it does gate on.
    """
    contract = contract_document().get("paths") or {}
    declared = {
        (path, verb.upper())
        for path, item in contract.items()
        for verb in (item or {})
        if verb in ("get", "post", "patch", "put", "delete")
    }

    def walk(routes, depth=0):
        if depth > 8:
            return
        for route in routes:
            yield route
            for attribute in ("routes", "original_router"):
                nested = getattr(route, attribute, None)
                if nested is None:
                    continue
                if isinstance(nested, (list, tuple)):
                    yield from walk(nested, depth + 1)
                elif hasattr(nested, "routes"):
                    yield from walk([nested], depth + 1)
                else:
                    yield nested

    served: set[tuple[str, str]] = set()
    for route in walk(app.routes):
        path = getattr(route, "path", None)
        if not isinstance(path, str):
            continue
        normalised = re.sub(r"\{[^}]+\}", "{}", path)
        for verb in getattr(route, "methods", None) or set():
            if verb.upper() in ("GET", "POST", "PATCH", "PUT", "DELETE"):
                served.add((normalised, verb.upper()))

    documentation_routes = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
    declared_normalised = {(re.sub(r"\{[^}]+\}", "{}", path), verb) for path, verb in declared}
    invented = sorted(
        pair
        for pair in served - declared_normalised
        if pair[0] not in documentation_routes
    )
    assert invented == [], (
        "the application serves path+verbs the contract does not declare: " + str(invented)
    )
    assert (PATH, "POST") in served, "the served route table has no POST " + PATH
    assert not [pair for pair in declared_normalised if pair[0] == PATH and pair not in served], (
        f"POST {PATH} is declared and not routed at all"
    )
    assert ("/health", "GET") in served, "the served route table has no GET /health"

    health = client.get("/health")
    assert health.status_code == 200, f"/health answered {health.status_code} to GET"
    reset_probe = client.post(PATH, headers=staff_headers(), json={"confirm": "NOPE"})
    assert not _fastapi_not_found(reset_probe), (
        "POST "
        + PATH
        + f" answered FastAPI's unroutable 404 ({reset_probe.status_code}), so no handler is "
        "behind the slot the route table names"
    )
    invented_probe = client.post("/api/v1/admin/reset/status", json={})
    assert _fastapi_not_found(invented_probe), (
        f"a path the contract does not declare answered {invented_probe.status_code} rather than "
        "FastAPI's unroutable 404, so the route table grew"
    )


def _fastapi_not_found(answer) -> bool:
    """Whether ``answer`` carries FastAPI's own unroutable ``{"detail":"Not Found"}`` body.

    The sentinel AC-10's block uses, factored out because two probes here read it and a 404 from a
    real handler (a not-found envelope, for instance) is not the same fact at all.
    """
    if answer.status_code != 404 or answer.text[:1] != "{":
        return False
    try:
        return answer.json().get("detail") == "Not Found"
    except Exception:  # pragma: no cover - a malformed 404 body is not the router's sentinel
        return False


AC1_OPERATION_ID_MESSAGE = (
    "the contract's reset operationId is no longer resetData, so the generated document and the "
    "contract of record no longer name the same operation"
)
"""AC-1's third arm, named because the assertion that uses it is already a long line."""
