"""E2E contract probe for T32 frontend integration.

Drives the core guest/staff flow against the in-process TestClient:
join -> login -> call -> board.

Uses the same TestClient pattern as other backend tests (no live server).
Verifies the contract paths and response shapes that the frontend depends on.

Note: The status endpoint requires a guest credential (the minted status_token or the
read-only phone_last3 lookup factor, T11). This test focuses on paths that work without
that factor, plus the cancel credential split.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_e2e_contract.db")
os.environ.setdefault("JWT_SECRET", "tq-test-jwt-secret-e2e-0123456789abcdef")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

import contextlib

import pytest
from fastapi.testclient import TestClient

from app.errors import AppError
from app.main import app, limiter
from app.models import (
    CancelledReason,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistStatus,
)
from app.services.rate_limit import BoundedFrozenClockMemoryStorage
from tests._db_test_support import TEST_CREDENTIAL_HASH
from tests.public_fixtures import seed_branch


@pytest.fixture
def client():
    """A TestClient over the shared app, using the module's database."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Provide a fresh database session with schema created."""
    from sqlalchemy.orm import Session

    from app import database

    # Create all tables
    database.Base.metadata.create_all(bind=database.engine)
    session = Session(bind=database.engine)
    # The store the test serves is put into this module's own state here, rather than being left
    # to a TestClient lifespan: main.py binds its lifespan to the engine it imported, which is
    # not necessarily the factory a request reads once another module has swapped the ambient
    # engine (test_auth holds its private file for the rest of the session, by design). T9 (D-1)
    # made the initial credential hash a precondition of login, so the row this module serves
    # must be the one it can answer, in every intra-session state the ambient store can arrive in:
    #   * an empty store (never bootstrapped) - bootstrap_defaults reproduces the startup INSERT;
    #   * a row an earlier seed left with an empty hash - the set below fills it;
    #   * a row holding ANOTHER module's PIN: test_auth rotates its own private PIN and its
    #     insert_setting leaves whichever row its last test wrote, so a store that arrives here
    #     can carry a hash that answers to a PIN this module never submits. Only a set of the
    #     credential this module logs in with (TEST_CREDENTIAL_HASH, the hash of the PIN below)
    #     reaches all three shapes; reading or filling the row conditionally leaves the third one
    #     order-dependent.
    from app.main import bootstrap_defaults
    from app.models import Settings as SettingsModel

    bootstrap_defaults(session)
    session.query(SettingsModel).first().staff_pin_hash = TEST_CREDENTIAL_HASH
    session.commit()
    try:
        yield session
    finally:
        session.close()
        # Clean up tables after test
        database.Base.metadata.drop_all(bind=database.engine)


def test_e2e_join_and_board(client, db_session):
    """Test join and board endpoints - core guest flow.

    Verifies the guest-facing contract paths and response shapes.
    Note: Status endpoint requires ownership factor (T34 scope).
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Join - returns 201 Created
    join_payload = {
        "name": "Test Guest",
        "phone": "0900-000-002",
        "party_size": 2,
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201
    join_data = join_response.json()
    assert "queue_number" in join_data
    assert "status" in join_data
    assert join_data["status"] == "WAITING"

    # Board should show the waiting count
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200
    board_data = board_response.json()
    assert "current_called" in board_data
    assert "next_up" in board_data
    assert "recent_calls" in board_data
    assert "waiting_count" in board_data
    assert board_data["waiting_count"] >= 1


def test_e2e_full_flow(client, db_session):
    """Full E2E flow: join -> login -> call -> board.

    This test verifies the complete contract that the frontend depends on:
    1. Guest joins waitlist via POST /api/v1/branches/{branch_id}/waitlist
    2. Staff logs in via POST /api/v1/auth/login
    3. Staff calls next party via PATCH /api/v1/staff/waitlist/call
    4. Board reflects changes via GET /api/v1/public/branches/{branch_id}/board

    Note: Status endpoint requires ownership factor (T34 scope) - skipped here.
    Note: Seat/release require table setup - tested separately.
    """
    # Setup: seed a branch and settings (seed_branch mutates the session)
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Step 1: Guest joins waitlist
    join_payload = {
        "name": "Test Guest",
        "phone": "0900-000-001",
        "party_size": 4,
        "note": "E2E test",
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201, f"Join failed: {join_response.text}"
    join_data = join_response.json()
    assert "id" in join_data, "Join response missing entry id"
    assert "queue_number" in join_data, "Join response missing queue_number"
    assert "status" in join_data, "Join response missing status"
    queue_number = join_data["queue_number"]
    entry_id = join_data["id"]

    # Step 2: Staff logs in
    login_response = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()
    assert "access_token" in login_data, "Login response missing access_token"
    access_token = login_data["access_token"]
    assert login_data["token_type"] == "bearer"  # noqa: S105  # contract literal, not a credential

    # Step 3: Staff calls next party (requires auth)
    # Note: call endpoint is POST /api/v1/staff/waitlist/{entry_id}/call
    call_headers = {"Authorization": f"Bearer {access_token}"}
    call_response = client.post(f"/api/v1/staff/waitlist/{entry_id}/call", headers=call_headers)
    assert call_response.status_code == 200, f"Call failed: {call_response.text}"
    call_data = call_response.json()
    # call_entry returns WaitlistEntryResponse directly
    assert call_data["queue_number"] == queue_number
    assert call_data["status"] == "CALLED"

    # Step 4: Board reflects the called party
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200, f"Board failed: {board_response.text}"
    board_data = board_response.json()
    assert "current_called" in board_data, "Board missing current_called"
    assert "next_up" in board_data, "Board missing next_up"
    assert "recent_calls" in board_data, "Board missing recent_calls"
    assert "waiting_count" in board_data, "Board missing waiting_count"
    # The current_called should be our guest
    if board_data["current_called"]:
        assert board_data["current_called"]["queue_number"] == queue_number


def test_e2e_board_endpoint(client, db_session):
    """Test board endpoint returns correct structure.

    Verifies the public board contract.
    """
    # Setup with some entries
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Board should work even with empty waitlist
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200
    board_data = board_response.json()
    assert "current_called" in board_data, "Board missing current_called"
    assert "next_up" in board_data, "Board missing next_up"
    assert "recent_calls" in board_data, "Board missing recent_calls"
    assert "waiting_count" in board_data, "Board missing waiting_count"


def test_e2e_login_response_shape(client, db_session):
    """Test login response has correct shape (access_token, not token).

    This is critical for the frontend's auth.ts which reads response.access_token.
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Login
    login_response = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert login_response.status_code == 200
    login_data = login_response.json()

    # Verify response shape matches contract
    assert "access_token" in login_data, "Login response must have access_token"
    assert "expires_in" in login_data, "Login response must have expires_in"
    assert "token_type" in login_data, "Login response must have token_type"
    assert login_data["token_type"] == "bearer"  # noqa: S105  # contract literal, not a credential
    assert isinstance(login_data["expires_in"], int), "expires_in must be seconds count"


def test_e2e_cancel_endpoint(client, db_session):
    """Test the cancel endpoint's credential split (T11 D-1).

    Verifies POST /api/v1/waitlist/{queue_number}/cancel: a credential-less cancel is the
    uniform 404 WAITLIST_NOT_FOUND (the openapi cancel operation declares 200/404/409 only),
    and the minted token the join handed back is the credential that cancels.
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Join
    join_payload = {
        "name": "Cancel Test",
        "phone": "0900-000-003",
        "party_size": 2,
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201
    join_data = join_response.json()
    queue_number = join_data["queue_number"]
    token = join_data["status_token"]
    assert isinstance(token, str) and token, "join response must carry the minted status_token"

    # Cancel with no credential: the uniform 404, not a 422 the openapi file does not declare.
    refused = client.post(f"/api/v1/waitlist/{queue_number}/cancel", json={})
    assert refused.status_code == 404, f"Unexpected cancel status: {refused.status_code}"
    assert refused.json()["error"]["code"] == "WAITLIST_NOT_FOUND"

    # Cancel with the minted token: the only credential that authorizes it.
    cancel_response = client.post(f"/api/v1/waitlist/{queue_number}/cancel", json={"token": token})
    assert cancel_response.status_code == 200, (
        f"Unexpected cancel status: {cancel_response.status_code}"
    )
    assert cancel_response.json()["status"] == "CANCELLED"


def test_stopped_legacy_client_paths_answer_404(client: TestClient) -> None:
    """T16 AC-1: the stopped client-facing legacy paths stay dead, each a bare 404."""
    assert client.get("/api/v1/public/board/1").status_code == 404
    assert client.post("/api/v1/staff/login", json={"pin": "1234"}).status_code == 404
    assert client.post("/api/v1/staff/pin/change", json={}).status_code == 404


def _staff_headers(client: TestClient) -> dict:
    """Log in with the module's test PIN (the settings row holds its hash) and return the header."""
    login_response = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def test_seat_without_body_answers_422_validation_error(client, db_session) -> None:
    """T16 AC-2: a bodiless seat request is 422 VALIDATION_ERROR with the envelope body."""
    resp = client.post(
        "/api/v1/staff/waitlist/00000000-0000-4000-8000-000000000000/seat",
        headers=_staff_headers(client),
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]


def test_close_day_cancels_calls_seats_and_moves_tables(client, db_session) -> None:
    """T16 AC-3: close-day closes the day's queue per section 4.9, in one answer."""
    branch = seed_branch(db_session, branch_id=1, is_open=True)
    table = Table(
        branch_id=branch.id,
        label="T1",
        capacity=2,
        section="Main Hall",
        sort_order=1,
        status=TableStatus.AVAILABLE,
        is_active=True,
    )
    db_session.add(table)
    db_session.commit()

    headers = _staff_headers(client)
    first = client.post(
        f"/api/v1/branches/{branch.id}/waitlist",
        json={"name": "Close A", "phone": "0912345678", "party_size": 2},
    )
    assert first.status_code == 201, f"Join failed: {first.text}"
    called_id = first.json()["id"]
    assert (
        client.post(f"/api/v1/staff/waitlist/{called_id}/call", headers=headers).status_code
        == 200
    )
    second = client.post(
        f"/api/v1/branches/{branch.id}/waitlist",
        json={"name": "Close B", "phone": "0912345679", "party_size": 2},
    )
    assert second.status_code == 201, f"Join failed: {second.text}"
    seated_id = second.json()["id"]
    assert (
        client.post(
            f"/api/v1/staff/waitlist/{seated_id}/seat",
            headers=headers,
            json={"table_id": str(table.id)},
        ).status_code
        == 200
    )

    resp = client.post("/api/v1/staff/waitlist/close-day", headers=headers)
    assert resp.status_code == 200, f"Close-day failed: {resp.text}"
    assert resp.json() == {"cancelled": 1, "done": 1, "tables_cleaning": 1}

    # The already-closed queue answers the same shape in zeros (idempotent close).
    assert client.post("/api/v1/staff/waitlist/close-day", headers=headers).json() == {
        "cancelled": 0,
        "done": 0,
        "tables_cleaning": 0,
    }

    # Read the entries back through the fixture session (their rows arrived with the close-day
    # commit), and the table back through the staff tables endpoint - the fixture session's
    # identity map still holds the pre-close Table object, and an endpoint read is the contract
    # surface the staff screen would use anyway.
    entries = {str(e.id): e for e in db_session.query(WaitlistEntry).all()}
    cancelled_row = entries[called_id]
    assert cancelled_row.status is WaitlistStatus.CANCELLED
    assert cancelled_row.cancelled_reason is CancelledReason.CLOSED_DAY
    assert cancelled_row.closed_at is not None
    done_row = entries[seated_id]
    assert done_row.status is WaitlistStatus.DONE
    assert done_row.closed_at is not None
    tables_resp = client.get("/api/v1/staff/tables", headers=headers)
    assert tables_resp.status_code == 200
    table_status = {item["label"]: item["status"] for item in tables_resp.json()["items"]}
    assert table_status["T1"] == "CLEANING"


def test_close_day_requires_staff_token(client: TestClient) -> None:
    """T16 AC-3: the close-day operation rides the staff auth, like its siblings."""
    resp = client.post("/api/v1/staff/waitlist/close-day")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# T18 AC-4: the conformance sweep over the eight non-2xx classes the contract ships.
# ---------------------------------------------------------------------------


def _envelope_problems(resp, want_status: int) -> list[str]:
    """Return the reasons ``resp`` is not the contract envelope for ``want_status``.

    An empty list is the pass. The checks are the AC's own: the status is the one asked
    for, the body is JSON whose top level is exactly the ``error`` key, ``code`` and
    ``message`` are non-empty strings, ``details`` is an object when present, and no
    framework ``detail`` key appears at the top level or inside ``error``. One helper
    applied per class is what the AC asks for, so all eight answers are measured the
    same way.
    """
    if resp.status_code != want_status:
        return [f"status is {resp.status_code}, want {want_status}"]
    try:
        body = resp.json()
    except ValueError:
        return ["the body is not JSON"]
    if not isinstance(body, dict) or set(body) != {"error"}:
        keys = sorted(body) if isinstance(body, dict) else type(body).__name__
        return [f"the top level carries {keys!r}, want exactly ['error']"]
    error = body["error"]
    if not isinstance(error, dict):
        return ["error is not an object"]
    if "detail" in body or "detail" in error:
        return ["a 'detail' key (framework default shape) leaked through"]
    if not isinstance(error.get("code"), str) or not error["code"]:
        return ["error.code is missing or not a non-empty string"]
    if not isinstance(error.get("message"), str) or not error["message"]:
        return ["error.message is missing or not a non-empty string"]
    if "details" in error and not isinstance(error["details"], dict):
        return ["error.details is present but is not an object"]
    return []


@contextlib.contextmanager
def limiter_on_fresh_store():
    """Enable the shared limiter on a fresh counter store, then restore both.

    The conftest ``disable_limiter`` fixture is autouse, so the 429 class can only be
    measured with the limiter switched on for the probe alone. The store swap mirrors
    ``test_rate_limit_t23.limiter_on_fresh_store``: a fresh bounded store makes the
    boundary exact (ten 200s, the eleventh 429) and keeps one burst from leaking into
    the next test's window.
    """
    previous_enabled = limiter.enabled
    previous_storage = limiter._storage  # noqa: SLF001
    limiter.enabled = True
    limiter._storage = BoundedFrozenClockMemoryStorage()  # noqa: SLF001
    try:
        yield
    finally:
        limiter.enabled = previous_enabled
        limiter._storage = previous_storage  # noqa: SLF001


def test_every_non_2xx_class_answers_the_contract_envelope(client, db_session) -> None:
    """T18 AC-4: every error class the contract can produce answers the envelope.

    The eight classes, probed the way the AC names: 401 an invalid PIN, 404 an
    unmatched route, 405 a method the router does not allow, 409 a duplicate-phone
    join, 422 a malformed body, 429 a guest-budget burst - all real contract answers
    the product already produces. The 500 and 503 are forced through the app's own
    error layer (an unhandled exception through the registered handler, and an
    ``AppError`` status override respectively) because the 503's real producer - the
    locked database - lands with t19. The two probe routes exist only for this test's
    body and are removed in the ``finally``: nothing a later test's route-table walk
    could find may be left behind.
    """
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    def check(label: str, resp, want_status: int) -> None:
        problems = _envelope_problems(resp, want_status)
        assert problems == [], f"{label}: the envelope is not the contract's: {problems}"

    # 401: an invalid PIN against a bootstrapped store - a refused credential, not a missing one.
    check("401 invalid PIN", client.post("/api/v1/auth/login", json={"pin": "9999"}), 401)

    # 404: a path no route serves, answered by the router-level error layer (t18 AC-1).
    check(
        "404 unmatched route",
        client.get("/api/v1/definitely-not-a-route"),
        404,
    )

    # 405: a method the router does not allow on a mounted path, the same layer.
    check("405 method not allowed", client.delete("/health"), 405)

    # 409: a phone that already holds a place today, the real conflict answer.
    join = {
        "name": "Sweep Guest",
        "phone": "0900-000-010",
        "party_size": 2,
    }
    first = client.post("/api/v1/branches/1/waitlist", json=join)
    assert first.status_code == 201, f"join failed: {first.text}"
    check("409 duplicate phone", client.post("/api/v1/branches/1/waitlist", json=join), 409)

    # 422: a malformed body the request schema rejects.
    check("422 malformed body", client.post("/api/v1/auth/login", json={}), 422)

    # 429: the guest budget on the un-limited branch read - ten answers, the eleventh refused.
    with limiter_on_fresh_store():
        burst = [client.get("/api/v1/public/branches/1") for _ in range(11)]
        assert all(r.status_code == 200 for r in burst[:10]), [
            r.status_code for r in burst[:10]
        ]
        check("429 guest budget burst", burst[10], 429)

    # 500/503: forced through the app's own error layer, see the docstring for why.
    routes_before = len(app.router.routes)
    try:

        @app.get("/_t18_sweep_500")
        def _t18_sweep_500() -> None:
            raise RuntimeError("the t18 sweep's forced 500")

        @app.get("/_t18_sweep_503")
        def _t18_sweep_503() -> None:
            raise AppError(
                "INTERNAL_ERROR", status_code=503, message="Service temporarily unavailable"
            )

        check("500 unhandled exception", client.get("/_t18_sweep_500"), 500)
        check(
            "503 service unavailable (status override; t19 lands the real producer)",
            client.get("/_t18_sweep_503"),
            503,
        )
    finally:
        del app.router.routes[routes_before:]
